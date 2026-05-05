"""CLI app for SAISYS SSB compilation."""

from __future__ import annotations

import argparse
from pathlib import Path

from script.ssb.binary import normalize_text_encoding
from script.ssb.compile import (
    apply_ac07_character_selection_file,
    apply_ac07_visible_clusters_file,
    apply_name_related_records_file,
    apply_text_entries_file,
    compile_project_file,
)


def _discover_project_jsons(root: Path) -> list[Path]:
    matches: list[Path] = []
    if root.is_file() and root.name == "script.json":
        matches.append(root)
    elif root.is_dir():
        direct = root / "script.json"
        if direct.is_file():
            matches.append(direct)
        matches.extend(path for path in root.rglob("script.json") if path != direct)
    unique = sorted({path.resolve(): path for path in matches}.values(), key=lambda path: str(path))
    return unique


def _default_text_entries_path(project_json: Path) -> Path:
    return project_json.parent / "translation_entries.json"


def run_single(
    project_json: Path,
    output_dir: Path,
    *,
    text_entries: Path | None,
    name_related_records: Path | None,
    ac07_visible_clusters: Path | None,
    ac07_character_selection: Path | None,
    target_encoding: str | None,
) -> None:
    if text_entries is not None:
        apply_text_entries_file(project_json, text_entries)
    if name_related_records is not None:
        apply_name_related_records_file(project_json, name_related_records)
    if ac07_visible_clusters is not None:
        apply_ac07_visible_clusters_file(project_json, ac07_visible_clusters)
    if ac07_character_selection is not None:
        apply_ac07_character_selection_file(project_json, ac07_character_selection)
    compile_project_file(project_json, output_dir, text_encoding=target_encoding)


def run_batch(
    input_root: Path,
    output_root: Path,
    *,
    use_default_text_entries: bool,
    target_encoding: str | None,
) -> int:
    project_jsons = _discover_project_jsons(input_root)
    if not project_jsons:
        raise FileNotFoundError(f"No script.json files found under: {input_root}")
    for project_json in project_jsons:
        relative_dir = project_json.parent.relative_to(input_root if input_root.is_dir() else input_root.parent)
        target_dir = output_root if str(relative_dir) == "." else output_root / relative_dir
        text_entries = _default_text_entries_path(project_json) if use_default_text_entries else None
        if use_default_text_entries and not text_entries.is_file():
            raise FileNotFoundError(f"Missing translation_entries.json for batch item: {project_json}")
        name_related_records = project_json.parent / "name_related_records.json"
        ac07_visible_clusters = project_json.parent / "ac07_visible_clusters.json"
        ac07_character_selection = project_json.parent / "ac07_character_selection_records.json"
        run_single(
            project_json,
            target_dir,
            text_entries=text_entries,
            name_related_records=name_related_records if name_related_records.is_file() else None,
            ac07_visible_clusters=ac07_visible_clusters if ac07_visible_clusters.is_file() else None,
            ac07_character_selection=ac07_character_selection if ac07_character_selection.is_file() else None,
            target_encoding=target_encoding,
        )
        print(f"[batch-compile] {project_json} -> {target_dir}")
    print(f"[batch-compile] processed {len(project_jsons)} project files")
    return len(project_jsons)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile SAISYS SSB JSON back into CODE.SSB and DATA.SSB")
    parser.add_argument("project_json", type=Path, help="Path to script.json produced by ssb_decompile.py")
    parser.add_argument("output_dir", type=Path, help="Directory to write CODE.SSB and DATA.SSB")
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Batch mode. Recursively find script.json under project_json and mirror CODE.SSB/DATA.SSB outputs under output_dir.",
    )
    parser.add_argument(
        "--text-entries",
        type=Path,
        help="Optional text_entries.json to apply before compilation",
    )
    parser.add_argument(
        "--name-related-records",
        type=Path,
        help="Optional name_related_records.json to apply before compilation",
    )
    parser.add_argument(
        "--ac07-character-selection",
        type=Path,
        help="Optional ac07_character_selection_records.json to apply before compilation",
    )
    parser.add_argument(
        "--ac07-visible-clusters",
        type=Path,
        help="Optional ac07_visible_clusters.json to apply before compilation",
    )
    parser.add_argument(
        "--text-encoding",
        default=None,
        help="Text encoding used for write-back. Default: use document text_encoding or cp932.",
    )
    parser.add_argument(
        "--use-default-text-entries",
        action="store_true",
        help="In batch mode, apply each sibling translation_entries.json automatically before compilation.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    target_encoding = normalize_text_encoding(args.text_encoding) if args.text_encoding else None
    if args.batch:
        if args.text_entries is not None:
            raise ValueError("--text-entries is not supported together with --batch; use --use-default-text-entries")
        if args.name_related_records is not None:
            raise ValueError("--name-related-records is not supported together with --batch; batch mode loads sibling files automatically")
        if args.ac07_visible_clusters is not None:
            raise ValueError("--ac07-visible-clusters is not supported together with --batch; batch mode loads sibling files automatically")
        if args.ac07_character_selection is not None:
            raise ValueError("--ac07-character-selection is not supported together with --batch; batch mode loads sibling files automatically")
        run_batch(
            args.project_json,
            args.output_dir,
            use_default_text_entries=args.use_default_text_entries,
            target_encoding=target_encoding,
        )
    else:
        run_single(
            args.project_json,
            args.output_dir,
            text_entries=args.text_entries,
            name_related_records=args.name_related_records,
            ac07_visible_clusters=args.ac07_visible_clusters,
            ac07_character_selection=args.ac07_character_selection,
            target_encoding=target_encoding,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
