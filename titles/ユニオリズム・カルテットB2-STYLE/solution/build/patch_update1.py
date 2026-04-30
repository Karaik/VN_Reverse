from __future__ import annotations

import argparse
import shutil
import struct
import zlib
from pathlib import Path

from solution.unpack.update1_ysbin_unpack import decode_path, decode_path_size


def _collect_updates(update_dir: Path) -> dict[str, Path]:
    updates: dict[str, Path] = {}
    for file in sorted(update_dir.glob("*.ybn")):
        updates[f"ysbin\\{file.name}"] = file
    return updates


def _scan_entries(index: bytes, entry_count: int) -> dict[str, dict[str, int]]:
    entries: dict[str, dict[str, int]] = {}
    p = 0
    for _ in range(entry_count):
        name_size = decode_path_size(index[p + 4])
        name_enc = index[p + 5:p + 5 + name_size]
        name = decode_path(name_enc)
        rest_pos = p + 5 + name_size
        decomp_size, comp_size, offset, data_crc = struct.unpack_from("<IIQI", index, rest_pos + 2)
        entries[name] = {
            "entry_pos": rest_pos,
            "decomp_size": decomp_size,
            "comp_size": comp_size,
            "offset": offset,
            "data_crc": data_crc,
        }
        p = rest_pos + 22
    return entries


def patch_pack(src_pack: Path, out_pack: Path, update_dir: Path) -> Path:
    updates = _collect_updates(update_dir)
    if not updates:
        out_pack.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_pack, out_pack)
        return out_pack

    with src_pack.open("rb") as fp:
        header = fp.read(32)
        sig, version, entry_count, index_size, *_ = struct.unpack("<4sIIIIIII", header)
        if sig[:3] != b"YPF":
            raise ValueError(f"unexpected signature: {sig!r}")
        index = bytearray(fp.read(index_size))

    entry_map = _scan_entries(index, entry_count)
    shutil.copy2(src_pack, out_pack)
    with out_pack.open("r+b") as fp:
        fp.seek(0, 2)
        append_offset = fp.tell()
        for target_path, new_file in updates.items():
            entry = entry_map[target_path]
            new_raw = new_file.read_bytes()
            new_comp = zlib.compress(new_raw)
            fp.seek(append_offset)
            fp.write(new_comp)

            struct.pack_into("<I", index, entry["entry_pos"] + 2, len(new_raw))
            struct.pack_into("<I", index, entry["entry_pos"] + 6, len(new_comp))
            struct.pack_into("<Q", index, entry["entry_pos"] + 10, append_offset)
            append_offset += len(new_comp)

        fp.seek(32)
        fp.write(index)

    return out_pack


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("src_pack")
    parser.add_argument("out_pack")
    parser.add_argument("update_dir")
    args = parser.parse_args()
    print(patch_pack(Path(args.src_pack), Path(args.out_pack), Path(args.update_dir)))


if __name__ == "__main__":
    main()
