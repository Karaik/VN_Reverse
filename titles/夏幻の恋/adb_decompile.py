#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nbda.adbsrc import render_ir_adbsrc
from nbda.decompile import parse_adb, parse_adb_ir, validate_magic


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Decompile NBDA script.")
    parser.add_argument("input", help="Input .adb file or directory.")
    parser.add_argument("output", nargs="?", help="Output file or directory.")
    parser.add_argument("--verbose", action="store_true", help="Print per-file conversion logs.")
    parser.add_argument(
        "--mode",
        choices=["ir", "raw"],
        default="ir",
        help="Intermediate mode. ir: instruction-level structure. raw: byte-exact structure.",
    )
    parser.add_argument(
        "--output-format",
        choices=["json", "adbsrc"],
        default="json",
        help="Output format. Default: json.",
    )
    return parser


def _iter_adb_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() == ".adb")
    raise ValueError(f"Input path not found: {input_path}")


def _default_output_for_file(input_file: Path, output_format: str) -> Path:
    if output_format == "json":
        return input_file.with_suffix(input_file.suffix + ".json")
    return input_file.with_suffix(".adbsrc")


def _default_output_for_relpath(rel: Path, output_format: str) -> Path:
    if output_format == "json":
        return rel.with_suffix(rel.suffix + ".json")
    return rel.with_suffix(".adbsrc")


def _resolve_output(
    input_path: Path,
    output_arg: str | None,
    adb_files: list[Path],
    output_format: str,
) -> list[tuple[Path, Path]]:
    if input_path.is_file():
        out = Path(output_arg) if output_arg else _default_output_for_file(input_path, output_format)
        return [(input_path, out)]

    if not adb_files:
        raise ValueError(f"No .adb files found in directory: {input_path}")

    suffix = "json" if output_format == "json" else "adbsrc"
    out_root = Path(output_arg) if output_arg else input_path.with_name(input_path.name + f"_{suffix}")
    pairs: list[tuple[Path, Path]] = []
    for adb_file in adb_files:
        rel = adb_file.relative_to(input_path)
        out_file = out_root / _default_output_for_relpath(rel, output_format)
        pairs.append((adb_file, out_file))
    return pairs


def _serialize(doc: dict, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(doc, ensure_ascii=False, indent=2)
    return render_ir_adbsrc(doc)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.output_format == "adbsrc" and args.mode != "ir":
        raise ValueError("ADBSRC output only supports ir mode.")

    input_path = Path(args.input)
    adb_files = _iter_adb_files(input_path)
    pairs = _resolve_output(input_path, args.output, adb_files, args.output_format)

    total_entries = 0
    editable_entries = 0
    for adb_file, output_path in pairs:
        data = adb_file.read_bytes()
        doc = parse_adb(data) if args.mode == "raw" else parse_adb_ir(data)
        validate_magic(doc)
        output_text = _serialize(doc, args.output_format)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
        if args.mode == "ir":
            total_entries += int(doc.get("entry_count", 0))
            editable_entries += int(doc.get("editable_entry_count", 0))
        if args.verbose:
            print(f"[ok] {adb_file} -> {output_path}")

    print(f"[done] converted {len(pairs)} file(s) to {args.output_format} (mode={args.mode}).")
    if args.mode == "ir":
        print(f"[stats] editable entries: {editable_entries}/{total_entries}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
