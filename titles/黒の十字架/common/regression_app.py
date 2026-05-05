"""Regression entry points for the title."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from script.ssb_compile_app import run_batch as run_batch_compile
from script.ssb_decompile_app import run_batch as run_batch_decompile
from script.ssb.compile import compile_project_file
from script.ssb.decompile import write_project

EXPECTED_EXTRACTION_SAMPLES = (
    "親愛なるヴォルフへ",
    "商売成功の知らせ、心より祝福する。",
    "「ヴォルフ！！」",
)
EXPECTED_NAME_SAMPLES = (
    "ヴォルフ\r",
    "御者\r",
    "フランツ\r",
)

CP932_INPLACE_PATCH_TEXT = "試験"
CP932_SHORT_PATCH_TEXT = "試"
CP932_VARIABLE_PATCH_TEXT = "試験追加"
GBK_PATCH_TEXT = "编码回写GBK测试"
AC07_NAME_PATCH_TEXT = "勇者"


def _fresh_regression_dir(title_root: Path, prefix: str) -> Path:
    base_dir = title_root / "_regression_tmp"
    base_dir.mkdir(parents=True, exist_ok=True)
    temp_root = base_dir / f"{prefix}{uuid.uuid4().hex[:8]}"
    temp_root.mkdir(parents=True, exist_ok=False)
    return temp_root


def _cleanup_regression_dir(temp_root: Path) -> None:
    shutil.rmtree(temp_root, ignore_errors=True)


def _find_first_ac07_character_selection_cluster(entries: list[dict[str, object]]) -> dict[str, object]:
    cluster = next((entry for entry in entries if entry.get("choices")), None)
    if cluster is None:
        raise AssertionError("No AC07 character selection cluster found")
    return cluster


def _find_first_ac07_option_cluster(entries: list[dict[str, object]]) -> dict[str, object]:
    cluster = next((entry for entry in entries if entry.get("choices")), None)
    if cluster is None:
        raise AssertionError("No AC07 option cluster found")
    return cluster


def _find_first_name_related_entry(entries: list[dict[str, object]], record_kind: str) -> dict[str, object]:
    entry = next((item for item in entries if item["record_kind"] == record_kind), None)
    if entry is None:
        raise AssertionError(f"No {record_kind} entry found")
    return entry


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


def run_ssb_batch_regression(title_root: Path) -> None:
    game_root = title_root / "game"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_batch_")
    try:
        dump_root = temp_root / "dump"
        rebuild_root = temp_root / "rebuild"
        processed_decompile = run_batch_decompile(game_root, dump_root, text_encoding="cp932")
        if processed_decompile != 1:
            raise AssertionError(f"Unexpected batch decompile item count: {processed_decompile}")
        dump_script_dir = dump_root / "SCRIPT"
        if not (dump_script_dir / "script.json").is_file():
            raise AssertionError("Batch decompile did not mirror SCRIPT/script.json")
        if not (dump_script_dir / "translation_entries.json").is_file():
            raise AssertionError("Batch decompile did not mirror SCRIPT/translation_entries.json")

        processed_compile = run_batch_compile(
            dump_root,
            rebuild_root,
            use_default_text_entries=True,
            target_encoding="cp932",
        )
        if processed_compile != 1:
            raise AssertionError(f"Unexpected batch compile item count: {processed_compile}")
        rebuild_script_dir = rebuild_root / "SCRIPT"
        if not (rebuild_script_dir / "CODE.SSB").is_file():
            raise AssertionError("Batch compile did not mirror SCRIPT/CODE.SSB")
        if not (rebuild_script_dir / "DATA.SSB").is_file():
            raise AssertionError("Batch compile did not mirror SCRIPT/DATA.SSB")

        original_code = (game_root / "SCRIPT" / "CODE.SSB").read_bytes()
        original_data = (game_root / "SCRIPT" / "DATA.SSB").read_bytes()
        rebuilt_code = (rebuild_script_dir / "CODE.SSB").read_bytes()
        rebuilt_data = (rebuild_script_dir / "DATA.SSB").read_bytes()
        if rebuilt_code != original_code:
            raise AssertionError("Batch compile CODE.SSB mismatch")
        if rebuilt_data != original_data:
            raise AssertionError("Batch compile DATA.SSB mismatch")
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
        ac07_character_selection_records = project["ac07_character_selection_records"]
        ac07_visible_clusters = project["ac07_visible_clusters"]
        ac07_option_clusters = project["ac07_option_clusters"]

        for text in EXPECTED_EXTRACTION_SAMPLES:
            matched = [entry for entry in translation_entries if entry["text"] == text]
            if not matched:
                raise AssertionError(f"Expected extracted text not found: {text}")
            if not any(entry["usage"] == "main_display_text" for entry in matched):
                raise AssertionError(f"Expected main-display text usage not found: {text}")

        for text in EXPECTED_NAME_SAMPLES:
            matched = [entry for entry in translation_entries if entry["text"] == text]
            if not matched:
                raise AssertionError(f"Expected extracted display name not found: {text}")
            if not any(entry["usage"] == "main_display_name" for entry in matched):
                raise AssertionError(f"Expected main-display name usage not found: {text}")

        if any("original_text" not in entry for entry in translation_entries):
            raise AssertionError("translation_entries contains entries without original_text")

        main_display_records = project["main_display_records"]
        if not any(
            record["display_name_text"] == "御者\r"
            and record["main_text"] == "「だんな、そろそろファルツ大司教領に入りますぜ」"
            for record in main_display_records
        ):
            raise AssertionError("Expected AA13 main-display record mapping not found")
        if not any(record["active_prefix_chain_count"] > 0 for record in main_display_records):
            raise AssertionError("Expected active 8351 prefix chain not found in main_display_records")
        expected_aa13_order = [
            "0x000714B5",
            "0x000714B4",
            "0x000714B3",
            "0x000714B2",
            "0x000714B1",
            "0x000714B0",
            "0x000714AF",
            "0x000714AE",
        ]
        expected_8351_order = [
            "0x00071249",
            "0x00071248",
            "0x00071247",
            "0x00071246",
        ]
        if not all(record["call_arg_slot_order"] == expected_aa13_order for record in main_display_records):
            raise AssertionError("Unexpected AA13 call arg slot order detected")
        if not all(
            prefix["call_arg_slot_order"] == expected_8351_order
            for record in main_display_records
            for prefix in record["active_prefix_chain"]
        ):
            raise AssertionError("Unexpected 8351 call arg slot order detected")
        if not all(
            prefix["slot_71248_value"] == 0 and prefix["slot_71246_value"] == 90
            for record in main_display_records
            for prefix in record["active_prefix_chain"]
        ):
            raise AssertionError("Unexpected 8351 prefix argument shape detected")
        if not all(
            prefix["slot_71249_value"] in {0, 1}
            for record in main_display_records
            for prefix in record["active_prefix_chain"]
        ):
            raise AssertionError("Unexpected 8351 prefix variant selector detected")
        if not any(
            prefix["slot_71249_value"] == 0 and prefix["layer_role"] == "base_visual_layer"
            for record in main_display_records
            for prefix in record["active_prefix_chain"]
        ):
            raise AssertionError("Expected selector-0 prefix family sample not found")
        if not any(
            prefix["slot_71249_value"] == 1 and prefix["layer_role"] == "overlay_diff_visual_layer"
            for record in main_display_records
            for prefix in record["active_prefix_chain"]
        ):
            raise AssertionError("Expected selector-1 prefix family sample not found")
        if not all(
            prefix["resource_chain_kind"] == "visual_prefix_resource_chain"
            for record in main_display_records
            for prefix in record["active_prefix_chain"]
        ):
            raise AssertionError("Unexpected 8351 prefix resource chain kind detected")
        if not all(
            prefix["resource_archive_kind"] == "grd_visual_resource"
            for record in main_display_records
            for prefix in record["active_prefix_chain"]
        ):
            raise AssertionError("Unexpected 8351 prefix resource archive kind detected")
        if not all(
            prefix["grd_resource_name"] == prefix["grd_label_text"] == prefix["label_text"]
            for record in main_display_records
            for prefix in record["active_prefix_chain"]
        ):
            raise AssertionError("Unexpected 8351 GRD resource name mismatch detected")
        if not all(
            prefix["prefix_family_kind"] == "visual_resource_family"
            for record in main_display_records
            for prefix in record["active_prefix_chain"]
        ):
            raise AssertionError("Unexpected 8351 prefix family kind detected")
        selector_sets = {tuple(record["active_prefix_selector_set"]) for record in main_display_records}
        if (1,) in selector_sets:
            raise AssertionError("Unexpected standalone selector-1 prefix chain detected")
        if not {(0,), (0, 1)}.issubset(selector_sets):
            raise AssertionError("Expected selector layering patterns not found")
        if not any(record["active_prefix_visual_mode"] == "base_only" for record in main_display_records):
            raise AssertionError("Expected base-only visual prefix mode not found")
        if not any(record["active_prefix_visual_mode"] == "base_plus_overlay" for record in main_display_records):
            raise AssertionError("Expected base-plus-overlay visual prefix mode not found")
        if not all(
            (not record["overlay_visual_label_text"] and record["active_prefix_visual_mode"] != "base_plus_overlay")
            or (record["overlay_visual_label_text"] and record["active_prefix_visual_mode"] == "base_plus_overlay")
            for record in main_display_records
        ):
            raise AssertionError("Overlay visual label field does not match visual mode")
        if not all(
            record["overlay_visual_label_text"] == record["overlay_grd_label_text"]
            for record in main_display_records
        ):
            raise AssertionError("Overlay GRD label fields are out of sync")
        if not all(
            (not record["base_visual_label_text"] and record["active_prefix_visual_mode"] == "none")
            or record["base_visual_label_text"]
            for record in main_display_records
        ):
            raise AssertionError("Base visual label field does not match visual mode")
        if not all(
            record["base_visual_label_text"] == record["base_grd_label_text"]
            for record in main_display_records
        ):
            raise AssertionError("Base GRD label fields are out of sync")
        if not all(record["slot_714B5_value"] == 0 for record in main_display_records):
            raise AssertionError("Unexpected AA13 slot_714B5_value detected")
        if not all(record["slot_714B3_value"] == 0 for record in main_display_records):
            raise AssertionError("Unexpected AA13 slot_714B3_value detected")
        if not all(record["selector"] == 18 for record in main_display_records):
            raise AssertionError("Unexpected AA13 selector detected")
        if not any(record["slot_714B2_value"] == 1 and not record["display_name_text"] for record in main_display_records):
            raise AssertionError("Expected narration-style AA13 text mode sample not found")
        if not any(record["slot_714B2_value"] == 2 and record["display_name_text"] for record in main_display_records):
            raise AssertionError("Expected named-dialogue AA13 text mode sample not found")
        if not any(record["slot_714B2_value"] == 3 and not record["display_name_text"] for record in main_display_records):
            raise AssertionError("Expected long-form unnamed AA13 text mode sample not found for mode 3")
        if not any(record["slot_714B2_value"] == 4 and not record["display_name_text"] for record in main_display_records):
            raise AssertionError("Expected long-form unnamed AA13 text mode sample not found for mode 4")
        if not any(len(record["choices"]) >= 2 for record in ac07_character_selection_records):
            raise AssertionError("Expected AC07 character selection cluster not found")
        if not any(len(cluster["choices"]) >= 2 for cluster in ac07_option_clusters):
            raise AssertionError("Expected AC07 visible option cluster not found")
    finally:
        _cleanup_regression_dir(temp_root)


def run_ssb_name_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_name_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        roundtrip_dump_dir = temp_root / "roundtrip_dump"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        text_entries_path = dump_dir / "translation_entries.json"
        text_entries_doc = json.loads(text_entries_path.read_text(encoding="utf-8"))
        target = next(
            (
                entry
                for entry in text_entries_doc["entries"]
                if entry["usage"] == "main_display_name" and entry["storage_bytes"] >= 6
            ),
            None,
        )
        if target is None:
            raise AssertionError("No patchable main-display name found")
        target["text"] = CP932_INPLACE_PATCH_TEXT
        text_entries_path.write_text(json.dumps(text_entries_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_text_entries_file

        apply_text_entries_file(project_json, text_entries_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="cp932")
        rebuilt_project_json, _ = write_project(rebuild_dir, roundtrip_dump_dir, text_encoding="cp932")
        rebuilt_project = json.loads(rebuilt_project_json.read_text(encoding="utf-8"))
        if not any(
            entry["text"] == CP932_INPLACE_PATCH_TEXT and entry["usage"] == "main_display_name"
            for entry in rebuilt_project["translation_entries"]
        ):
            raise AssertionError("Patched main-display name not recovered after re-decompile")
    finally:
        _cleanup_regression_dir(temp_root)


def run_ssb_name_short_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_name_short_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        roundtrip_dump_dir = temp_root / "roundtrip_dump"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        text_entries_path = dump_dir / "translation_entries.json"
        text_entries_doc = json.loads(text_entries_path.read_text(encoding="utf-8"))
        target = next(
            (
                entry
                for entry in text_entries_doc["entries"]
                if entry["usage"] == "main_display_name" and entry["storage_bytes"] >= len(CP932_SHORT_PATCH_TEXT.encode("cp932")) + 1
            ),
            None,
        )
        if target is None:
            raise AssertionError("No short-patchable main-display name found")
        target["text"] = CP932_SHORT_PATCH_TEXT
        text_entries_path.write_text(json.dumps(text_entries_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_text_entries_file

        apply_text_entries_file(project_json, text_entries_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="cp932")
        rebuilt_project_json, _ = write_project(rebuild_dir, roundtrip_dump_dir, text_encoding="cp932")
        rebuilt_project = json.loads(rebuilt_project_json.read_text(encoding="utf-8"))
        if not any(
            entry["text"] == CP932_SHORT_PATCH_TEXT and entry["usage"] == "main_display_name"
            for entry in rebuilt_project["translation_entries"]
        ):
            raise AssertionError("Short patched main-display name not recovered after re-decompile")
    finally:
        _cleanup_regression_dir(temp_root)


def run_ssb_name_long_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_name_long_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        roundtrip_dump_dir = temp_root / "roundtrip_dump"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        text_entries_path = dump_dir / "translation_entries.json"
        text_entries_doc = json.loads(text_entries_path.read_text(encoding="utf-8"))
        target = next(
            (
                entry
                for entry in text_entries_doc["entries"]
                if entry["usage"] == "main_display_name"
                and entry["storage_bytes"] < len(CP932_VARIABLE_PATCH_TEXT.encode("cp932")) + 1
            ),
            None,
        )
        if target is None:
            raise AssertionError("No variable-length main-display name target found")
        target["text"] = CP932_VARIABLE_PATCH_TEXT
        text_entries_path.write_text(json.dumps(text_entries_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_text_entries_file

        apply_text_entries_file(project_json, text_entries_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="cp932")
        rebuilt_project_json, _ = write_project(rebuild_dir, roundtrip_dump_dir, text_encoding="cp932")
        rebuilt_project = json.loads(rebuilt_project_json.read_text(encoding="utf-8"))
        if not any(
            entry["text"] == CP932_VARIABLE_PATCH_TEXT and entry["usage"] == "main_display_name"
            for entry in rebuilt_project["translation_entries"]
        ):
            raise AssertionError("Variable-length patched main-display name not recovered after re-decompile")
    finally:
        _cleanup_regression_dir(temp_root)


def run_ssb_ac07_character_selection_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_ac07_name_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        roundtrip_dump_dir = temp_root / "roundtrip_dump"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        selection_path = dump_dir / "ac07_character_selection_records.json"
        selection_doc = json.loads(selection_path.read_text(encoding="utf-8"))
        cluster = _find_first_ac07_character_selection_cluster(selection_doc["entries"])
        target_choice = next((choice for choice in cluster["choices"] if choice["text"]), None)
        if target_choice is None:
            raise AssertionError("No AC07 character selection target found")
        target_choice["text"] = AC07_NAME_PATCH_TEXT
        selection_path.write_text(json.dumps(selection_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_ac07_character_selection_file

        apply_ac07_character_selection_file(project_json, selection_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="cp932")
        rebuilt_project_json, _ = write_project(rebuild_dir, roundtrip_dump_dir, text_encoding="cp932")
        rebuilt_project = json.loads(rebuilt_project_json.read_text(encoding="utf-8"))
        rebuilt_clusters = rebuilt_project["ac07_character_selection_records"]
        if not any(
            choice["text"] == AC07_NAME_PATCH_TEXT
            for cluster in rebuilt_clusters
            for choice in cluster["choices"]
        ):
            raise AssertionError("Patched AC07 character selection name not recovered after re-decompile")
    finally:
        _cleanup_regression_dir(temp_root)


def run_ssb_ac07_visible_cluster_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_ac07_cluster_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        roundtrip_dump_dir = temp_root / "roundtrip_dump"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        cluster_path = dump_dir / "ac07_option_clusters.json"
        cluster_doc = json.loads(cluster_path.read_text(encoding="utf-8"))
        cluster = _find_first_ac07_option_cluster(cluster_doc["entries"])
        target_choice = next((choice for choice in cluster["choices"] if choice["text"]), None)
        if target_choice is None:
            raise AssertionError("No AC07 option target found")
        target_choice["text"] = AC07_NAME_PATCH_TEXT
        cluster_path.write_text(json.dumps(cluster_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_ac07_visible_clusters_file

        apply_ac07_visible_clusters_file(project_json, cluster_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="cp932")
        rebuilt_project_json, _ = write_project(rebuild_dir, roundtrip_dump_dir, text_encoding="cp932")
        rebuilt_project = json.loads(rebuilt_project_json.read_text(encoding="utf-8"))
        rebuilt_clusters = rebuilt_project["ac07_option_clusters"]
        if not any(
            choice["text"] == AC07_NAME_PATCH_TEXT
            for cluster in rebuilt_clusters
            for choice in cluster["choices"]
        ):
            raise AssertionError("Patched AC07 option text not recovered after re-decompile")
    finally:
        _cleanup_regression_dir(temp_root)


def run_ssb_ac07_visible_cluster_short_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_ac07_cluster_short_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        roundtrip_dump_dir = temp_root / "roundtrip_dump"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        cluster_path = dump_dir / "ac07_option_clusters.json"
        cluster_doc = json.loads(cluster_path.read_text(encoding="utf-8"))
        cluster = _find_first_ac07_option_cluster(cluster_doc["entries"])
        target_choice = next(
            (
                choice
                for choice in cluster["choices"]
                if len(str(choice["text"]).encode("cp932")) + 1 >= len(CP932_SHORT_PATCH_TEXT.encode("cp932")) + 1
            ),
            None,
        )
        if target_choice is None:
            raise AssertionError("No short-patchable AC07 option target found")
        target_choice["text"] = CP932_SHORT_PATCH_TEXT
        cluster_path.write_text(json.dumps(cluster_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_ac07_visible_clusters_file

        apply_ac07_visible_clusters_file(project_json, cluster_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="cp932")
        rebuilt_project_json, _ = write_project(rebuild_dir, roundtrip_dump_dir, text_encoding="cp932")
        rebuilt_project = json.loads(rebuilt_project_json.read_text(encoding="utf-8"))
        rebuilt_clusters = rebuilt_project["ac07_option_clusters"]
        if not any(
            choice["text"] == CP932_SHORT_PATCH_TEXT
            for cluster in rebuilt_clusters
            for choice in cluster["choices"]
        ):
            raise AssertionError("Short patched AC07 option text not recovered after re-decompile")
    finally:
        _cleanup_regression_dir(temp_root)


def run_ssb_ac07_visible_cluster_long_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_ac07_cluster_long_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        roundtrip_dump_dir = temp_root / "roundtrip_dump"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        cluster_path = dump_dir / "ac07_option_clusters.json"
        cluster_doc = json.loads(cluster_path.read_text(encoding="utf-8"))
        target_choice = next(
            (
                choice
                for cluster in cluster_doc["entries"]
                for choice in cluster["choices"]
                if len(str(choice["text"]).encode("cp932")) + 1 < len(CP932_VARIABLE_PATCH_TEXT.encode("cp932")) + 1
            ),
            None,
        )
        if target_choice is None:
            raise AssertionError("No variable-length AC07 option target found")
        target_choice["text"] = CP932_VARIABLE_PATCH_TEXT
        cluster_path.write_text(json.dumps(cluster_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_ac07_visible_clusters_file

        apply_ac07_visible_clusters_file(project_json, cluster_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="cp932")
        rebuilt_project_json, _ = write_project(rebuild_dir, roundtrip_dump_dir, text_encoding="cp932")
        rebuilt_project = json.loads(rebuilt_project_json.read_text(encoding="utf-8"))
        rebuilt_clusters = rebuilt_project["ac07_option_clusters"]
        if not any(
            choice["text"] == CP932_VARIABLE_PATCH_TEXT
            for cluster in rebuilt_clusters
            for choice in cluster["choices"]
        ):
            raise AssertionError("Variable-length patched AC07 option text not recovered after re-decompile")
    finally:
        _cleanup_regression_dir(temp_root)


def run_ssb_name_related_records_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_name_related_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        roundtrip_dump_dir = temp_root / "roundtrip_dump"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        records_path = dump_dir / "name_related_records.json"
        records_doc = json.loads(records_path.read_text(encoding="utf-8"))

        aa13_done = False
        ac07_done = False
        for entry in records_doc["entries"]:
            if entry["record_kind"] == "aa13_display_name" and not aa13_done:
                entry["text"] = CP932_INPLACE_PATCH_TEXT
                aa13_done = True
            elif entry["record_kind"] == "ac07_character_selection_name" and not ac07_done:
                entry["text"] = AC07_NAME_PATCH_TEXT
                ac07_done = True
            if aa13_done and ac07_done:
                break
        if not aa13_done or not ac07_done:
            raise AssertionError("Could not find both AA13 and AC07 name-related targets")
        records_path.write_text(json.dumps(records_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_name_related_records_file

        apply_name_related_records_file(project_json, records_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="cp932")
        rebuilt_project_json, _ = write_project(rebuild_dir, roundtrip_dump_dir, text_encoding="cp932")
        rebuilt_project = json.loads(rebuilt_project_json.read_text(encoding="utf-8"))
        if not any(rec["display_name_text"] == CP932_INPLACE_PATCH_TEXT for rec in rebuilt_project["main_display_records"]):
            raise AssertionError("Patched AA13 name not recovered from name_related_records")
        if not any(
            choice["text"] == AC07_NAME_PATCH_TEXT
            for cluster in rebuilt_project["ac07_character_selection_records"]
            for choice in cluster["choices"]
        ):
            raise AssertionError("Patched AC07 character selection name not recovered from name_related_records")
    finally:
        _cleanup_regression_dir(temp_root)


def run_ssb_name_related_records_short_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_name_related_short_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        roundtrip_dump_dir = temp_root / "roundtrip_dump"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        records_path = dump_dir / "name_related_records.json"
        records_doc = json.loads(records_path.read_text(encoding="utf-8"))
        target = next(
            (
                entry
                for entry in records_doc["entries"]
                if entry["record_kind"] in {"aa13_display_name", "ac07_character_selection_name"}
                and len(str(entry["text"]).encode("cp932")) + 1 >= len(CP932_SHORT_PATCH_TEXT.encode("cp932")) + 1
            ),
            None,
        )
        if target is None:
            raise AssertionError("No short-patchable name-related target found")
        target["text"] = CP932_SHORT_PATCH_TEXT
        records_path.write_text(json.dumps(records_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_name_related_records_file

        apply_name_related_records_file(project_json, records_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="cp932")
        rebuilt_project_json, _ = write_project(rebuild_dir, roundtrip_dump_dir, text_encoding="cp932")
        rebuilt_project = json.loads(rebuilt_project_json.read_text(encoding="utf-8"))
        if not any(
            entry["text"] == CP932_SHORT_PATCH_TEXT
            for entry in rebuilt_project["name_related_records"]
            if entry["record_kind"] in {"aa13_display_name", "ac07_character_selection_name"}
        ):
            raise AssertionError("Short patched name-related text not recovered after re-decompile")
    finally:
        _cleanup_regression_dir(temp_root)


def run_ssb_name_related_records_long_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_name_related_long_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        roundtrip_dump_dir = temp_root / "roundtrip_dump"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        records_path = dump_dir / "name_related_records.json"
        records_doc = json.loads(records_path.read_text(encoding="utf-8"))
        target = next(
            (
                entry
                for entry in records_doc["entries"]
                if entry["record_kind"] in {"aa13_display_name", "ac07_character_selection_name"}
                and len(str(entry["text"]).encode("cp932")) + 1 < len(CP932_VARIABLE_PATCH_TEXT.encode("cp932")) + 1
            ),
            None,
        )
        if target is None:
            raise AssertionError("No variable-length name-related target found")
        target["text"] = CP932_VARIABLE_PATCH_TEXT
        records_path.write_text(json.dumps(records_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_name_related_records_file

        apply_name_related_records_file(project_json, records_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="cp932")
        rebuilt_project_json, _ = write_project(rebuild_dir, roundtrip_dump_dir, text_encoding="cp932")
        rebuilt_project = json.loads(rebuilt_project_json.read_text(encoding="utf-8"))
        if not any(
            entry["text"] == CP932_VARIABLE_PATCH_TEXT
            for entry in rebuilt_project["name_related_records"]
            if entry["record_kind"] in {"aa13_display_name", "ac07_character_selection_name"}
        ):
            raise AssertionError("Variable-length patched name-related text not recovered after re-decompile")
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
                if entry["usage"] == "main_display_text" and entry["storage_bytes"] >= 6
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


def run_ssb_text_short_patch_regression(title_root: Path) -> None:
    script_dir = title_root / "game" / "SCRIPT"
    temp_root = _fresh_regression_dir(title_root, "kuro_ssb_patch_short_")
    try:
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        roundtrip_dump_dir = temp_root / "roundtrip_dump"
        project_json, _ = write_project(script_dir, dump_dir, text_encoding="cp932")
        text_entries_path = dump_dir / "translation_entries.json"
        text_entries_doc = json.loads(text_entries_path.read_text(encoding="utf-8"))
        target = next(
            (
                entry
                for entry in text_entries_doc["entries"]
                if entry["usage"] == "main_display_text" and entry["storage_bytes"] >= len(CP932_SHORT_PATCH_TEXT.encode("cp932")) + 1
            ),
            None,
        )
        if target is None:
            raise AssertionError("No short-patchable main-display text found")
        target["text"] = CP932_SHORT_PATCH_TEXT
        text_entries_path.write_text(json.dumps(text_entries_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        from script.ssb.compile import apply_text_entries_file

        apply_text_entries_file(project_json, text_entries_path)
        compile_project_file(project_json, rebuild_dir, text_encoding="cp932")
        rebuilt_project_json, _ = write_project(rebuild_dir, roundtrip_dump_dir, text_encoding="cp932")
        rebuilt_project = json.loads(rebuilt_project_json.read_text(encoding="utf-8"))
        if not any(
            entry["text"] == CP932_SHORT_PATCH_TEXT and entry["usage"] == "main_display_text"
            for entry in rebuilt_project["translation_entries"]
        ):
            raise AssertionError("Short patched main-display text not recovered after re-decompile")
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
                if entry["usage"] == "main_display_text"
                and entry["storage_bytes"] < len(CP932_VARIABLE_PATCH_TEXT.encode("cp932")) + 1
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
                if entry["usage"] == "main_display_text"
                and entry["storage_bytes"] >= len(GBK_PATCH_TEXT.encode("gbk")) + 1
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
