from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import struct
from pathlib import Path

from archive.csaf_decoded import decode_extra_region, unpack_decoded_archive
from archive.recover_resources_app import recover_all_resources
from archive.csaf_raw import pack_raw_archive, unpack_raw_archive
from archive.resource_tree_pack import build_resource_tree_name_map_for_archive, pack_resource_tree_archive
from script.adb_compile_app import (
    iter_source_files as iter_compile_source_files,
    load_doc as load_compile_doc,
    resolve_output as resolve_compile_output,
)
from script.adb_decompile_app import (
    iter_adb_files as iter_decompile_adb_files,
    resolve_output as resolve_decompile_output,
    serialize_doc as serialize_decompile_doc,
)
from script.nbda.adbsrc import parse_adbsrc, render_ir_adbsrc
from script.nbda.compile import compile_adb
from script.nbda.decompile import parse_adb, parse_adb_ir


def resolve_adb_dir(game_dir: Path, tmp_dir: Path) -> Path:
    recovered_adv_dir = tmp_dir / "resource_tree" / "adv"
    if recovered_adv_dir.is_dir() and any(recovered_adv_dir.rglob("*.adb")):
        return recovered_adv_dir
    raise RuntimeError(f"Recovered script tree not found: {recovered_adv_dir}")


def run_adb_roundtrip(game_dir: Path, tmp_dir: Path) -> None:
    adb_dir = resolve_adb_dir(game_dir, tmp_dir)
    adb_files = sorted(adb_dir.rglob("*.adb"))
    if not adb_files:
        raise RuntimeError(f"No script files found: {adb_dir}")

    for adb_path in adb_files:
        original = adb_path.read_bytes()
        doc = parse_adb(original)
        rebuilt = compile_adb(doc)
        if rebuilt != original:
            raise RuntimeError(f"ADB regression failed: {adb_path.name}")


def run_adb_ir_roundtrip(game_dir: Path, tmp_dir: Path) -> None:
    adb_dir = resolve_adb_dir(game_dir, tmp_dir)
    adb_files = sorted(adb_dir.rglob("*.adb"))
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


def run_adbsrc_roundtrip(game_dir: Path, tmp_dir: Path) -> None:
    adb_dir = resolve_adb_dir(game_dir, tmp_dir)
    adb_files = sorted(adb_dir.rglob("*.adb"))
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


def _entry_slot(doc: dict, entry_index: int) -> dict:
    entries = list(doc.get("entries", []))
    if entry_index < 0 or entry_index >= len(entries):
        raise RuntimeError(f"Entry index out of range: {entry_index}")
    entry = entries[entry_index]
    slot_id = int(entry["slot_id"])
    slots = _slot_map(doc)
    if slot_id not in slots:
        raise RuntimeError(f"Entry points to missing slot_id: {slot_id}")
    return slots[slot_id]


def run_text_length_change_regression(game_dir: Path, tmp_dir: Path) -> None:
    adb_dir = resolve_adb_dir(game_dir, tmp_dir)
    adb_files = sorted(adb_dir.rglob("*.adb"))
    if not adb_files:
        raise RuntimeError(f"No script files found: {adb_dir}")

    checked = 0
    for adb_path in adb_files:
        original = adb_path.read_bytes()
        doc = parse_adb_ir(original)
        entries = list(doc.get("entries", []))
        editable_entry_index = next(
            (
                i
                for i, entry in enumerate(entries)
                if entry.get("editable_text") and _entry_slot(doc, i).get("text_role") == "dialogue"
            ),
            None,
        )
        if editable_entry_index is None:
            continue

        checked += 1
        editable_entry = entries[editable_entry_index]
        target_slot_id = int(editable_entry["slot_id"])
        mutated_doc = copy.deepcopy(doc)
        target_slot = next((slot for slot in mutated_doc["slots"] if int(slot["slot_id"]) == target_slot_id), None)
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
        raise RuntimeError("Length-change regression failed: no editable dialogue entries found.")


