"""Regression entry points for the title."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from script.ssb.compile import compile_project_file
from script.ssb.decompile import write_project

EXPECTED_EXTRACTION_SAMPLES = (
    "親愛なるヴォルフへ",
    "商売成功の知らせ、心より祝福する。",
    "ロタール",
    "フランツ",
    "「ヴォルフ！！」",
)

CHARACTER_NAME_SAMPLES = {"ロタール", "フランツ", "モーリッツ", "枢機卿"}
CP932_INPLACE_PATCH_TEXT = "試験"
CP932_VARIABLE_PATCH_TEXT = "試験追加"
GBK_PATCH_TEXT = "编码回写GBK测试"
NAME_PATCH_TEXT = "甲乙"


def _fresh_regression_dir(title_root: Path, prefix: str) -> Path:
    base_dir = title_root / "_regression_tmp"
    base_dir.mkdir(parents=True, exist_ok=True)
    temp_root = base_dir / f"{prefix}{uuid.uuid4().hex[:8]}"
    temp_root.mkdir(parents=True, exist_ok=False)
    return temp_root


def _cleanup_regression_dir(temp_root: Path) -> None:
    shutil.rmtree(temp_root, ignore_errors=True)


def run_ssb_roundtrip_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    original_code = (script_dir / "CODE.SSB").read_bytes()
    original_data = (script_dir / "DATA.SSB").read_bytes()
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        compile_project_file(project_json, rebuild_dir)
        rebuilt_code = (rebuild_dir / "CODE.SSB").read_bytes()
        rebuilt_data = (rebuild_dir / "DATA.SSB").read_bytes()
        if rebuilt_code != original_code:
            raise AssertionError("CODE.SSB roundtrip mismatch")
        if rebuilt_data != original_data:
            raise AssertionError("DATA.SSB roundtrip mismatch")
    finally:
        _cleanup_regression_dir(temp_root)


def run_ssb_translation_coverage_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_extract_")
    try:
        dump_dir = temp_root / "dump"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        project = json.loads(project_json.read_text(encoding="utf-8"))
        translation_entries = project["translation_entries"]
        translation_keys = {
            (int(entry["byte_offset"]), int(entry["word_offset"]) if entry["word_offset"] is not None else -1)
            for entry in translation_entries
        }

        for text in EXPECTED_EXTRACTION_SAMPLES:
            matched = [entry for entry in translation_entries if entry["text"] == text]
            if not matched:
                raise AssertionError(f"Expected extracted text not found: {text}")

        missing = []
        for entry in project["strings"]:
            key = (int(entry["byte_offset"]), int(entry["word_offset"]) if entry["word_offset"] is not None else -1)
            if entry["category"] not in {"jp_text", "text"}:
                continue
            if int(entry["reference_count"]) <= 0:
                continue
            if key not in translation_keys:
                missing.append(entry)
        if missing:
            preview = ", ".join(f"0x{int(entry['byte_offset']):X}:{entry['text']}" for entry in missing[:5])
            raise AssertionError(f"Referenced text missing from translation_entries: {len(missing)} entries; sample: {preview}")
    finally:
        _cleanup_regression_dir(temp_root)


def run_ssb_character_name_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_name_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        roundtrip_dump_dir = temp_root / "roundtrip_dump"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        text_entries_path = dump_dir / "translation_entries.json"
        text_entries_doc = json.loads(text_entries_path.read_text(encoding="utf-8"))
        target = next((entry for entry in text_entries_doc["entries"] if entry["text"] in CHARACTER_NAME_SAMPLES and entry["storage_bytes"] >= 5), None)
        if target is None:
            raise AssertionError("No patchable character-name entry found")
        patched_text = NAME_PATCH_TEXT
        target["text"] = patched_text
        text_entries_path.write_text(json.dumps(text_entries_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_text_entries_file

        apply_text_entries_file(project_json, text_entries_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="cp932")
        rebuilt_project_json, _ = write_project(rebuild_dir, roundtrip_dump_dir, text_encoding="cp932")
        rebuilt_project = json.loads(rebuilt_project_json.read_text(encoding="utf-8"))
        if not any(entry["text"] == patched_text for entry in rebuilt_project["translation_entries"]):
            raise AssertionError("Character-name patched text not recovered after re-decompile")
    finally:
        _cleanup_regression_dir(temp_root)


def run_ssb_text_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_patch_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        text_entries_path = dump_dir / "translation_entries.json"
        project = json.loads(project_json.read_text(encoding="utf-8"))
        text_entries_doc = json.loads(text_entries_path.read_text(encoding="utf-8"))
        target = next(
            (
                entry
                for entry in text_entries_doc["entries"]
                if entry["category"] == "jp_text" and entry["storage_bytes"] >= 6
            ),
            None,
        )
        if target is None:
            raise AssertionError("No patchable jp_text string found")
        target["text"] = CP932_INPLACE_PATCH_TEXT
        text_entries_path.write_text(json.dumps(text_entries_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_text_entries_file

        apply_text_entries_file(project_json, text_entries_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="cp932")
        rebuilt_data = (rebuild_dir / "DATA.SSB").read_bytes()
        decoded = bytes(byte ^ 0xAA for byte in rebuilt_data)
        start = int(target["byte_offset"])
        if decoded[start : start + len(CP932_INPLACE_PATCH_TEXT.encode("cp932"))].decode("cp932") != CP932_INPLACE_PATCH_TEXT:
            raise AssertionError("Patched jp_text not found in rebuilt DATA.SSB")
    finally:
        _cleanup_regression_dir(temp_root)


def run_ssb_variable_length_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_var_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        roundtrip_dump_dir = temp_root / "roundtrip_dump"
        original_code = (script_dir / "CODE.SSB").read_bytes()
        original_data = (script_dir / "DATA.SSB").read_bytes()
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        text_entries_path = dump_dir / "translation_entries.json"
        text_entries_doc = json.loads(text_entries_path.read_text(encoding="utf-8"))
        target = next(
            (
                entry
                for entry in text_entries_doc["entries"]
                if entry["category"] == "jp_text" and entry["storage_bytes"] < len(CP932_VARIABLE_PATCH_TEXT.encode("cp932")) + 1
            ),
            None,
        )
        if target is None:
            raise AssertionError("No variable-length jp_text target found")
        target["text"] = CP932_VARIABLE_PATCH_TEXT
        text_entries_path.write_text(json.dumps(text_entries_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_text_entries_file

        apply_text_entries_file(project_json, text_entries_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="cp932")
        rebuilt_code = (rebuild_dir / "CODE.SSB").read_bytes()
        rebuilt_data = (rebuild_dir / "DATA.SSB").read_bytes()
        if rebuilt_code == original_code:
            raise AssertionError("Variable-length patch did not alter CODE.SSB references")
        if rebuilt_data == original_data:
            raise AssertionError("Variable-length patch did not alter DATA.SSB")
        rebuilt_script_dir = rebuild_dir
        rebuilt_project_json, _ = write_project(rebuilt_script_dir, roundtrip_dump_dir, text_encoding="cp932")
        rebuilt_project = json.loads(rebuilt_project_json.read_text(encoding="utf-8"))
        if not any(entry["text"] == CP932_VARIABLE_PATCH_TEXT for entry in rebuilt_project["translation_entries"]):
            raise AssertionError("Variable-length patched text not recovered after re-decompile")
    finally:
        _cleanup_regression_dir(temp_root)


def run_ssb_target_encoding_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_gbk_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild_gbk"
        roundtrip_dump_dir = temp_root / "roundtrip_gbk"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        text_entries_path = dump_dir / "translation_entries.json"
        text_entries_doc = json.loads(text_entries_path.read_text(encoding="utf-8"))
        target = next(
            (
                entry
                for entry in text_entries_doc["entries"]
                if entry["category"] == "jp_text" and entry["storage_bytes"] >= len(GBK_PATCH_TEXT.encode("gbk")) + 1
            ),
            None,
        )
        if target is None:
            raise AssertionError("No GBK-capable target text found")
        target["text"] = GBK_PATCH_TEXT
        text_entries_path.write_text(json.dumps(text_entries_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_text_entries_file

        apply_text_entries_file(project_json, text_entries_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="gbk")
        rebuilt_project_json, _ = write_project(rebuild_dir, roundtrip_dump_dir, text_encoding="gbk")
        rebuilt_project = json.loads(rebuilt_project_json.read_text(encoding="utf-8"))
        if not any(entry["text"] == GBK_PATCH_TEXT for entry in rebuilt_project["translation_entries"]):
            raise AssertionError("GBK write-back text not recovered after re-decompile")
    finally:
        _cleanup_regression_dir(temp_root)
