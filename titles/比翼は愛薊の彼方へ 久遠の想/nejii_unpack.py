#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from nejii.rk1 import unpack_rk1

ARCHIVE_EXTS = {".dat", ".vdt", ".cdt", ".ovd", ".pdt"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unpack NEJII RK1 archives.")
    parser.add_argument("input", help="Input archive file or directory.")
    parser.add_argument("output", nargs="?", help="Output directory or root directory.")
    parser.add_argument("--verbose", action="store_true", help="Print per-file logs.")
    return parser


def _iter_inputs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(
            p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() in ARCHIVE_EXTS
        )
    raise ValueError(f"Input path not found: {input_path}")


def _default_output_for_file(src: Path) -> Path:
    return src.with_name(src.stem + "_unpack")


def _resolve_output(input_path: Path, output_arg: str | None, files: list[Path]) -> list[tuple[Path, Path]]:
    if input_path.is_file():
        out = Path(output_arg) if output_arg else _default_output_for_file(input_path)
        return [(input_path, out)]
    if not files:
        raise ValueError(f"No RK1 archives found in directory: {input_path}")
    out_root = Path(output_arg) if output_arg else input_path.with_name(input_path.name + "_unpack")
    pairs: list[tuple[Path, Path]] = []
    for src in files:
        rel = src.relative_to(input_path)
        out = out_root / rel.with_suffix("")
        pairs.append((src, out))
    return pairs


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    files = _iter_inputs(input_path)
    pairs = _resolve_output(input_path, args.output, files)
    for src, out_dir in pairs:
        manifest = unpack_rk1(src, out_dir)
        if args.verbose:
            print(f"[ok] {src} -> {manifest}")
    print(f"[done] unpacked {len(pairs)} archive(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
