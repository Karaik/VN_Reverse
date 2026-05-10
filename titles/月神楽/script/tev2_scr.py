from __future__ import annotations

import hashlib
import json
import bisect
import struct
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from script.container import extract_ascii_literals, extract_nonzero_words, preview_u32_words, transform_mode2_words


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


@dataclass
class ScrOuterDoc:
    format: str
    source_path: str
    raw_header: dict[str, object]
    decoded_payload_preview_hex: str
    decoded_payload_sha256: str
    decoded_u32_preview: list[dict[str, object]]
    decoded_nonzero_words: list[dict[str, object]]
    ascii_literals: list[dict[str, object]]
    known_container_magics: list[dict[str, object]]
    container_summary: dict[str, object]
    decoded_payload_bytes: bytes = field(repr=False)


@dataclass
class ScrTextDoc:
    format: str
    source_path: str
    text_encoding: str
    raw_header: dict[str, object]
    entries: list[dict[str, object]]


@dataclass
class ScrSectionDoc:
    sec1_length_offset: int
    sec1_data_offset: int
    sec2_length_offset: int
    sec2_data_offset: int
    sec3_length_offset: int
    sec3_data_offset: int
    sec4_length_offset: int
    sec4_data_offset: int
    sec5_length_offset: int
    sec5_data_offset: int
    sec1_bytes: bytes
    sec2_bytes: bytes
    sec3_bytes: bytes
    sec4_offsets: list[int]
    sec4_offset_positions: list[int]
    sec5_entries: list[dict[str, object]]
    sec3_u32_offset_hits: list[tuple[int, int]]


@dataclass
class ScrCommandDoc:
    start: int
    end: int
    opcode_u32: int | None
    raw_bytes: bytes
    kind: str


@dataclass
class ScrStringSlotDoc:
    local_marker_pos: int
    marker_u8: int
    text_start: int
    text_end: int
    text: str
    decoded: bool
    raw_bytes: bytes
    is_ascii: bool


STRUCTURAL_SEC3_REFERENCE_FIELDS: dict[int, tuple[int, ...]] = {}


@dataclass
class ScrRebuildImpact:
    anchor_offset: int
    original_offset: int
    current_offset: int
    old_length: int
    new_length: int
    delta: int
    outer_decoded_payload_size_field_offset: int
    sec3_length_field_offset: int
    sec4_impacted_indices: list[int]
    sec4_impacted_value_positions: list[int]
    sec5_impacted_indices: list[int]
    sec5_impacted_value_positions: list[int]
    sec3_u32_in_range_count: int
    sec3_impacted_u32_sample_positions: list[int]
    sec3_impacted_u32_sample_values: list[int]
    sec3_high_confidence_impacted_positions: list[int]
    sec3_high_confidence_impacted_values: list[int]


KNOWN_SEC3_REFERENCE_PATTERNS: set[tuple[str, int]] = set()


def parse_scr_commands(sec3_bytes: bytes) -> list[ScrCommandDoc]:
    command_starts = [
        pos
        for pos in range(0, len(sec3_bytes) - 4)
        if sec3_bytes[pos] == 0x0C and sec3_bytes[pos + 2 : pos + 5] == b"\x00\x00\x00"
    ]
    commands: list[ScrCommandDoc] = []
    if not command_starts:
        if sec3_bytes:
            commands.append(
                ScrCommandDoc(
                    start=0,
                    end=len(sec3_bytes),
                    opcode_u32=None,
                    raw_bytes=sec3_bytes,
                    kind="prologue",
                )
            )
        return commands

    if command_starts[0] > 0:
        commands.append(
            ScrCommandDoc(
                start=0,
                end=command_starts[0],
                opcode_u32=None,
                raw_bytes=sec3_bytes[: command_starts[0]],
                kind="prologue",
            )
        )

    for index, start in enumerate(command_starts):
        end = command_starts[index + 1] if index + 1 < len(command_starts) else len(sec3_bytes)
        opcode_u32 = sec3_bytes[start + 1] if start + 5 <= len(sec3_bytes) else None
        commands.append(
            ScrCommandDoc(
                start=start,
                end=end,
                opcode_u32=opcode_u32,
                raw_bytes=sec3_bytes[start:end],
                kind="command",
            )
        )
    return commands


