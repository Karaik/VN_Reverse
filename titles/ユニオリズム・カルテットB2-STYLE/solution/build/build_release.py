from __future__ import annotations

import json
import shutil
from pathlib import Path

from solution.common.paths import (
    BASE_EXE_NAME,
    GAME_DIR,
    OUT_DIR,
    PATCH_FOLDER_NAME,
    PATCH_PACK_NAME,
    timestamp_slug,
)
from solution.common.subprocess_utils import copy_file, write_text
from solution.runtime.build_chs_exe import build_chs_exe


ROOT_COPY_FILES = [
    "COPYING",
    "readme.txt",
    "yscfg.dat",
    "YSPNG.DLL",
    "YSSNP.DLL",
    "YSWBP.DLL",
    "YSZLB.DLL",
    "エンジン設定.exe",
]
ROOT_EXTRA_FILES = [
    "UQ_B2S_minidorama_SIR.wav",
    "UQ_B2S_minidorama_YUR.wav",
]


def _write_package_readme(path: Path) -> None:
    text = """覆盖说明

1. 将本目录中的 UQB2S_chs.exe、patch_chs.dll 复制到原版游戏根目录。
2. 将 patch_chs/ 整个目录复制到原版游戏根目录。
3. 从 UQB2S_chs.exe 启动游戏。
"""
    write_text(path, text)


def build_outputs(patched_pack: Path) -> tuple[Path, Path]:
    stamp = timestamp_slug()
    package_dir = OUT_DIR / f"package_{stamp}"
    release_dir = OUT_DIR / f"release_{stamp}"
    package_patch_pac_dir = package_dir / PATCH_FOLDER_NAME / "pac"
    release_patch_pac_dir = release_dir / PATCH_FOLDER_NAME / "pac"
    release_pac_dir = release_dir / "pac"

    package_patch_pac_dir.mkdir(parents=True, exist_ok=True)
    release_patch_pac_dir.mkdir(parents=True, exist_ok=True)
    release_pac_dir.mkdir(parents=True, exist_ok=True)

    build_chs_exe(GAME_DIR / BASE_EXE_NAME, package_dir)
    copy_file(patched_pack, package_patch_pac_dir / PATCH_PACK_NAME)
    _write_package_readme(package_dir / "readme.txt")

    for name in ROOT_COPY_FILES:
        src = GAME_DIR / name
        if src.exists():
            copy_file(src, release_dir / name)
    for name in ROOT_EXTRA_FILES:
        src = GAME_DIR / name
        if src.exists():
            copy_file(src, release_dir / name)
    if (GAME_DIR / "save").exists():
        shutil.copytree(GAME_DIR / "save", release_dir / "save")
    for pack_file in sorted((GAME_DIR / "pac").glob("*")):
        copy_file(pack_file, release_pac_dir / pack_file.name)

    copy_file(patched_pack, release_patch_pac_dir / PATCH_PACK_NAME)

    build_chs_exe(GAME_DIR / BASE_EXE_NAME, release_dir)
    summary = {
        "package_dir": str(package_dir),
        "release_dir": str(release_dir),
        "patched_pack": str(patched_pack),
    }
    write_text(release_dir / "pipeline_summary.json", json.dumps(summary, ensure_ascii=False, indent=2))
    _write_package_readme(release_dir / "readme.txt")
    return release_dir, package_dir
