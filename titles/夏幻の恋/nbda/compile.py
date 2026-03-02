from __future__ import annotations

import base64
import struct

from .binary import from_hex
from .constants import ADB_MAGIC_U32, HEADER_STRUCT


def _from_b64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def _blob_from_doc(doc: dict, hex_key: str, b64_key: str) -> bytes:
    if hex_key in doc:
        return from_hex(str(doc.get(hex_key, "")))
    return _from_b64(str(doc.get(b64_key, "")))


def _compile_adb_raw(doc: dict) -> bytes:
    header_u32 = list(doc["header_u32"])
    if len(header_u32) != 12:
        raise ValueError("header_u32 must contain exactly 12 uint32 values.")

    section0 = _blob_from_doc(doc, "section0_hex", "section0_base64")
    section1 = _blob_from_doc(doc, "section1_hex", "section1_base64")
    tail = _blob_from_doc(doc, "tail_hex", "tail_base64")
    index_u32 = list(doc.get("index_u32", []))

    header_u32[0] = ADB_MAGIC_U32
    header_u32[1] = int(doc.get("version_u32", header_u32[1]))
    header_u32[4] = len(section0)
    header_u32[5] = len(index_u32)
    header_u32[6] = len(section1)

    header_blob = HEADER_STRUCT.pack(*header_u32)
    index_blob = struct.pack(f"<{len(index_u32)}I", *index_u32) if index_u32 else b""
    return header_blob + section0 + index_blob + section1 + tail


def _u16_units_to_bytes(units: list[int]) -> bytes:
    if not units:
        return b""
    return struct.pack(f"<{len(units)}H", *units)


def _slot_bytes_ir(slot: dict) -> bytes:
    if "bytes_u8" in slot:
        return bytes(int(x) & 0xFF for x in list(slot.get("bytes_u8", [])))

    words = list(slot.get("words", []))
    opcode = slot.get("opcode")
    if opcode is None and words:
        opcode = words[0]

    if opcode == 0x601 and slot.get("editable_text", False):
        text = str(slot.get("text", ""))
        text_raw = text.encode("utf-16le")
        text_units = list(struct.unpack(f"<{len(text_raw) // 2}H", text_raw)) if text_raw else []
        speaker_default = words[1] if len(words) > 1 else 0
        speaker = int(slot.get("speaker_u16", speaker_default)) & 0xFFFF
        suffix_words = [int(x) & 0xFFFF for x in list(slot.get("suffix_words", []))]
        words = [0x601, speaker, len(text_units), *text_units, 0, *suffix_words]

    if not words:
        raise ValueError("IR slot missing words/bytes_u8.")
    return struct.pack(f"<{len(words)}H", *[int(x) & 0xFFFF for x in words])


def _compile_adb_ir(doc: dict) -> bytes:
    header_u32 = list(doc["header_u32"])
    if len(header_u32) != 12:
        raise ValueError("header_u32 must contain exactly 12 uint32 values.")

    section0 = _blob_from_doc(doc, "section0_hex", "section0_base64")
    tail = _blob_from_doc(doc, "tail_hex", "tail_base64")
    slots = list(doc.get("slots", []))
    if not slots:
        raise ValueError("IR mode requires non-empty slots.")

    sorted_slots = sorted(
        slots,
        key=lambda s: (int(s.get("original_offset", 0)), int(s.get("slot_id", 0))),
    )

    section1 = bytearray()
    old_off_to_new: dict[int, int] = {}
    slot_id_to_new: dict[int, int] = {}
    for i, slot in enumerate(sorted_slots):
        old_off = int(slot.get("original_offset", 0))
        slot_id = int(slot.get("slot_id", i))
        new_off = len(section1)
        section1.extend(_slot_bytes_ir(slot))
        old_off_to_new[old_off] = new_off
        slot_id_to_new[slot_id] = new_off

    index_u32: list[int] = []
    entries = list(doc.get("entries", []))
    if entries:
        for entry in entries:
            if "slot_id" in entry:
                slot_id = int(entry["slot_id"])
                if slot_id not in slot_id_to_new:
                    raise ValueError(f"Unknown slot_id in entry: {slot_id}")
                index_u32.append(slot_id_to_new[slot_id])
                continue
            old_off = int(entry.get("original_offset", -1))
            if old_off not in old_off_to_new:
                raise ValueError(f"Unknown original_offset in entry: {old_off}")
            index_u32.append(old_off_to_new[old_off])
    else:
        for old_off in list(doc.get("index_u32", [])):
            old = int(old_off)
            if old not in old_off_to_new:
                raise ValueError(f"Unknown original index offset: {old}")
            index_u32.append(old_off_to_new[old])

    header_u32[0] = ADB_MAGIC_U32
    header_u32[1] = int(doc.get("version_u32", header_u32[1]))
    header_u32[4] = len(section0)
    header_u32[5] = len(index_u32)
    header_u32[6] = len(section1)

    header_blob = HEADER_STRUCT.pack(*header_u32)
    index_blob = struct.pack(f"<{len(index_u32)}I", *index_u32) if index_u32 else b""
    return header_blob + section0 + index_blob + bytes(section1) + tail


