"""Decompiler for SAISYS SSB script files."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from .binary import load_code_words, load_script_pair, normalize_text_encoding, to_signed_u32, xor_aa
from .constants import DEFAULT_TEXT_ENCODING, JSON_FORMAT, JSON_VERSION, KNOWN_OPCODE_NAMES

TEXT_RELATED_WINDOW_OPS = {
    -0x7FFBFFFF,  # VM_FORMAT_INT_OR_TEXT
    -0x7FF6FFFE,  # 407A5C text object set string
    -0x7FFF0000,  # raw data load often used to fetch string slot
    -0x7FFBFFFE,  # direct control text set
}


ASCII_RESOURCE_RE = re.compile(r"^[A-Za-z0-9_./:\\-]+$")


def _looks_text(text: str) -> bool:
    if not text:
        return False
    printable = sum(1 for ch in text if ch.isprintable())
    return printable / len(text) >= 0.9


def _is_japanese_text(text: str) -> bool:
    return any(
        ("\u3040" <= ch <= "\u30ff") or ("\u4e00" <= ch <= "\u9fff")
        for ch in text
    )


def _categorize_text(text: str) -> str:
    if _is_japanese_text(text):
        return "jp_text"
    if ASCII_RESOURCE_RE.fullmatch(text):
        return "ascii_resource"
    return "text"


def scan_strings(
    decoded_data: bytes,
    reference_counts: dict[int, int],
    text_reference_map: dict[int, list[int]],
    text_encoding: str,
) -> list[dict[str, object]]:
    strings: list[dict[str, object]] = []
    offset = 0
    size = len(decoded_data)
    while offset < size:
        if offset > 0 and decoded_data[offset - 1] != 0:
            offset += 1
            continue
        terminator = decoded_data.find(b"\x00", offset)
        if terminator == -1:
            break
        raw = decoded_data[offset:terminator]
        offset = terminator + 1
        if len(raw) < 4:
            continue
        try:
            text = raw.decode(text_encoding)
        except UnicodeDecodeError:
            continue
        if not _looks_text(text):
            continue
        word_offset = offset_to_word_offset(terminator - len(raw))
        text_reference_pcs = text_reference_map.get(word_offset, []) if word_offset is not None else []
        strings.append(
            {
                "byte_offset": terminator - len(raw),
                "word_offset": word_offset,
                "storage_bytes": len(raw) + 1,
                "raw_hex": raw.hex(),
                "text": text,
                "original_text": text,
                "category": _categorize_text(text),
                "reference_count": reference_counts.get(word_offset, 0) if word_offset is not None else 0,
                "text_reference_count": len(text_reference_pcs),
                "text_reference_pcs": text_reference_pcs[:8],
            }
        )
    return strings


def offset_to_word_offset(byte_offset: int) -> int | None:
    if byte_offset % 4 != 0:
        return None
    return byte_offset // 4


def build_reference_counts(code_words: list[int], data_size: int) -> dict[int, int]:
    counts: dict[int, int] = {}
    for word in code_words:
        if word >= 0x80000000:
            continue
        byte_offset = word * 4
        if byte_offset >= data_size:
            continue
        counts[word] = counts.get(word, 0) + 1
    return counts


def build_text_reference_map(code_words: list[int], data_size: int) -> dict[int, list[int]]:
    refs: dict[int, list[int]] = {}
    for index, word in enumerate(code_words):
        if word >= 0x80000000:
            continue
        start = max(0, index - 6)
        window = [to_signed_u32(code_words[pos]) for pos in range(start, index) if code_words[pos] >= 0x80000000]
        if not any(op in TEXT_RELATED_WINDOW_OPS for op in window):
            continue
        byte_offset = word * 4
        if byte_offset >= data_size:
            continue
        refs.setdefault(word, []).append(index)
    return refs


def build_text_entries(strings: list[dict[str, object]]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for entry in strings:
        if entry["text_reference_count"] <= 0:
            continue
        if entry["category"] not in {"jp_text", "text"}:
            continue
        entries.append(
            {
                "word_offset": entry["word_offset"],
                "byte_offset": entry["byte_offset"],
                "storage_bytes": entry["storage_bytes"],
                "text": entry["text"],
                "category": entry["category"],
                "text_reference_count": entry["text_reference_count"],
            }
        )
    return sorted(entries, key=lambda item: (item["byte_offset"], item["word_offset"]))


def build_translation_entries(strings: list[dict[str, object]]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for entry in strings:
        if entry["text_reference_count"] <= 0:
            continue
        if entry["category"] == "ascii_resource":
            continue
        text = str(entry["text"])
        usage = "dialogue"
        if text in {"はい", "いいえ", "やめる", "帰る", "わかった", "止める", "止めない"}:
            usage = "choice"
        elif text.startswith("→") or text.endswith("へ") or text.endswith("エンド") or text == "NO DATA":
            usage = "system_or_label"
        elif any(mark in text for mark in {"。", "、", "！", "？", "…", "・", "♪", "　", "「", "」", "～"}):
            usage = "dialogue"
        elif len(text) <= 16 and "　" not in text and "。" not in text and "、" not in text and "「" not in text:
            usage = "choice_or_label"
        entries.append(
            {
                "word_offset": entry["word_offset"],
                "byte_offset": entry["byte_offset"],
                "storage_bytes": entry["storage_bytes"],
                "text": entry["text"],
                "category": entry["category"],
                "usage": usage,
                "text_reference_count": entry["text_reference_count"],
                "text_reference_pcs": entry["text_reference_pcs"],
            }
        )
    return sorted(entries, key=lambda item: (item["byte_offset"], item["word_offset"]))


def refine_translation_entry_usages(code_words: list[int], entries: list[dict[str, object]]) -> list[dict[str, object]]:
    for entry in entries:
        for pc in entry.get("text_reference_pcs", []):
            if pc + 4 >= len(code_words):
                continue
            next1 = code_words[pc + 1]
            next2 = code_words[pc + 2]
            next3 = to_signed_u32(code_words[pc + 3])
            next4 = to_signed_u32(code_words[pc + 4])
            if next1 == 0x50777 and next2 < 0x80000000 and next3 == -2147418112 and next4 == -2147483647:
                text = str(entry["text"])
                if any(mark in text for mark in {"。", "、", "！", "？", "…", "・", "♪", "　", "「", "」", "～"}):
                    entry["usage"] = "table_entry_dialogue"
                else:
                    entry["usage"] = "table_entry_label"
                break
            if entry["usage"] == "dialogue":
                if next3 == -2147418111 and next4 == -2147418112:
                    entry["usage"] = "table_entry_dialogue"
                    break
                if next1 == 473810 and next3 == -2147418112 and next4 == -2147483647:
                    entry["usage"] = "table_entry_dialogue"
                    break
    return entries


def build_project(script_dir: Path, text_encoding: str = DEFAULT_TEXT_ENCODING) -> dict[str, object]:
    text_encoding = normalize_text_encoding(text_encoding)
    code_bytes, data_bytes = load_script_pair(script_dir)
    decoded_data = xor_aa(data_bytes)
    code_words = load_code_words(code_bytes)
    reference_counts = build_reference_counts(code_words, len(decoded_data))
    text_reference_map = build_text_reference_map(code_words, len(decoded_data))
    strings = scan_strings(decoded_data, reference_counts, text_reference_map, text_encoding)
    text_entries = build_text_entries(strings)
    translation_entries = build_translation_entries(strings)
    translation_entries = refine_translation_entry_usages(code_words, translation_entries)
    return {
        "format": JSON_FORMAT,
        "version": JSON_VERSION,
        "text_encoding": text_encoding,
        "script_dir": str(script_dir),
        "code_size": len(code_bytes),
        "data_size": len(data_bytes),
        "code_words": code_words,
        "decoded_data_base64": base64.b64encode(decoded_data).decode("ascii"),
        "strings": strings,
        "text_entries": text_entries,
        "translation_entries": translation_entries,
    }


def build_ssbsrc(project: dict[str, object]) -> str:
    code_words = project["code_words"]
    strings = project["strings"]
    string_lookup = {
        entry["word_offset"]: entry["text"]
        for entry in strings
        if entry["word_offset"] is not None
    }
    lines = [
        "# SAISYS SSB source dump",
        "# Positive values are kept as literals; if they align to a decoded string offset, a preview is attached.",
        "",
    ]
    for index, unsigned_value in enumerate(code_words):
        signed_value = to_signed_u32(unsigned_value)
        if signed_value < 0:
            name = KNOWN_OPCODE_NAMES.get(signed_value, f"OP_0x{unsigned_value:08X}")
            lines.append(f"{index:08d}: 0x{unsigned_value:08X} {signed_value:12d} {name}")
            continue
        preview = ""
        if unsigned_value in string_lookup:
            text = string_lookup[unsigned_value].replace("\r", "\\r").replace("\n", "\\n")
            preview = f" ; text={text!r}"
        lines.append(f"{index:08d}: 0x{unsigned_value:08X} {signed_value:12d}{preview}")
    return "\n".join(lines) + "\n"


def write_project(script_dir: Path, output_dir: Path, text_encoding: str = DEFAULT_TEXT_ENCODING) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    project = build_project(script_dir, text_encoding=text_encoding)
    json_path = output_dir / "script.json"
    src_path = output_dir / "script.ssbsrc"
    text_json_path = output_dir / "text_entries.json"
    translation_json_path = output_dir / "translation_entries.json"
    json_path.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    src_path.write_text(build_ssbsrc(project), encoding="utf-8")
    text_json_path.write_text(
        json.dumps(
            {
                "format": "saisys-ssb-text-entries",
                "version": JSON_VERSION,
                "entries": project["text_entries"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    translation_json_path.write_text(
        json.dumps(
            {
                "format": "saisys-ssb-translation-entries",
                "version": JSON_VERSION,
                "entries": project["translation_entries"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return json_path, src_path
