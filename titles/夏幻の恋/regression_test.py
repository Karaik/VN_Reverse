#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import shutil
from pathlib import Path

import csaf_pack
import csaf_unpack
from nbda.adbsrc import parse_adbsrc, render_ir_adbsrc
from nbda.compile import compile_adb
from nbda.decompile import parse_adb, parse_adb_ir


def run_adb_roundtrip(game_dir: Path) -> None:
    adb_dir = game_dir / "Family Adv System"
    adb_files = sorted(adb_dir.glob("*.adb"))
    if not adb_files:
        raise RuntimeError(f"No script files found: {adb_dir}")

    for adb_path in adb_files:
        original = adb_path.read_bytes()
        doc = parse_adb(original)
        rebuilt = compile_adb(doc)
        if rebuilt != original:
            raise RuntimeError(f"ADB regression failed: {adb_path.name}")


def run_adb_ir_roundtrip(game_dir: Path) -> None:
    adb_dir = game_dir / "Family Adv System"
    adb_files = sorted(adb_dir.glob("*.adb"))
    if not adb_files:
        raise RuntimeError(f"No script files found: {adb_dir}")

    editable_slot_total = 0
    for adb_path in adb_files:
        original = adb_path.read_bytes()
        doc = parse_adb_ir(original)
        editable_slot_total += sum(1 for entry in doc["entries"] if entry.get("editable_text"))
        rebuilt = compile_adb(doc)
        if rebuilt != original:
            raise RuntimeError(f"ADB IR regression failed: {adb_path.name}")
    if editable_slot_total == 0:
        raise RuntimeError("ADB IR regression failed: no editable text slots detected.")


def run_adbsrc_roundtrip(game_dir: Path) -> None:
    adb_dir = game_dir / "Family Adv System"
    adb_files = sorted(adb_dir.glob("*.adb"))
    if not adb_files:
        raise RuntimeError(f"No script files found: {adb_dir}")

    editable_slot_total = 0
    for adb_path in adb_files:
        original = adb_path.read_bytes()
        doc = parse_adb_ir(original)
        editable_slot_total += sum(1 for entry in doc["entries"] if entry.get("editable_text"))
        src_text = render_ir_adbsrc(doc)
        parsed_doc = parse_adbsrc(src_text)
        rebuilt = compile_adb(parsed_doc)
        if rebuilt != original:
            raise RuntimeError(f"ADBSRC regression failed: {adb_path.name}")
    if editable_slot_total == 0:
        raise RuntimeError("ADBSRC regression failed: no editable text slots detected.")


def _slot_map(doc: dict) -> dict[int, dict]:
    return {int(slot["slot_id"]): slot for slot in list(doc.get("slots", []))}


def _entry_text(doc: dict, entry_index: int) -> str:
    entries = list(doc.get("entries", []))
    if entry_index < 0 or entry_index >= len(entries):
        raise RuntimeError(f"Entry index out of range: {entry_index}")
    entry = entries[entry_index]
    slot_id = int(entry["slot_id"])
    slots = _slot_map(doc)
    if slot_id not in slots:
        raise RuntimeError(f"Entry points to missing slot_id: {slot_id}")
    slot = slots[slot_id]
    if not slot.get("editable_text", False):
        raise RuntimeError(f"Entry is not editable text: {entry_index}")
    return str(slot.get("text", ""))


def run_text_length_change_regression(game_dir: Path) -> None:
    adb_dir = game_dir / "Family Adv System"
    adb_files = sorted(adb_dir.glob("*.adb"))
    if not adb_files:
        raise RuntimeError(f"No script files found: {adb_dir}")

    checked = 0
    for adb_path in adb_files:
        original = adb_path.read_bytes()
        doc = parse_adb_ir(original)
        entries = list(doc.get("entries", []))
        editable_entry_index = next((i for i, e in enumerate(entries) if e.get("editable_text")), None)
        if editable_entry_index is None:
            continue

        checked += 1
        editable_entry = entries[editable_entry_index]
        target_slot_id = int(editable_entry["slot_id"])
        mutated_doc = copy.deepcopy(doc)
        target_slot = next(
            (s for s in mutated_doc["slots"] if int(s["slot_id"]) == target_slot_id),
            None,
        )
        if target_slot is None:
            raise RuntimeError(f"Editable slot not found during mutation: {adb_path.name}")

        base_text = str(target_slot.get("text", ""))
        new_text = base_text + " [LEN_EXPAND_0123456789]"
        target_slot["text"] = new_text

        rebuilt = compile_adb(mutated_doc)
        reparsed = parse_adb_ir(rebuilt)
        reparsed_text = _entry_text(reparsed, editable_entry_index)
        if reparsed_text != new_text:
            raise RuntimeError(f"Length-change IR regression failed: {adb_path.name}")

        rebuilt_again = compile_adb(reparsed)
        if rebuilt_again != rebuilt:
            raise RuntimeError(f"Length-change IR rebuild instability: {adb_path.name}")

        src_text = render_ir_adbsrc(mutated_doc)
        src_doc = parse_adbsrc(src_text)
        rebuilt_from_src = compile_adb(src_doc)
        reparsed_src = parse_adb_ir(rebuilt_from_src)
        reparsed_src_text = _entry_text(reparsed_src, editable_entry_index)
        if reparsed_src_text != new_text:
            raise RuntimeError(f"Length-change ADBSRC regression failed: {adb_path.name}")

    if checked == 0:
        raise RuntimeError("Length-change regression failed: no editable text entries found.")


def run_csaf_roundtrip(game_dir: Path, tmp_dir: Path, archives: list[str]) -> None:
    for name in archives:
        src = game_dir / name
        unpack_dir = tmp_dir / f"unpack_{name}"
        manifest = csaf_unpack.unpack_archive(src, unpack_dir, {})
        repacked = tmp_dir / f"{name}.repack"
        csaf_pack.pack_archive(manifest, repacked, update_checksum=False)
        if repacked.read_bytes() != src.read_bytes():
            raise RuntimeError(f"CSAF regression failed: {name}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Regression test: ADB(raw/ir/adbsrc) roundtrip, text-length mutation, and CSAF roundtrip."
    )
    parser.add_argument("--game-dir", default="game", help="Game directory. Default: ./game")
    parser.add_argument("--tmp-dir", default="_regression_tmp", help="Temporary directory. Default: ./_regression_tmp")
    parser.add_argument("--archives", nargs="+", default=["adv", "system"], help="Archive list for pack/unpack regression.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    root = Path.cwd()
    game_dir = (root / args.game_dir).resolve()
    tmp_dir = (root / args.tmp_dir).resolve()

    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    run_adb_roundtrip(game_dir)
    run_adb_ir_roundtrip(game_dir)
    run_adbsrc_roundtrip(game_dir)
    run_text_length_change_regression(game_dir)
    run_csaf_roundtrip(game_dir, tmp_dir, args.archives)
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
