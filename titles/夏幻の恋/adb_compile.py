#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nbda.adbsrc import parse_adbsrc
from nbda.compile import compile_adb


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile script source back to NBDA.")
    parser.add_argument("input", help="Input .json/.adbsrc file or directory.")
    parser.add_argument("output", nargs="?", help="Output .adb file or directory.")
    parser.add_argument("--verbose", action="store_true", help="Print per-file conversion logs.")
    parser.add_argument(
        "--input-format",
        choices=["auto", "json", "adbsrc"],
        default="auto",
        help="Input source format. Default: auto by extension.",
    )
    return parser


def _detect_format(path: Path, input_format: str) -> str:
    if input_format != "auto":
        return input_format
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".adbsrc":
        return "adbsrc"
    raise ValueError(f"Unsupported file extension for auto format: {path}")


def _iter_source_files(input_path: Path, input_format: str) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        if input_format == "json":
            return sorted(p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() == ".json")
        if input_format == "adbsrc":
            return sorted(p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() == ".adbsrc")
        files = [
            p
            for p in input_path.rglob("*")
            if p.is_file() and p.suffix.lower() in {".json", ".adbsrc"}
        ]
        return sorted(files)
    raise ValueError(f"Input path not found: {input_path}")


def _default_output_for_file(input_file: Path, source_format: str) -> Path:
    if source_format == "json" and input_file.suffix.lower() == ".json":
        return input_file.with_suffix("")
    if source_format == "adbsrc" and input_file.suffix.lower() == ".adbsrc":
        return input_file.with_suffix(".adb")
    return input_file.with_suffix(input_file.suffix + ".adb")


def _resolve_output(
    input_path: Path,
    output_arg: str | None,
    source_files: list[Path],
    input_format: str,
) -> list[tuple[Path, Path, str]]:
    if input_path.is_file():
        fmt = _detect_format(input_path, input_format)
        out = Path(output_arg) if output_arg else _default_output_for_file(input_path, fmt)
        return [(input_path, out, fmt)]

    if not source_files:
        raise ValueError(f"No source files found in directory: {input_path}")

    out_root = Path(output_arg) if output_arg else input_path.with_name(input_path.name + "_adb")
    pairs: list[tuple[Path, Path, str]] = []
    for src in source_files:
        fmt = _detect_format(src, input_format)
        rel = src.relative_to(input_path)
        out_file = out_root / _default_output_for_file(rel, fmt)
        pairs.append((src, out_file, fmt))
    return pairs


def _load_doc(path: Path, source_format: str) -> dict:
    text = path.read_text(encoding="utf-8")
    if source_format == "json":
        return json.loads(text)
    return parse_adbsrc(text)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    source_files = _iter_source_files(input_path, args.input_format)
    pairs = _resolve_output(input_path, args.output, source_files, args.input_format)

    for src, output_path, source_format in pairs:
        doc = _load_doc(src, source_format)
        data = compile_adb(doc)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
        if args.verbose:
            print(f"[ok] {src} ({source_format}) -> {output_path}")

    print(f"[done] converted {len(pairs)} file(s) to ADB.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
