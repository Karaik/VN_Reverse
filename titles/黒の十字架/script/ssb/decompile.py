"""Decompiler for SAISYS SSB script files."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from .binary import load_code_words, load_script_pair, normalize_text_encoding, to_signed_u32, xor_aa
from .constants import DEFAULT_TEXT_ENCODING, JSON_FORMAT, JSON_VERSION, KNOWN_OPCODE_NAMES


ALLOWED_TEXT_CONTROL_CHARS = {"\r", "\n", "\t"}
VM_CALL_ABS_OPCODE = 0x8000000C
VM_DATA_STORE_DWORD_OPCODE = 0x80000001
AA13_SUBROUTINE_PC = 0x0000AA13
AA13_SLOT_MESSAGE_TAG = 0x000714AE
AA13_SLOT_SELECTOR = 0x000714AF
AA13_SLOT_SHADOW_TEXT = 0x000714B0
AA13_SLOT_MAIN_TEXT = 0x000714B1
AA13_SLOT_DISPLAY_NAME = 0x000714B4
AA13_SLOT_LEADING_FLAG = 0x000714B5
AA13_SLOT_TEXT_MODE = 0x000714B2
AA13_SLOT_NAME_MODE = 0x000714B3
CALL_8351_SUBROUTINE_PC = 0x00008351
CALL_8351_SLOT_LABEL = 0x00071247
AC07_SUBROUTINE_PC = 0x0000AC07
AC07_SLOT_KIND = 0x000714C2
AC07_SLOT_TEXT = 0x000714C3
AC07_COMMIT_SUBROUTINE_PC = 0x0000AC31
AC07_MARKER_BIND_OPCODE = 0x80070008
AC07_MARKER_STORE_OPCODE = 0x80010002
AC07_MARKER_RETURN_OPCODE = 0x80010000
AC07_MARKER_JUMP_OPCODE = 0x80000010


def _decode_string_entry(
    decoded_data: bytes,
    byte_offset: int,
    text_encoding: str,
    *,
    allowed_control_chars: set[str] | None = None,
) -> dict[str, object] | None:
    if byte_offset < 0 or byte_offset >= len(decoded_data):
        return None
    terminator = decoded_data.find(b"\x00", byte_offset)
    if terminator == -1:
        return None
    raw = decoded_data[byte_offset:terminator]
    if len(raw) < 1:
        return None
    try:
        text = raw.decode(text_encoding)
    except UnicodeDecodeError:
        return None
    allowed_controls = allowed_control_chars or set()
    printable_chars = 0
    for ch in text:
        if ch.isprintable():
            printable_chars += 1
            continue
        if ch in allowed_controls:
            continue
        return None
    if printable_chars == 0:
        return None
    word_offset = offset_to_word_offset(byte_offset)
    return {
        "byte_offset": byte_offset,
        "word_offset": word_offset,
        "storage_bytes": len(raw) + 1,
        "raw_hex": raw.hex(),
        "text": text,
        "original_text": text,
        "reference_count": 0,
        "text_reference_count": 0,
        "text_reference_pcs": [],
        "main_display_reference_count": 0,
        "main_display_reference_pcs": [],
        "main_display_name_reference_count": 0,
        "main_display_name_reference_pcs": [],
    }


def _decode_string_entry_at_word_offset(
    decoded_data: bytes,
    word_offset: int,
    text_encoding: str,
    *,
    allowed_control_chars: set[str] | None = None,
) -> dict[str, object] | None:
    byte_offset = word_offset * 4
    return _decode_string_entry(
        decoded_data,
        byte_offset,
        text_encoding,
        allowed_control_chars=allowed_control_chars,
    )


def _collect_immediate_call_args(code_words: list[int], call_pc: int, arg_count: int) -> list[int] | None:
    start = call_pc - arg_count
    if start < 0:
        return None
    args = code_words[start:call_pc]
    if len(args) != arg_count:
        return None
    if any(value >= 0x80000000 for value in args):
        return None
    return args


def _derive_call_arg_slot_order(code_words: list[int], subroutine_pc: int) -> list[int]:
    slots: list[int] = []
    pc = subroutine_pc
    while pc + 1 < len(code_words):
        maybe_slot = code_words[pc]
        maybe_store = code_words[pc + 1]
        if maybe_slot >= 0x80000000 or maybe_store != VM_DATA_STORE_DWORD_OPCODE:
            break
        slots.append(maybe_slot)
        pc += 2
    return list(reversed(slots))


def _merge_string_entries(
    strings: list[dict[str, object]],
    extra_entries: list[dict[str, object]],
) -> list[dict[str, object]]:
    merged: dict[tuple[int | None, int], dict[str, object]] = {
        (entry["word_offset"], int(entry["byte_offset"])): entry for entry in strings
    }
    for entry in extra_entries:
        key = (entry["word_offset"], int(entry["byte_offset"]))
        merged.setdefault(key, entry)
    return sorted(merged.values(), key=lambda item: (int(item["byte_offset"]), int(item["word_offset"] or -1)))


def scan_strings(
    decoded_data: bytes,
    reference_counts: dict[int, int],
    text_reference_map: dict[int, list[int]],
    text_encoding: str,
) -> list[dict[str, object]]:
    strings: list[dict[str, object]] = []
    offset = 0
    size = len(decoded_data)
    while offset < size:
        if offset > 0 and decoded_data[offset - 1] != 0:
            offset += 1
            continue
        start = offset
        terminator = decoded_data.find(b"\x00", offset)
        if terminator == -1:
            break
        offset = terminator + 1
        entry = _decode_string_entry(
            decoded_data,
            start,
            text_encoding,
            allowed_control_chars=ALLOWED_TEXT_CONTROL_CHARS,
        )
        if entry is None:
            continue
        word_offset = entry["word_offset"]
        text_reference_pcs = text_reference_map.get(word_offset, []) if word_offset is not None else []
        entry["reference_count"] = reference_counts.get(word_offset, 0) if word_offset is not None else 0
        entry["text_reference_count"] = len(text_reference_pcs)
        entry["text_reference_pcs"] = text_reference_pcs[:8]
        strings.append(entry)
    return strings


def offset_to_word_offset(byte_offset: int) -> int | None:
    if byte_offset % 4 != 0:
        return None
    return byte_offset // 4


def build_reference_counts(code_words: list[int], data_size: int) -> dict[int, int]:
    counts: dict[int, int] = {}
    for word in code_words:
        if word >= 0x80000000:
            continue
        byte_offset = word * 4
        if byte_offset >= data_size:
            continue
        counts[word] = counts.get(word, 0) + 1
    return counts


def build_text_reference_map(code_words: list[int], data_size: int) -> dict[int, list[int]]:
    # Phase 1 keeps only VM-proven main-display text commands in the formal text chain.
    # Generic text-related window inference is intentionally disabled until the relevant
    # VM subroutines are fully reversed.
    return {}


def is_main_display_reference(code_words: list[int], pc: int) -> bool:
    if pc < 8 or pc + 8 >= len(code_words):
        return False
    return (
        to_signed_u32(code_words[pc - 8]) == -2147483632
        and to_signed_u32(code_words[pc - 5]) == -2147483647
        and code_words[pc + 2] == 0x12
        and code_words[pc + 4] == 0x0000AA13
        and to_signed_u32(code_words[pc + 5]) == -2147483636
        and code_words[pc + 6] == 1
        and code_words[pc + 7] == 0x000415A5
        and to_signed_u32(code_words[pc + 8]) in {-2147483647, -2147483641}
    )


def build_main_display_reference_map(code_words: list[int], data_size: int) -> dict[int, list[int]]:
    refs: dict[int, list[int]] = {}
    for index, word in enumerate(code_words):
        if word >= 0x80000000:
            continue
        byte_offset = word * 4
        if byte_offset >= data_size:
            continue
        if not is_main_display_reference(code_words, index):
            continue
        refs.setdefault(word, []).append(index)
    return refs


def build_main_display_records(
    code_words: list[int],
    decoded_data: bytes,
    text_encoding: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    call_8351_arg_slot_order = _derive_call_arg_slot_order(code_words, CALL_8351_SUBROUTINE_PC)
    aa13_call_arg_slot_order = _derive_call_arg_slot_order(code_words, AA13_SUBROUTINE_PC)
    active_prefix_reset_pc: int | None = None
    active_prefix_chain: list[dict[str, object]] = []
    for index, word in enumerate(code_words):
        if word == 0x00008309 and index + 1 < len(code_words) and code_words[index + 1] == VM_CALL_ABS_OPCODE:
            active_prefix_reset_pc = index
            active_prefix_chain = []
            continue

        if word == 0x00008351 and index + 1 < len(code_words) and code_words[index + 1] == VM_CALL_ABS_OPCODE:
            call_args = _collect_immediate_call_args(code_words, index, len(call_8351_arg_slot_order))
            if call_args is not None:
                slot_values = {
                    slot: value for slot, value in zip(call_8351_arg_slot_order, call_args)
                }
                label_word_offset = slot_values[CALL_8351_SLOT_LABEL]
                label_entry = _decode_string_entry_at_word_offset(
                    decoded_data,
                    label_word_offset,
                    text_encoding,
                    allowed_control_chars=ALLOWED_TEXT_CONTROL_CHARS,
                )
                active_prefix_chain.append(
                    {
                        "call_pc": index,
                        "call_opcode_pc": index + 1,
                        "call_arg_slot_order": [f"0x{slot:08X}" for slot in call_8351_arg_slot_order],
                        "call_arg_values": call_args,
                        "slot_values": {f"0x{slot:08X}": value for slot, value in slot_values.items()},
                        "slot_71249_value": slot_values[0x00071249],
                        "variant_selector_kind": "prefix_variant_selector",
                        "variant_selector_domain": [0, 1],
                        "resource_chain_kind": "visual_prefix_resource_chain",
                        "resource_archive_kind": "grd_visual_resource",
                        "layer_role": (
                            "base_visual_layer"
                            if slot_values[0x00071249] == 0
                            else "overlay_diff_visual_layer"
                        ),
                        "prefix_family_kind": "visual_resource_family",
                        "slot_71248_value": slot_values[0x00071248],
                        "label_word_offset": label_entry["word_offset"] if label_entry else label_word_offset,
                        "label_byte_offset": label_entry["byte_offset"] if label_entry else label_word_offset * 4,
                        "label_text": label_entry["text"] if label_entry else "",
                        "grd_label_text": label_entry["text"] if label_entry else "",
                        "grd_resource_name": label_entry["text"] if label_entry else "",
                        "slot_71246_value": slot_values[0x00071246],
                    }
                )
            continue

        if word != 0x0000AA13:
            continue
        if index + 1 >= len(code_words):
            continue
        if to_signed_u32(code_words[index + 1]) != -2147483636:
            continue
        if index < 8:
            continue
        if code_words[index - 2] != 0x12:
            continue

        call_args = _collect_immediate_call_args(code_words, index, len(aa13_call_arg_slot_order))
        if call_args is None:
            continue
        slot_values = {slot: value for slot, value in zip(aa13_call_arg_slot_order, call_args)}

        display_name_word_offset = slot_values[AA13_SLOT_DISPLAY_NAME]
        main_text_word_offset = slot_values[AA13_SLOT_MAIN_TEXT]
        shadow_text_word_offset = slot_values[AA13_SLOT_SHADOW_TEXT]
        message_tag_word_offset = slot_values[AA13_SLOT_MESSAGE_TAG]
        selector_value = slot_values[AA13_SLOT_SELECTOR]

        main_text_entry = (
            _decode_string_entry_at_word_offset(
                decoded_data,
                main_text_word_offset,
                text_encoding,
                allowed_control_chars=ALLOWED_TEXT_CONTROL_CHARS,
            )
            if main_text_word_offset < 0x80000000
            else None
        )
        shadow_text_entry = (
            _decode_string_entry_at_word_offset(
                decoded_data,
                shadow_text_word_offset,
                text_encoding,
                allowed_control_chars=ALLOWED_TEXT_CONTROL_CHARS,
            )
            if shadow_text_word_offset < 0x80000000
            else None
        )
        display_name_entry = (
            _decode_string_entry_at_word_offset(
                decoded_data,
                display_name_word_offset,
                text_encoding,
                allowed_control_chars=ALLOWED_TEXT_CONTROL_CHARS,
            )
            if display_name_word_offset < 0x80000000
            else None
        )
        message_tag_entry = (
            _decode_string_entry_at_word_offset(
                decoded_data,
                message_tag_word_offset,
                text_encoding,
                allowed_control_chars=ALLOWED_TEXT_CONTROL_CHARS,
            )
            if message_tag_word_offset < 0x80000000
            else None
        )
        if main_text_entry is None:
            continue

        base_prefix_entries = [item for item in active_prefix_chain if item["slot_71249_value"] == 0]
        overlay_prefix_entries = [item for item in active_prefix_chain if item["slot_71249_value"] == 1]

        records.append(
            {
                "record_pc": index,
                "call_opcode_pc": index + 1,
                "call_arg_slot_order": [f"0x{slot:08X}" for slot in aa13_call_arg_slot_order],
                "call_arg_values": call_args,
                "slot_values": {f"0x{slot:08X}": value for slot, value in slot_values.items()},
                "active_prefix_reset_pc": active_prefix_reset_pc,
                "active_prefix_chain": [dict(item) for item in active_prefix_chain],
                "active_prefix_chain_count": len(active_prefix_chain),
                "active_prefix_selector_set": sorted({item["slot_71249_value"] for item in active_prefix_chain}),
                "active_prefix_visual_mode": (
                    "none"
                    if not active_prefix_chain
                    else (
                        "base_plus_overlay"
                        if any(item["slot_71249_value"] == 1 for item in active_prefix_chain)
                        else "base_only"
                    )
                ),
                "base_visual_label_text": base_prefix_entries[0]["label_text"] if base_prefix_entries else "",
                "base_grd_label_text": base_prefix_entries[0]["grd_label_text"] if base_prefix_entries else "",
                "overlay_visual_label_text": overlay_prefix_entries[0]["label_text"] if overlay_prefix_entries else "",
                "overlay_grd_label_text": overlay_prefix_entries[0]["grd_label_text"] if overlay_prefix_entries else "",
                "slot_714B5_value": slot_values[AA13_SLOT_LEADING_FLAG],
                "display_name_word_offset": display_name_entry["word_offset"] if display_name_entry else None,
                "display_name_byte_offset": display_name_entry["byte_offset"] if display_name_entry else None,
                "display_name_text": display_name_entry["text"] if display_name_entry else "",
                "slot_714B3_value": slot_values[AA13_SLOT_NAME_MODE],
                "slot_714B2_value": slot_values[AA13_SLOT_TEXT_MODE],
                "text_mode_kind": "main_display_text_mode",
                "has_display_name": bool(display_name_entry and display_name_entry["text"]),
                "main_text_word_offset": main_text_entry["word_offset"],
                "main_text_byte_offset": main_text_entry["byte_offset"],
                "main_text": main_text_entry["text"],
                "shadow_text_word_offset": shadow_text_entry["word_offset"] if shadow_text_entry else None,
                "shadow_text_byte_offset": shadow_text_entry["byte_offset"] if shadow_text_entry else None,
                "shadow_text": shadow_text_entry["text"] if shadow_text_entry else "",
                "selector": selector_value,
                "message_tag_word_offset": message_tag_entry["word_offset"] if message_tag_entry else None,
                "message_tag_byte_offset": message_tag_entry["byte_offset"] if message_tag_entry else None,
                "message_tag_text": message_tag_entry["text"] if message_tag_entry else "",
            }
        )
    return records


def build_ac07_ui_records(
    code_words: list[int],
    decoded_data: bytes,
    text_encoding: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    ac07_call_arg_slot_order = _derive_call_arg_slot_order(code_words, AC07_SUBROUTINE_PC)
    if not ac07_call_arg_slot_order:
        return records

    for index, word in enumerate(code_words):
        if word != AC07_SUBROUTINE_PC:
            continue
        if index + 1 >= len(code_words) or code_words[index + 1] != VM_CALL_ABS_OPCODE:
            continue
        call_args = _collect_immediate_call_args(code_words, index, len(ac07_call_arg_slot_order))
        if call_args is None:
            continue
        slot_values = {slot: value for slot, value in zip(ac07_call_arg_slot_order, call_args)}
        text_word_offset = slot_values[AC07_SLOT_TEXT]
        text_entry = (
            _decode_string_entry_at_word_offset(
                decoded_data,
                text_word_offset,
                text_encoding,
                allowed_control_chars=ALLOWED_TEXT_CONTROL_CHARS,
            )
            if text_word_offset < 0x80000000
            else None
        )
        marker_word_offset: int | None = None
        marker_byte_offset: int | None = None
        marker_text = ""
        if (
            index >= 8
            and code_words[index - 7] == AC07_MARKER_BIND_OPCODE
            and code_words[index - 6] == AC07_MARKER_STORE_OPCODE
            and code_words[index - 5] == AC07_MARKER_RETURN_OPCODE
            and code_words[index - 4] == index + 2
            and code_words[index - 3] == AC07_MARKER_JUMP_OPCODE
        ):
            candidate_word_offset = code_words[index - 8]
            candidate_entry = _decode_string_entry_at_word_offset(
                decoded_data,
                candidate_word_offset,
                text_encoding,
                allowed_control_chars=ALLOWED_TEXT_CONTROL_CHARS,
            )
            if candidate_entry is not None:
                marker_word_offset = int(candidate_entry["word_offset"])
                marker_byte_offset = int(candidate_entry["byte_offset"])
                marker_text = str(candidate_entry["text"])
        records.append(
            {
                "record_pc": index,
                "call_opcode_pc": index + 1,
                "call_arg_slot_order": [f"0x{slot:08X}" for slot in ac07_call_arg_slot_order],
                "call_arg_values": call_args,
                "slot_values": {f"0x{slot:08X}": value for slot, value in slot_values.items()},
                "marker_word_offset": marker_word_offset,
                "marker_byte_offset": marker_byte_offset,
                "marker_text": marker_text,
                "text_word_offset": text_entry["word_offset"] if text_entry else text_word_offset,
                "text_byte_offset": text_entry["byte_offset"] if text_entry else text_word_offset * 4,
                "text": text_entry["text"] if text_entry else "",
                "slot_714C2_value": slot_values[AC07_SLOT_KIND],
                "slot_714C3_value": slot_values[AC07_SLOT_TEXT],
                "ui_record_kind": (
                    "ac07_visible_text_item"
                    if slot_values[AC07_SLOT_KIND] == 1 and text_entry and text_entry["text"]
                    else "ac07_internal_or_paging_item"
                ),
                "record_kind": "ac07_ui_text_record",
            }
        )
    return records


def build_ac07_visible_clusters(
    code_words: list[int],
    ui_records: list[dict[str, object]],
) -> list[dict[str, object]]:
    visible_items = [record for record in ui_records if record["ui_record_kind"] == "ac07_visible_text_item"]
    clusters: list[dict[str, object]] = []
    items: list[dict[str, object]] = []

    def flush() -> None:
        nonlocal items
        if not items:
            return
        last_pc = int(items[-1]["record_pc"])
        commit_pc = None
        for pos in range(last_pc + 2, len(code_words) - 1):
            if code_words[pos] == AC07_SUBROUTINE_PC and code_words[pos + 1] == VM_CALL_ABS_OPCODE:
                break
            if code_words[pos] == AC07_COMMIT_SUBROUTINE_PC and code_words[pos + 1] == VM_CALL_ABS_OPCODE:
                commit_pc = pos
                break
        if commit_pc is not None:
            marker_values = [str(item.get("marker_text", "")) for item in items if item.get("marker_text")]
            clusters.append(
                {
                    "record_kind": "ac07_visible_text_cluster",
                    "cluster_size": len(items),
                    "start_pc": int(items[0]["record_pc"]),
                    "end_pc": int(items[-1]["record_pc"]),
                    "commit_pc": commit_pc,
                    "markers": marker_values,
                    "choices": [
                        {
                            "record_pc": int(item["record_pc"]),
                            "marker_text": str(item.get("marker_text", "")),
                            "marker_word_offset": item.get("marker_word_offset"),
                            "marker_byte_offset": item.get("marker_byte_offset"),
                            "text_word_offset": int(item["text_word_offset"]),
                            "text_byte_offset": int(item["text_byte_offset"]),
                            "text": str(item["text"]),
                        }
                        for item in items
                    ],
                }
            )
        items = []

    for item in visible_items:
        if not items:
            items.append(item)
            continue
        prev_pc = int(items[-1]["record_pc"])
        current_pc = int(item["record_pc"])
        segment = code_words[prev_pc + 2 : current_pc]
        has_intermediate_ac07 = any(
            segment[pos] == AC07_SUBROUTINE_PC and pos + 1 < len(segment) and segment[pos + 1] == VM_CALL_ABS_OPCODE
            for pos in range(len(segment) - 1)
        )
        has_commit = any(
            segment[pos] == AC07_COMMIT_SUBROUTINE_PC and pos + 1 < len(segment) and segment[pos + 1] == VM_CALL_ABS_OPCODE
            for pos in range(len(segment) - 1)
        )
        if has_intermediate_ac07 or has_commit:
            flush()
        items.append(item)
    flush()
    return clusters


def build_ac07_character_selection_records(visible_clusters: list[dict[str, object]]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for cluster in visible_clusters:
        marker_values = [str(marker) for marker in cluster["markers"] if marker]
        unique_markers = sorted(set(marker_values))
        if len(cluster["choices"]) >= 2 and len(unique_markers) == 1:
            entries.append(
                {
                    "record_kind": "ac07_character_selection_cluster",
                    "cluster_size": int(cluster["cluster_size"]),
                    "start_pc": int(cluster["start_pc"]),
                    "end_pc": int(cluster["end_pc"]),
                    "marker_text": unique_markers[0],
                    "choices": [
                        {
                            "record_pc": int(item["record_pc"]),
                            "text_word_offset": int(item["text_word_offset"]),
                            "text_byte_offset": int(item["text_byte_offset"]),
                            "text": str(item["text"]),
                        }
                        for item in cluster["choices"]
                        if item["text"]
                    ],
                }
            )
    return entries


def build_ac07_option_clusters(visible_clusters: list[dict[str, object]]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for cluster in visible_clusters:
        marker_values = [str(marker) for marker in cluster["markers"] if marker]
        unique_markers = sorted(set(marker_values))
        if len(cluster["choices"]) < 2 or len(unique_markers) == 1:
            continue
        entries.append(
            {
                "record_kind": "ac07_option_cluster",
                "cluster_size": int(cluster["cluster_size"]),
                "start_pc": int(cluster["start_pc"]),
                "end_pc": int(cluster["end_pc"]),
                "commit_pc": int(cluster["commit_pc"]),
                "markers": list(cluster["markers"]),
                "choices": [dict(choice) for choice in cluster["choices"]],
            }
        )
    return entries


def build_name_related_records(project: dict[str, object]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for record in project["main_display_records"]:
        if not record["display_name_text"]:
            continue
        entries.append(
            {
                "record_kind": "aa13_display_name",
                "record_pc": record["record_pc"],
                "text_word_offset": record["display_name_word_offset"],
                "text_byte_offset": record["display_name_byte_offset"],
                "text": record["display_name_text"],
            }
        )
    for cluster in project["ac07_character_selection_records"]:
        for choice in cluster["choices"]:
            entries.append(
                {
                    "record_kind": "ac07_character_selection_name",
                    "marker_text": cluster["marker_text"],
                    "record_pc": choice["record_pc"],
                    "text_word_offset": choice["text_word_offset"],
                    "text_byte_offset": choice["text_byte_offset"],
                    "text": choice["text"],
                }
            )
    for cluster in project["ac07_option_clusters"]:
        for choice in cluster["choices"]:
            entries.append(
                {
                    "record_kind": "ac07_option_text",
                    "markers": cluster["markers"],
                    "marker_text": choice.get("marker_text", ""),
                    "record_pc": choice["record_pc"],
                    "text_word_offset": choice["text_word_offset"],
                    "text_byte_offset": choice["text_byte_offset"],
                    "text": choice["text"],
                }
            )
    return entries


def build_main_display_name_reference_map(records: list[dict[str, object]]) -> dict[int, list[int]]:
    refs: dict[int, list[int]] = {}
    for record in records:
        word_offset = record["display_name_word_offset"]
        if word_offset is None:
            continue
        refs.setdefault(int(word_offset), []).append(int(record["record_pc"]))
    return refs


def build_text_entries(strings: list[dict[str, object]]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for entry in strings:
        usage = None
        if int(entry["main_display_name_reference_count"]) > 0:
            usage = "main_display_name"
        elif int(entry["main_display_reference_count"]) > 0:
            usage = "main_display_text"
        if usage is None:
            continue
        entries.append(
            {
                "word_offset": entry["word_offset"],
                "byte_offset": entry["byte_offset"],
                "storage_bytes": entry["storage_bytes"],
                "text": entry["text"],
                "original_text": entry["original_text"],
                "raw_hex": entry["raw_hex"],
                "text_reference_count": entry["text_reference_count"],
                "main_display_reference_count": entry["main_display_reference_count"],
                "main_display_name_reference_count": entry["main_display_name_reference_count"],
                "usage": usage,
            }
        )
    return sorted(
        entries,
        key=lambda item: (
            item["main_display_reference_count"] == 0,
            item["byte_offset"],
            item["word_offset"],
        ),
    )


def build_translation_entries(strings: list[dict[str, object]]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for entry in strings:
        usage = None
        if int(entry["main_display_name_reference_count"]) > 0:
            usage = "main_display_name"
        elif int(entry["main_display_reference_count"]) > 0:
            usage = "main_display_text"
        if usage is None:
            continue
        entries.append(
            {
                "word_offset": entry["word_offset"],
                "byte_offset": entry["byte_offset"],
                "storage_bytes": entry["storage_bytes"],
                "text": entry["text"],
                "original_text": entry["original_text"],
                "raw_hex": entry["raw_hex"],
                "usage": usage,
                "reference_count": entry["reference_count"],
                "text_reference_count": entry["text_reference_count"],
                "text_reference_pcs": entry["text_reference_pcs"],
                "main_display_reference_count": entry["main_display_reference_count"],
                "main_display_reference_pcs": entry["main_display_reference_pcs"],
                "main_display_name_reference_count": entry["main_display_name_reference_count"],
                "main_display_name_reference_pcs": entry["main_display_name_reference_pcs"],
            }
        )
    usage_order = {"main_display_name": 0, "main_display_text": 1}
    return sorted(
        entries,
        key=lambda item: (
            min(
                item["main_display_name_reference_pcs"] + item["main_display_reference_pcs"]
                if (item["main_display_name_reference_pcs"] or item["main_display_reference_pcs"])
                else [10**9]
            ),
            usage_order.get(str(item["usage"]), 9),
            item["byte_offset"],
            item["word_offset"],
        ),
    )


def refine_translation_entry_usages(code_words: list[int], entries: list[dict[str, object]]) -> list[dict[str, object]]:
    return entries


def build_project(script_dir: Path, text_encoding: str = DEFAULT_TEXT_ENCODING) -> dict[str, object]:
    text_encoding = normalize_text_encoding(text_encoding)
    code_bytes, data_bytes = load_script_pair(script_dir)
    decoded_data = xor_aa(data_bytes)
    code_words = load_code_words(code_bytes)
    reference_counts = build_reference_counts(code_words, len(decoded_data))
    text_reference_map = build_text_reference_map(code_words, len(decoded_data))
    main_display_reference_map = build_main_display_reference_map(code_words, len(decoded_data))
    main_display_records = build_main_display_records(code_words, decoded_data, text_encoding)
    ac07_ui_records = build_ac07_ui_records(code_words, decoded_data, text_encoding)
    ac07_visible_clusters = build_ac07_visible_clusters(code_words, ac07_ui_records)
    ac07_character_selection_records = build_ac07_character_selection_records(ac07_visible_clusters)
    ac07_option_clusters = build_ac07_option_clusters(ac07_visible_clusters)
    main_display_name_reference_map = build_main_display_name_reference_map(main_display_records)
    strings = scan_strings(decoded_data, reference_counts, text_reference_map, text_encoding)
    missing_record_strings: list[dict[str, object]] = []
    for record in main_display_records:
        word_offset = record["display_name_word_offset"]
        if word_offset is None:
            continue
        entry = _decode_string_entry_at_word_offset(
            decoded_data,
            int(word_offset),
            text_encoding,
            allowed_control_chars=ALLOWED_TEXT_CONTROL_CHARS,
        )
        if entry is not None:
            entry["reference_count"] = reference_counts.get(int(word_offset), 0)
            missing_record_strings.append(entry)
    strings = _merge_string_entries(strings, missing_record_strings)
    for entry in strings:
        word_offset = entry["word_offset"]
        if word_offset is None:
            continue
        main_display_pcs = main_display_reference_map.get(word_offset, [])
        main_display_name_pcs = main_display_name_reference_map.get(word_offset, [])
        entry["main_display_reference_count"] = len(main_display_pcs)
        entry["main_display_reference_pcs"] = main_display_pcs[:8]
        entry["text_reference_count"] = len(main_display_pcs)
        entry["text_reference_pcs"] = main_display_pcs[:8]
        entry["main_display_name_reference_count"] = len(main_display_name_pcs)
        entry["main_display_name_reference_pcs"] = main_display_name_pcs[:8]
    text_entries = build_text_entries(strings)
    translation_entries = build_translation_entries(strings)
    translation_entries = refine_translation_entry_usages(code_words, translation_entries)
    project = {
        "format": JSON_FORMAT,
        "version": JSON_VERSION,
        "text_encoding": text_encoding,
        "script_dir": str(script_dir),
        "code_size": len(code_bytes),
        "data_size": len(data_bytes),
        "code_words": code_words,
        "decoded_data_base64": base64.b64encode(decoded_data).decode("ascii"),
        "strings": strings,
        "main_display_records": main_display_records,
        "ac07_ui_records": ac07_ui_records,
        "ac07_visible_clusters": ac07_visible_clusters,
        "ac07_character_selection_records": ac07_character_selection_records,
        "ac07_option_clusters": ac07_option_clusters,
        "text_entries": text_entries,
        "translation_entries": translation_entries,
    }
    project["name_related_records"] = build_name_related_records(project)
    return project


def build_ssbsrc(project: dict[str, object]) -> str:
    code_words = project["code_words"]
    strings = project["strings"]
    string_lookup = {
        entry["word_offset"]: entry["text"]
        for entry in strings
        if entry["word_offset"] is not None
    }
    lines = [
        "# SAISYS SSB source dump",
        "# Positive values are kept as literals; if they align to a decoded string offset, a preview is attached.",
        "",
    ]
    for index, unsigned_value in enumerate(code_words):
        signed_value = to_signed_u32(unsigned_value)
        if signed_value < 0:
            name = KNOWN_OPCODE_NAMES.get(signed_value, f"OP_0x{unsigned_value:08X}")
            lines.append(f"{index:08d}: 0x{unsigned_value:08X} {signed_value:12d} {name}")
            continue
        preview = ""
        if unsigned_value in string_lookup:
            text = string_lookup[unsigned_value].replace("\r", "\\r").replace("\n", "\\n")
            preview = f" ; text={text!r}"
        lines.append(f"{index:08d}: 0x{unsigned_value:08X} {signed_value:12d}{preview}")
    return "\n".join(lines) + "\n"


def write_project(script_dir: Path, output_dir: Path, text_encoding: str = DEFAULT_TEXT_ENCODING) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    project = build_project(script_dir, text_encoding=text_encoding)
    json_path = output_dir / "script.json"
    src_path = output_dir / "script.ssbsrc"
    text_json_path = output_dir / "text_entries.json"
    translation_json_path = output_dir / "translation_entries.json"
    records_json_path = output_dir / "main_display_records.json"
    ac07_json_path = output_dir / "ac07_ui_records.json"
    ac07_cluster_json_path = output_dir / "ac07_visible_clusters.json"
    ac07_character_json_path = output_dir / "ac07_character_selection_records.json"
    ac07_option_json_path = output_dir / "ac07_option_clusters.json"
    name_related_json_path = output_dir / "name_related_records.json"
    json_path.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    src_path.write_text(build_ssbsrc(project), encoding="utf-8")
    text_json_path.write_text(
        json.dumps(
            {
                "format": "saisys-ssb-text-entries",
                "version": JSON_VERSION,
                "entries": project["text_entries"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    translation_json_path.write_text(
        json.dumps(
            {
                "format": "saisys-ssb-translation-entries",
                "version": JSON_VERSION,
                "entries": project["translation_entries"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    records_json_path.write_text(
        json.dumps(
            {
                "format": "saisys-ssb-main-display-records",
                "version": JSON_VERSION,
                "entries": project["main_display_records"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    ac07_json_path.write_text(
        json.dumps(
            {
                "format": "saisys-ssb-ac07-ui-records",
                "version": JSON_VERSION,
                "entries": project["ac07_ui_records"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    ac07_cluster_json_path.write_text(
        json.dumps(
            {
                "format": "saisys-ssb-ac07-visible-clusters",
                "version": JSON_VERSION,
                "entries": project["ac07_visible_clusters"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    ac07_character_json_path.write_text(
        json.dumps(
            {
                "format": "saisys-ssb-ac07-character-selection-records",
                "version": JSON_VERSION,
                "entries": project["ac07_character_selection_records"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    ac07_option_json_path.write_text(
        json.dumps(
            {
                "format": "saisys-ssb-ac07-option-clusters",
                "version": JSON_VERSION,
                "entries": project["ac07_option_clusters"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    name_related_json_path.write_text(
        json.dumps(
            {
                "format": "saisys-ssb-name-related-records",
                "version": JSON_VERSION,
                "entries": project["name_related_records"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return json_path, src_path
