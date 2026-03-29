from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from solution.common.paths import ORIGINAL_GALTRANS_JSON_DIR, ORIGINAL_TRILINE_DIR


_SPEAKER_SPLIT_RE = re.compile(r"^(.{1,20}?)([「『（].*)$")


def split_speaker(text: str) -> tuple[str | None, str]:
    match = _SPEAKER_SPLIT_RE.match(text)
    if not match:
        return None, text
    return match.group(1), match.group(2)


def parse_triline_file(path: Path) -> list[dict[str, object]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    items: list[dict[str, object]] = []
    offset = None
    index = 0
    for line in lines:
        if line.startswith("[") and line.endswith("]") and "opt" not in line:
            offset = int(line[1:-1])
        elif line.startswith("ORI="):
            text = line[4:]
            speaker, message = split_speaker(text)
            index += 1
            item: dict[str, object] = {
                "index": index,
                "offset": offset,
                "message": message,
            }
            if speaker:
                item["name"] = speaker
            items.append(item)
    return items


def export_galtrans_json(triline_dir: Path = ORIGINAL_TRILINE_DIR, out_dir: Path = ORIGINAL_GALTRANS_JSON_DIR) -> Path:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for triline_file in sorted(triline_dir.glob("*.txt")):
        items = parse_triline_file(triline_file)
        out_file = out_dir / triline_file.name.replace(".ori.txt", ".json")
        out_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_dir
