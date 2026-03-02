#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nejii.script_bin import (
    compile_script_bin,
    normalize_text_encoding,
    parse_nejsrc,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile JSON/NEJSRC script to NEJII BIN.")
    parser.add_argument("input", help="Input .json/.nejsrc file or directory.")
    parser.add_argument("output", nargs="?", help="Output .bin file or directory.")
    parser.add_argument("--input-format", choices=["auto", "json", "nejsrc"], default="auto", help="Input format.")
    parser.add_argument(
        "--text-encoding",
        default=None,
        help="Text encoding used for write-back. Default: use document text_encoding or cp932.",
    )
    parser.add_argument(
        "--source-text-encoding",
        default=None,
        help="Source text encoding for filter fallback. Default: use document text_encoding or cp932.",
    )
    parser.add_argument("--verbose", action="store_true", help="Print per-file logs.")
    return parser


def _detect_format(path: Path, force_fmt: str) -> str:
    if force_fmt != "auto":
        return force_fmt
    ext = path.suffix.lower()
    if ext == ".json":
        return "json"
    if ext == ".nejsrc":
        return "nejsrc"
    raise ValueError(f"Unsupported extension for auto format: {path}")


def _iter_inputs(input_path: Path, input_format: str) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        if input_format == "json":
            return sorted(p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() == ".json")
        if input_format == "nejsrc":
            return sorted(p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() == ".nejsrc")
        return sorted(
            p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() in {".json", ".nejsrc"}
        )
    raise ValueError(f"Input path not found: {input_path}")


def _default_output_for_file(path: Path, src_fmt: str) -> Path:
    if src_fmt == "json" and path.suffix.lower() == ".json":
        return path.with_suffix("")
    if src_fmt == "nejsrc" and path.suffix.lower() == ".nejsrc":
        return path.with_suffix(".bin")
    return path.with_suffix(path.suffix + ".bin")


def _resolve_output(
    input_path: Path,
    output_arg: str | None,
    files: list[Path],
    input_format: str,
) -> list[tuple[Path, Path, str]]:
    if input_path.is_file():
        fmt = _detect_format(input_path, input_format)
        out = Path(output_arg) if output_arg else _default_output_for_file(input_path, fmt)
        return [(input_path, out, fmt)]
    if not files:
        raise ValueError(f"No source files found in directory: {input_path}")
    out_root = Path(output_arg) if output_arg else input_path.with_name(input_path.name + "_bin")
    pairs: list[tuple[Path, Path, str]] = []
    for src in files:
        fmt = _detect_format(src, input_format)
        rel = src.relative_to(input_path)
        out = out_root / _default_output_for_file(rel, fmt)
        pairs.append((src, out, fmt))
    return pairs


def _load_doc(path: Path, fmt: str) -> dict:
    text = path.read_text(encoding="utf-8")
    if fmt == "json":
        return json.loads(text)
    return parse_nejsrc(text)


def _load_filters_for_source(src: Path) -> list[str] | None:
    filter_path = src.parent / "filter_text.txt"
    if not filter_path.is_file():
        return None
    lines = [line.strip() for line in filter_path.read_text(encoding="utf-8").splitlines()]
    filters = [line for line in lines if line]
    return filters if filters else None


def main() -> int:
    args = build_parser().parse_args()
    target_encoding = normalize_text_encoding(args.text_encoding) if args.text_encoding else None
    source_encoding = normalize_text_encoding(args.source_text_encoding) if args.source_text_encoding else None
    input_path = Path(args.input)
    files = _iter_inputs(input_path, args.input_format)
    pairs = _resolve_output(input_path, args.output, files, args.input_format)
    for src, dst, fmt in pairs:
        doc = _load_doc(src, fmt)
        filters = _load_filters_for_source(src)
        data = compile_script_bin(
            doc=doc,
            text_encoding=target_encoding,
            source_text_encoding=source_encoding,
            fallback_filters=filters,
        )
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        if args.verbose:
            active_encoding = target_encoding or doc.get("text_encoding", "cp932")
            filter_count = len(filters) if filters else 0
            print(f"[ok] {src} ({fmt}) -> {dst} (encoding={active_encoding}, filters={filter_count})")
    if target_encoding:
        print(f"[done] compiled {len(pairs)} file(s) to BIN (encoding={target_encoding}).")
    else:
        print(f"[done] compiled {len(pairs)} file(s) to BIN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
