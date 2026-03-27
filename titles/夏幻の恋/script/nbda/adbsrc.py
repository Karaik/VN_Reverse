from __future__ import annotations

import json
import re


def _parse_int(token: str) -> int:
    text = token.strip()
    if text.lower().startswith("0x"):
        return int(text, 16)
    return int(text, 10)


def _parse_u16_list(text: str) -> list[int]:
    body = text.strip()
    if not body.startswith("[") or not body.endswith("]"):
        raise ValueError(f"Invalid u16 list: {text}")
    inner = body[1:-1].strip()
    if not inner:
        return []
    out: list[int] = []
    for item in inner.split(","):
        out.append(_parse_int(item) & 0xFFFF)
    return out


def _parse_u8_list(text: str) -> list[int]:
    body = text.strip()
    if not body.startswith("[") or not body.endswith("]"):
        raise ValueError(f"Invalid u8 list: {text}")
    inner = body[1:-1].strip()
    if not inner:
        return []
    out: list[int] = []
    for item in inner.split(","):
        out.append(_parse_int(item) & 0xFF)
    return out


def _fmt_u16_list(values: list[int]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(f"0x{int(v) & 0xFFFF:04X}" for v in values) + "]"


def _fmt_u8_list(values: list[int]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(f"0x{int(v) & 0xFF:02X}" for v in values) + "]"


def render_ir_adbsrc(doc: dict) -> str:
    if doc.get("mode") != "ir":
        raise ValueError("ADBSRC renderer requires IR JSON (mode=ir).")

    header_u32 = [int(x) & 0xFFFFFFFF for x in list(doc.get("header_u32", []))]
    if len(header_u32) != 12:
        raise ValueError("IR document header_u32 must contain exactly 12 uint32 values.")

    slots = list(doc.get("slots", []))
    entries = list(doc.get("entries", []))
    editable_entry_count = sum(1 for item in entries if item.get("editable_text"))

    lines: list[str] = []
    lines.append("; ADBSRC v1")
    lines.append("version 1")
    lines.append(f"format {doc.get('format', 'NBDA')}")
    lines.append("mode ir")
    lines.append(f"magic_u32 0x{int(doc.get('magic_u32', 0)) & 0xFFFFFFFF:08X}")
    lines.append(f"version_u32 0x{int(doc.get('version_u32', 0)) & 0xFFFFFFFF:08X}")
    lines.append("header_u32 " + " ".join(f"0x{value:08X}" for value in header_u32))
    lines.append(f"section0_hex {str(doc.get('section0_hex', ''))}")
    lines.append(f"tail_hex {str(doc.get('tail_hex', ''))}")
    lines.append(f"slot_count {len(slots)}")
    lines.append(f"entry_count {len(entries)}")
    lines.append(f"editable_entry_count {editable_entry_count}")
    lines.append("")
    lines.append("[slots]")

    for slot in slots:
        slot_id = int(slot.get("slot_id", -1))
        off = int(slot.get("original_offset", 0))

        if "bytes_u8" in slot:
            raw = [int(v) & 0xFF for v in list(slot.get("bytes_u8", []))]
            lines.append(f"slot {slot_id:05d} off=0x{off:08X} bytes={_fmt_u8_list(raw)}")
            continue

        opcode = slot.get("opcode")
        if opcode is None:
            raise ValueError(f"IR slot missing opcode/bytes_u8: slot_id={slot_id}")
        opcode = int(opcode) & 0xFFFF
        mnemonic = str(slot.get("mnemonic", f"OP_{opcode:04X}"))

        if opcode == 0x0601 and slot.get("editable_text", False):
            words = [int(v) & 0xFFFF for v in list(slot.get("words", []))]
            default_speaker = words[1] if len(words) > 1 else 0
            speaker = int(slot.get("speaker_u16", default_speaker)) & 0xFFFF
            text = str(slot.get("text", ""))
            suffix = [int(v) & 0xFFFF for v in list(slot.get("suffix_words", []))]
            lines.append(
                f"slot {slot_id:05d} off=0x{off:08X} op=0x0601 mnemonic={mnemonic} "
                f"speaker=0x{speaker:04X} text={json.dumps(text, ensure_ascii=False)} "
                f"suffix={_fmt_u16_list(suffix)}"
            )
            continue

        if opcode == 0x0600 and slot.get("editable_text", False) and slot.get("text_role") == "speaker_name":
            speaker_name = str(slot.get("speaker_name", slot.get("text", "")))
            lines.append(
                f"slot {slot_id:05d} off=0x{off:08X} op=0x0600 mnemonic={mnemonic} "
                f"speaker_name={json.dumps(speaker_name, ensure_ascii=False)}"
            )
            continue

        words = [int(v) & 0xFFFF for v in list(slot.get("words", []))]
        if not words:
            words = [opcode]
        lines.append(
            f"slot {slot_id:05d} off=0x{off:08X} op=0x{opcode:04X} mnemonic={mnemonic} "
            f"words={_fmt_u16_list(words)}"
        )

    lines.append("[entries]")
    for entry in entries:
        idx = int(entry.get("index", -1))
        off = int(entry.get("original_offset", 0))
        slot_id = int(entry.get("slot_id", -1))
        editable = 1 if entry.get("editable_text", False) else 0
        opcode = entry.get("opcode")
        op_text = "----" if opcode is None else f"0x{int(opcode) & 0xFFFF:04X}"
        mnemonic = str(entry.get("mnemonic", "RAW_BYTES" if opcode is None else "UNKNOWN"))
        line = (
            f"entry {idx:05d} off=0x{off:08X} slot={slot_id:05d} op={op_text} "
            f"mnemonic={mnemonic} editable={editable}"
        )
        if "speaker_name_slot_id" in entry:
            line += f" speaker_name_slot={int(entry['speaker_name_slot_id']):05d}"
        lines.append(line)

    return "\n".join(lines) + "\n"


_SLOT_BYTES_RE = re.compile(r"^slot\s+(\d+)\s+off=(\S+)\s+bytes=(\[[^\]]*\])$")
_SLOT_WORDS_RE = re.compile(
    r"^slot\s+(\d+)\s+off=(\S+)\s+op=(\S+)\s+mnemonic=([^\s]+)\s+words=(\[[^\]]*\])$"
)
_SLOT_SPEAKER_RE = re.compile(
    r"^slot\s+(\d+)\s+off=(\S+)\s+op=(\S+)\s+mnemonic=([^\s]+)\s+speaker_name=(.+)$"
)
_SLOT_TEXT_RE = re.compile(
    r"^slot\s+(\d+)\s+off=(\S+)\s+op=(\S+)\s+mnemonic=([^\s]+)\s+speaker=(\S+)\s+text=(.+)\s+suffix=(\[[^\]]*\])$"
)
_ENTRY_RE = re.compile(
    r"^entry\s+(\d+)\s+off=(\S+)\s+slot=(\d+)\s+op=([^\s]+)\s+mnemonic=([^\s]+)\s+editable=(\d+)(?:\s+speaker_name_slot=(\d+))?$"
)


def parse_adbsrc(text: str) -> dict:
    meta: dict[str, object] = {}
    slots: list[dict] = []
    entries: list[dict] = []
    section = "meta"

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue
        if line == "[slots]":
            section = "slots"
            continue
        if line == "[entries]":
            section = "entries"
            continue

        if section == "meta":
            if " " in line:
                key, value = line.split(" ", 1)
                value = value.strip()
            else:
                key = line
                value = ""
            if key == "version":
                if value == "":
                    raise ValueError(f"Invalid meta line: {line}")
                meta["version"] = _parse_int(value)
            elif key == "format":
                if value == "":
                    raise ValueError(f"Invalid meta line: {line}")
                meta["format"] = value
            elif key == "mode":
                if value == "":
                    raise ValueError(f"Invalid meta line: {line}")
                meta["mode"] = value
            elif key == "magic_u32":
                if value == "":
                    raise ValueError(f"Invalid meta line: {line}")
                meta["magic_u32"] = _parse_int(value) & 0xFFFFFFFF
            elif key == "version_u32":
                if value == "":
                    raise ValueError(f"Invalid meta line: {line}")
                meta["version_u32"] = _parse_int(value) & 0xFFFFFFFF
            elif key == "header_u32":
                if value == "":
                    raise ValueError(f"Invalid meta line: {line}")
                parts = value.split()
                header = [(_parse_int(item) & 0xFFFFFFFF) for item in parts]
                meta["header_u32"] = header
            elif key == "section0_hex":
                meta["section0_hex"] = value
            elif key == "tail_hex":
                meta["tail_hex"] = value
            elif key in {"slot_count", "entry_count", "editable_entry_count"}:
                if value == "":
                    raise ValueError(f"Invalid meta line: {line}")
                meta[key] = _parse_int(value)
            else:
                raise ValueError(f"Unknown meta key: {key}")
            continue

        if section == "slots":
            m = _SLOT_BYTES_RE.match(line)
            if m:
                slot_id = int(m.group(1))
                off = _parse_int(m.group(2))
                raw = _parse_u8_list(m.group(3))
                slots.append(
                    {
                        "slot_id": slot_id,
                        "original_offset": off,
                        "editable_text": False,
                        "mnemonic": "RAW_BYTES",
                        "bytes_u8": raw,
                    }
                )
                continue

            m = _SLOT_WORDS_RE.match(line)
            if m:
                slot_id = int(m.group(1))
                off = _parse_int(m.group(2))
                opcode = _parse_int(m.group(3)) & 0xFFFF
                mnemonic = m.group(4)
                words = _parse_u16_list(m.group(5))
                slots.append(
                    {
                        "slot_id": slot_id,
                        "original_offset": off,
                        "editable_text": False,
                        "opcode": opcode,
                        "opcode_hex": f"0x{opcode:04X}",
                        "mnemonic": mnemonic,
                        "words": words,
                    }
                )
                continue

            m = _SLOT_SPEAKER_RE.match(line)
            if m:
                slot_id = int(m.group(1))
                off = _parse_int(m.group(2))
                opcode = _parse_int(m.group(3)) & 0xFFFF
                if opcode != 0x0600:
                    raise ValueError(f"Speaker-name slot opcode must be 0x0600, got 0x{opcode:04X}")
                mnemonic = m.group(4)
                speaker_name_value = json.loads(m.group(5))
                if not isinstance(speaker_name_value, str):
                    raise ValueError("speaker_name field in slot is not a JSON string.")
                slots.append(
                    {
                        "slot_id": slot_id,
                        "original_offset": off,
                        "editable_text": True,
                        "text_role": "speaker_name",
                        "opcode": 0x0600,
                        "opcode_hex": "0x0600",
                        "mnemonic": mnemonic,
                        "speaker_name": speaker_name_value,
                        "text": speaker_name_value,
                    }
                )
                continue

            m = _SLOT_TEXT_RE.match(line)
            if m:
                slot_id = int(m.group(1))
                off = _parse_int(m.group(2))
                opcode = _parse_int(m.group(3)) & 0xFFFF
                if opcode != 0x0601:
                    raise ValueError(f"Text slot opcode must be 0x0601, got 0x{opcode:04X}")
                mnemonic = m.group(4)
                speaker = _parse_int(m.group(5)) & 0xFFFF
                text_json = m.group(6)
                suffix = _parse_u16_list(m.group(7))
                text_value = json.loads(text_json)
                if not isinstance(text_value, str):
                    raise ValueError("Text field in slot is not a JSON string.")
                slots.append(
                    {
                        "slot_id": slot_id,
                        "original_offset": off,
                        "editable_text": True,
                        "text_role": "dialogue",
                        "opcode": 0x0601,
                        "opcode_hex": "0x0601",
                        "mnemonic": mnemonic,
                        "speaker_u16": speaker,
                        "text": text_value,
                        "suffix_words": suffix,
                    }
                )
                continue

            raise ValueError(f"Invalid slot line: {line}")

        if section == "entries":
            m = _ENTRY_RE.match(line)
            if not m:
                raise ValueError(f"Invalid entry line: {line}")
            idx = int(m.group(1))
            off = _parse_int(m.group(2))
            slot_id = int(m.group(3))
            op_text = m.group(4)
            opcode = None if op_text == "----" else (_parse_int(op_text) & 0xFFFF)
            mnemonic = m.group(5)
            editable = bool(int(m.group(6)))
            speaker_name_slot_id = m.group(7)
            entries.append(
                {
                    "index": idx,
                    "original_offset": off,
                    "slot_id": slot_id,
                    "opcode": opcode,
                    "mnemonic": mnemonic,
                    "editable_text": editable,
                    **({"speaker_name_slot_id": int(speaker_name_slot_id)} if speaker_name_slot_id is not None else {}),
                }
            )
            continue

        raise ValueError(f"Unknown parse section: {section}")

    header_u32 = list(meta.get("header_u32", []))
    if len(header_u32) != 12:
        raise ValueError("ADBSRC header_u32 must contain exactly 12 uint32 values.")

    mode = str(meta.get("mode", "ir"))
    if mode != "ir":
        raise ValueError(f"Unsupported ADBSRC mode: {mode}")

    magic_u32 = int(meta.get("magic_u32", header_u32[0])) & 0xFFFFFFFF
    version_u32 = int(meta.get("version_u32", header_u32[1])) & 0xFFFFFFFF
    section0_hex = str(meta.get("section0_hex", ""))
    tail_hex = str(meta.get("tail_hex", ""))

    editable_entry_count = sum(1 for item in entries if item.get("editable_text"))
    slot_by_id = {int(slot["slot_id"]): slot for slot in slots}
    pending_speaker_name_slot_id: int | None = None
    for entry in entries:
        slot = slot_by_id[int(entry["slot_id"])]
        text_role = slot.get("text_role")
        if text_role == "speaker_name":
            pending_speaker_name_slot_id = int(slot["slot_id"])
            continue
        if text_role == "dialogue":
            linked_slot_id = entry.get("speaker_name_slot_id")
            if linked_slot_id is None and pending_speaker_name_slot_id is not None:
                linked_slot_id = pending_speaker_name_slot_id
            if linked_slot_id is not None and int(linked_slot_id) in slot_by_id:
                linked_slot_id = int(linked_slot_id)
                speaker_slot = slot_by_id[linked_slot_id]
                speaker_name = str(speaker_slot.get("speaker_name", ""))
                entry["speaker_name_slot_id"] = linked_slot_id
                entry["speaker_name"] = speaker_name
                slot["speaker_name_slot_id"] = linked_slot_id
                slot["speaker_name"] = speaker_name
            pending_speaker_name_slot_id = None
    return {
        "format": str(meta.get("format", "NBDA")),
        "mode": "ir",
        "magic_u32": magic_u32,
        "version_u32": version_u32,
        "header_u32": header_u32,
        "section0_hex": section0_hex,
        "tail_hex": tail_hex,
        "slot_count": len(slots),
        "entry_count": len(entries),
        "editable_entry_count": editable_entry_count,
        "slots": slots,
        "entries": entries,
    }
