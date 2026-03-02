#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import struct
from pathlib import Path

HEADER_STRUCT = struct.Struct("<4sIII16s")
ENTRY_STRUCT = struct.Struct("<16sII")
BLOCK_SIZE = 0x1000


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _hash_name(name: str) -> str:
    normalized = name.replace("/", "\\").lower()
    return hashlib.md5(normalized.encode("utf-16le")).hexdigest()


def _guess_ext(data: bytes) -> str:
    if data.startswith(b"NBDA"):
        return ".adb"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WAVE":
        return ".wav"
    if data.startswith(b"OggS"):
        return ".ogg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    return ".bin"


def _normalize_rel_name(name: str) -> str:
    raw = name.replace("\\", "/").lstrip("/").strip()
    parts = [p for p in raw.split("/") if p]
    if any(p == ".." for p in parts):
        raise ValueError(f"Invalid path: {name}")
    return "/".join(parts)


def _load_name_map(name_list: Path | None, name_dir: Path | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if name_list:
        for line in name_list.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key = _hash_name(line)
            mapping[key] = line
    if name_dir:
        base = name_dir.resolve()
        for file_path in sorted(base.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(base).as_posix().replace("/", "\\")
            key = _hash_name(rel)
            mapping[key] = rel
    return mapping


def unpack_archive(archive_path: Path, out_dir: Path, name_map: dict[str, str]) -> Path:
    data = archive_path.read_bytes()
    if len(data) < HEADER_STRUCT.size:
        raise ValueError("File is smaller than CSAF header size.")

    magic, version_flags, file_count, extra_size, checksum = HEADER_STRUCT.unpack_from(data, 0)
    if magic != b"CSAF":
        raise ValueError(f"Magic is not CSAF: {magic!r}")

    table_size = ((24 * file_count + 31) & 0xFFFFF000) + 4064
    entry_table_off = HEADER_STRUCT.size
    entry_table_end = entry_table_off + file_count * ENTRY_STRUCT.size
    table_region_end = entry_table_off + table_size
    extra_end = table_region_end + extra_size
    if extra_end > len(data):
        raise ValueError("Table/extra region declared in header exceeds file length.")

    entries = []
    for i in range(file_count):
        off = entry_table_off + i * ENTRY_STRUCT.size
        hash_bytes, start_block, size = ENTRY_STRUCT.unpack_from(data, off)
        entries.append(
            {
                "index": i,
                "hash_hex": hash_bytes.hex(),
                "start_block": start_block,
                "size": size,
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    files_root = out_dir / "files"
    files_root.mkdir(parents=True, exist_ok=True)

    total_blocks = len(data) // BLOCK_SIZE
    sorted_starts = sorted({e["start_block"] for e in entries})
    next_start_map: dict[int, int] = {}
    for i, start in enumerate(sorted_starts):
        next_start_map[start] = sorted_starts[i + 1] if i + 1 < len(sorted_starts) else total_blocks

    for e in entries:
        start = e["start_block"]
        end = next_start_map[start]
        allocated = (end - start) * BLOCK_SIZE
        blob_off = start * BLOCK_SIZE
        blob = data[blob_off : blob_off + allocated]
        file_bytes = blob[: e["size"]]
        padding = blob[e["size"] :]

        known_name = name_map.get(e["hash_hex"])
        if known_name:
            rel_name = _normalize_rel_name(known_name)
            rel_path = Path("files") / rel_name
        else:
            rel_path = Path("files") / f"{e['index']:05d}_{e['hash_hex']}{_guess_ext(file_bytes)}"
        abs_path = out_dir / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(file_bytes)

        e["file"] = rel_path.as_posix()
        e["allocated_blocks"] = end - start
        e["padding_base64"] = _b64(padding)

    manifest = {
        "format": "CSAF",
        "archive_name": archive_path.name,
        "magic": "CSAF",
        "version_flags": version_flags,
        "version": version_flags & 0x7FFFFFFF,
        "encrypted": bool(version_flags & 0x80000000),
        "file_count": file_count,
        "extra_size": extra_size,
        "checksum_hex": checksum.hex(),
        "table_size": table_size,
        "table_padding_base64": _b64(data[entry_table_end:table_region_end]),
        "extra_region_base64": _b64(data[table_region_end:extra_end]),
        "entries": entries,
    }

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unpack CSAF archive.")
    parser.add_argument("archive", help="Input archive file, e.g. game/adv.")
    parser.add_argument("out_dir", help="Output directory.")
    parser.add_argument("--name-list", help="Name dictionary text file, one in-archive path per line.")
    parser.add_argument("--name-dir", help="Name dictionary directory. Recursively scanned and hashed by relative path.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    archive_path = Path(args.archive)
    out_dir = Path(args.out_dir)
    name_list = Path(args.name_list) if args.name_list else None
    name_dir = Path(args.name_dir) if args.name_dir else None
    name_map = _load_name_map(name_list, name_dir)

    manifest_path = unpack_archive(archive_path, out_dir, name_map)
    print(manifest_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
