from __future__ import annotations

import shutil
import sys
from pathlib import Path

from solution.common.paths import KEY_FILE, ORIGINAL_TRILINE_DIR, TEXT_WORK_DIR, WORK_DIR, YURIS_TOOLS_DIR
from solution.common.subprocess_utils import copy_tree, run_command
from solution.unpack.restore_tree import run_back_structure


def prepare_text_workspace(source_work_dir: Path = WORK_DIR, text_work_dir: Path = TEXT_WORK_DIR, key_file: Path = KEY_FILE) -> Path:
    if text_work_dir.exists():
        shutil.rmtree(text_work_dir)
    text_work_dir.mkdir(parents=True, exist_ok=True)

    copy_tree(source_work_dir / "ysbin", text_work_dir / "ysbin")

    script_root = source_work_dir / "script" / "data" / "script"
    filtered_root = text_work_dir / "script" / "data" / "script"
    filtered_root.mkdir(parents=True, exist_ok=True)
    for folder_name in ("userscript", "userdefine"):
        src = script_root / folder_name
        if src.exists():
            copy_tree(src, filtered_root / folder_name)

    shutil.copy2(key_file, text_work_dir / "Key.txt")
    run_back_structure(text_work_dir)
    return text_work_dir


def export_triline(text_work_dir: Path = TEXT_WORK_DIR, out_dir: Path = ORIGINAL_TRILINE_DIR) -> Path:
    script = YURIS_TOOLS_DIR / "read_YSTB_FILE.py"
    run_command([sys.executable, str(script)], cwd=text_work_dir, env={"PYTHONIOENCODING": "utf-8"})

    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(text_work_dir / "triline_text_ori", out_dir)
    return out_dir