def _decode_command_string_slot(
    command: ScrCommandDoc,
    local_marker_pos: int,
    *,
    text_encoding: str,
) -> ScrStringSlotDoc | None:
    if local_marker_pos < 0 or local_marker_pos >= len(command.raw_bytes):
        return None
    marker_u8 = command.raw_bytes[local_marker_pos]
    if marker_u8 not in (0x0A, 0x0B):
        return None
    text_start = local_marker_pos + 1
    text_end = text_start
    while text_end < len(command.raw_bytes) and command.raw_bytes[text_end] != 0:
        text_end += 1
    if text_end >= len(command.raw_bytes):
        return None
    raw_bytes = command.raw_bytes[text_start:text_end]
    try:
        text = raw_bytes.decode(text_encoding)
        decoded = True
    except UnicodeDecodeError:
        text = raw_bytes.decode(text_encoding, errors="replace")
        decoded = False
    is_ascii = all(byte < 0x80 for byte in raw_bytes)
    return ScrStringSlotDoc(
        local_marker_pos=local_marker_pos,
        marker_u8=marker_u8,
        text_start=text_start,
        text_end=text_end,
        text=text,
        decoded=decoded,
        raw_bytes=raw_bytes,
        is_ascii=is_ascii,
    )


def _is_control_only_text(text: str) -> bool:
    if not text:
        return True
    return all(ord(char) < 0x20 for char in text)


def _looks_like_resource_identifier(text: str) -> bool:
    if not text:
        return False
    if any(ord(char) >= 0x80 for char in text):
        return False
    if text.startswith("_"):
        return False
    if any(char.isspace() for char in text):
        return False
    if not all(char.isalnum() or char in "_#*.-" for char in text):
        return False
    return any(char.islower() for char in text)


def _iter_command_string_slots(command: ScrCommandDoc, *, text_encoding: str) -> list[ScrStringSlotDoc]:
    slots: list[ScrStringSlotDoc] = []
    seen: set[tuple[int, int]] = set()
    for local_pos, marker_u8 in enumerate(command.raw_bytes):
        if marker_u8 not in (0x0A, 0x0B):
            continue
        slot = _decode_command_string_slot(command, local_pos, text_encoding=text_encoding)
        if slot is None:
            continue
        key = (slot.text_start, slot.text_end)
        if key in seen:
            continue
        seen.add(key)
        slots.append(slot)
    return slots


def _select_translatable_slots(command: ScrCommandDoc, slots: list[ScrStringSlotDoc]) -> list[tuple[ScrStringSlotDoc, str]]:
    opcode = command.opcode_u32
    selected: list[tuple[ScrStringSlotDoc, str]] = []
    for slot in slots:
        if not slot.decoded or not slot.text or _is_control_only_text(slot.text):
            continue

        usage = "text"
        include = False

        if slot.marker_u8 == 0x0B:
            include = True
            usage = "dialogue" if opcode == 0x1B else "text"
        elif not slot.is_ascii:
            include = True
            usage = "choice" if opcode in {0x12, 0x17, 0x23, 0x24} else "text"
        elif not _looks_like_resource_identifier(slot.text):
            include = True
            usage = "system"

        if opcode == 0x1B and slot.marker_u8 == 0x0B:
            usage = "dialogue"
        elif opcode in {0x02, 0x09, 0x0A, 0x14, 0x15, 0x16} and include:
            usage = "name"
        elif opcode in {0x12, 0x17, 0x23, 0x24, 0x21} and include:
            usage = "choice"
        elif opcode == 0x00 and include:
            usage = "system"

        if include:
            selected.append((slot, usage))
    return selected


