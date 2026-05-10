from __future__ import annotations

import json
from pathlib import Path


def patch_text_doc(
    input_path: Path,
    output_path: Path,
    *,
    entry_index: int | None = None,
    entry_offset: int | None = None,
    text: str,
) -> Path:
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

    target["text"] = text
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
