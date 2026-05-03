"""CLI app for SAISYS SSB compilation."""

from __future__ import annotations

import argparse
from pathlib import Path

from script.ssb.binary import normalize_text_encoding
from script.ssb.compile import apply_text_entries_file, compile_project_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile SAISYS SSB JSON back into CODE.SSB and DATA.SSB")
    parser.add_argument("project_json", type=Path, help="Path to script.json produced by ssb_decompile.py")
    parser.add_argument("output_dir", type=Path, help="Directory to write CODE.SSB and DATA.SSB")
    parser.add_argument(
        "--text-entries",
        type=Path,
        help="Optional text_entries.json to apply before compilation",
    )
    parser.add_argument(
        "--text-encoding",
        default=None,
        help="Text encoding used for write-back. Default: use document text_encoding or cp932.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.text_entries is not None:
        apply_text_entries_file(args.project_json, args.text_entries)
    target_encoding = normalize_text_encoding(args.text_encoding) if args.text_encoding else None
    compile_project_file(args.project_json, args.output_dir, text_encoding=target_encoding)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