def _extract_cp932_text_candidates(data: bytes, text_encoding: str = "cp932") -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    seen: set[tuple[int, int]] = set()
    for command_index, command in enumerate(parse_scr_commands(data)):
        slot_docs = _iter_command_string_slots(command, text_encoding=text_encoding)
        selected_slots = _select_translatable_slots(command, slot_docs)
        for record_slot_index, (slot, usage) in enumerate(selected_slots):
            start = command.start + slot.text_start
            end = command.start + slot.text_end
            if (start, end) in seen:
                continue
            opcode_label = "prologue" if command.opcode_u32 is None else f"opcode_{command.opcode_u32:02x}"
            candidates.append(
                {
                    "command_index": command_index,
                    "command_kind": command.kind,
                    "command_start": command.start,
                    "command_end": command.end,
                    "record_start": command.start,
                    "record_offset": command.start + slot.local_marker_pos,
                    "offset": start,
                    "length": len(slot.raw_bytes),
                    "capacity_bytes": len(slot.raw_bytes),
                    "in_place_capacity_bytes": len(slot.raw_bytes),
                    "text": slot.text,
                    "original_text": slot.text,
                    "text_raw_hex": slot.raw_bytes.hex(" "),
                    "source_rule": f"{opcode_label}_slot_{slot.local_marker_pos:02x}",
                    "prefix_marker_u8": slot.marker_u8,
                    "record_header_hex": command.raw_bytes[5 : slot.local_marker_pos].hex(" "),
                    "command_header_hex": command.raw_bytes[: min(16, len(command.raw_bytes))].hex(" "),
                    "patch_mode": "section_rebuild_expandable",
                    "supports_expansion_rebuild": True,
                    "prefix_hex": command.raw_bytes[max(0, slot.text_start - 8) : slot.text_start].hex(" "),
                    "suffix_hex": command.raw_bytes[slot.text_end : min(len(command.raw_bytes), slot.text_end + 8)].hex(" "),
                    "usage": usage,
                    "decoded": slot.decoded,
                    "is_ascii": slot.is_ascii,
                    "record_slot_index": record_slot_index,
                    "record_opcode_u32": command.opcode_u32,
                }
            )
            seen.add((start, end))
    candidates.sort(key=lambda item: int(item["offset"]))
    slot_counts: dict[int | None, int] = {}
    slot_indices: dict[int | None, int] = {}
    for item in candidates:
        record_start = item.get("record_start")
        slot_counts[record_start] = slot_counts.get(record_start, 0) + 1
    for item in candidates:
        record_start = item.get("record_start")
        item["record_slot_index"] = slot_indices.get(record_start, int(item.get("record_slot_index", 0)))
        item["record_text_slot_count"] = slot_counts.get(record_start, 1)
        slot_indices[record_start] = item["record_slot_index"] + 1
    for logical_index, item in enumerate(candidates):
        item["index"] = logical_index
    return candidates


def probe_scr(path: Path) -> ScrOuterDoc:
    return _probe_scr_cached(str(path))


