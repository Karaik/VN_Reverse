from __future__ import annotations

import codecs
import json
import re
import struct

RECORD_SIZE = 144
STR1_OFF = 1
STR1_SIZE = 64
STR2_OFF = 65
STR2_SIZE = 65
TAIL_OFF = 130
TAIL_SIZE = 14

CP932 = "cp932"
DEFAULT_TEXT_ENCODING = CP932
TEXT_ENCODING_ALIASES = {
    "win-31j": CP932,
    "windows-31j": CP932,
    "shift-jis": CP932,
    "shift_jis": CP932,
    "sjis": CP932,
    "ms932": CP932,
}

OPCODE_NAMES = {
    -128: "BG_BACK_SET",
    -127: "BG_FRONT_SET",
    -126: "TRANSITION",
    -125: "TRANSITION_CLEAR",
    -121: "EFFECT",
    -116: "PAN_BG",
    -115: "PAN_CHAR",
    -110: "SLIDE",
    -108: "JUMP_LABEL_IF_READY",
    -106: "MODE_SET",
    -105: "MODE_WAIT",
    -104: "MODE_POLL",
    -103: "MODE_EXIT",
    -101: "SOUND_PLAY_SE",
    -100: "SOUND_PLAY",
    -99: "SOUND_PLAY_FORCE_SE",
    -98: "SOUND_CTRL",
    -97: "SOUND_WAIT",
    -96: "JUMP_LABEL",
    -91: "IF_GOTO",
    -86: "VAR_SET",
    -84: "VAR_ADD",
    -83: "VAR_SUB",
    -76: "STATE_SET",
    -56: "END",
    -51: "CHOICE_DEF",
    -50: "CHOICE_MENU",
    -49: "CHOICE_MENU_DEFAULT",
    -46: "CALL_BIN",
    -4: "RETURN",
    100: "TEXT_LINE",
    105: "LOG_PUSH",
    106: "TITLE_SET",
    107: "SUBTITLE_SET",
    110: "WAIT_INPUT",
    111: "WAIT_END",
    112: "WAIT_INPUT_NOAUTO",
    116: "WAIT_TIMER",
    118: "FADE_STEP",
    119: "SCENE_END",
    120: "BG_LOAD",
    122: "CHAR_LOAD",
    124: "CHAR_CLEAR",
    126: "EVENT_LOAD",
}


def normalize_text_encoding(text_encoding: str) -> str:
    key = str(text_encoding).strip().lower()
    if not key:
        key = DEFAULT_TEXT_ENCODING
    normalized = TEXT_ENCODING_ALIASES.get(key, key)
    try:
        codecs.lookup(normalized)
    except LookupError as exc:
        raise ValueError(f"Unsupported text encoding: {text_encoding}") from exc
    return normalized


