from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

RK1_MAGIC_U32 = 0x00314B52  # "RK1\0"
ENTRY_SIZE = 32
FOOTER_SIZE = 12
FOOTER_STRUCT = struct.Struct("<III")
ENTRY_STRUCT = struct.Struct("<16s4I")


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def lzss_decompress(src: bytes, out_size: int) -> bytes:
    if out_size == 0:
        return b""
    ring = bytearray(0x1010)
    ring_pos = 4078
    src_pos = 0
    flags = 0
    out = bytearray()
    while len(out) < out_size:
        need_reload = (flags & 0x200) == 0
        flags >>= 1
        if need_reload:
            if src_pos >= len(src):
                raise ValueError("LZSS: source EOF while reading flags.")
            flags = src[src_pos] | 0xFF00
            src_pos += 1
        if flags & 1:
            if src_pos >= len(src):
                raise ValueError("LZSS: source EOF while reading literal.")
            b = src[src_pos]
            src_pos += 1
            out.append(b)
            ring[ring_pos] = b
            ring_pos = (ring_pos + 1) & 0xFFF
            continue
        if src_pos + 1 >= len(src):
            raise ValueError("LZSS: source EOF while reading backref.")
        low = src[src_pos]
        high = src[src_pos + 1]
        src_pos += 2
        start = low | ((high & 0xF0) << 4)
        count = (high & 0x0F) + 3
        for j in range(count):
            b = ring[(start + j) & 0xFFF]
            out.append(b)
            ring[ring_pos] = b
            ring_pos = (ring_pos + 1) & 0xFFF
            if len(out) >= out_size:
                break
    return bytes(out)


def parse_rk1(data: bytes) -> dict:
    if len(data) < FOOTER_SIZE:
        raise ValueError("RK1 file is smaller than footer.")
    magic_u32, entry_count, table_off = FOOTER_STRUCT.unpack_from(data, len(data) - FOOTER_SIZE)
    if magic_u32 != RK1_MAGIC_U32:
        raise ValueError(f"Invalid RK1 magic: 0x{magic_u32:08X}")
    table_size = entry_count * ENTRY_SIZE
    if table_off + table_size + FOOTER_SIZE != len(data):
        raise ValueError("RK1 table/footer layout mismatch.")

    entries: list[dict] = []
    for i in range(entry_count):
        off = table_off + i * ENTRY_SIZE
        name_raw, packed_size, unpacked_size, flag_u32, data_off = ENTRY_STRUCT.unpack_from(data, off)
        name = name_raw.split(b"\x00", 1)[0].decode("ascii")
        if data_off + packed_size > table_off:
            raise ValueError(f"Entry data exceeds table region: index={i}")
        packed_blob = data[data_off : data_off + packed_size]
        if flag_u32 == 0:
            if unpacked_size > packed_size:
                raise ValueError(f"Invalid uncompressed entry size: index={i}")
            unpacked_blob = packed_blob[:unpacked_size]
        elif flag_u32 == 1:
            unpacked_blob = lzss_decompress(packed_blob, unpacked_size)
        else:
            raise ValueError(f"Unsupported RK1 flag: index={i}, flag={flag_u32}")
        entries.append(
            {
                "index": i,
                "name": name,
                "packed_size_u32": packed_size,
                "unpacked_size_u32": unpacked_size,
                "flag_u32": flag_u32,
                "data_off_u32": data_off,
                "packed_blob": packed_blob,
                "unpacked_blob": unpacked_blob,
            }
        )
    return {
        "format": "RK1",
        "magic_u32": magic_u32,
        "entry_count_u32": entry_count,
        "table_off_u32": table_off,
        "entries": entries,
    }