def probe_scr_bytes(data: bytes, *, source_path: str = "<memory>") -> ScrOuterDoc:
    if len(data) < 20:
        raise ValueError("SCR file too small")
    if data[:4] != b"SCR ":
        raise ValueError(f"Unexpected SCR magic: {data[:4]!r}")

    version_u32 = struct.unpack_from("<I", data, 4)[0]
    codec_mode_u32 = struct.unpack_from("<I", data, 8)[0]
    key_seed_u32 = struct.unpack_from("<I", data, 12)[0]
    decoded_payload_size_u32 = struct.unpack_from("<I", data, 16)[0]
    if codec_mode_u32 != 2:
        raise ValueError(f"Unsupported SCR codec mode: {codec_mode_u32}")

    decoded_payload = transform_mode2_words(data[20:], key_seed_u32)
    known_container_magics = [
        {"magic_ascii": "SCR ", "magic_u32": 0x20524353, "known_from": "raw_file_header"},
        {"magic_ascii": "TSCR", "magic_u32": 0x52435354, "known_from": "runtime_parser"},
        {"magic_ascii": "TUTA", "magic_u32": 0x41545554, "known_from": "runtime_parser"},
        {"magic_ascii": "TCRP", "magic_u32": 0x50524354, "known_from": "runtime_parser"},
        {"magic_ascii": "TXT0", "magic_u32": 0x30545854, "known_from": "runtime_parser"},
        {"magic_ascii": "M3H0", "magic_u32": 0x3048334D, "known_from": "runtime_parser"},
        {"magic_ascii": "M3P0", "magic_u32": 0x3050334D, "known_from": "runtime_parser"},
    ]
    container_summary = {
        "raw_outer_magic": "SCR ",
        "version_u32": version_u32,
        "codec_mode_u32": codec_mode_u32,
        "decoded_payload_size_u32": decoded_payload_size_u32,
        "status": "outer_container_decoded_inner_instruction_payload_unfinished",
    }

    return ScrOuterDoc(
        format="TE_V2_SCR_OUTER",
        source_path=source_path,
        raw_header={
            "magic_ascii": "SCR ",
            "version_u32": version_u32,
            "codec_mode_u32": codec_mode_u32,
            "key_seed_u32": key_seed_u32,
            "decoded_payload_size_u32": decoded_payload_size_u32,
            "encoded_payload_size_u32": len(data) - 20,
        },
        decoded_payload_preview_hex=decoded_payload[:512].hex(" "),
        decoded_payload_sha256=hashlib.sha256(decoded_payload).hexdigest(),
        decoded_u32_preview=preview_u32_words(decoded_payload, limit=48),
        decoded_nonzero_words=extract_nonzero_words(decoded_payload, limit=96),
        ascii_literals=extract_ascii_literals(decoded_payload),
        known_container_magics=known_container_magics,
        container_summary=container_summary,
        decoded_payload_bytes=decoded_payload,
    )


@lru_cache(maxsize=128)
def _probe_scr_cached(path_str: str) -> ScrOuterDoc:
    data = Path(path_str).read_bytes()
    return probe_scr_bytes(data, source_path=path_str)


def parse_scr_text(path: Path, text_encoding: str = "cp932", *, include_impact: bool = False) -> ScrTextDoc:
    cached = _parse_scr_text_cached(str(path), text_encoding, include_impact)
    entries = json.loads(json.dumps(cached["entries"], ensure_ascii=False))
    return ScrTextDoc(
        format=str(cached["format"]),
        source_path=str(cached["source_path"]),
        text_encoding=str(cached["text_encoding"]),
        raw_header=dict(cached["raw_header"]),
        entries=entries,
    )


@lru_cache(maxsize=128)
def _parse_scr_text_cached(path_str: str, text_encoding: str, include_impact: bool) -> dict[str, object]:
    path = Path(path_str)
    outer = probe_scr(path)
    return _build_scr_text_payload(outer, text_encoding=text_encoding, include_impact=include_impact)


def parse_scr_text_bytes(
    data: bytes,
    *,
    source_path: str = "<memory>",
    text_encoding: str = "cp932",
    include_impact: bool = False,
) -> ScrTextDoc:
    payload = _build_scr_text_payload(
        probe_scr_bytes(data, source_path=source_path),
        text_encoding=text_encoding,
        include_impact=include_impact,
    )
    entries = json.loads(json.dumps(payload["entries"], ensure_ascii=False))
    return ScrTextDoc(
        format=str(payload["format"]),
        source_path=str(payload["source_path"]),
        text_encoding=str(payload["text_encoding"]),
        raw_header=dict(payload["raw_header"]),
        entries=entries,
    )


