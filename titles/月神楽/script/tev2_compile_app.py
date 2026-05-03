from __future__ import annotations

import argparse
import json
from pathlib import Path

from script.tev2_bttext import compile_bttext
from script.tev2_scr import compile_scr_text
from script.tev2_text_tables import compile_table


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile TE_V2 text carrier JSON.")
    parser.add_argument("input", type=Path, help="Input JSON file.")
    parser.add_argument("output", type=Path, help="Output table file.")
    parser.add_argument(
        "--text-encoding",
        default="cp932",
        help="Encoding used for write-back. Supports aliases: win-31j/sjis/cp932.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    doc = json.loads(args.input.read_text(encoding="utf-8"))
    if str(doc.get("format")) == "TE_V2_BTTEXT_TEXT":
        data = compile_bttext(doc, text_encoding=args.text_encoding)
    elif str(doc.get("format")) == "TE_V2_SCR_TEXT_CANDIDATES":
        data = compile_scr_text(doc, text_encoding=args.text_encoding)
    else:
        data = compile_table(doc, text_encoding=args.text_encoding)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