def run_speaker_name_change_regression(game_dir: Path, tmp_dir: Path) -> None:
    adb_dir = resolve_adb_dir(game_dir, tmp_dir)
    adb_files = sorted(adb_dir.rglob("*.adb"))
    if not adb_files:
        raise RuntimeError(f"No script files found: {adb_dir}")

    checked = 0
    for adb_path in adb_files:
        original = adb_path.read_bytes()
        doc = parse_adb_ir(original)
        entries = list(doc.get("entries", []))
        speaker_entry_index = next(
            (
                i
                for i, entry in enumerate(entries)
                if entry.get("editable_text") and _entry_slot(doc, i).get("text_role") == "speaker_name"
            ),
            None,
        )
        if speaker_entry_index is None:
            continue

        checked += 1
        speaker_entry = entries[speaker_entry_index]
        target_slot_id = int(speaker_entry["slot_id"])
        mutated_doc = copy.deepcopy(doc)
        target_slot = next((slot for slot in mutated_doc["slots"] if int(slot["slot_id"]) == target_slot_id), None)
        if target_slot is None:
            raise RuntimeError(f"Speaker-name slot not found during mutation: {adb_path.name}")

        base_name = str(target_slot.get("speaker_name", target_slot.get("text", "")))
        new_name = base_name + " [SPK]"
        target_slot["speaker_name"] = new_name
        target_slot["text"] = new_name

        rebuilt = compile_adb(mutated_doc)
        reparsed = parse_adb_ir(rebuilt)
        reparsed_name = _entry_text(reparsed, speaker_entry_index)
        if reparsed_name != new_name:
            raise RuntimeError(f"Speaker-name IR regression failed: {adb_path.name}")

        rebuilt_again = compile_adb(reparsed)
        if rebuilt_again != rebuilt:
            raise RuntimeError(f"Speaker-name IR rebuild instability: {adb_path.name}")

        src_text = render_ir_adbsrc(mutated_doc)
        src_doc = parse_adbsrc(src_text)
        rebuilt_from_src = compile_adb(src_doc)
        reparsed_src = parse_adb_ir(rebuilt_from_src)
        reparsed_src_name = _entry_text(reparsed_src, speaker_entry_index)
        if reparsed_src_name != new_name:
            raise RuntimeError(f"Speaker-name ADBSRC regression failed: {adb_path.name}")

        linked_dialogue_index = next(
            (
                i
                for i, entry in enumerate(reparsed_src.get("entries", []))
                if int(entry.get("speaker_name_slot_id", -1)) == target_slot_id
            ),
            None,
        )
        if linked_dialogue_index is not None:
            linked_slot = _entry_slot(reparsed_src, linked_dialogue_index)
            if linked_slot.get("speaker_name") != new_name:
                raise RuntimeError(f"Speaker-name link regression failed: {adb_path.name}")

    if checked == 0:
        raise RuntimeError("Speaker-name regression failed: no editable speaker-name entries found.")