def _build_scr_text_payload(outer: ScrOuterDoc, *, text_encoding: str, include_impact: bool) -> dict[str, object]:
    section_doc = parse_scr_sections(outer.decoded_payload_bytes)
    entries = _extract_cp932_text_candidates(section_doc.sec3_bytes, text_encoding=text_encoding)
    if include_impact:
        for entry in entries:
            impact = plan_scr_rebuild_impact(
                section_doc,
                anchor_offset=int(entry.get("record_offset", entry["offset"])),
                original_offset=int(entry["offset"]),
                current_offset=int(entry["offset"]),
                old_length=int(entry["length"]),
                new_length=int(entry["length"]),
            )
            entry["rebuild_impact"] = {
                "anchor_offset": impact.anchor_offset,
                "outer_decoded_payload_size_field_offset": impact.outer_decoded_payload_size_field_offset,
                "sec3_length_field_offset": impact.sec3_length_field_offset,
                "sec4_impacted_indices_if_expand": impact.sec4_impacted_indices,
                "sec4_impacted_value_positions_if_expand": impact.sec4_impacted_value_positions,
                "sec5_impacted_indices_if_expand": impact.sec5_impacted_indices,
                "sec5_impacted_value_positions_if_expand": impact.sec5_impacted_value_positions,
                "sec3_u32_in_range_count_if_expand": impact.sec3_u32_in_range_count,
                "sec3_impacted_u32_sample_positions_if_expand": impact.sec3_impacted_u32_sample_positions,
                "sec3_impacted_u32_sample_values_if_expand": impact.sec3_impacted_u32_sample_values,
                "sec3_high_confidence_impacted_positions_if_expand": impact.sec3_high_confidence_impacted_positions,
                "sec3_high_confidence_impacted_values_if_expand": impact.sec3_high_confidence_impacted_values,
            }
    return {
        "format": "TE_V2_SCR_TEXT_CANDIDATES",
        "source_path": outer.source_path,
        "text_encoding": text_encoding,
        "raw_header": dict(outer.raw_header),
        "entries": entries,
    }


@lru_cache(maxsize=128)
def _parse_scr_sections_cached(path_str: str) -> ScrSectionDoc:
    outer = _probe_scr_cached(path_str)
    return parse_scr_sections(outer.decoded_payload_bytes)


def parse_scr_sections(decoded_payload_bytes: bytes) -> ScrSectionDoc:
    pos = 0
    sec1_length_offset = pos
    sec1_len = struct.unpack_from("<I", decoded_payload_bytes, pos)[0]
    pos += 4
    sec1_data_offset = pos
    sec1 = decoded_payload_bytes[pos : pos + sec1_len]
    pos += sec1_len

    sec2_length_offset = pos
    sec2_len = struct.unpack_from("<I", decoded_payload_bytes, pos)[0]
    pos += 4
    sec2_data_offset = pos
    sec2 = decoded_payload_bytes[pos : pos + sec2_len]
    pos += sec2_len

    sec3_length_offset = pos
    sec3_len = struct.unpack_from("<I", decoded_payload_bytes, pos)[0]
    pos += 4
    sec3_data_offset = pos
    sec3 = decoded_payload_bytes[pos : pos + sec3_len]
    pos += sec3_len

    sec4_length_offset = pos
    sec4_len = struct.unpack_from("<I", decoded_payload_bytes, pos)[0]
    pos += 4
    sec4_data_offset = pos
    sec4_raw = decoded_payload_bytes[pos : pos + sec4_len]
    pos += sec4_len
    sec4_offsets = [struct.unpack_from("<I", sec4_raw, off)[0] for off in range(0, len(sec4_raw), 4)]
    sec4_offset_positions = [sec4_data_offset + off for off in range(0, len(sec4_raw), 4)]

    sec5_length_offset = pos
    sec5_len = struct.unpack_from("<I", decoded_payload_bytes, pos)[0]
    pos += 4
    sec5_data_offset = pos
    sec5_end = pos + sec5_len
    sec5_entries: list[dict[str, object]] = []
    while pos < sec5_end:
        name_end = decoded_payload_bytes.index(0, pos, sec5_end)
        name = decoded_payload_bytes[pos:name_end].decode("cp932", errors="replace")
        pos = name_end + 1
        offset_pos = pos
        target_offset = struct.unpack_from("<I", decoded_payload_bytes, pos)[0]
        pos += 4
        sec5_entries.append(
            {
                "name": name,
                "offset": target_offset,
                "offset_position": offset_pos,
            }
        )

    sec3_u32_offset_hits: list[tuple[int, int]] = []
    for sec3_pos in range(0, len(sec3) - 3, 4):
        value = struct.unpack_from("<I", sec3, sec3_pos)[0]
        if 0 <= value < len(sec3):
            sec3_u32_offset_hits.append((sec3_data_offset + sec3_pos, value))

    return ScrSectionDoc(
        sec1_length_offset=sec1_length_offset,
        sec1_data_offset=sec1_data_offset,
        sec2_length_offset=sec2_length_offset,
        sec2_data_offset=sec2_data_offset,
        sec3_length_offset=sec3_length_offset,
        sec3_data_offset=sec3_data_offset,
        sec4_length_offset=sec4_length_offset,
        sec4_data_offset=sec4_data_offset,
        sec5_length_offset=sec5_length_offset,
        sec5_data_offset=sec5_data_offset,
        sec1_bytes=sec1,
        sec2_bytes=sec2,
        sec3_bytes=sec3,
        sec4_offsets=sec4_offsets,
        sec4_offset_positions=sec4_offset_positions,
        sec5_entries=sec5_entries,
        sec3_u32_offset_hits=sec3_u32_offset_hits,
    )


