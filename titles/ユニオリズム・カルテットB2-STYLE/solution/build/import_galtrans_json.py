from __future__ import annotations

import json
from pathlib import Path

from solution.common.paths import (
    ORIGINAL_TRILINE_DIR,
    TRANSLATED_GALTRANS_JSON_DIR,
    TRANSLATED_TRILINE_DIR,
)
from solution.unpack.export_galtrans_json import split_speaker


def import_galtrans_json(
    translated_json_dir: Path = TRANSLATED_GALTRANS_JSON_DIR,
    original_triline_dir: Path = ORIGINAL_TRILINE_DIR,
    out_dir: Path = TRANSLATED_TRILINE_DIR,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    for original_file in sorted(original_triline_dir.glob("*.txt")):
        json_file = translated_json_dir / original_file.name.replace(".ori.txt", ".json")
        if not json_file.exists():
            continue

        items = json.loads(json_file.read_text(encoding="utf-8"))
        item_index = 0
        out_lines = []
        current_item = None
        current_source_name = ""
        for line in original_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("[") and line.endswith("]") and "opt" not in line:
                if item_index >= len(items):
                    raise ValueError(f"{json_file} 条目数量不足")
                current_item = items[item_index]
                item_index += 1
                current_source_name = ""
                out_lines.append(line)
            elif line.startswith("ORI="):
                source_name, _ = split_speaker(line[4:])
                current_source_name = source_name or ""
                out_lines.append(line)
            elif line.startswith("TR2="):
                if current_item is None:
                    raise ValueError(f"{json_file} 缺少当前条目")
                message = current_item.get("message", "")
                rebuilt = f"{current_source_name}{message}" if current_source_name else message
                out_lines.append(f"TR2={rebuilt}")
            else:
                out_lines.append(line)

        out_file = out_dir / original_file.name.replace(".ori.txt", ".tra.txt")
        out_file.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return out_dir