def _entry_bytes_legacy(entry: dict) -> bytes:
    if entry.get("opcode_u16") == 0x601 and entry.get("editable_text", False):
        text = str(entry.get("text", ""))
        text_raw = text.encode("utf-16le")
        text_len = len(text_raw) // 2
        speaker = int(entry.get("speaker_u16", 0)) & 0xFFFF
        suffix = _from_b64(entry.get("suffix_base64", ""))
        return struct.pack("<3H", 0x601, speaker, text_len) + text_raw + b"\x00\x00" + suffix

    if "editable_text" in entry:
        if not entry.get("editable_text", False):
            return _from_b64(entry.get("raw_base64", ""))
        prefix_units = list(entry.get("prefix_u16", []))
        text = str(entry.get("text", ""))
        suffix = _from_b64(entry.get("suffix_base64", ""))
        terminator = b"\x00\x00" if entry.get("has_terminator", True) else b""
        return _u16_units_to_bytes(prefix_units) + text.encode("utf-16le") + terminator + suffix

    if "raw_base64" in entry and "prefix_u16" not in entry:
        return _from_b64(entry.get("raw_base64", ""))

    prefix_units = list(entry.get("prefix_u16", []))
    text = str(entry.get("text", ""))
    return _u16_units_to_bytes(prefix_units) + text.encode("utf-16le") + b"\x00\x00"


def _legacy_build_editable(entries: list[dict]) -> tuple[bytearray, list[int]]:
    section1 = bytearray()
    index_u32: list[int] = []
    for entry in entries:
        index_u32.append(len(section1))
        section1.extend(_entry_bytes_legacy(entry))
    return section1, index_u32


def _detect_old_len(section1: bytes, off: int, entry: dict) -> int:
    storage_len = entry.get("storage_len")
    if storage_len is not None:
        return int(storage_len)

    raw_base64 = entry.get("raw_base64")
    if raw_base64 is not None:
        return len(_from_b64(raw_base64))

    raw_u16 = entry.get("raw_u16")
    if raw_u16 is not None:
        return (len(list(raw_u16)) + 1) * 2

    pos = off
    while pos + 1 < len(section1):
        if section1[pos] == 0 and section1[pos + 1] == 0:
            return pos + 2 - off
        pos += 2
    raise ValueError(f"Unterminated UTF-16 string at offset: {off}")


def _build_editable_preserve_layout(doc: dict, entries: list[dict]) -> tuple[bytearray, list[int]]:
    if ("section1_base64" not in doc and "section1_hex" not in doc) or "index_u32" not in doc:
        return _legacy_build_editable(entries)

    section1 = bytearray(_blob_from_doc(doc, "section1_hex", "section1_base64"))
    index_original = list(doc.get("index_u32", []))
    base_section1 = bytes(section1)

    replacements: dict[int, tuple[bytes, int]] = {}
    for entry in entries:
        off = int(entry.get("original_offset", -1))
        if off < 0:
            raise ValueError("editable entry missing original_offset")
        new_blob = _entry_bytes_legacy(entry)
        old_len = _detect_old_len(base_section1, off, entry)
        existing = replacements.get(off)
        if existing:
            if existing[0] != new_blob:
                raise ValueError(f"Inconsistent editable content for shared offset: {off}")
            continue
        replacements[off] = (new_blob, old_len)

    shift = 0
    delta_events: list[tuple[int, int]] = []
    for off in sorted(replacements):
        new_blob, old_len = replacements[off]
        cur_off = off + shift
        if cur_off < 0 or cur_off + old_len > len(section1):
            raise ValueError(f"Editable replacement out of range at offset: {off}")
        section1[cur_off : cur_off + old_len] = new_blob
        delta = len(new_blob) - old_len
        if delta:
            delta_events.append((off, delta))
            shift += delta

    index_u32: list[int] = []
    for orig_off in index_original:
        updated = int(orig_off)
        for changed_off, delta in delta_events:
            if orig_off > changed_off:
                updated += delta
        index_u32.append(updated)
    return section1, index_u32


def _compile_adb_editable_legacy(doc: dict) -> bytes:
    header_u32 = list(doc["header_u32"])
    if len(header_u32) != 12:
        raise ValueError("header_u32 must contain exactly 12 uint32 values.")

    section0 = _blob_from_doc(doc, "section0_hex", "section0_base64")
    tail = _blob_from_doc(doc, "tail_hex", "tail_base64")
    entries = list(doc.get("entries", []))
    section1, index_u32 = _build_editable_preserve_layout(doc, entries)

    header_u32[0] = ADB_MAGIC_U32
    header_u32[1] = int(doc.get("version_u32", header_u32[1]))
    header_u32[4] = len(section0)
    header_u32[5] = len(index_u32)
    header_u32[6] = len(section1)

    header_blob = HEADER_STRUCT.pack(*header_u32)
    index_blob = struct.pack(f"<{len(index_u32)}I", *index_u32) if index_u32 else b""
    return header_blob + section0 + index_blob + bytes(section1) + tail


def compile_adb(doc: dict) -> bytes:
    mode = doc.get("mode")
    if mode == "ir":
        return _compile_adb_ir(doc)
    if mode == "editable":
        if "slots" in doc:
            return _compile_adb_ir(doc)
        return _compile_adb_editable_legacy(doc)
    return _compile_adb_raw(doc)