def run_resource_tree_script_workflow_regression(tmp_dir: Path) -> tuple[Path, str]:
    adv_dir = tmp_dir / "resource_tree" / "adv"
    if not adv_dir.is_dir():
        raise RuntimeError(f"Workflow regression failed: missing recovered adv root: {adv_dir}")

    adbsrc_root = tmp_dir / "adv_adbsrc"
    json_root = tmp_dir / "adv_json"
    work_tree = tmp_dir / "resource_tree_work"
    for path in [adbsrc_root, json_root, work_tree]:
        if path.exists():
            shutil.rmtree(path)

    adb_files = iter_decompile_adb_files(adv_dir)
    if len(adb_files) != 72:
        raise RuntimeError(f"Workflow regression failed: expected 72 adv scripts, got {len(adb_files)}")

    mutated_adbsrc_target: tuple[Path, int, str] | None = None
    mutated_json_target: tuple[Path, int, str] | None = None
    for output_format, out_root in [("adbsrc", adbsrc_root), ("json", json_root)]:
        pairs = resolve_decompile_output(adv_dir, str(out_root), adb_files, output_format)
        for adb_file, output_path in pairs:
            doc = parse_adb_ir(adb_file.read_bytes())
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(serialize_decompile_doc(doc, output_format), encoding="utf-8")
            if mutated_adbsrc_target is None:
                for idx, entry in enumerate(doc.get("entries", [])):
                    if entry.get("editable_text") and _entry_slot(doc, idx).get("text_role") == "dialogue":
                        rel_target = adb_file.relative_to(adv_dir).with_suffix(".adb").as_posix()
                        mutated_adbsrc_target = (adbsrc_root / adb_file.relative_to(adv_dir).with_suffix(".adbsrc"), idx, rel_target)
                        mutated_json_target = (json_root / adb_file.relative_to(adv_dir).with_suffix(".adb.json"), idx, rel_target)
                        break

    adbsrc_files = sorted(adbsrc_root.rglob("*.adbsrc"))
    if len(adbsrc_files) != 72:
        raise RuntimeError(f"Workflow regression failed: expected 72 exported ADBSRC files, got {len(adbsrc_files)}")
    json_files = sorted(json_root.rglob("*.json"))
    if len(json_files) != 72:
        raise RuntimeError(f"Workflow regression failed: expected 72 exported JSON files, got {len(json_files)}")
    if mutated_adbsrc_target is None or mutated_json_target is None:
        raise RuntimeError("Workflow regression failed: no editable dialogue found for workflow mutation.")

    mutated_src, entry_index, rel_target = mutated_adbsrc_target
    shutil.copytree(tmp_dir / "resource_tree", work_tree)

    adbsrc_sources = iter_compile_source_files(adbsrc_root, "adbsrc")
    for src_file, output_path, source_format in resolve_compile_output(adbsrc_root, str(work_tree / "adv"), adbsrc_sources, "adbsrc"):
        doc = load_compile_doc(src_file, source_format)
        if src_file == mutated_src:
            target_slot = _entry_slot(doc, entry_index)
            target_slot["text"] = str(target_slot.get("text", "")) + " [WF]"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(compile_adb(doc))

    rebuilt_files = sorted((work_tree / "adv").rglob("*.adb"))
    if len(rebuilt_files) != 72:
        raise RuntimeError(f"Workflow regression failed: expected 72 rebuilt adv scripts, got {len(rebuilt_files)}")

    reparsed = parse_adb_ir((work_tree / "adv" / rel_target).read_bytes())
    text_after = _entry_text(reparsed, entry_index)
    if not text_after.endswith(" [WF]"):
        raise RuntimeError("Workflow regression failed: rebuilt script did not land back in resource tree as expected.")

    shutil.rmtree(work_tree)
    shutil.copytree(tmp_dir / "resource_tree", work_tree)
    mutated_json_src, json_entry_index, json_rel_target = mutated_json_target
    json_sources = iter_compile_source_files(json_root, "json")
    for json_file, output_path, source_format in resolve_compile_output(json_root, str(work_tree / "adv"), json_sources, "json"):
        doc = load_compile_doc(json_file, source_format)
        if json_file == mutated_json_src:
            target_slot = _entry_slot(doc, json_entry_index)
            target_slot["text"] = str(target_slot.get("text", "")) + " [WF_JSON]"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(compile_adb(doc))

    rebuilt_json_files = sorted((work_tree / "adv").rglob("*.adb"))
    if len(rebuilt_json_files) != 72:
        raise RuntimeError(f"Workflow regression failed: expected 72 rebuilt JSON scripts, got {len(rebuilt_json_files)}")

    reparsed_json = parse_adb_ir((work_tree / "adv" / json_rel_target).read_bytes())
    text_after_json = _entry_text(reparsed_json, json_entry_index)
    if not text_after_json.endswith(" [WF_JSON]"):
        raise RuntimeError("Workflow regression failed: JSON rebuild did not land back in resource tree as expected.")
    return work_tree, json_rel_target


def run_pristine_byte_identical_pack_regression(game_dir: Path, tmp_dir: Path) -> None:
    source_archive = game_dir / "adv"
    if not source_archive.is_file():
        raise RuntimeError(f"Pristine regression failed: missing source archive: {source_archive}")

    tree_root = tmp_dir / "resource_tree"
    adv_dir = tree_root / "adv"
    if not adv_dir.is_dir():
        raise RuntimeError(f"Pristine regression failed: missing recovered adv root: {adv_dir}")

    pristine_adbsrc = tmp_dir / "pristine_adbsrc"
    pristine_work = tmp_dir / "pristine_tree_work"
    pristine_pack = tmp_dir / "pristine_adv"
    for path in [pristine_adbsrc, pristine_work]:
        if path.exists():
            shutil.rmtree(path)
    if pristine_pack.exists():
        pristine_pack.unlink()

    adb_files = iter_decompile_adb_files(adv_dir)
    if len(adb_files) != 72:
        raise RuntimeError(f"Pristine regression failed: expected 72 adv scripts, got {len(adb_files)}")

    pairs = resolve_decompile_output(adv_dir, str(pristine_adbsrc), adb_files, "adbsrc")
    for adb_file, output_path in pairs:
        doc = parse_adb_ir(adb_file.read_bytes())
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialize_decompile_doc(doc, "adbsrc"), encoding="utf-8")

    exported = sorted(pristine_adbsrc.rglob("*.adbsrc"))
    if len(exported) != 72:
        raise RuntimeError(f"Pristine regression failed: expected 72 exported ADBSRC files, got {len(exported)}")

    shutil.copytree(tree_root, pristine_work)
    sources = iter_compile_source_files(pristine_adbsrc, "adbsrc")
    for src_file, output_path, source_format in resolve_compile_output(pristine_adbsrc, str(pristine_work / "adv"), sources, "adbsrc"):
        doc = load_compile_doc(src_file, source_format)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(compile_adb(doc))

    pack_resource_tree_archive(source_archive, pristine_work, pristine_pack)
    if not pristine_pack.is_file():
        raise RuntimeError("Pristine regression failed: repacked archive was not created.")

    orig = source_archive.read_bytes()
    new = pristine_pack.read_bytes()
    if orig != new:
        first_diff = next((i for i, (a, b) in enumerate(zip(orig, new)) if a != b), None)
        raise RuntimeError(f"Pristine regression failed: byte-identical compare mismatch at offset {first_diff}.")


