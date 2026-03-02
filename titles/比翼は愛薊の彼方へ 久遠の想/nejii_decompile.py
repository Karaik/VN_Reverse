#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nejii.script_bin import parse_script_bin, render_nejsrc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Decompile NEJII script BIN to JSON or NEJSRC.")
    parser.add_argument("input", help="Input .bin file or directory.")
    parser.add_argument("output", nargs="?", help="Output file or directory.")
    parser.add_argument("--output-format", choices=["json", "nejsrc"], default="json", help="Output format.")
    parser.add_argument(
        "--text-encoding",
        default="cp932",
        help="Encoding used to decode script text. Supports aliases: win-31j/sjis/cp932.",
    )
    parser.add_argument("--verbose", action="store_true", help="Print per-file logs.")
    return parser


def _iter_inputs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(
            p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() == ".bin"
        )
    raise ValueError(f"Input path not found: {input_path}")


def _default_output_for_file(path: Path, output_format: str) -> Path:
    if output_format == "json":
        return path.with_suffix(path.suffix + ".json")
    return path.with_suffix(path.suffix + ".nejsrc")


def _resolve_output(input_path: Path, output_arg: str | None, files: list[Path], output_format: str) -> list[tuple[Path, Path]]:
    if input_path.is_file():
        out = Path(output_arg) if output_arg else _default_output_for_file(input_path, output_format)
        return [(input_path, out)]
    if not files:
        raise ValueError(f"No .bin files found in directory: {input_path}")
    suffix = "json" if output_format == "json" else "nejsrc"
    out_root = Path(output_arg) if output_arg else input_path.with_name(input_path.name + f"_{suffix}")
    pairs: list[tuple[Path, Path]] = []
    for src in files:
        rel = src.relative_to(input_path)
        out = out_root / _default_output_for_file(rel, output_format)
        pairs.append((src, out))
    return pairs


def _render(doc: dict, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(doc, ensure_ascii=False, indent=2)
    return render_nejsrc(doc)


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    files = _iter_inputs(input_path)
    pairs = _resolve_output(input_path, args.output, files, args.output_format)
    for src, dst in pairs:
        doc = parse_script_bin(src.read_bytes(), text_encoding=args.text_encoding)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(_render(doc, args.output_format), encoding="utf-8")
        if args.verbose:
            print(f"[ok] {src} -> {dst} (encoding={doc.get('text_encoding')})")
    print(f"[done] decompiled {len(pairs)} file(s) to {args.output_format}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
