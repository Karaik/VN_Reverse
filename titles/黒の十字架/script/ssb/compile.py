"""Compiler for SAISYS SSB project JSON."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from .binary import normalize_text_encoding, pack_code_words, write_script_pair, xor_aa
from .constants import DEFAULT_TEXT_ENCODING, JSON_FORMAT


def load_project(project_path: Path) -> dict[str, object]:
    project = json.loads(project_path.read_text(encoding="utf-8"))
    if project.get("format") != JSON_FORMAT:
        raise ValueError("Unsupported project format")
    return project


def _apply_string_patch(decoded_data: bytearray, entry: dict[str, object]) -> None:
    start = int(entry["byte_offset"])
    storage_bytes = int(entry["storage_bytes"])
    text = str(entry["text"])
    encoded = text.encode("cp932")
    if len(encoded) > storage_bytes:
        raise ValueError(
            f"String at 0x{start:08X} exceeds in-place storage: {len(encoded)} > {storage_bytes}"
        )
    padded = encoded + (b"\x00" * (storage_bytes - len(encoded)))
    decoded_data[start : start + storage_bytes] = padded


def _apply_string_patch_with_relocation(
    decoded_data: bytearray,
    entry: dict[str, object],
    code_words: list[int],
    target_text_encoding: str,
    source_text_encoding: str,
) -> None:
    start = int(entry["byte_offset"])
    storage_bytes = int(entry["storage_bytes"])
    old_word_offset = int(entry["word_offset"])
    text = str(entry["text"])
    original_text = str(entry.get("original_text", text))
    original_raw_hex = str(entry.get("raw_hex", ""))
    if text == original_text and original_raw_hex:
        encoded = bytes.fromhex(original_raw_hex) + b"\x00"
    else:
        encoded = text.encode(target_text_encoding) + b"\x00"
    if len(encoded) <= storage_bytes:
        padded = encoded + (b"\x00" * (storage_bytes - len(encoded)))
        decoded_data[start : start + storage_bytes] = padded
        return

    while len(decoded_data) % 4 != 0:
        decoded_data.append(0)
    new_byte_offset = len(decoded_data)
    decoded_data.extend(encoded)
    while len(decoded_data) % 4 != 0:
        decoded_data.append(0)
    new_word_offset = new_byte_offset // 4

    for index, value in enumerate(code_words):
        if value == old_word_offset:
            code_words[index] = new_word_offset


def compile_project(
    project: dict[str, object],
    text_encoding: str | None = None,
    source_text_encoding: str | None = None,
) -> tuple[bytes, bytes]:
    if text_encoding is None:
        text_encoding = str(project.get("text_encoding", DEFAULT_TEXT_ENCODING))
    target_text_encoding = normalize_text_encoding(text_encoding)
    if source_text_encoding is None:
        source_text_encoding = str(project.get("text_encoding", DEFAULT_TEXT_ENCODING))
    source_text_encoding = normalize_text_encoding(source_text_encoding)
    code_words = [int(value) & 0xFFFFFFFF for value in project["code_words"]]
    decoded_data = bytearray(base64.b64decode(project["decoded_data_base64"]))
    for entry in project["strings"]:
        _apply_string_patch_with_relocation(
            decoded_data,
            entry,
            code_words,
            target_text_encoding=target_text_encoding,
            source_text_encoding=source_text_encoding,
        )
    code_bytes = pack_code_words(code_words)
    encoded_data = xor_aa(bytes(decoded_data))
    return code_bytes, encoded_data


def compile_project_file(
    project_path: Path,
    output_dir: Path,
    text_encoding: str | None = None,
    source_text_encoding: str | None = None,
) -> tuple[Path, Path]:
    project = load_project(project_path)
    code_bytes, data_bytes = compile_project(
        project,
        text_encoding=text_encoding,
        source_text_encoding=source_text_encoding,
    )
    write_script_pair(output_dir, code_bytes, data_bytes)
    return output_dir / "CODE.SSB", output_dir / "DATA.SSB"


def apply_text_entries_file(project_path: Path, text_entries_path: Path) -> None:
    project = load_project(project_path)
    text_entries_doc = json.loads(text_entries_path.read_text(encoding="utf-8"))
    patches = {
        (int(entry["word_offset"]), int(entry["byte_offset"])): entry["text"]
        for entry in text_entries_doc["entries"]
    }
    updated = 0
    for entry in project["strings"]:
        key = (int(entry["word_offset"]) if entry["word_offset"] is not None else -1, int(entry["byte_offset"]))
        if key in patches:
            entry["text"] = str(patches[key])
            updated += 1
    if updated == 0:
        raise ValueError("No matching text entries were applied")
    # keep text_entries in sync for subsequent exports / edits
    if "text_entries" in project:
        for entry in project["text_entries"]:
            key = (int(entry["word_offset"]) if entry["word_offset"] is not None else -1, int(entry["byte_offset"]))
            if key in patches:
                entry["text"] = str(patches[key])
    if "translation_entries" in project:
        for entry in project["translation_entries"]:
            key = (int(entry["word_offset"]) if entry["word_offset"] is not None else -1, int(entry["byte_offset"]))
            if key in patches:
                entry["text"] = str(patches[key])
    project_path.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_ac07_character_selection_file(project_path: Path, selection_path: Path) -> None:
    project = load_project(project_path)
    selection_doc = json.loads(selection_path.read_text(encoding="utf-8"))
    patches = {
        (int(choice["text_word_offset"]), int(choice["text_byte_offset"])): str(choice["text"])
        for cluster in selection_doc["entries"]
        for choice in cluster["choices"]
    }
    updated = 0
    for entry in project["strings"]:
        key = (
            int(entry["word_offset"]) if entry["word_offset"] is not None else -1,
            int(entry["byte_offset"]),
        )
        if key in patches:
            entry["text"] = patches[key]
            updated += 1
    if updated == 0:
        raise ValueError("No matching AC07 character selection entries were applied")
    if "ac07_ui_records" in project:
        for entry in project["ac07_ui_records"]:
            key = (int(entry["text_word_offset"]), int(entry["text_byte_offset"]))
            if key in patches:
                entry["text"] = patches[key]
    if "strings" in project:
        for entry in project["strings"]:
            key = (
                int(entry["word_offset"]) if entry["word_offset"] is not None else -1,
                int(entry["byte_offset"]),
            )
            if key in patches:
                entry["text"] = patches[key]
    if "ac07_visible_clusters" in project:
        for cluster in project["ac07_visible_clusters"]:
            for choice in cluster["choices"]:
                key = (int(choice["text_word_offset"]), int(choice["text_byte_offset"]))
                if key in patches:
                    choice["text"] = patches[key]
    if "ac07_character_selection_records" in project:
        for cluster in project["ac07_character_selection_records"]:
            for choice in cluster["choices"]:
                key = (int(choice["text_word_offset"]), int(choice["text_byte_offset"]))
                if key in patches:
                    choice["text"] = patches[key]
    if "name_related_records" in project:
        for entry in project["name_related_records"]:
            key = (int(entry["text_word_offset"]), int(entry["text_byte_offset"]))
            if key in patches:
                entry["text"] = patches[key]
    project_path.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_ac07_visible_clusters_file(project_path: Path, cluster_path: Path) -> None:
    project = load_project(project_path)
    cluster_doc = json.loads(cluster_path.read_text(encoding="utf-8"))
    patches = {
        (int(choice["text_word_offset"]), int(choice["text_byte_offset"])): str(choice["text"])
        for cluster in cluster_doc["entries"]
        for choice in cluster["choices"]
        if choice.get("text")
    }
    updated = 0
    for entry in project["strings"]:
        key = (
            int(entry["word_offset"]) if entry["word_offset"] is not None else -1,
            int(entry["byte_offset"]),
        )
        if key in patches:
            entry["text"] = patches[key]
            updated += 1
    if updated == 0:
        raise ValueError("No matching AC07 visible cluster entries were applied")
    if "ac07_ui_records" in project:
        for entry in project["ac07_ui_records"]:
            key = (int(entry["text_word_offset"]), int(entry["text_byte_offset"]))
            if key in patches:
                entry["text"] = patches[key]
    if "ac07_visible_clusters" in project:
        for cluster in project["ac07_visible_clusters"]:
            for choice in cluster["choices"]:
                key = (int(choice["text_word_offset"]), int(choice["text_byte_offset"]))
                if key in patches:
                    choice["text"] = patches[key]
    if "ac07_character_selection_records" in project:
        for cluster in project["ac07_character_selection_records"]:
            for choice in cluster["choices"]:
                key = (int(choice["text_word_offset"]), int(choice["text_byte_offset"]))
                if key in patches:
                    choice["text"] = patches[key]
    if "ac07_option_clusters" in project:
        for cluster in project["ac07_option_clusters"]:
            for choice in cluster["choices"]:
                key = (int(choice["text_word_offset"]), int(choice["text_byte_offset"]))
                if key in patches:
                    choice["text"] = patches[key]
    if "name_related_records" in project:
        for entry in project["name_related_records"]:
            key = (int(entry["text_word_offset"]), int(entry["text_byte_offset"]))
            if key in patches:
                entry["text"] = patches[key]
    project_path.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_name_related_records_file(project_path: Path, records_path: Path) -> None:
    project = load_project(project_path)
    records_doc = json.loads(records_path.read_text(encoding="utf-8"))
    patches = {
        (int(entry["text_word_offset"]), int(entry["text_byte_offset"])): str(entry["text"])
        for entry in records_doc["entries"]
    }
    updated = 0
    for entry in project["strings"]:
        key = (
            int(entry["word_offset"]) if entry["word_offset"] is not None else -1,
            int(entry["byte_offset"]),
        )
        if key in patches:
            entry["text"] = patches[key]
            updated += 1
    if updated == 0:
        raise ValueError("No matching name-related entries were applied")
    if "main_display_records" in project:
        for record in project["main_display_records"]:
            key = (int(record["display_name_word_offset"]) if record["display_name_word_offset"] is not None else -1, int(record["display_name_byte_offset"] or -1))
            if key in patches:
                record["display_name_text"] = patches[key]
    if "ac07_ui_records" in project:
        for entry in project["ac07_ui_records"]:
            key = (int(entry["text_word_offset"]), int(entry["text_byte_offset"]))
            if key in patches:
                entry["text"] = patches[key]
    if "ac07_visible_clusters" in project:
        for cluster in project["ac07_visible_clusters"]:
            for choice in cluster["choices"]:
                key = (int(choice["text_word_offset"]), int(choice["text_byte_offset"]))
                if key in patches:
                    choice["text"] = patches[key]
    if "ac07_character_selection_records" in project:
        for cluster in project["ac07_character_selection_records"]:
            for choice in cluster["choices"]:
                key = (int(choice["text_word_offset"]), int(choice["text_byte_offset"]))
                if key in patches:
                    choice["text"] = patches[key]
    if "ac07_option_clusters" in project:
        for cluster in project["ac07_option_clusters"]:
            for choice in cluster["choices"]:
                key = (int(choice["text_word_offset"]), int(choice["text_byte_offset"]))
                if key in patches:
                    choice["text"] = patches[key]
    if "name_related_records" in project:
        for entry in project["name_related_records"]:
            key = (int(entry["text_word_offset"]), int(entry["text_byte_offset"]))
            if key in patches:
                entry["text"] = patches[key]
    project_path.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
