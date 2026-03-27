from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import struct
from pathlib import Path

try:
    from Crypto.Cipher import AES
except ImportError as exc:  # pragma: no cover - import guard for local runtime
    raise RuntimeError("Decoded CSAF unpack requires pycryptodome (`pip install pycryptodome`).") from exc

from archive.csaf_raw import (
    BLOCK_SIZE,
    ENTRY_STRUCT,
    HEADER_STRUCT,
    build_output_relpath,
    guess_payload_ext,
    infer_output_class,
    infer_resource_kind,
    load_name_map,
    normalize_rel_name,
)


TITLE_SEED_TEXT = "\u590f\u5e7b\u306e\u604b"
RUNTIME_IV = b"FamilyAdvSystem "
_MD5_PADDING = bytes([0x80]) + b"\x00" * 63
_MD5_SHIFTS = [7, 12, 17, 22] * 4 + [5, 9, 14, 20] * 4 + [4, 11, 16, 23] * 4 + [6, 10, 15, 21] * 4
_MD5_K = [int(abs(math.sin(i + 1)) * (1 << 32)) & 0xFFFFFFFF for i in range(64)]


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _rol32(value: int, shift: int) -> int:
    value &= 0xFFFFFFFF
    return ((value << shift) | (value >> (32 - shift))) & 0xFFFFFFFF


def _md5_compress(state: list[int], block64: bytes) -> list[int]:
    words = list(struct.unpack("<16I", block64))
    a, b, c, d = state
    aa, bb, cc, dd = a, b, c, d
    for i in range(64):
        if i < 16:
            f = (b & c) | (~b & d)
            g = i
        elif i < 32:
            f = (d & b) | (~d & c)
            g = (5 * i + 1) % 16
        elif i < 48:
            f = b ^ c ^ d
            g = (3 * i + 5) % 16
        else:
            f = c ^ (b | ~d)
            g = (7 * i) % 16
        temp = (a + f + _MD5_K[i] + words[g]) & 0xFFFFFFFF
        a, d, c, b = d, c, b, (b + _rol32(temp, _MD5_SHIFTS[i])) & 0xFFFFFFFF
    return [
        (aa + a) & 0xFFFFFFFF,
        (bb + b) & 0xFFFFFFFF,
        (cc + c) & 0xFFFFFFFF,
        (dd + d) & 0xFFFFFFFF,
    ]


class _Md5Ctx:
    def __init__(self) -> None:
        self.state = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476]
        self.low = 0
        self.high = 0
        self.buffer = bytearray(64)

    def update(self, data: bytes) -> None:
        old_low = self.low
        self.low = (self.low + (len(data) << 3)) & 0xFFFFFFFF
        if self.low < old_low:
            self.high = (self.high + 1) & 0xFFFFFFFF
        self.high = (self.high + (len(data) >> 29)) & 0xFFFFFFFF

        index = (old_low >> 3) & 0x3F
        part = 64 - index
        offset = 0
        if len(data) >= part:
            self.buffer[index : index + part] = data[:part]
            self.state = _md5_compress(self.state, bytes(self.buffer))
            offset = part
            while offset + 63 < len(data):
                self.state = _md5_compress(self.state, data[offset : offset + 64])
                offset += 64
            index = 0
        self.buffer[index : index + (len(data) - offset)] = data[offset:]

    def final(self) -> bytes:
        saved_count = struct.pack("<II", self.low, self.high)
        index = (self.low >> 3) & 0x3F
        pad_len = 56 - index if index < 56 else 120 - index
        self.update(_MD5_PADDING[:pad_len])
        self.update(saved_count)
        return struct.pack("<4I", *self.state)


def build_seed_tables(seed_text: str = TITLE_SEED_TEXT) -> tuple[bytes, bytes]:
    raw = seed_text.encode("utf-16le")
    if not raw:
        raise ValueError("Decoded CSAF seed text is empty.")
    table0 = hashlib.md5(raw).digest()
    table1 = hashlib.md5(raw[1:-1]).digest()
    return table0, table1


def derive_decoded_key(block_index: int, seed_text: str = TITLE_SEED_TEXT) -> bytes:
    table0, table1 = build_seed_tables(seed_text)
    offset = (block_index >> 3) & 0x0F
    rotate = block_index & 7

    def rotate_table(src: bytes) -> bytes:
        out = bytearray(16)
        for i in range(16):
            value = src[(offset + i) & 0x0F]
            if rotate:
                value = ((value << rotate) & 0xFF) | (value >> (8 - rotate))
            out[i] = value
        return bytes(out)

    ctx = _Md5Ctx()
    ctx.update(rotate_table(table0))
    digest0 = ctx.final()
    ctx.update(rotate_table(table1))
    digest1 = ctx.final()
    return digest0 + digest1


