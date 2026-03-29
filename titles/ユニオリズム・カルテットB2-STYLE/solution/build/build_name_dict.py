from __future__ import annotations

import json
from pathlib import Path

from solution.common.paths import TRANSLATED_NAME_TABLE_DIR


def build_name_dict(name_table_file: Path | None = None, out_file: Path | None = None) -> Path:
    if name_table_file is None:
        name_table_file = TRANSLATED_NAME_TABLE_DIR / "name_table.json"
    if out_file is None:
        out_file = TRANSLATED_NAME_TABLE_DIR / "galtrans_names.toml"

    data = json.loads(name_table_file.read_text(encoding="utf-8"))
    lines = ["gptDict = ["]
    for entry in data:
        source_name = entry.get("source_name", "")
        translated_name = entry.get("translated_name", "")
        enabled = entry.get("enabled", True)
        if not enabled or not translated_name:
            continue
        lines.append(f'  {{org = "{source_name}", rep = "{translated_name}"}},')
    lines.append("]")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_file
