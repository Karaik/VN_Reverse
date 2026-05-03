from __future__ import annotations

import argparse
from pathlib import Path

from script.tev2_scr import write_probe


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Studio_e-go_V2 SCR outer-container structure.")
    parser.add_argument("input", type=Path, help="Input .scr file")
    parser.add_argument("output", type=Path, help="Output JSON file")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    write_probe(args.input, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