def _has_jp(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if 0x3040 <= code <= 0x30FF:
            return True
        if 0x4E00 <= code <= 0x9FFF:
            return True
    return False


def _decode_field(raw: bytes, text_encoding: str) -> tuple[bool, str]:
    end = raw.find(0)
    if end < 0:
        end = len(raw)
    payload = raw[:end]
    try:
        text = payload.decode(text_encoding)
    except UnicodeDecodeError:
        return False, ""
    return True, text


def _matches_fallback_filter(text: str, fallback_filters: list[str] | None) -> bool:
    if not fallback_filters:
        return False
    for marker in fallback_filters:
        if marker and marker in text:
            return True
    return False


def _pack_text_field(
    cmd: dict,
    key_prefix: str,
    field_size: int,
    target_encoding: str,
    source_encoding: str,
    fallback_filters: list[str] | None,
) -> bytes:
    raw_key = f"{key_prefix}_raw_hex"
    decoded_key = f"{key_prefix}_decoded"
    text_key = f"{key_prefix}_text"
    original_text_key = f"{key_prefix}_original_text"

    decoded = bool(cmd.get(decoded_key, False))
    current_text = str(cmd.get(text_key, ""))
    original_text = str(cmd.get(original_text_key, current_text))
    if raw_key in cmd and decoded and current_text == original_text:
        raw = bytes.fromhex(str(cmd[raw_key]))
        if len(raw) != field_size:
            raise ValueError(f"{key_prefix} raw size mismatch: expected {field_size}, got {len(raw)}")
        return raw
    if raw_key in cmd and not decoded:
        raw = bytes.fromhex(str(cmd[raw_key]))
        if len(raw) != field_size:
            raise ValueError(f"{key_prefix} raw size mismatch: expected {field_size}, got {len(raw)}")
        return raw
    if not decoded:
        raw = bytes.fromhex(str(cmd.get(raw_key, "")))
        if len(raw) != field_size:
            raise ValueError(f"{key_prefix} is not decoded and has no valid raw bytes.")
        return raw

    write_encoding = source_encoding if _matches_fallback_filter(current_text, fallback_filters) else target_encoding
    payload = current_text.encode(write_encoding)
    if len(payload) + 1 > field_size:
        raise ValueError(
            f"{key_prefix} is too long for fixed field ({field_size} bytes): {len(payload)} bytes encoded."
        )
    return payload + b"\x00" + (b"\x00" * (field_size - len(payload) - 1))


def parse_script_bin(data: bytes, text_encoding: str = DEFAULT_TEXT_ENCODING) -> dict:
    text_encoding = normalize_text_encoding(text_encoding)
    if len(data) % RECORD_SIZE != 0:
        raise ValueError(f"Script size is not a multiple of {RECORD_SIZE}: {len(data)}")
    commands: list[dict] = []
    record_count = len(data) // RECORD_SIZE
    for i in range(record_count):
        rec = data[i * RECORD_SIZE : (i + 1) * RECORD_SIZE]
        opcode_s8 = struct.unpack_from("<b", rec, 0)[0]
        str1_raw = rec[STR1_OFF : STR1_OFF + STR1_SIZE]
        str2_raw = rec[STR2_OFF : STR2_OFF + STR2_SIZE]
        tail = rec[TAIL_OFF : TAIL_OFF + TAIL_SIZE]
        str1_decoded, str1_text = _decode_field(str1_raw, text_encoding)
        str2_decoded, str2_text = _decode_field(str2_raw, text_encoding)

        arg0_u16, arg1_u16, arg2_u16 = struct.unpack_from("<3H", tail, 0)
        commands.append(
            {
                "index": i,
                "opcode_s8": opcode_s8,
                "mnemonic": OPCODE_NAMES.get(opcode_s8, f"OP_{opcode_s8 & 0xFF:02X}"),
                "arg0_u16": int(arg0_u16),
                "arg1_u16": int(arg1_u16),
                "arg2_u16": int(arg2_u16),
                "str1_raw_hex": str1_raw.hex(),
                "str1_decoded": str1_decoded,
                "str1_text": str1_text if str1_decoded else "",
                "str1_original_text": str1_text if str1_decoded else "",
                "str1_editable": bool(str1_decoded and _has_jp(str1_text)),
                "str2_raw_hex": str2_raw.hex(),
                "str2_decoded": str2_decoded,
                "str2_text": str2_text if str2_decoded else "",
                "str2_original_text": str2_text if str2_decoded else "",
                "str2_editable": bool(str2_decoded and _has_jp(str2_text)),
                "tail_hex": tail.hex(),
            }
        )
    return {
        "format": "NEJII_SCRIPT_BIN",
        "mode": "ir",
        "record_size_u32": RECORD_SIZE,
        "record_count_u32": record_count,
        "text_encoding": text_encoding,
        "commands": commands,
    }


def compile_script_bin(
    doc: dict,
    text_encoding: str | None = None,
    source_text_encoding: str | None = None,
    fallback_filters: list[str] | None = None,
) -> bytes:
    if doc.get("format") != "NEJII_SCRIPT_BIN":
        raise ValueError("Document format is not NEJII_SCRIPT_BIN.")
    if int(doc.get("record_size_u32", RECORD_SIZE)) != RECORD_SIZE:
        raise ValueError("Unexpected record_size_u32.")

    if text_encoding is None:
        text_encoding = str(doc.get("text_encoding", DEFAULT_TEXT_ENCODING))
    target_encoding = normalize_text_encoding(text_encoding)
    if source_text_encoding is None:
        source_text_encoding = str(doc.get("text_encoding", DEFAULT_TEXT_ENCODING))
    source_encoding = normalize_text_encoding(source_text_encoding)

    commands = sorted(list(doc.get("commands", [])), key=lambda x: int(x["index"]))
    out = bytearray()
    for cmd in commands:
        rec = bytearray(RECORD_SIZE)
        opcode_s8 = int(cmd["opcode_s8"])
        rec[0] = opcode_s8 & 0xFF
        rec[STR1_OFF : STR1_OFF + STR1_SIZE] = _pack_text_field(
            cmd=cmd,
            key_prefix="str1",
            field_size=STR1_SIZE,
            target_encoding=target_encoding,
            source_encoding=source_encoding,
            fallback_filters=fallback_filters,
        )
        rec[STR2_OFF : STR2_OFF + STR2_SIZE] = _pack_text_field(
            cmd=cmd,
            key_prefix="str2",
            field_size=STR2_SIZE,
            target_encoding=target_encoding,
            source_encoding=source_encoding,
            fallback_filters=fallback_filters,
        )

        tail_hex = str(cmd.get("tail_hex", ""))
        tail = bytearray(bytes.fromhex(tail_hex)) if tail_hex else bytearray(TAIL_SIZE)
        if len(tail) != TAIL_SIZE:
            raise ValueError(f"Invalid tail size in command {cmd.get('index')}: {len(tail)}")
        struct.pack_into("<H", tail, 0, int(cmd.get("arg0_u16", 0)) & 0xFFFF)
        struct.pack_into("<H", tail, 2, int(cmd.get("arg1_u16", 0)) & 0xFFFF)
        struct.pack_into("<H", tail, 4, int(cmd.get("arg2_u16", 0)) & 0xFFFF)
        rec[TAIL_OFF : TAIL_OFF + TAIL_SIZE] = tail
        out.extend(rec)
    return bytes(out)


def render_nejsrc(doc: dict) -> str:
    if doc.get("format") != "NEJII_SCRIPT_BIN":
        raise ValueError("NEJSRC renderer requires NEJII_SCRIPT_BIN document.")
    meta = {
        "format": "NEJII_SCRIPT_BIN",
        "record_size_u32": int(doc.get("record_size_u32", RECORD_SIZE)),
        "record_count_u32": int(doc.get("record_count_u32", 0)),
        "text_encoding": str(doc.get("text_encoding", DEFAULT_TEXT_ENCODING)),
    }
    lines = ["; NEJSRC v1", "@meta " + json.dumps(meta, ensure_ascii=False, separators=(",", ":"))]
    for cmd in list(doc.get("commands", [])):
        lines.append("@cmd " + json.dumps(cmd, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines) + "\n"


def parse_nejsrc(text: str) -> dict:
    meta: dict | None = None
    commands: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("@meta "):
            meta = json.loads(line[6:])
            continue
        if line.startswith("@cmd "):
            commands.append(json.loads(line[5:]))
            continue
        raise ValueError(f"Invalid NEJSRC line: {line}")
    if meta is None:
        raise ValueError("NEJSRC is missing @meta.")
    if meta.get("format") != "NEJII_SCRIPT_BIN":
        raise ValueError("NEJSRC meta format is not NEJII_SCRIPT_BIN.")
    return {
        "format": "NEJII_SCRIPT_BIN",
        "mode": "ir",
        "record_size_u32": int(meta.get("record_size_u32", RECORD_SIZE)),
        "record_count_u32": int(meta.get("record_count_u32", len(commands))),
        "text_encoding": normalize_text_encoding(str(meta.get("text_encoding", DEFAULT_TEXT_ENCODING))),
        "commands": commands,
    }


_NEJSRC_RE = re.compile(r"\.nejsrc$", re.IGNORECASE)


def is_nejsrc_path(path: str) -> bool:
    return _NEJSRC_RE.search(path) is not None
