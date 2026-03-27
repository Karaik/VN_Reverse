from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.csaf_raw import infer_output_class, infer_resource_kind
from archive.resource_recovery import recover_resource_tree


KNOWN_ARCHIVES = ["system", "adv", "bg", "ch", "ev", "voice", "BGM", "SE", "song"]
FINAL_MANIFEST_NAME = "资源清单.json"


def detect_archives(game_dir: Path) -> list[str]:
    return [name for name in KNOWN_ARCHIVES if (game_dir / name).is_file()]


def clean_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def move_if_exists(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        clean_path(dst)
    shutil.move(str(src), str(dst))


def _human_recovery_status(output_class: str) -> str:
    if output_class == "final":
        return "已恢复原名与原目录"
    if output_class == "partial":
        return "待补原名"
    if output_class.endswith("unresolved_name_and_dir"):
        return "待补原目录与原名"
    if output_class.endswith("unresolved_name"):
        return "待补原名"
    return "待确认"


def build_root_summary(
    out_dir: Path,
    game_dir: Path,
    processed_archives: list[str],
    per_archive_meta: dict[str, str],
) -> dict:
    script_dirs: set[str] = set()
    image_dirs: set[str] = set()
    system_dirs: set[str] = set()
    unknown_dirs: set[str] = set()
    fully_recovered_examples: list[str] = []
    partial_recovery_examples: list[str] = []
    per_kind_counts = Counter()
    per_state_counts = Counter()
    per_dir_counts: dict[str, Counter] = defaultdict(Counter)
    human_entries: list[dict] = []

    for archive_name, meta_path in per_archive_meta.items():
        manifest = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        for entry in manifest.get("entries", []):
            rel = Path(entry["file"])
            output_class = entry.get("output_class") or infer_output_class(rel, bool(entry.get("resolved_name")))
            resource_kind = entry.get("resource_kind") or infer_resource_kind(rel)
            parent = rel.parent.as_posix()

            per_kind_counts[resource_kind] += 1
            per_state_counts[output_class] += 1
            per_dir_counts[output_class][parent] += 1

            if resource_kind == "script":
                script_dirs.add(parent)
            if output_class.startswith(("unknown", "pending")):
                unknown_dirs.add(parent)
            elif resource_kind == "image":
                image_dirs.add(parent)

            if rel.parts and rel.parts[0] == "system":
                system_dirs.add(parent)
            elif rel.parts and rel.parts[0] == "unknown" and len(rel.parts) > 1 and rel.parts[1] == "system":
                system_dirs.add(parent)

            if entry.get("resolved_name") and len(fully_recovered_examples) < 80:
                fully_recovered_examples.append(rel.as_posix())
            if output_class == "partial" and len(partial_recovery_examples) < 80:
                partial_recovery_examples.append(rel.as_posix())

            evidence_sources = entry.get("evidence_sources") or ["包内目录项"]
            human_entries.append(
                {
                    "archive": archive_name,
                    "original_path": entry.get("original_path"),
                    "current_path": rel.as_posix(),
                    "resource_category": resource_kind,
                    "recovery_status": _human_recovery_status(output_class),
                    "evidence_sources": evidence_sources,
                    "evidence_files": entry.get("evidence_files") or [],
                    "archive_hash_hex": entry.get("hash_hex"),
                    "archive_entry_index": entry.get("index"),
                    "archive_original_size": entry.get("size"),
                }
            )

    return {
        "title": "澶忓够銇亱",
        "goal": "recover_original_resource_tree",
        "game_dir": game_dir.as_posix(),
        "archives": processed_archives,
        "final_root": out_dir.as_posix(),
        "final_dirs": sorted(
            {
                *[name for name in processed_archives if (out_dir / name).exists()],
            }
        ),
        "entrypoint_answers": {
            "scripts_where": sorted(script_dirs),
            "images_where": sorted(image_dirs),
            "system_resources_where": sorted(system_dirs),
            "unknown_resources_where": sorted(unknown_dirs),
            "fully_recovered_name_examples": fully_recovered_examples,
            "partially_recovered_examples": partial_recovery_examples,
        },
        "summary": {
            "by_resource_kind": dict(per_kind_counts),
            "by_recovery_state": dict(per_state_counts),
            "recovery_state_dirs": {state: dict(counter) for state, counter in per_dir_counts.items()},
        },
        "entries": human_entries,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recover original resource tree from the game archives.")
    parser.add_argument("game_dir", help="Game directory that contains adv/system/bg/ch/ev/voice/BGM/SE/song.")
    parser.add_argument("out_dir", help="Output directory for recovered resource tree.")
    return parser


def recover_all_resources(
    title_root: Path,
    game_dir: Path,
    out_dir: Path,
    *,
    debug_root: Path | None = None,
) -> dict:
    archives = detect_archives(game_dir)
    if not archives:
        raise ValueError(f"No known archives found under: {game_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)
    if debug_root is not None:
        debug_root.mkdir(parents=True, exist_ok=True)
        meta_root = debug_root / "meta"
        meta_root.mkdir(parents=True, exist_ok=True)
    else:
        meta_root = None

    per_archive_meta: dict[str, str] = {}
    with TemporaryDirectory(prefix="vn_reverse_recover_") as stage_root_text:
        stage_root = Path(stage_root_text)
        for archive_name in archives:
            archive_path = game_dir / archive_name
            stage_dir = stage_root / f"stage_{archive_name}"
            stage_dir.mkdir(parents=True, exist_ok=True)

            stage_manifest = recover_resource_tree(title_root, archive_path, stage_dir, extra_search_roots=[out_dir])
            per_archive_meta[archive_name] = stage_manifest.as_posix()

            move_if_exists(stage_dir / archive_name, out_dir / archive_name)
            if meta_root is not None:
                final_meta = meta_root / f"{archive_name}.resource_tree.json"
                move_if_exists(stage_manifest, final_meta)
                per_archive_meta[archive_name] = final_meta.as_posix()
        summary = build_root_summary(out_dir, game_dir, archives, per_archive_meta)
        (out_dir / FINAL_MANIFEST_NAME).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if debug_root is not None:
        debug_summary = dict(summary)
        debug_summary["per_archive_meta"] = per_archive_meta
        debug_summary["meta_root"] = meta_root.as_posix() if meta_root else ""
        summary_path = debug_root / "resource_tree.json"
        summary_path.write_text(json.dumps(debug_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    title_root = Path(__file__).resolve().parent.parent
    game_dir = Path(args.game_dir)
    out_dir = Path(args.out_dir)
    recover_all_resources(title_root, game_dir, out_dir)
    print(out_dir.as_posix())
    return 0
