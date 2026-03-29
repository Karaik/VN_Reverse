from __future__ import annotations

import json
import struct
from pathlib import Path

from solution.common.paths import YURIS_TOOLS_DIR
from solution.common.subprocess_utils import run_command


def run_make_structure(work_dir: Path) -> None:
    tool = YURIS_TOOLS_DIR / "YSTL_Parse.exe"
    run_command([str(tool), "-make"], cwd=work_dir)


def run_back_structure(work_dir: Path) -> None:
    tool = YURIS_TOOLS_DIR / "YSTL_Parse.exe"
    run_command([str(tool), "-back"], cwd=work_dir)


def read_ystl_entries(yst_list_path: Path) -> list[dict[str, object]]:
    data = yst_list_path.read_bytes()
    sig, version, entry_count = struct.unpack_from("<4sII", data, 0)
    if sig != b"YSTL":
        raise ValueError(f"YSTL 签名错误：{sig!r}")

    p = 12
    entries: list[dict[str, object]] = []
    for _ in range(entry_count):
        sequence, path_size = struct.unpack_from("<II", data, p)
        p += 8
        path_bytes = data[p:p + path_size]
        p += path_size
        _high_time, _low_time, var_count, label_count, text_count = struct.unpack_from("<IIIII", data, p)
        p += 20
        path = path_bytes.decode("cp932", errors="replace")
        entries.append(
            {
                "sequence": sequence,
                "ybn_name": f"yst{sequence:05d}.ybn",
                "path": path,
                "text_count": text_count,
                "variable_count": var_count,
                "label_count": label_count,
            }
        )
    return entries


def save_ystl_entries(yst_list_path: Path, out_file: Path) -> Path:
    entries = read_ystl_entries(yst_list_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_file
