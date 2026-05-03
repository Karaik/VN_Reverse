from __future__ import annotations

import argparse
from pathlib import Path

from script.tev2_bttext import parse_bttext_text, write_text_doc
from script.tev2_scr import parse_scr_text, write_text_doc as write_scr_text_doc
from script.tev2_text_tables import parse_table, write_doc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Decompile TE_V2 text carrier.")
    parser.add_argument("input", type=Path, help="Input text table file.")
    parser.add_argument("output", type=Path, help="Output JSON file.")
    parser.add_argument(
        "--text-encoding",
        default="cp932",
        help="Encoding used to decode text table entries. Supports aliases: win-31j/sjis/cp932.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    head = args.input.read_bytes()[:4]
    if head == b"TSCR":
        doc = parse_bttext_text(args.input, text_encoding=args.text_encoding)
        write_text_doc(args.output, doc)
    elif head == b"SCR ":
        doc = parse_scr_text(args.input, text_encoding=args.text_encoding)
        write_scr_text_doc(args.output, doc)
    else:
        doc = parse_table(args.input, text_encoding=args.text_encoding)
        write_doc(args.output, doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
