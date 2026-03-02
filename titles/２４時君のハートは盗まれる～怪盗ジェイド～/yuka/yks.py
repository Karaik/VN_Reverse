from __future__ import annotations

import codecs
import json
import re
import struct

YKS_HEADER_STRUCT = struct.Struct("<8s8I")
YKS_ENTRY_STRUCT = struct.Struct("<4I")
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


def _has_cjk(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if 0x3040 <= code <= 0x30FF:
            return True
        if 0x4E00 <= code <= 0x9FFF:
            return True
    return False


def _tokenize_blob(blob: bytes) -> list[tuple[int, bytes, int]]:
    tokens: list[tuple[int, bytes, int]] = []
    pos = 0
    n = len(blob)
    while pos < n:
        end = blob.find(b"\x00", pos)
        if end < 0:
            tokens.append((pos, blob[pos:], 0))
            break
        raw = blob[pos:end]
        z = end
        while z < n and blob[z] == 0:
            z += 1
        term_zeros = z - end
        tokens.append((pos, raw, term_zeros))
        pos = z
    return tokens


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


def _decode_blob_token(raw: bytes, text_encoding: str) -> tuple[bool, str]:
    try:
        text = raw.decode(text_encoding)
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


def parse_yks(data: bytes, text_encoding: str = DEFAULT_TEXT_ENCODING) -> dict:
    text_encoding = normalize_text_encoding(text_encoding)
    if len(data) < YKS_HEADER_STRUCT.size:
        raise ValueError("File is smaller than YKS header.")
    magic8, header_size, reserved_u32, table1_off, table1_count, entry_off, entry_count, blob_off, blob_size = (
        YKS_HEADER_STRUCT.unpack_from(data, 0)
    )
    if header_size < YKS_HEADER_STRUCT.size:
        raise ValueError(f"Invalid YKS header_size: {header_size}")

    table1_end = table1_off + table1_count * 4
    entry_end = entry_off + entry_count * YKS_ENTRY_STRUCT.size
    blob_end = blob_off + blob_size
    if table1_end > len(data):
        raise ValueError("table1 exceeds file size.")
    if entry_end > len(data):
        raise ValueError("entry table exceeds file size.")
    if blob_end > len(data):
        raise ValueError("blob exceeds file size.")

    table1 = list(struct.unpack_from(f"<{table1_count}I", data, table1_off)) if table1_count else []
    entries = [YKS_ENTRY_STRUCT.unpack_from(data, entry_off + i * YKS_ENTRY_STRUCT.size) for i in range(entry_count)]
    blob_raw = bytearray(data[blob_off:blob_end])
    xor_blob = (struct.unpack_from("<H", data, 6)[0] == 1)
    if xor_blob:
        for i in range(len(blob_raw)):
            blob_raw[i] ^= 0xAA

    token_pairs = _tokenize_blob(bytes(blob_raw))
    off_to_token: dict[int, int] = {}
    tokens: list[dict] = []
    for token_id, (off, raw, term_zeros) in enumerate(token_pairs):
        off_to_token[off] = token_id
        decoded, text = _decode_blob_token(raw, text_encoding)
        tokens.append(
            {
                "token_id": token_id,
                "original_offset_u32": off,
                "raw_hex": raw.hex(),
                "term_zeros_u32": term_zeros,
                "decoded_text": decoded,
                "decoded_cp932": decoded,
                "text": text if decoded else "",
                "original_text": text if decoded else "",
                "editable_text": bool(decoded and _has_cjk(text)),
            }
        )

    out_entries: list[dict] = []
    for i, row in enumerate(entries):
        t, a, b, c = [int(v) for v in row]
        item = {
            "entry_id": i,
            "type_u32": t,
            "a_u32": a,
            "b_u32": b,
            "c_u32": c,
        }
        if a in off_to_token:
            item["a_token_id"] = off_to_token[a]
        if b in off_to_token:
            item["b_token_id"] = off_to_token[b]
        out_entries.append(item)

    flow = [{"index": i, "entry_id": int(v)} for i, v in enumerate(table1)]
    return {
        "format": "YKS",
        "mode": "ir",
        "text_encoding": text_encoding,
        "magic8_hex": magic8.hex(),
        "header_size_u32": int(header_size),
        "reserved_u32": int(reserved_u32),
        "xor_blob": xor_blob,
        "table1_count": len(table1),
        "entry_count": len(out_entries),
        "token_count": len(tokens),
        "tokens": tokens,
        "entries": out_entries,
        "flow": flow,
    }


def compile_yks(
    doc: dict,
    text_encoding: str | None = None,
    source_text_encoding: str | None = None,
    fallback_filters: list[str] | None = None,
) -> bytes:
    if doc.get("format") != "YKS":
        raise ValueError("Document format is not YKS.")
    if text_encoding is None:
        text_encoding = str(doc.get("text_encoding", DEFAULT_TEXT_ENCODING))
    target_text_encoding = normalize_text_encoding(text_encoding)
    if source_text_encoding is None:
        source_text_encoding = str(doc.get("text_encoding", DEFAULT_TEXT_ENCODING))
    source_text_encoding = normalize_text_encoding(source_text_encoding)

    magic8 = bytes.fromhex(str(doc.get("magic8_hex", "")))
    if len(magic8) != 8:
        raise ValueError("Invalid magic8_hex.")
    header_size = int(doc.get("header_size_u32", YKS_HEADER_STRUCT.size))
    reserved_u32 = int(doc.get("reserved_u32", 0))
    if header_size < YKS_HEADER_STRUCT.size:
        raise ValueError(f"Invalid header_size_u32: {header_size}")

    tokens = sorted(list(doc.get("tokens", [])), key=lambda x: int(x["token_id"]))
    token_offset_map: dict[int, int] = {}
    blob = bytearray()
    for token in tokens:
        token_id = int(token["token_id"])
        token_offset_map[token_id] = len(blob)
        decoded = bool(token.get("decoded_text", token.get("decoded_cp932", False)))
        if "raw_hex" in token and decoded:
            original_text = str(token.get("original_text", token.get("text", "")))
            current_text = str(token.get("text", ""))
            if current_text == original_text:
                raw = bytes.fromhex(str(token.get("raw_hex", "")))
            else:
                if _matches_fallback_filter(current_text, fallback_filters):
                    raw = current_text.encode(source_text_encoding)
                else:
                    raw = current_text.encode(target_text_encoding)
        elif decoded:
            current_text = str(token.get("text", ""))
            if _matches_fallback_filter(current_text, fallback_filters):
                raw = current_text.encode(source_text_encoding)
            else:
                raw = current_text.encode(target_text_encoding)
        else:
            raw = bytes.fromhex(str(token.get("raw_hex", "")))
        term_zeros = int(token.get("term_zeros_u32", 1))
        if term_zeros < 0:
            raise ValueError(f"Invalid term_zeros_u32 in token {token_id}: {term_zeros}")
        blob.extend(raw)
        if term_zeros:
            blob.extend(b"\x00" * term_zeros)

    entries_doc = sorted(list(doc.get("entries", [])), key=lambda x: int(x["entry_id"]))
    entry_rows: list[tuple[int, int, int, int]] = []
    for e in entries_doc:
        t = int(e.get("type_u32", 0)) & 0xFFFFFFFF
        a = int(e.get("a_u32", 0)) & 0xFFFFFFFF
        b = int(e.get("b_u32", 0)) & 0xFFFFFFFF
        c = int(e.get("c_u32", 0)) & 0xFFFFFFFF
        if "a_token_id" in e:
            token_id = int(e["a_token_id"])
            if token_id not in token_offset_map:
                raise ValueError(f"a_token_id out of range: {token_id}")
            a = token_offset_map[token_id]
        if "b_token_id" in e:
            token_id = int(e["b_token_id"])
            if token_id not in token_offset_map:
                raise ValueError(f"b_token_id out of range: {token_id}")
            b = token_offset_map[token_id]
        entry_rows.append((t, a, b, c))

    flow_doc = sorted(list(doc.get("flow", [])), key=lambda x: int(x["index"]))
    table1 = [int(item["entry_id"]) & 0xFFFFFFFF for item in flow_doc]

    table1_off = header_size
    table1_blob = struct.pack(f"<{len(table1)}I", *table1) if table1 else b""
    entry_off = table1_off + len(table1_blob)
    entry_blob = b"".join(YKS_ENTRY_STRUCT.pack(*row) for row in entry_rows)
    blob_off = entry_off + len(entry_blob)
    blob_out = bytearray(blob)
    if bool(doc.get("xor_blob", False)):
        for i in range(len(blob_out)):
            blob_out[i] ^= 0xAA

    header_blob = YKS_HEADER_STRUCT.pack(
        magic8,
        header_size,
        reserved_u32,
        table1_off,
        len(table1),
        entry_off,
        len(entry_rows),
        blob_off,
        len(blob),
    )
    if header_size == YKS_HEADER_STRUCT.size:
        padding = b""
    else:
        padding = b"\x00" * (header_size - YKS_HEADER_STRUCT.size)

    return header_blob + padding + table1_blob + entry_blob + bytes(blob_out)


def render_ykssrc(doc: dict) -> str:
    if doc.get("format") != "YKS":
        raise ValueError("YKSRC renderer requires YKS document.")
    lines: list[str] = []
    meta = {
        "format": "YKS",
        "text_encoding": str(doc.get("text_encoding", DEFAULT_TEXT_ENCODING)),
        "magic8_hex": doc.get("magic8_hex"),
        "header_size_u32": doc.get("header_size_u32"),
        "reserved_u32": doc.get("reserved_u32"),
        "xor_blob": bool(doc.get("xor_blob", False)),
    }
    lines.append("; YKSRC v1")
    lines.append("@meta " + json.dumps(meta, ensure_ascii=False, separators=(",", ":")))
    for token in list(doc.get("tokens", [])):
        lines.append("@token " + json.dumps(token, ensure_ascii=False, separators=(",", ":")))
    for entry in list(doc.get("entries", [])):
        lines.append("@entry " + json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
    for flow in list(doc.get("flow", [])):
        lines.append("@flow " + json.dumps(flow, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines) + "\n"


def parse_ykssrc(text: str) -> dict:
    meta: dict | None = None
    tokens: list[dict] = []
    entries: list[dict] = []
    flow: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("@meta "):
            meta = json.loads(line[6:])
            continue
        if line.startswith("@token "):
            tokens.append(json.loads(line[7:]))
            continue
        if line.startswith("@entry "):
            entries.append(json.loads(line[7:]))
            continue
        if line.startswith("@flow "):
            flow.append(json.loads(line[6:]))
            continue
        raise ValueError(f"Invalid YKSRC line: {line}")
    if meta is None:
        raise ValueError("YKSRC is missing @meta.")
    if meta.get("format") != "YKS":
        raise ValueError("YKSRC meta format is not YKS.")
    return {
        "format": "YKS",
        "mode": "ir",
        "text_encoding": normalize_text_encoding(str(meta.get("text_encoding", DEFAULT_TEXT_ENCODING))),
        "magic8_hex": str(meta.get("magic8_hex", "")),
        "header_size_u32": int(meta.get("header_size_u32", YKS_HEADER_STRUCT.size)),
        "reserved_u32": int(meta.get("reserved_u32", 0)),
        "xor_blob": bool(meta.get("xor_blob", False)),
        "token_count": len(tokens),
        "entry_count": len(entries),
        "table1_count": len(flow),
        "tokens": tokens,
        "entries": entries,
        "flow": flow,
    }


_YKSRC_REF_RE = re.compile(r"\.ykssrc$", re.IGNORECASE)


def is_ykssrc_path(path: str) -> bool:
    return _YKSRC_REF_RE.search(path) is not None