def decode_runtime_block(raw_block: bytes, absolute_block_index: int, seed_text: str = TITLE_SEED_TEXT) -> bytes:
    if len(raw_block) > BLOCK_SIZE:
        raise ValueError("A runtime block cannot exceed 4096 bytes.")
    cipher = AES.new(derive_decoded_key(absolute_block_index, seed_text), AES.MODE_ECB)
    out = bytearray()
    previous = RUNTIME_IV
    for pos in range(0, len(raw_block), 16):
        chunk = raw_block[pos : pos + 16]
        padded = chunk if len(chunk) == 16 else chunk.ljust(16, b"\x00")
        # Mirrors 414DD0 + 417040:
        # plaintext = AES-256-decrypt(ciphertext) XOR previous_ciphertext_or_iv
        decrypted = cipher.decrypt(padded)
        plain = bytes(a ^ b for a, b in zip(decrypted[: len(chunk)], previous[: len(chunk)]))
        out.extend(plain)
        previous = padded
    return bytes(out)


def decode_runtime_payload(raw_payload: bytes, start_block: int, seed_text: str = TITLE_SEED_TEXT) -> bytes:
    if len(raw_payload) % BLOCK_SIZE != 0:
        raise ValueError("Runtime payload must be aligned to 4096 bytes before decoded unpack.")
    out = bytearray()
    for block_offset in range(0, len(raw_payload), BLOCK_SIZE):
        absolute_block_index = start_block + block_offset // BLOCK_SIZE
        raw_block = raw_payload[block_offset : block_offset + BLOCK_SIZE]
        out.extend(decode_runtime_block(raw_block, absolute_block_index, seed_text))
    return bytes(out)


def decode_extra_region(raw_extra_region: bytes, seed_text: str = TITLE_SEED_TEXT) -> bytes:
    out = bytearray()
    for block_offset in range(0, len(raw_extra_region), BLOCK_SIZE):
        absolute_block_index = block_offset // BLOCK_SIZE
        raw_block = raw_extra_region[block_offset : block_offset + BLOCK_SIZE]
        out.extend(decode_runtime_block(raw_block, absolute_block_index, seed_text))
    return bytes(out[: len(raw_extra_region)])


def decoded_extra_region_matches_header(archive_path: Path, seed_text: str = TITLE_SEED_TEXT) -> tuple[bool, str, str]:
    blob = archive_path.read_bytes()
    magic, version_flags, file_count, extra_size, checksum = HEADER_STRUCT.unpack_from(blob, 0)
    if magic != b"CSAF":
        raise ValueError(f"Magic is not CSAF: {magic!r}")
    table_size = ((24 * file_count + 31) & 0xFFFFF000) + 4064
    table_off = HEADER_STRUCT.size
    table_end = table_off + table_size
    extra_end = table_end + extra_size
    table_region = blob[table_off:table_end]
    raw_extra = blob[table_end:extra_end]
    decoded_extra = decode_extra_region(raw_extra, seed_text)
    decoded_md5 = hashlib.md5(table_region + decoded_extra).hexdigest()
    expected_md5 = checksum.hex()
    return decoded_md5 == expected_md5, decoded_md5, expected_md5


