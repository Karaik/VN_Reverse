from __future__ import annotations

import struct

from .binary import from_hex, text_quality, to_hex, u16_words
from .constants import ADB_MAGIC_U32, HEADER_STRUCT, opcode_name


def parse_adb(data: bytes) -> dict:
    if len(data) < HEADER_STRUCT.size:
        raise ValueError("File is smaller than ADB header size (48 bytes).")

    header_u32 = list(HEADER_STRUCT.unpack_from(data, 0))
    section0_size = header_u32[4]
    index_count = header_u32[5]
    section1_size = header_u32[6]

    index_bytes = index_count * 4
    body_size = section0_size + index_bytes + section1_size
    body_end = HEADER_STRUCT.size + body_size
    if body_end > len(data):
        raise ValueError("Section sizes declared in header exceed file length.")

    cursor = HEADER_STRUCT.size
    section0 = data[cursor : cursor + section0_size]
    cursor += section0_size

    if index_count:
        index_u32 = list(struct.unpack(f"<{index_count}I", data[cursor : cursor + index_bytes]))
    else:
        index_u32 = []
    cursor += index_bytes

    section1 = data[cursor : cursor + section1_size]
    tail = data[body_end:]

    return {
        "format": "NBDA",
        "mode": "raw",
        "magic_u32": header_u32[0],
        "magic_text": data[:4].decode("ascii", errors="replace"),
        "version_u32": header_u32[1],
        "header_u32": header_u32,
        "section0_size": section0_size,
        "index_count": index_count,
        "section1_size": section1_size,
        "section0_hex": to_hex(section0),
        "index_u32": index_u32,
        "section1_hex": to_hex(section1),
        "tail_hex": to_hex(tail),
        "total_size": len(data),
    }


def _decode_slot(chunk: bytes) -> dict:
    slot: dict = {
        "size_bytes": len(chunk),
        "editable_text": False,
    }
    if len(chunk) % 2 != 0:
        slot["bytes_u8"] = list(chunk)
        slot["mnemonic"] = "RAW_BYTES"
        return slot

    words = u16_words(chunk)
    slot["words"] = words
    if not words:
        slot["opcode"] = None
        slot["mnemonic"] = "EMPTY"
        return slot

    opcode = words[0]
    slot["opcode"] = opcode
    slot["opcode_hex"] = f"0x{opcode:04X}"
    slot["mnemonic"] = opcode_name(opcode)

    # 0x0601: [opcode][speaker][text_len][text_u16...][0][suffix_words...]
    if opcode == 0x0601 and len(words) >= 4:
        speaker = words[1]
        text_len = words[2]
        term_index = 3 + text_len
        if term_index < len(words) and words[term_index] == 0:
            text_units = words[3:term_index]
            text_raw = struct.pack(f"<{len(text_units)}H", *text_units) if text_units else b""
            try:
                text = text_raw.decode("utf-16le")
            except UnicodeDecodeError:
                return slot
            if text_quality(text) >= 0.2:
                slot["editable_text"] = True
                slot["speaker_u16"] = speaker
                slot["text_len_u16"] = text_len
                slot["text"] = text
                slot["suffix_words"] = words[term_index + 1 :]
    return slot


def parse_adb_ir(data: bytes) -> dict:
    raw_doc = parse_adb(data)
    section1 = from_hex(raw_doc["section1_hex"])
    index_u32 = list(raw_doc["index_u32"])

    unique_offsets = sorted(set(index_u32))
    slots: list[dict] = []
    offset_to_slot_id: dict[int, int] = {}
    for slot_id, off in enumerate(unique_offsets):
        if off < 0 or off > len(section1):
            raise ValueError(f"Index offset out of range: {off}")
        end = unique_offsets[slot_id + 1] if slot_id + 1 < len(unique_offsets) else len(section1)
        if end < off:
            raise ValueError(f"Invalid slot range at offset: {off}")
        slot = _decode_slot(section1[off:end])
        slot["slot_id"] = slot_id
        slot["original_offset"] = off
        slots.append(slot)
        offset_to_slot_id[off] = slot_id

    entries: list[dict] = []
    editable_entry_count = 0
    for i, off in enumerate(index_u32):
        slot_id = offset_to_slot_id[off]
        slot = slots[slot_id]
        if slot.get("editable_text", False):
            editable_entry_count += 1
        entries.append(
            {
                "index": i,
                "original_offset": off,
                "slot_id": slot_id,
                "opcode": slot.get("opcode"),
                "mnemonic": slot.get("mnemonic"),
                "editable_text": bool(slot.get("editable_text", False)),
            }
        )

    return {
        "format": "NBDA",
        "mode": "ir",
        "magic_u32": raw_doc["magic_u32"],
        "version_u32": raw_doc["version_u32"],
        "header_u32": raw_doc["header_u32"],
        "section0_hex": raw_doc["section0_hex"],
        "index_u32": index_u32,
        "tail_hex": raw_doc["tail_hex"],
        "slot_count": len(slots),
        "entry_count": len(entries),
        "editable_entry_count": editable_entry_count,
        "slots": slots,
        "entries": entries,
    }


def validate_magic(doc: dict) -> None:
    if doc.get("magic_u32") != ADB_MAGIC_U32:
        raise ValueError(
            f"Magic mismatch: 0x{int(doc.get('magic_u32', 0)):08X}, expected 0x{ADB_MAGIC_U32:08X}."
        )


def parse_adb_editable(data: bytes) -> dict:
    return parse_adb_ir(data)
