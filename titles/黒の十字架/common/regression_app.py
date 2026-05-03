"""Regression entry points for the title."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from script.ssb.compile import compile_project_file
from script.ssb.decompile import write_project


def run_ssb_roundtrip_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    original_code = (script_dir / "CODE.SSB").read_bytes()
    original_data = (script_dir / "DATA.SSB").read_bytes()
    with tempfile.TemporaryDirectory(prefix="kuro_ssb_", dir=title_root) as temp_dir:
        temp_root = Path(temp_dir)
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


def run_ssb_text_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    with tempfile.TemporaryDirectory(prefix="kuro_ssb_patch_", dir=title_root) as temp_dir:
        temp_root = Path(temp_dir)
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
        target["text"] = "試験"
        text_entries_path.write_text(json.dumps(text_entries_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_text_entries_file

        apply_text_entries_file(project_json, text_entries_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="cp932")
        rebuilt_data = (rebuild_dir / "DATA.SSB").read_bytes()
        decoded = bytes(byte ^ 0xAA for byte in rebuilt_data)
        start = int(target["byte_offset"])
        if decoded[start : start + len("試験".encode("cp932"))].decode("cp932") != "試験":
            raise AssertionError("Patched jp_text not found in rebuilt DATA.SSB")


def run_ssb_variable_length_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    with tempfile.TemporaryDirectory(prefix="kuro_ssb_var_", dir=title_root) as temp_dir:
        temp_root = Path(temp_dir)
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
                if entry["category"] == "jp_text" and entry["storage_bytes"] < len("試験追加".encode("cp932")) + 1
            ),
            None,
        )
        if target is None:
            raise AssertionError("No variable-length jp_text target found")
        target["text"] = "試験追加"
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
        if not any(entry["text"] == "試験追加" for entry in rebuilt_project["translation_entries"]):
            raise AssertionError("Variable-length patched text not recovered after re-decompile")


def run_ssb_target_encoding_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    with tempfile.TemporaryDirectory(prefix="kuro_ssb_gbk_", dir=title_root) as temp_dir:
        temp_root = Path(temp_dir)
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
                if entry["category"] == "jp_text" and entry["storage_bytes"] >= len("编码回写GBK测试".encode("gbk")) + 1
            ),
            None,
        )
        if target is None:
            raise AssertionError("No GBK-capable target text found")
        target["text"] = "编码回写GBK测试"
        text_entries_path.write_text(json.dumps(text_entries_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_text_entries_file

        apply_text_entries_file(project_json, text_entries_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="gbk")
        rebuilt_project_json, _ = write_project(rebuild_dir, roundtrip_dump_dir, text_encoding="gbk")
        rebuilt_project = json.loads(rebuilt_project_json.read_text(encoding="utf-8"))
        if not any(entry["text"] == "编码回写GBK测试" for entry in rebuilt_project["translation_entries"]):
            raise AssertionError("GBK write-back text not recovered after re-decompile")
