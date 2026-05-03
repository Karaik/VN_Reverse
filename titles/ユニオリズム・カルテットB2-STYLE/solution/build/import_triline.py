from __future__ import annotations

import shutil
import sys
from pathlib import Path

from solution.common.paths import KEY_FILE, TEXT_WORK_DIR, TRANSLATED_TRILINE_DIR, YURIS_TOOLS_DIR


def normalize_for_gbk(text: str) -> str:
    replacements = {
        "・": "·",
        "“": "\"",
        "”": "\"",
        "‘": "'",
        "’": "'",
        "〜": "~",
        "−": "-",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def import_triline(
    translated_triline_dir: Path = TRANSLATED_TRILINE_DIR,
    text_work_dir: Path = TEXT_WORK_DIR,
    out_dir: Path | None = None,
) -> Path:
    if out_dir is None:
        out_dir = text_work_dir / "Release" / "ysbin"

    trans_dir = text_work_dir / "triline_text_trans"
    if trans_dir.exists():
        shutil.rmtree(trans_dir)
    shutil.copytree(translated_triline_dir, trans_dir)

    sys.path.insert(0, str(YURIS_TOOLS_DIR))
    import YSTB_FILE as ystb_module  # noqa: E402

    def replace_halfwidth_with_fullwidth(text: str) -> str:
        return text

    ystb_module.replace_halfwidth_with_fullwidth = replace_halfwidth_with_fullwidth
    ystb_file = ystb_module.YSTB_FILE

    key = int(KEY_FILE.read_text(encoding="utf-8").strip(), 16)
    patch_out_dir = text_work_dir / "scr_trans"
    if patch_out_dir.exists():
        shutil.rmtree(patch_out_dir)
    patch_out_dir.mkdir(parents=True, exist_ok=True)

    for filename in sorted(trans_dir.iterdir()):
        if not filename.name.endswith(".tra.txt"):
            continue
        source_ybn = text_work_dir / "ysbin_new" / filename.name.replace(".tra.txt", "")
        if not source_ybn.exists():
            continue
        ystb = ystb_file(path=str(source_ybn), encrypt=key)
        is_opt = False
        command_offset = 0
        current_ori = ""
        for line in filename.read_text(encoding="utf-8").splitlines():
            if line.startswith("[") and line.endswith("]") and "opt" not in line:
                command_offset = int(line[1:-1])
                is_opt = False
                current_ori = ""
            elif line.startswith("[") and line.endswith("]opt"):
                command_offset = int(line[1:-4])
                is_opt = True
                current_ori = ""
            elif line.startswith("ORI="):
                current_ori = line[4:]
            elif line.startswith("TR2="):
                trans_text = normalize_for_gbk(line[4:])
                if trans_text == current_ori:
                    continue
                if is_opt:
                    ystb.append_opt(command_offset, trans_text)
                else:
                    ystb.append_trans(command_offset, trans_text)

        out_file = patch_out_dir / filename.name.replace(".tra.txt", "")
        ystb.save_file(str(out_file), encrypt=key)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(patch_out_dir, out_dir)
    return out_dir
