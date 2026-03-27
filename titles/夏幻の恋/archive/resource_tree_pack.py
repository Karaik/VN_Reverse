from __future__ import annotations

import hashlib
import json
from pathlib import Path

from Crypto.Cipher import AES

from archive.csaf_decoded import RUNTIME_IV, TITLE_SEED_TEXT, decode_runtime_payload, derive_decoded_key, unpack_decoded_archive
from archive.csaf_raw import BLOCK_SIZE, ENTRY_STRUCT, HEADER_STRUCT
from archive.recover_resources_app import FINAL_MANIFEST_NAME


def _load_source_archive_layout(source_archive: Path) -> dict:
    data = source_archive.read_bytes()
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

    sorted_starts = sorted({entry["start_block"] for entry in entries})
    total_blocks = len(data) // BLOCK_SIZE
    next_start_map: dict[int, int] = {}
    for i, start in enumerate(sorted_starts):
        next_start_map[start] = sorted_starts[i + 1] if i + 1 < len(sorted_starts) else total_blocks

    for entry in entries:
        entry["allocated_blocks"] = next_start_map[entry["start_block"]] - entry["start_block"]

    return {
        "blob": data,
        "original_checksum": checksum,
        "version_flags": version_flags,
        "file_count": file_count,
        "extra_size": extra_size,
        "table_size": table_size,
        "original_table_blob": data[entry_table_off:entry_table_end],
        "table_padding": data[entry_table_end:table_region_end],
        "extra_region": data[table_region_end:extra_end],
        "entries": entries,
    }


def _load_resource_tree_manifest(resource_tree_root: Path) -> dict:
    manifest_path = resource_tree_root / FINAL_MANIFEST_NAME
    if not manifest_path.is_file():
        fallback = next(resource_tree_root.glob("*.json"), None)
        if fallback is None or not fallback.is_file():
            raise ValueError(f"Missing resource tree manifest: {manifest_path}")
        manifest_path = fallback
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _build_hash_to_current_path(resource_tree_root: Path, archive_name: str) -> dict[str, Path]:
    manifest = _load_resource_tree_manifest(resource_tree_root)
    mapping: dict[str, Path] = {}
    for entry in manifest.get("entries", []):
        if str(entry.get("archive", "")).lower() != archive_name.lower():
            continue
        hash_hex = entry.get("archive_hash_hex")
        current_path = entry.get("current_path")
        if not hash_hex or not current_path:
            continue
        mapping[str(hash_hex).lower()] = resource_tree_root / Path(str(current_path))
    return mapping


def build_resource_tree_name_map_for_archive(resource_tree_root: Path, archive_name: str) -> dict[str, str]:
    manifest = _load_resource_tree_manifest(resource_tree_root)
    mapping: dict[str, str] = {}
    for entry in manifest.get("entries", []):
        if str(entry.get("archive", "")).lower() != archive_name.lower():
            continue
        original_path = entry.get("original_path")
        hash_hex = entry.get("archive_hash_hex")
        if original_path and hash_hex:
            mapping[str(hash_hex).lower()] = str(original_path)
    return mapping


def encode_runtime_block(plain_block: bytes, absolute_block_index: int, seed_text: str = TITLE_SEED_TEXT) -> bytes:
    if len(plain_block) != BLOCK_SIZE:
        raise ValueError("Runtime block encode expects an exact 4096-byte block.")
    cipher = AES.new(derive_decoded_key(absolute_block_index, seed_text), AES.MODE_ECB)
    out = bytearray()
    previous = RUNTIME_IV
    for pos in range(0, len(plain_block), 16):
        chunk = plain_block[pos : pos + 16]
        xored = bytes(a ^ b for a, b in zip(chunk, previous))
        cipher_chunk = cipher.encrypt(xored)
        out.extend(cipher_chunk)
        previous = cipher_chunk
    return bytes(out)


def encode_runtime_payload(decoded_file: bytes, start_block: int, allocated_blocks: int, seed_text: str = TITLE_SEED_TEXT) -> bytes:
    total_len = allocated_blocks * BLOCK_SIZE
    if len(decoded_file) > total_len:
        raise ValueError("Decoded file exceeds allocated block capacity.")
    padded = decoded_file + b"\x00" * (total_len - len(decoded_file))
    return encode_runtime_payload_exact(padded, start_block)


def encode_runtime_payload_exact(plain_payload: bytes, start_block: int, seed_text: str = TITLE_SEED_TEXT) -> bytes:
    if len(plain_payload) % BLOCK_SIZE != 0:
        raise ValueError("Exact runtime payload encode expects a whole number of 4096-byte blocks.")
    out = bytearray()
    allocated_blocks = len(plain_payload) // BLOCK_SIZE
    for i in range(allocated_blocks):
        block = plain_payload[i * BLOCK_SIZE : (i + 1) * BLOCK_SIZE]
        out.extend(encode_runtime_block(block, start_block + i, seed_text))
    return bytes(out)