def run_resource_tree_pack_regression(game_dir: Path, tmp_dir: Path, work_tree: Path, rel_target: str) -> None:
    source_archive = game_dir / "adv"
    if not source_archive.is_file():
        raise RuntimeError(f"Pack regression failed: missing source archive: {source_archive}")

    repacked_archive = tmp_dir / "adv"
    if repacked_archive.exists():
        repacked_archive.unlink()

    pack_resource_tree_archive(source_archive, work_tree, repacked_archive)
    if not repacked_archive.is_file():
        raise RuntimeError("Pack regression failed: repacked archive was not created.")

    unpack_dir = tmp_dir / "repacked_adv_from_tree"
    if unpack_dir.exists():
        shutil.rmtree(unpack_dir)
    name_map = build_resource_tree_name_map_for_archive(work_tree, source_archive.name)
    manifest_path = unpack_decoded_archive(repacked_archive, unpack_dir, name_map)
    unpacked_adv_dir = manifest_path.parent / "adv"
    if not unpacked_adv_dir.is_dir():
        raise RuntimeError(f"Pack regression failed: repacked archive did not unpack to adv root: {unpacked_adv_dir}")

    target_path = unpacked_adv_dir / rel_target
    if not target_path.is_file():
        raise RuntimeError(f"Pack regression failed: rebuilt script missing after repack: {target_path}")

    reparsed = parse_adb_ir(target_path.read_bytes())
    entry_index = next(
        (
            i
            for i, entry in enumerate(reparsed.get("entries", []))
            if entry.get("editable_text") and _entry_slot(reparsed, i).get("text_role") == "dialogue"
        ),
        None,
    )
    if entry_index is None:
        raise RuntimeError("Pack regression failed: no editable dialogue after repack.")
    if not _entry_text(reparsed, entry_index).endswith(" [WF_JSON]"):
        raise RuntimeError("Pack regression failed: resource tree change did not survive repack and unpack.")


def run_csaf_raw_roundtrip(game_dir: Path, tmp_dir: Path, archives: list[str]) -> None:
    for name in archives:
        src = game_dir / name
        unpack_dir = tmp_dir / f"unpack_{name}"
        manifest = unpack_raw_archive(src, unpack_dir, {})
        repacked = tmp_dir / f"{name}.repack"
        pack_raw_archive(manifest, repacked, update_checksum=False)
        if repacked.read_bytes() != src.read_bytes():
            raise RuntimeError(f"CSAF regression failed: {name}")