def unpack_rk1(archive_path: Path, out_dir: Path) -> Path:
    doc = parse_rk1(archive_path.read_bytes())
    files_root = out_dir / "files"
    packed_root = out_dir / "packed"
    files_root.mkdir(parents=True, exist_ok=True)
    packed_root.mkdir(parents=True, exist_ok=True)

    manifest_entries: list[dict] = []
    for entry in doc["entries"]:
        idx = int(entry["index"])
        name = str(entry["name"])
        unpacked_blob = bytes(entry["unpacked_blob"])
        packed_blob = bytes(entry["packed_blob"])
        out_file = files_root / name
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_bytes(unpacked_blob)

        packed_rel = Path("packed") / f"{idx:05d}.bin"
        (out_dir / packed_rel).write_bytes(packed_blob)

        manifest_entries.append(
            {
                "index": idx,
                "name": name,
                "packed_size_u32": int(entry["packed_size_u32"]),
                "unpacked_size_u32": int(entry["unpacked_size_u32"]),
                "flag_u32": int(entry["flag_u32"]),
                "data_off_u32": int(entry["data_off_u32"]),
                "unpacked_sha1": _sha1(unpacked_blob),
                "packed_sha1": _sha1(packed_blob),
                "packed_rel": packed_rel.as_posix(),
            }
        )

    manifest = {
        "format": "RK1_MANIFEST",
        "archive_name": archive_path.name,
        "magic_u32": int(doc["magic_u32"]),
        "entry_count_u32": int(doc["entry_count_u32"]),
        "table_off_u32": int(doc["table_off_u32"]),
        "entries": manifest_entries,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def _encode_entry_name(name: str) -> bytes:
    raw = name.encode("ascii")
    if len(raw) > 16:
        raise ValueError(f"RK1 entry name is longer than 16 bytes: {name}")
    if len(raw) == 16:
        return raw
    return raw + (b"\x00" * (16 - len(raw)))


def pack_rk1(manifest_path: Path, out_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "RK1_MANIFEST":
        raise ValueError("Manifest format is not RK1_MANIFEST.")
    entries = sorted(list(manifest.get("entries", [])), key=lambda x: int(x["index"]))
    base_dir = manifest_path.parent
    files_dir = base_dir / "files"

    table_rows: list[tuple[bytes, int, int, int, int]] = []
    data_blobs: list[bytes] = []
    current_off = 0

    for entry in entries:
        index = int(entry["index"])
        name = str(entry["name"])
        flag_u32 = int(entry["flag_u32"])
        file_path = files_dir / name
        if not file_path.is_file():
            raise ValueError(f"Missing unpacked file: {file_path}")
        unpacked_blob = file_path.read_bytes()
        unpacked_sha1 = _sha1(unpacked_blob)
        original_unpacked_sha1 = str(entry.get("unpacked_sha1", ""))

        reuse_original = unpacked_sha1 == original_unpacked_sha1 and str(entry.get("packed_rel", "")) != ""
        if reuse_original:
            packed_rel = Path(str(entry["packed_rel"]))
            packed_path = base_dir / packed_rel
            if not packed_path.is_file():
                raise ValueError(f"Missing original packed blob: {packed_path}")
            packed_blob = packed_path.read_bytes()
            packed_size = int(entry["packed_size_u32"])
            unpacked_size = int(entry["unpacked_size_u32"])
            if packed_size != len(packed_blob):
                raise ValueError(f"Packed blob size mismatch at index={index}")
        else:
            # For modified files, fallback to uncompressed entry.
            packed_blob = unpacked_blob
            packed_size = len(packed_blob)
            unpacked_size = len(unpacked_blob)
            flag_u32 = 0

        table_rows.append(
            (
                _encode_entry_name(name),
                packed_size,
                unpacked_size,
                flag_u32,
                current_off,
            )
        )
        data_blobs.append(packed_blob)
        current_off += packed_size

    table_off = current_off
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as fp:
        for blob in data_blobs:
            fp.write(blob)
        for row in table_rows:
            fp.write(ENTRY_STRUCT.pack(*row))
        fp.write(FOOTER_STRUCT.pack(RK1_MAGIC_U32, len(table_rows), table_off))