def unpack_decoded_archive(
    archive_path: Path,
    out_dir: Path,
    name_map: dict[str, str],
    name_catalog: dict[str, dict] | None = None,
    seed_text: str = TITLE_SEED_TEXT,
) -> Path:
    archive_name = archive_path.name
    blob = archive_path.read_bytes()
    if len(blob) < HEADER_STRUCT.size:
        raise ValueError("File is smaller than CSAF header size.")

    magic, version_flags, file_count, extra_size, checksum = HEADER_STRUCT.unpack_from(blob, 0)
    if magic != b"CSAF":
        raise ValueError(f"Magic is not CSAF: {magic!r}")

    table_size = ((24 * file_count + 31) & 0xFFFFF000) + 4064
    entry_table_off = HEADER_STRUCT.size
    entry_table_end = entry_table_off + file_count * ENTRY_STRUCT.size
    table_region_end = entry_table_off + table_size
    extra_end = table_region_end + extra_size
    if extra_end > len(blob):
        raise ValueError("Table/extra region declared in header exceeds file length.")

    decoded_extra = decode_extra_region(blob[table_region_end:extra_end], seed_text)
    decoded_extra_md5 = hashlib.md5(blob[entry_table_off:table_region_end] + decoded_extra).hexdigest()
    expected_checksum = checksum.hex()

    entries = []
    for i in range(file_count):
        off = entry_table_off + i * ENTRY_STRUCT.size
        hash_bytes, start_block, size = ENTRY_STRUCT.unpack_from(blob, off)
        entries.append(
            {
                "index": i,
                "hash_hex": hash_bytes.hex(),
                "start_block": start_block,
                "size": size,
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)

    total_blocks = len(blob) // BLOCK_SIZE
    sorted_starts = sorted({entry["start_block"] for entry in entries})
    next_start_map: dict[int, int] = {}
    for i, start in enumerate(sorted_starts):
        next_start_map[start] = sorted_starts[i + 1] if i + 1 < len(sorted_starts) else total_blocks

    for entry in entries:
        start = entry["start_block"]
        end = next_start_map[start]
        allocated_blocks = end - start
        allocated_bytes = allocated_blocks * BLOCK_SIZE
        blob_off = start * BLOCK_SIZE
        raw_payload = blob[blob_off : blob_off + allocated_bytes]
        decoded_payload = decode_runtime_payload(raw_payload, start, seed_text)
        decoded_file = decoded_payload[: entry["size"]]
        raw_padding = raw_payload[entry["size"] :]

        known_name = name_map.get(entry["hash_hex"])
        name_info = (name_catalog or {}).get(entry["hash_hex"], {})
        suffix = guess_payload_ext(decoded_file)
        rel_path = build_output_relpath(
            archive_name,
            entry_index=entry["index"],
            hash_hex=entry["hash_hex"],
            data=decoded_file,
            suffix=suffix,
            original_path=known_name,
        )
        abs_path = out_dir / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(decoded_file)

        entry["file"] = rel_path.as_posix()
        entry["original_path"] = known_name
        entry["resolved_name"] = bool(known_name)
        entry["output_class"] = infer_output_class(rel_path, bool(known_name))
        entry["resource_kind"] = infer_resource_kind(rel_path)
        evidence_sources = ["包内目录项"]
        for source in name_info.get("evidence_sources", []):
            if source not in evidence_sources:
                evidence_sources.append(source)
        entry["evidence_sources"] = evidence_sources
        entry["evidence_files"] = list(name_info.get("evidence_files", []))
        entry["allocated_blocks"] = allocated_blocks
        entry["raw_padding_base64"] = _b64(raw_padding)
        entry["decoded_magic_hex"] = decoded_file[:4].hex()

    manifest = {
        "format": "CSAF",
        "semantic_layer": "decoded",
        "decoded_from": "runtime_payload",
        "archive_name": archive_path.name,
        "seed_text": seed_text,
        "runtime_iv_ascii": RUNTIME_IV.decode("ascii"),
        "version_flags": version_flags,
        "version": version_flags & 0x7FFFFFFF,
        "encrypted": bool(version_flags & 0x80000000),
        "file_count": file_count,
        "extra_size": extra_size,
        "checksum_hex": expected_checksum,
        "decoded_extra_checksum_hex": decoded_extra_md5,
        "decoded_extra_matches_header_checksum": decoded_extra_md5 == expected_checksum,
        "entries": entries,
    }

    manifest_path = out_dir / "resource_tree.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unpack CSAF decoded runtime payload.")
    parser.add_argument("archive", help="Input archive file, e.g. game/adv.")
    parser.add_argument("out_dir", help="Output directory for decoded files and decoded manifest.")
    parser.add_argument("--name-list", help="Name dictionary text file, one in-archive path per line.")
    parser.add_argument("--name-dir", help="Name dictionary directory. Recursively scanned and hashed by relative path.")
    parser.add_argument(
        "--seed-text",
        default=TITLE_SEED_TEXT,
        help="Decoded seed text used by runtime table initialization. Default: current title name.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    archive_path = Path(args.archive)
    out_dir = Path(args.out_dir)
    name_list = Path(args.name_list) if args.name_list else None
    name_dir = Path(args.name_dir) if args.name_dir else None
    name_map = load_name_map(name_list, name_dir, archive_path.name)

    manifest_path = unpack_decoded_archive(archive_path, out_dir, name_map, seed_text=args.seed_text)
    print(manifest_path.as_posix())
    return 0