def run_csaf_decoded_regression(game_dir: Path, tmp_dir: Path, archives: list[str]) -> None:
    header = struct.Struct("<4sIII16s")

    decoded_magic_expectations = {
        "system": {b"NBDA", b"\x89PNG\r\n\x1a\n"},
        "adv": {b"NBDA"},
    }

    for name in archives:
        src = game_dir / name
        blob = src.read_bytes()
        magic, version_flags, file_count, extra_size, checksum = header.unpack_from(blob, 0)
        if magic != b"CSAF":
            raise RuntimeError(f"Decoded CSAF regression failed: bad magic for {name}")
        table_size = ((24 * file_count + 31) & 0xFFFFF000) + 4064
        table = blob[header.size : header.size + table_size]
        raw_extra = blob[header.size + table_size : header.size + table_size + extra_size]
        decoded_extra = decode_extra_region(raw_extra)
        decoded_extra_md5 = hashlib.md5(table + decoded_extra).digest()
        if decoded_extra_md5 != checksum:
            raise RuntimeError(f"Decoded CSAF regression failed: extra checksum mismatch for {name}")

        unpack_dir = tmp_dir / f"decoded_{name}"
        manifest_path = unpack_decoded_archive(src, unpack_dir, {})
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not manifest.get("decoded_extra_matches_header_checksum", False):
            raise RuntimeError(f"Decoded CSAF regression failed: manifest checksum flag false for {name}")

        expected_magics = decoded_magic_expectations.get(name, set())
        if expected_magics:
            hits = 0
            for entry in manifest.get("entries", []):
                data = (unpack_dir / entry["file"]).read_bytes()[:8]
                if any(data.startswith(sig) for sig in expected_magics):
                    hits += 1
            if hits == 0:
                raise RuntimeError(f"Decoded CSAF regression failed: no decoded magic hits for {name}")