def pack_resource_tree_archive(
    source_archive: Path,
    resource_tree_root: Path,
    output_archive: Path,
    *,
    seed_text: str = TITLE_SEED_TEXT,
) -> None:
    archive_name = source_archive.name
    layout = _load_source_archive_layout(source_archive)
    hash_to_path = _build_hash_to_current_path(resource_tree_root, archive_name)

    metadata_size = HEADER_STRUCT.size + layout["table_size"] + layout["extra_size"]
    if metadata_size % BLOCK_SIZE != 0:
        raise ValueError("Metadata region is not aligned to 4096 bytes.")

    next_block = max(metadata_size // BLOCK_SIZE, max(entry["start_block"] + entry["allocated_blocks"] for entry in layout["entries"]))
    rebuilt_entries: list[dict] = []
    payloads: list[tuple[int, bytes]] = []

    for entry in layout["entries"]:
        hash_hex = entry["hash_hex"].lower()
        if hash_hex not in hash_to_path:
            raise ValueError(f"Resource tree is missing archive entry for hash: {hash_hex}")
        asset_path = hash_to_path[hash_hex]
        if not asset_path.is_file():
            raise ValueError(f"Resource tree file not found for hash {hash_hex}: {asset_path}")

        decoded_bytes = asset_path.read_bytes()
        original_start_block = int(entry["start_block"])
        original_allocated_blocks = int(entry["allocated_blocks"])
        original_allocated_bytes = original_allocated_blocks * BLOCK_SIZE

        if len(decoded_bytes) <= original_allocated_bytes:
            start_block = original_start_block
            allocated_blocks = original_allocated_blocks
            blob = layout["blob"]
            raw_off = original_start_block * BLOCK_SIZE
            original_raw_payload = blob[raw_off : raw_off + original_allocated_bytes]
            original_decoded_payload = decode_runtime_payload(original_raw_payload, original_start_block, seed_text)
            full_plain_payload = decoded_bytes + original_decoded_payload[len(decoded_bytes) : original_allocated_bytes]
            encoded_payload = encode_runtime_payload_exact(full_plain_payload, start_block, seed_text)
        else:
            allocated_blocks = max(1, (len(decoded_bytes) + BLOCK_SIZE - 1) // BLOCK_SIZE)
            start_block = next_block
            next_block += allocated_blocks
            encoded_payload = encode_runtime_payload(decoded_bytes, start_block, allocated_blocks, seed_text)

        payloads.append((start_block, encoded_payload))
        rebuilt_entries.append(
            {
                "hash_hex": hash_hex,
                "start_block": start_block,
                "size": len(decoded_bytes),
            }
        )

    archive = bytearray(next_block * BLOCK_SIZE)
    table_off = HEADER_STRUCT.size
    table_blob = bytearray(layout["file_count"] * ENTRY_STRUCT.size)
    for i, entry in enumerate(rebuilt_entries):
        ENTRY_STRUCT.pack_into(
            table_blob,
            i * ENTRY_STRUCT.size,
            bytes.fromhex(entry["hash_hex"]),
            int(entry["start_block"]),
            int(entry["size"]),
        )

    table_end = table_off + len(table_blob)
    table_region_end = table_off + layout["table_size"]
    extra_off = table_region_end
    extra_end = extra_off + layout["extra_size"]

    archive[table_off:table_end] = table_blob
    archive[table_end:table_region_end] = layout["table_padding"]
    archive[extra_off:extra_end] = layout["extra_region"]

    for start_block, payload in payloads:
        data_off = start_block * BLOCK_SIZE
        archive[data_off : data_off + len(payload)] = payload

    if table_blob == layout["original_table_blob"] and layout["extra_region"] == archive[extra_off:extra_end]:
        checksum = layout["original_checksum"]
    else:
        checksum = hashlib.md5(archive[table_off:extra_end]).digest()
    header = HEADER_STRUCT.pack(b"CSAF", layout["version_flags"], layout["file_count"], layout["extra_size"], checksum)
    archive[: HEADER_STRUCT.size] = header
    output_archive.parent.mkdir(parents=True, exist_ok=True)
    output_archive.write_bytes(archive)


def validate_packed_resource_tree_archive(
    source_archive: Path,
    resource_tree_root: Path,
    repacked_archive: Path,
    *,
    seed_text: str = TITLE_SEED_TEXT,
) -> dict:
    name_map = build_resource_tree_name_map_for_archive(resource_tree_root, source_archive.name)
    unpack_root = repacked_archive.parent / (repacked_archive.stem + "_decoded_check")
    if unpack_root.exists():
        if unpack_root.is_dir():
            for child in unpack_root.rglob("*"):
                pass
    manifest_path = unpack_decoded_archive(repacked_archive, unpack_root, name_map, seed_text=seed_text)
    return {
        "manifest_path": manifest_path.as_posix(),
        "unpack_root": unpack_root.as_posix(),
    }
