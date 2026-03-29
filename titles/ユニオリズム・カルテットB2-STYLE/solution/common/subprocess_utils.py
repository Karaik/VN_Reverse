from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def run_command(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    print("$", " ".join(args))
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