def run_resource_tree_recovery_regression(root: Path, game_dir: Path, tmp_dir: Path) -> None:
    out_dir = tmp_dir / "resource_tree"
    manifest = recover_all_resources(root, game_dir, out_dir, debug_root=tmp_dir / "resource_tree_debug")

    if manifest.get("goal") != "recover_original_resource_tree":
        raise RuntimeError("Resource-tree regression failed: wrong root manifest goal.")

    forbidden_default_paths = [
        out_dir / "_pending",
        out_dir / "resource_tree.json",
        out_dir / "raw_index.json",
    ]
    exposed = [path.as_posix() for path in forbidden_default_paths if path.exists()]
    if exposed:
        raise RuntimeError(f"Resource-tree regression failed: default output still exposes internal artifacts: {exposed}")

    final_manifest_path = out_dir / "资源清单.json"
    if not final_manifest_path.is_file():
        raise RuntimeError("Resource-tree regression failed: missing final human-readable manifest.")
    final_manifest = json.loads(final_manifest_path.read_text(encoding="utf-8"))
    entries = list(final_manifest.get("entries", []))
    if not entries:
        raise RuntimeError("Resource-tree regression failed: final manifest contains no entries.")
    required_human_fields = {
        "original_path",
        "current_path",
        "resource_category",
        "recovery_status",
        "evidence_sources",
        "archive_hash_hex",
    }
    missing_human_fields = sorted(required_human_fields - set(entries[0].keys()))
    if missing_human_fields:
        raise RuntimeError(
            f"Resource-tree regression failed: final manifest is missing human-facing fields: {missing_human_fields}"
        )
    allowed_evidence_sources = {"包内目录项", "外部索引", "运行时路径", "脚本引用", "系统表", "其他来源"}
    bad_evidence = []
    for entry in entries:
        sources = list(entry.get("evidence_sources") or [])
        if not sources:
            bad_evidence.append({"current_path": entry.get("current_path"), "evidence_sources": sources})
            if len(bad_evidence) >= 10:
                break
            continue
        if any(source not in allowed_evidence_sources for source in sources):
            bad_evidence.append({"current_path": entry.get("current_path"), "evidence_sources": sources})
            if len(bad_evidence) >= 10:
                break
    if bad_evidence:
        raise RuntimeError(f"Resource-tree regression failed: final manifest has invalid evidence sources: {bad_evidence}")

    adv_dir = out_dir / "adv"
    if not adv_dir.is_dir():
        raise RuntimeError(f"Resource-tree regression failed: missing script root: {adv_dir}")

    adv_adb_files = sorted(adv_dir.rglob("*.adb"))
    if len(adv_adb_files) != 72:
        raise RuntimeError(f"Resource-tree regression failed: expected 72 adv scripts, got {len(adv_adb_files)}")

    expected_files = [
        out_dir / "adv" / "logo.adb",
        out_dir / "adv" / "SNR.adb",
        out_dir / "system" / "save" / "save.adb",
        out_dir / "system" / "window" / "menu.adb",
        out_dir / "system" / "album" / "list.csv",
        out_dir / "SE" / "sys01.ogg",
        out_dir / "ev" / "EV01_01.png",
    ]
    missing = [path.as_posix() for path in expected_files if not path.exists()]
    if missing:
        raise RuntimeError(f"Resource-tree regression failed: missing expected recovered files: {missing}")

    if (out_dir / "unknown").exists():
        raise RuntimeError("Resource-tree regression failed: default output still exposes legacy unknown root.")

    scripts_where = set(manifest.get("entrypoint_answers", {}).get("scripts_where", []))
    if "adv" not in scripts_where:
        raise RuntimeError("Resource-tree regression failed: root manifest does not point scripts to adv.")
    if "adv/待补原名" not in scripts_where:
        raise RuntimeError("Resource-tree regression failed: root manifest does not point unresolved adv scripts to adv/待补原名.")
    if "system/scripts/待补原名" not in scripts_where:
        raise RuntimeError("Resource-tree regression failed: root manifest does not point unresolved system scripts to system/scripts/待补原名.")

    images_where = set(manifest.get("entrypoint_answers", {}).get("images_where", []))
    if "ev" not in images_where:
        raise RuntimeError("Resource-tree regression failed: root manifest does not point images to ev.")

    system_where = set(manifest.get("entrypoint_answers", {}).get("system_resources_where", []))
    if "system/window" not in system_where:
        raise RuntimeError("Resource-tree regression failed: root manifest does not point system resources to system/window.")

    unknown_where = set(manifest.get("entrypoint_answers", {}).get("unknown_resources_where", []))
    expected_unknown_dirs = {
        "bg/待补原名/images",
        "ch/待补原名/images",
        "voice/待补原名/clips",
        "BGM/待补原名/audio",
        "song/待补原名/audio",
        "SE/待补原名/audio",
        "system/_unknown_dir/待补原目录与原名/images",
    }
    missing_unknown_dirs = sorted(expected_unknown_dirs - unknown_where)
    if missing_unknown_dirs:
        raise RuntimeError(
            f"Resource-tree regression failed: root manifest does not expose categorized unknown resources: {missing_unknown_dirs}"
        )

    top_level_files = [path.name for path in out_dir.iterdir() if path.is_file()]
    unexpected_top_level_files = [name for name in top_level_files if name != "资源清单.json"]
    if unexpected_top_level_files:
        raise RuntimeError(f"Resource-tree regression failed: default output root still exposes files: {unexpected_top_level_files}")

    hash_name_re = re.compile(r"[0-9a-f]{32}", re.IGNORECASE)
    bad_paths: list[str] = []
    for path in out_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(out_dir).as_posix()
        if "/_pending/" in rel or rel.startswith("_pending/"):
            continue
        if hash_name_re.search(path.name):
            bad_paths.append(rel)
        if len(bad_paths) >= 10:
            break
    if bad_paths:
        raise RuntimeError(f"Resource-tree regression failed: final output still contains hash-like names: {bad_paths}")

    expected_unknown_files = [
        out_dir / "bg" / "待补原名" / "images" / "image_00000.bin",
        out_dir / "voice" / "待补原名" / "clips" / "clip_00000.bin",
        out_dir / "BGM" / "待补原名" / "audio" / "track_00000.bin",
    ]
    missing_unknown_files = [path.as_posix() for path in expected_unknown_files if not path.exists()]
    if missing_unknown_files:
        raise RuntimeError(
            f"Resource-tree regression failed: categorized unknown resources are not written to default output: {missing_unknown_files}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Regression test: resource-tree recovery, ADB(raw/ir/adbsrc) roundtrip, dialogue length change, speaker-name change, CSAF raw roundtrip, and CSAF decoded checks."
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

    run_resource_tree_recovery_regression(root, game_dir, tmp_dir)
    run_pristine_byte_identical_pack_regression(game_dir, tmp_dir)
    work_tree, rel_target = run_resource_tree_script_workflow_regression(tmp_dir)
    run_resource_tree_pack_regression(game_dir, tmp_dir, work_tree, rel_target)
    run_adb_roundtrip(game_dir, tmp_dir)
    run_adb_ir_roundtrip(game_dir, tmp_dir)
    run_adbsrc_roundtrip(game_dir, tmp_dir)
    run_text_length_change_regression(game_dir, tmp_dir)
    run_speaker_name_change_regression(game_dir, tmp_dir)
    run_csaf_raw_roundtrip(game_dir, tmp_dir, args.archives)
    run_csaf_decoded_regression(game_dir, tmp_dir, args.archives)
    print("PASS")
    return 0
