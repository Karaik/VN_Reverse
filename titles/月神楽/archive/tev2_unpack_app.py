from __future__ import annotations

import argparse
from pathlib import Path

from archive.tev2_archive import unpack_pak0, write_probe_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe or unpack Studio_e-go_V2 PAK0 archives.")
    parser.add_argument("input", type=Path, help="Input game directory or single .dat archive")
    parser.add_argument("output_dir", type=Path, help="Output directory")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.input.is_dir():
        write_probe_manifest(args.input, args.output_dir)
    else:
        unpack_pak0(args.input, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
