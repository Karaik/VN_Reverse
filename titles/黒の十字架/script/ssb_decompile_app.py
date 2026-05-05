"""CLI app for SAISYS SSB decompilation."""

from __future__ import annotations

import argparse
from pathlib import Path

from script.ssb.binary import normalize_text_encoding
from script.ssb.decompile import write_project


def _discover_script_dirs(root: Path) -> list[Path]:
    matches: list[Path] = []
    if (root / "CODE.SSB").is_file() and (root / "DATA.SSB").is_file():
        matches.append(root)
    for code_path in root.rglob("CODE.SSB"):
        script_dir = code_path.parent
        if script_dir == root:
            continue
        if (script_dir / "DATA.SSB").is_file():
            matches.append(script_dir)
    unique = sorted({path.resolve(): path for path in matches}.values(), key=lambda path: str(path))
    return unique


def run_single(script_dir: Path, output_dir: Path, text_encoding: str) -> None:
    write_project(script_dir, output_dir, text_encoding=text_encoding)


def run_batch(input_root: Path, output_root: Path, text_encoding: str) -> int:
    script_dirs = _discover_script_dirs(input_root)
    if not script_dirs:
        raise FileNotFoundError(f"No CODE.SSB / DATA.SSB pairs found under: {input_root}")
    for script_dir in script_dirs:
        relative = script_dir.relative_to(input_root)
        target_dir = output_root if str(relative) == "." else output_root / relative
        write_project(script_dir, target_dir, text_encoding=text_encoding)
        print(f"[batch-decompile] {script_dir} -> {target_dir}")
    print(f"[batch-decompile] processed {len(script_dirs)} script directories")
    return len(script_dirs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Decompile SAISYS SSB scripts into JSON and readable source.")
    parser.add_argument("script_dir", type=Path, help="Directory containing CODE.SSB and DATA.SSB")
    parser.add_argument("output_dir", type=Path, help="Output directory for JSON and SSBSRC")
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Batch mode. Recursively find CODE.SSB/DATA.SSB pairs under script_dir and mirror outputs under output_dir.",
    )
    parser.add_argument(
        "--text-encoding",
        default="cp932",
        help="Encoding used to decode script text. Supports aliases: win-31j/sjis/cp932.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    text_encoding = normalize_text_encoding(args.text_encoding)
    if args.batch:
        run_batch(args.script_dir, args.output_dir, text_encoding=text_encoding)
    else:
        run_single(args.script_dir, args.output_dir, text_encoding=text_encoding)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
