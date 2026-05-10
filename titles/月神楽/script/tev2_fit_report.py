from __future__ import annotations

import json
from pathlib import Path


def build_fit_report(
    input_path: Path,
    output_path: Path,
    *,
    extra_bytes: int = 0,
    text_encoding: str = "cp932",
) -> Path:
    if extra_bytes < 0:
        raise ValueError("extra_bytes must be non-negative")
    doc = json.loads(input_path.read_text(encoding="utf-8"))
    entries = doc.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Document does not contain an entries list")

    report_entries: list[dict[str, object]] = []
    for entry in entries:
        original_text = str(entry.get("original_text", entry.get("text", "")))
        capacity = int(entry.get("capacity_bytes", entry.get("length", 0)))
        in_place_capacity = int(entry.get("in_place_capacity_bytes", capacity))
        supports_expansion_rebuild = bool(entry.get("supports_expansion_rebuild", False))
        original_bytes = len(original_text.encode(text_encoding, errors="replace"))
        estimated_bytes = original_bytes + extra_bytes
        report_entries.append(
            {
                "index": int(entry.get("index", -1)),
                "offset": int(entry.get("offset", -1)),
                "patch_mode": str(entry.get("patch_mode", "unknown")),
                "capacity_bytes": capacity,
                "in_place_capacity_bytes": in_place_capacity,
                "original_bytes": original_bytes,
                "estimated_bytes": estimated_bytes,
                "fits_estimate": estimated_bytes <= in_place_capacity,
                "fits_in_place_estimate": estimated_bytes <= in_place_capacity,
                "requires_expansion_rebuild_estimate": estimated_bytes > in_place_capacity,
                "supports_expansion_rebuild": supports_expansion_rebuild,
                "can_rebuild_with_expansion_estimate": supports_expansion_rebuild,
                "text_preview": original_text,
            }
        )

    payload = {
        "format": "TE_V2_TEXT_FIT_REPORT",
        "source_path": str(input_path),
        "text_encoding": text_encoding,
        "extra_bytes": extra_bytes,
        "entries": report_entries,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
