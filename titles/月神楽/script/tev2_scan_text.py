from __future__ import annotations

import json
from pathlib import Path

from script.tev2_bttext import parse_bttext_text
from script.tev2_scr import parse_scr_text
from script.tev2_text_tables import parse_table


def build_text_scan(resource_root: Path, output_path: Path, *, text_encoding: str = "cp932") -> Path:
    carriers: list[dict[str, object]] = []

    data_root = resource_root / "data"
    script_root = resource_root / "script"

    if data_root.is_dir():
        for path in sorted(data_root.glob("*.dat")):
            name = path.name.lower()
            if name.startswith("tiname") or name.startswith("tiballoon"):
                doc = parse_table(path, text_encoding=text_encoding)
                carriers.append(
                    {
                        "carrier_type": "fixed_table",
                        "path": str(path),
                        "entry_count": len(doc.entries),
                    }
                )
            elif name == "bttext.dat":
                try:
                    doc = parse_bttext_text(path, text_encoding=text_encoding)
                    carriers.append(
                        {
                            "carrier_type": "bttext",
                            "path": str(path),
                            "entry_count": len(doc.entries),
                        }
                    )
                except ValueError:
                    pass

    if script_root.is_dir():
        for path in sorted(script_root.glob("*.scr")):
            doc = parse_scr_text(path, text_encoding=text_encoding)
            carriers.append(
                {
                    "carrier_type": "scr_text_candidates",
                    "path": str(path),
                    "entry_count": len(doc.entries),
                }
            )

    payload = {
        "format": "TE_V2_TEXT_SCAN",
        "resource_root": str(resource_root),
        "text_encoding": text_encoding,
        "carrier_count": len(carriers),
        "carriers": carriers,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
