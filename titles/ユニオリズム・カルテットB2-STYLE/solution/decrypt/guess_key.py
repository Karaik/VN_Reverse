from __future__ import annotations

from pathlib import Path

from solution.common.paths import KEY_FILE, YURIS_TOOLS_DIR
from solution.common.subprocess_utils import run_command


def guess_key(ysbin_dir: Path, out_file: Path = KEY_FILE) -> Path:
    tool = YURIS_TOOLS_DIR / "YSTB_GuessXorKey.exe"
    candidates = sorted(ysbin_dir.glob("yst*.ybn"), key=lambda p: p.stat().st_size, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"未找到可用于猜 key 的 ybn：{ysbin_dir}")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    run_command([str(tool), str(candidates[0])], cwd=out_file.parent)
    temp_key = out_file.parent / "Key.txt"
    if not temp_key.exists():
        raise FileNotFoundError("YSTB_GuessXorKey.exe 未生成 Key.txt")
    if temp_key != out_file:
        temp_key.replace(out_file)
    return out_file
