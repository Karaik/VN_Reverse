#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from yuka.ykdat import unpack_ykdat


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unpack YKC archive to files + manifest.")
    parser.add_argument("input", help="Input .dat file.")
    parser.add_argument("output", nargs="?", help="Output directory.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    if not input_path.is_file():
        raise ValueError(f"Input file not found: {input_path}")
    output_dir = Path(args.output) if args.output else input_path.with_suffix(input_path.suffix + ".unpack")
    manifest = unpack_ykdat(input_path, output_dir)
    print(f"[done] unpacked: {input_path} -> {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
