from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from solution.common.paths import KEY_FILE, TEXT_WORK_DIR, TRANSLATED_NAME_TABLE_DIR, YURIS_TOOLS_DIR


def import_name_define(
    name_table_file: Path | None = None,
    text_work_dir: Path = TEXT_WORK_DIR,
    out_dir: Path | None = None,
) -> Path | None:
    if name_table_file is None:
        name_table_file = TRANSLATED_NAME_TABLE_DIR / "name_table.json"
    if not name_table_file.exists():
        return None

    data = json.loads(name_table_file.read_text(encoding="utf-8"))
    mapping_by_ybn: dict[str, dict[str, str]] = defaultdict(dict)
    for entry in data:
        translated_name = entry.get("translated_name", "").strip()
        if not translated_name:
            continue
        mapping_by_ybn[str(entry["source_ybn"])][str(entry["source_name"])] = translated_name

    if not mapping_by_ybn:
        return None

    if out_dir is None:
        out_dir = text_work_dir / "Release" / "ysbin"
    out_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(YURIS_TOOLS_DIR))
    import YSTB_FILE as ystb_module  # noqa: E402

    key = int(KEY_FILE.read_text(encoding="utf-8").strip(), 16)
    changed_any = False
    for ybn_name, mapping in mapping_by_ybn.items():
        source_file = text_work_dir / "ysbin_new" / ybn_name
        name_def = ystb_module.YSTB_NAMEDEF_FILE(path=str(source_file), encrypt=key)
        decoded_entries: list[tuple[object, bytes, str]] = []
        for command in name_def.command_list:
            content = name_def._read_bytes_from_command(command)
            if not content:
                continue
            original_name = content[4:-1].decode("sjis", errors="replace")
            decoded_entries.append((command, content, original_name))

        changed_current = False
        index = 0
        while index < len(decoded_entries):
            command, content, original_name = decoded_entries[index]
            next_index = index + 1

            if next_index < len(decoded_entries) and decoded_entries[next_index][2] == original_name:
                display_name = mapping.get(original_name, original_name)
                key_data = content[:4] + original_name.encode("gbk") + content[-1:]
                name_def._append_new_namedef(command.command_offset, key_data)

                next_command, next_content, _ = decoded_entries[next_index]
                display_data = next_content[:4] + display_name.encode("gbk") + next_content[-1:]
                name_def._append_new_namedef(next_command.command_offset, display_data)
                changed_current = True
                index += 2
                continue

            trans_name = mapping.get(original_name, original_name)
            new_data = content[:4] + trans_name.encode("gbk") + content[-1:]
            name_def._append_new_namedef(command.command_offset, new_data)
            changed_current = True
            index += 1

        if changed_current:
            name_def.save_file(str(out_dir / ybn_name), encrypt=key)
            changed_any = True

    return out_dir if changed_any else None
