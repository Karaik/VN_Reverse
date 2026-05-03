"""CLI app for SAISYS SSB decompilation."""

from __future__ import annotations

import argparse
from pathlib import Path

from script.ssb.binary import normalize_text_encoding
from script.ssb.decompile import write_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Decompile SAISYS SSB scripts into JSON and readable source.")
    parser.add_argument("script_dir", type=Path, help="Directory containing CODE.SSB and DATA.SSB")
    parser.add_argument("output_dir", type=Path, help="Output directory for JSON and SSBSRC")
    parser.add_argument(
        "--text-encoding",
        default="cp932",
        help="Encoding used to decode script text. Supports aliases: win-31j/sjis/cp932.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    write_project(args.script_dir, args.output_dir, text_encoding=normalize_text_encoding(args.text_encoding))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
