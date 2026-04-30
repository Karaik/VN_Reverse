from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path


def decode_path_size(enc_size: int) -> int:
    table = [
        0x00, 0x01, 0x02, 0x0A, 0x04, 0x05, 0x35, 0x07, 0x08, 0x0B, 0x03, 0x09, 0x10, 0x13, 0x0E, 0x0F,
        0x0C, 0x18, 0x12, 0x0D, 0x2E, 0x1B, 0x16, 0x17, 0x11, 0x19, 0x1A, 0x15, 0x1E, 0x1D, 0x1C, 0x1F,
        0x23, 0x21, 0x22, 0x20, 0x24, 0x25, 0x29, 0x27, 0x28, 0x26, 0x2A, 0x2B, 0x2F, 0x2D, 0x14, 0x2C,
        0x30, 0x31, 0x32, 0x33, 0x34, 0x06, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F,
    ] + list(range(0x40, 0x100))
    return table[0xFF - enc_size]


def decode_path(data: bytes) -> str:
    raw = bytes((((~x) & 0xFF) ^ 0x36) for x in data)
    return raw.decode("cp932", errors="replace")


def iter_entries(pack_path: Path):
    with pack_path.open("rb") as fp:
        header = fp.read(32)
        sig, version, entry_count, index_size, *_ = struct.unpack("<4sIIIIIII", header)
        if sig[:3] != b"YPF":
            raise ValueError(f"unexpected signature: {sig!r}")
        index = fp.read(index_size)
        p = 0
        for _ in range(entry_count):
            path_size = decode_path_size(index[p + 4])
            path_enc = index[p + 5:p + 5 + path_size]
            p += 5 + path_size
            file_type = index[p]
            comp_flag = index[p + 1]
            decomp_size, comp_size, offset, data_crc = struct.unpack_from("<IIQI", index, p + 2)
            p += 22
            yield {
                "path": decode_path(path_enc),
                "file_type": file_type,
                "comp_flag": comp_flag,
                "decomp_size": decomp_size,
                "comp_size": comp_size,
                "offset": offset,
                "data_crc": data_crc,
            }


def unpack_ysbin(pack_path: Path, out_dir: Path) -> int:
    count = 0
    out_dir.mkdir(parents=True, exist_ok=True)
    with pack_path.open("rb") as fp:
        for entry in iter_entries(pack_path):
            if not entry["path"].startswith("ysbin\\"):
                continue
            fp.seek(entry["offset"])
            data = fp.read(entry["comp_size"])
            if entry["comp_flag"]:
                data = zlib.decompress(data)
            rel = entry["path"].split("\\", 1)[1]
            target = out_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pack_path")
    parser.add_argument("out_dir")
    args = parser.parse_args()
    count = unpack_ysbin(Path(args.pack_path), Path(args.out_dir))
    print(f"unpacked {count} ysbin entries")


if __name__ == "__main__":
    main()