def build_scr_sections(section_doc: ScrSectionDoc) -> bytes:
    sec4_raw = b"".join(offset.to_bytes(4, "little") for offset in section_doc.sec4_offsets)
    sec5_raw = bytearray()
    for entry in section_doc.sec5_entries:
        sec5_raw.extend(str(entry["name"]).encode("cp932"))
        sec5_raw.append(0)
        sec5_raw.extend(int(entry["offset"]).to_bytes(4, "little"))
    out = bytearray()
    out.extend(len(section_doc.sec1_bytes).to_bytes(4, "little"))
    out.extend(section_doc.sec1_bytes)
    out.extend(len(section_doc.sec2_bytes).to_bytes(4, "little"))
    out.extend(section_doc.sec2_bytes)
    out.extend(len(section_doc.sec3_bytes).to_bytes(4, "little"))
    out.extend(section_doc.sec3_bytes)
    out.extend(len(sec4_raw).to_bytes(4, "little"))
    out.extend(sec4_raw)
    out.extend(len(sec5_raw).to_bytes(4, "little"))
    out.extend(sec5_raw)
    while len(out) & 3:
        out.append(0)
    return bytes(out)


def plan_scr_rebuild_impact(section_doc: ScrSectionDoc, *, anchor_offset: int, original_offset: int, current_offset: int, old_length: int, new_length: int) -> ScrRebuildImpact:
    delta = new_length - old_length
    sec4_impacted_indices = [idx for idx, target_offset in enumerate(section_doc.sec4_offsets) if target_offset > anchor_offset]
    sec5_impacted_indices = [
        idx for idx, sec5_entry in enumerate(section_doc.sec5_entries) if int(sec5_entry["offset"]) > anchor_offset
    ]
    commands = parse_scr_commands(section_doc.sec3_bytes)
    sec3_structural_reference_positions: list[int] = []
    sec3_structural_reference_values: list[int] = []
    sec3_impacted_u32_positions_if_expand: list[int] = []
    sec3_impacted_u32_values_if_expand: list[int] = []
    sec3_high_confidence_impacted_positions: list[int] = []
    sec3_high_confidence_impacted_values: list[int] = []
    for command in commands:
        if command.kind != "command" or command.opcode_u32 is None:
            continue
        parameter_offsets = STRUCTURAL_SEC3_REFERENCE_FIELDS.get(command.opcode_u32, ())
        for local_offset in parameter_offsets:
            if local_offset < 0 or local_offset + 4 > len(command.raw_bytes):
                continue
            value = struct.unpack_from("<I", command.raw_bytes, local_offset)[0]
            if anchor_offset < value < len(section_doc.sec3_bytes):
                sec3_structural_reference_positions.append(section_doc.sec3_data_offset + command.start + local_offset)
                sec3_structural_reference_values.append(value)
    for absolute_pos, value in section_doc.sec3_u32_offset_hits:
        rel_pos = absolute_pos - section_doc.sec3_data_offset
        if anchor_offset < value < len(section_doc.sec3_bytes):
            sec3_impacted_u32_positions_if_expand.append(absolute_pos)
            sec3_impacted_u32_values_if_expand.append(value)
        tail8 = section_doc.sec3_bytes[max(0, rel_pos - 8) : rel_pos].hex()
        for pattern_tail8, delta_to_anchor in KNOWN_SEC3_REFERENCE_PATTERNS:
            if tail8 == pattern_tail8 and value == anchor_offset + delta_to_anchor:
                sec3_high_confidence_impacted_positions.append(absolute_pos)
                sec3_high_confidence_impacted_values.append(value)
                break
    return ScrRebuildImpact(
        anchor_offset=anchor_offset,
        original_offset=original_offset,
        current_offset=current_offset,
        old_length=old_length,
        new_length=new_length,
        delta=delta,
        outer_decoded_payload_size_field_offset=16,
        sec3_length_field_offset=section_doc.sec3_length_offset,
        sec4_impacted_indices=sec4_impacted_indices,
        sec4_impacted_value_positions=[section_doc.sec4_offset_positions[idx] for idx in sec4_impacted_indices],
        sec5_impacted_indices=sec5_impacted_indices,
        sec5_impacted_value_positions=[int(section_doc.sec5_entries[idx]["offset_position"]) for idx in sec5_impacted_indices],
        sec3_u32_in_range_count=len(sec3_impacted_u32_positions_if_expand),
        sec3_impacted_u32_sample_positions=sec3_impacted_u32_positions_if_expand[:32],
        sec3_impacted_u32_sample_values=sec3_impacted_u32_values_if_expand[:32],
        sec3_high_confidence_impacted_positions=sec3_structural_reference_positions or sec3_high_confidence_impacted_positions,
        sec3_high_confidence_impacted_values=sec3_structural_reference_values or sec3_high_confidence_impacted_values,
    )


