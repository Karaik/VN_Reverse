#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from yuka.ykdat import pack_ykdat


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pack YKC archive from manifest + files.")
    parser.add_argument("manifest", help="Input manifest.json.")
    parser.add_argument("output", nargs="?", help="Output .dat file.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_file():
        raise ValueError(f"Manifest not found: {manifest_path}")
    output_path = Path(args.output) if args.output else manifest_path.with_name("repack.dat")
    pack_ykdat(manifest_path, output_path)
    print(f"[done] packed: {manifest_path} -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
