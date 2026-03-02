from __future__ import annotations

import json
import struct
from pathlib import Path, PureWindowsPath

YKC_HEADER_STRUCT = struct.Struct("<8s4I")
YKC_ENTRY_STRUCT = struct.Struct("<5I")
CP932 = "cp932"


def parse_ykdat(data: bytes) -> dict:
    if len(data) < YKC_HEADER_STRUCT.size:
        raise ValueError("File is smaller than YKC header.")
    magic8, header_size, reserved_u32, table_off, table_size = YKC_HEADER_STRUCT.unpack_from(data, 0)
    if header_size < YKC_HEADER_STRUCT.size:
        raise ValueError(f"Invalid header_size: {header_size}")
    if table_size % YKC_ENTRY_STRUCT.size != 0:
        raise ValueError(f"Invalid table_size: {table_size}")
    table_end = table_off + table_size
    if table_end > len(data):
        raise ValueError("Table region exceeds file size.")

    entry_count = table_size // YKC_ENTRY_STRUCT.size
    entries: list[dict] = []
    for i in range(entry_count):
        base = table_off + i * YKC_ENTRY_STRUCT.size
        name_off, name_len, data_off, data_len, unk_u32 = YKC_ENTRY_STRUCT.unpack_from(data, base)
        if name_off + name_len > len(data):
            raise ValueError(f"Name range out of bounds at entry {i}")
        if data_off + data_len > len(data):
            raise ValueError(f"Data range out of bounds at entry {i}")
        name_bytes = data[name_off : name_off + name_len]
        name = name_bytes.rstrip(b"\x00").decode(CP932, errors="replace")
        entries.append(
            {
                "index": i,
                "name": name,
                "name_bytes_hex": name_bytes.hex(),
                "name_off_u32": name_off,
                "name_len_u32": name_len,
                "data_off_u32": data_off,
                "data_len_u32": data_len,
                "unk_u32": unk_u32,
            }
        )

    return {
        "format": "YKC",
        "magic8_hex": magic8.hex(),
        "header_size_u32": header_size,
        "reserved_u32": reserved_u32,
        "table_off_u32": table_off,
        "table_size_u32": table_size,
        "entry_count": entry_count,
        "entries": entries,
        "file_size": len(data),
    }


def _name_to_rel_path(name: str) -> Path:
    win = PureWindowsPath(name)
    clean_parts = [p for p in win.parts if p not in ("", ".", "..")]
    return Path(*clean_parts)


def unpack_ykdat(input_path: Path, output_dir: Path) -> Path:
    data = input_path.read_bytes()
    doc = parse_ykdat(data)

    files_root = output_dir / "files"
    files_root.mkdir(parents=True, exist_ok=True)
    for entry in doc["entries"]:
        rel = _name_to_rel_path(entry["name"])
        entry["file_rel"] = rel.as_posix()
        dst = files_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        off = int(entry["data_off_u32"])
        size = int(entry["data_len_u32"])
        dst.write_bytes(data[off : off + size])

    manifest = output_dir / "manifest.json"
    manifest.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def pack_ykdat(manifest_path: Path, output_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "YKC":
        raise ValueError("Manifest format is not YKC.")

    entries = list(manifest.get("entries", []))
    if not entries:
        raise ValueError("Manifest has no entries.")

    base_dir = manifest_path.parent
    files_root = base_dir / "files"
    header_size = int(manifest.get("header_size_u32", YKC_HEADER_STRUCT.size))
    reserved_u32 = int(manifest.get("reserved_u32", 0))
    magic8 = bytes.fromhex(str(manifest.get("magic8_hex", "")))
    if len(magic8) != 8:
        raise ValueError("Invalid magic8_hex in manifest.")

    data_blobs: list[bytes] = []
    name_blobs: list[bytes] = []
    for entry in entries:
        rel = Path(str(entry.get("file_rel", "")))
        blob = (files_root / rel).read_bytes()
        data_blobs.append(blob)
        if "name_bytes_hex" in entry:
            name_blob = bytes.fromhex(str(entry["name_bytes_hex"]))
        else:
            name_blob = str(entry["name"]).encode(CP932) + b"\x00"
        name_blobs.append(name_blob)

    cursor = header_size
    data_offs: list[int] = []
    for blob in data_blobs:
        data_offs.append(cursor)
        cursor += len(blob)

    name_offs: list[int] = []
    for name_blob in name_blobs:
        name_offs.append(cursor)
        cursor += len(name_blob)

    table_off = cursor
    table_size = len(entries) * YKC_ENTRY_STRUCT.size
    cursor += table_size

    out = bytearray(cursor)
    out[: YKC_HEADER_STRUCT.size] = YKC_HEADER_STRUCT.pack(
        magic8,
        header_size,
        reserved_u32,
        table_off,
        table_size,
    )

    for i, blob in enumerate(data_blobs):
        off = data_offs[i]
        out[off : off + len(blob)] = blob

    for i, name_blob in enumerate(name_blobs):
        off = name_offs[i]
        out[off : off + len(name_blob)] = name_blob

    for i, entry in enumerate(entries):
        base = table_off + i * YKC_ENTRY_STRUCT.size
        data_len = len(data_blobs[i])
        name_len = len(name_blobs[i])
        unk_u32 = int(entry.get("unk_u32", 0))
        out[base : base + YKC_ENTRY_STRUCT.size] = YKC_ENTRY_STRUCT.pack(
            name_offs[i],
            name_len,
            data_offs[i],
            data_len,
            unk_u32,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(out))
