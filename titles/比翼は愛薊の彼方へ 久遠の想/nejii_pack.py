#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nejii.rk1 import pack_rk1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pack NEJII RK1 archives from manifest.")
    parser.add_argument("input", help="Input manifest.json file or directory.")
    parser.add_argument("output", nargs="?", help="Output archive file or root directory.")
    parser.add_argument("--verbose", action="store_true", help="Print per-file logs.")
    return parser


def _iter_inputs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(
            p for p in input_path.rglob("manifest.json") if p.is_file()
        )
    raise ValueError(f"Input path not found: {input_path}")


def _archive_name_from_manifest(manifest_path: Path) -> str:
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    name = str(doc.get("archive_name", ""))
    if not name:
        name = manifest_path.parent.name + ".dat"
    return name


def _resolve_output(input_path: Path, output_arg: str | None, manifests: list[Path]) -> list[tuple[Path, Path]]:
    if input_path.is_file():
        if output_arg:
            return [(input_path, Path(output_arg))]
        name = _archive_name_from_manifest(input_path)
        return [(input_path, input_path.with_name(name))]
    if not manifests:
        raise ValueError(f"No manifest.json found in directory: {input_path}")
    out_root = Path(output_arg) if output_arg else input_path.with_name(input_path.name + "_repack")
    pairs: list[tuple[Path, Path]] = []
    for mf in manifests:
        rel = mf.parent.relative_to(input_path)
        out = out_root / rel / _archive_name_from_manifest(mf)
        pairs.append((mf, out))
    return pairs


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    manifests = _iter_inputs(input_path)
    pairs = _resolve_output(input_path, args.output, manifests)
    for manifest_path, out_path in pairs:
        pack_rk1(manifest_path, out_path)
        if args.verbose:
            print(f"[ok] {manifest_path} -> {out_path}")
    print(f"[done] packed {len(pairs)} archive(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
