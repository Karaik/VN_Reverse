from __future__ import annotations

import json
from pathlib import Path


def check_text_fit(
    input_path: Path,
    *,
    entry_index: int | None = None,
    entry_offset: int | None = None,
    text: str,
    text_encoding: str = "cp932",
) -> dict[str, object]:
    if entry_index is None and entry_offset is None:
        raise ValueError("Either entry_index or entry_offset must be provided")
    doc = json.loads(input_path.read_text(encoding="utf-8"))
    entries = doc.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Document does not contain an entries list")

    target = None
    for entry in entries:
        if entry_index is not None and int(entry.get("index", -1)) == entry_index:
            target = entry
            break
        if entry_offset is not None and int(entry.get("offset", -1)) == entry_offset:
            target = entry
            break
    if target is None:
        raise ValueError("Requested entry was not found in document")

    encoded = text.encode(text_encoding)
    capacity = int(target.get("capacity_bytes", target.get("length", 0)))
    in_place_capacity = int(target.get("in_place_capacity_bytes", capacity))
    supports_expansion_rebuild = bool(target.get("supports_expansion_rebuild", False))
    return {
        "offset": int(target.get("offset", -1)),
        "index": int(target.get("index", -1)),
        "original_text": str(target.get("original_text", "")),
        "replacement_text": text,
        "patch_mode": str(target.get("patch_mode", "unknown")),
        "capacity_bytes": capacity,
        "in_place_capacity_bytes": in_place_capacity,
        "replacement_bytes": len(encoded),
        "fits": len(encoded) <= in_place_capacity,
        "fits_in_place": len(encoded) <= in_place_capacity,
        "requires_expansion_rebuild": len(encoded) > in_place_capacity,
        "supports_expansion_rebuild": supports_expansion_rebuild,
        "can_rebuild_with_expansion": supports_expansion_rebuild,
    }