def _build_scr_bytes(raw_header: dict[str, object], decoded_payload_bytes: bytes) -> bytes:
    encoded_payload = transform_mode2_words(decoded_payload_bytes, int(raw_header["key_seed_u32"]))
    rebuilt = (
        b"SCR "
        + int(raw_header["version_u32"]).to_bytes(4, "little")
        + int(raw_header["codec_mode_u32"]).to_bytes(4, "little")
        + int(raw_header["key_seed_u32"]).to_bytes(4, "little")
        + int(raw_header["decoded_payload_size_u32"]).to_bytes(4, "little")
        + encoded_payload
    )
    if len(decoded_payload_bytes) != int(raw_header["decoded_payload_size_u32"]):
        raise ValueError("Decoded SCR payload size does not match header")
    return rebuilt


def compile_scr_text(doc: dict[str, object], text_encoding: str = "cp932") -> bytes:
    if str(doc.get("format")) != "TE_V2_SCR_TEXT_CANDIDATES":
        raise ValueError("Unsupported SCR text document format")
    source_path = Path(str(doc["source_path"]))
    outer = deepcopy(_probe_scr_cached(str(source_path)))
    sections = deepcopy(_parse_scr_sections_cached(str(source_path)))
    original_sec3 = sections.sec3_bytes
    changed_entries = sorted(
        (
            entry
            for entry in doc["entries"]
            if str(entry.get("text", "")) != str(entry.get("original_text", entry.get("text", "")))
        ),
        key=lambda item: int(item["offset"]),
    )
    replacements: list[dict[str, object]] = []
    last_original_end = 0
    for entry in changed_entries:
        current_text = str(entry.get("text", ""))
        original_offset = int(entry["offset"])
        length = int(entry.get("capacity_bytes", entry["length"]))
        original_end = original_offset + length
        if original_offset < last_original_end:
            raise ValueError("SCR text entries overlap and cannot be rebuilt safely")
        encoded = current_text.encode(text_encoding)
        if len(encoded) <= length:
            replacement_bytes = encoded + (b"\x00" * (length - len(encoded)))
        else:
            replacement_bytes = encoded
        replacements.append(
            {
                "offset": original_offset,
                "length": length,
                "replacement_bytes": replacement_bytes,
                "anchor_offset": int(entry.get("record_offset", original_offset)),
                "delta": len(replacement_bytes) - length,
            }
        )
        last_original_end = original_end

    if replacements:
        rebuilt_sec3 = bytearray()
        cursor = 0
        anchor_positions: list[int] = []
        anchor_deltas: list[int] = []
        prefix_deltas: list[int] = []
        running_delta = 0
        for replacement in replacements:
            original_offset = int(replacement["offset"])
            length = int(replacement["length"])
            rebuilt_sec3.extend(original_sec3[cursor:original_offset])
            rebuilt_sec3.extend(bytes(replacement["replacement_bytes"]))
            cursor = original_offset + length
            anchor_positions.append(int(replacement["anchor_offset"]))
            anchor_deltas.append(int(replacement["delta"]))
            running_delta += int(replacement["delta"])
            prefix_deltas.append(running_delta)
        rebuilt_sec3.extend(original_sec3[cursor:])
        sections.sec3_bytes = bytes(rebuilt_sec3)

        def _shift_after_anchor(target_offset: int) -> int:
            idx = bisect.bisect_left(anchor_positions, target_offset) - 1
            if idx < 0:
                return 0
            return prefix_deltas[idx]

        sections.sec4_offsets = [int(value) + _shift_after_anchor(int(value)) for value in sections.sec4_offsets]
        for entry in sections.sec5_entries:
            original_target = int(entry["offset"])
            entry["offset"] = original_target + _shift_after_anchor(original_target)
    else:
        sections.sec3_bytes = original_sec3

    rebuilt_payload = build_scr_sections(sections)
    raw_header = dict(outer.raw_header)
    raw_header["decoded_payload_size_u32"] = len(rebuilt_payload)
    return _build_scr_bytes(raw_header, rebuilt_payload)


