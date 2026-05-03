from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

from solution.common.paths import (
    NAME_DEFINE_FILENAME,
    ORIGINAL_NAME_TABLE_DIR,
    ORIGINAL_TRILINE_DIR,
    TEXT_WORK_DIR,
    TRANSLATED_NAME_TABLE_DIR,
    YURIS_TOOLS_DIR,
)
from solution.unpack.restore_tree import read_ystl_entries

_SPEAKER_RE = re.compile(r"^(.{1,20}?)([「『（].*)$")


def _load_name_define_names(text_work_dir: Path) -> tuple[str, list[str]]:
    sys.path.insert(0, str(YURIS_TOOLS_DIR))
    import YSTB_FILE as ystb_module  # noqa: E402

    source = text_work_dir / "script" / "data" / "script" / "userdefine" / NAME_DEFINE_FILENAME
    temp_dir = text_work_dir / "name_table_extract"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / "charname.ybn"
    shutil.copy2(source, temp_file)
    key = int((text_work_dir / "Key.txt").read_text(encoding="utf-8").strip(), 16)
    ystb = ystb_module.YSTB_NAMEDEF_FILE(path=str(temp_file), encrypt=key)

    names: list[str] = []
    for command in ystb.command_list:
        data = ystb._read_bytes_from_command(command)
        if not data:
            continue
        names.append(data[4:-1].decode("sjis", errors="replace"))
    return "charname.ybn", names


def _load_script_speaker_names(triline_dir: Path) -> list[str]:
    names: set[str] = set()
    for triline_file in triline_dir.glob("*.txt"):
        for line in triline_file.read_text(encoding="utf-8").splitlines():
            if not line.startswith("ORI="):
                continue
            match = _SPEAKER_RE.match(line[4:])
            if match:
                names.add(match.group(1))
    return sorted(names)


def extract_name_table(
    text_work_dir: Path = TEXT_WORK_DIR,
    triline_dir: Path = ORIGINAL_TRILINE_DIR,
    original_out_dir: Path = ORIGINAL_NAME_TABLE_DIR,
    translated_out_dir: Path = TRANSLATED_NAME_TABLE_DIR,
) -> tuple[Path, Path]:
    yst_list_entries = read_ystl_entries(text_work_dir / "ysbin" / "yst_list.ybn")
    charname_entry = next(entry for entry in yst_list_entries if str(entry["path"]).endswith(NAME_DEFINE_FILENAME))
    charname_ybn = str(charname_entry["ybn_name"])
    _, defined_names = _load_name_define_names(text_work_dir)
    speaker_names = _load_script_speaker_names(triline_dir)

    merged = []
    seen: set[str] = set()
    for name in defined_names + speaker_names:
        if name in seen:
            continue
        seen.add(name)
        merged.append(
            {
                "source_name": name,
                "translated_name": "",
                "enabled": True,
                "source_ybn": charname_ybn,
                "notes": "",
            }
        )

    original_out_dir.mkdir(parents=True, exist_ok=True)
    translated_out_dir.mkdir(parents=True, exist_ok=True)
    original_file = original_out_dir / "name_table.json"
    translated_file = translated_out_dir / "name_table.json"
    original_file.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    if not translated_file.exists():
        translated_file.write_text(original_file.read_text(encoding="utf-8"), encoding="utf-8")
    return original_file, translated_file