def rebuild_scr(doc: ScrOuterDoc) -> bytes:
    return _build_scr_bytes(doc.raw_header, doc.decoded_payload_bytes)


def compile_scr_from_decoded_payload(raw_header: dict[str, object], decoded_payload_bytes: bytes) -> bytes:
    header = dict(raw_header)
    header["decoded_payload_size_u32"] = len(decoded_payload_bytes)
    return _build_scr_bytes(header, decoded_payload_bytes)


def write_probe(path: Path, output_path: Path) -> Path:
    doc = probe_scr(path)
    payload = {
        "format": doc.format,
        "source_path": doc.source_path,
        "raw_header": doc.raw_header,
        "decoded_payload_preview_hex": doc.decoded_payload_preview_hex,
        "decoded_payload_sha256": doc.decoded_payload_sha256,
        "decoded_u32_preview": doc.decoded_u32_preview,
        "decoded_nonzero_words": doc.decoded_nonzero_words,
        "ascii_literals": doc.ascii_literals,
        "known_container_magics": doc.known_container_magics,
        "container_summary": doc.container_summary,
    }
    _write_json_atomic(output_path, payload)
    return output_path


def write_text_doc(path: Path, doc: ScrTextDoc) -> None:
    payload = {
        "format": doc.format,
        "source_path": doc.source_path,
        "text_encoding": doc.text_encoding,
        "raw_header": doc.raw_header,
        "entries": doc.entries,
    }
    _write_json_atomic(path, payload)
