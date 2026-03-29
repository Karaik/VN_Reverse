import shutil

from solution.common.paths import (
    KEY_FILE,
    ORIGINAL_GALTRANS_JSON_DIR,
    ORIGINAL_NAME_TABLE_DIR,
    ORIGINAL_TRILINE_DIR,
    PACK_PATH,
    TEXT_WORK_DIR,
    TMP_DIR,
    WORK_DIR,
    ensure_base_dirs,
)
from solution.decrypt.guess_key import guess_key
from solution.unpack.export_galtrans_json import export_galtrans_json
from solution.unpack.export_triline import export_triline, prepare_text_workspace
from solution.unpack.extract_name_table import extract_name_table
from solution.unpack.restore_tree import run_make_structure, save_ystl_entries
from solution.unpack.update1_ysbin_unpack import unpack_ysbin


def main() -> None:
    ensure_base_dirs()
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    unpack_ysbin(PACK_PATH, WORK_DIR / "ysbin")
    guess_key(WORK_DIR / "ysbin", KEY_FILE)
    run_make_structure(WORK_DIR)
    save_ystl_entries(WORK_DIR / "ysbin" / "yst_list.ybn", TMP_DIR / "ystl_entries.json")
    prepare_text_workspace(WORK_DIR, TEXT_WORK_DIR, KEY_FILE)
    export_triline(TEXT_WORK_DIR, ORIGINAL_TRILINE_DIR)
    export_galtrans_json(ORIGINAL_TRILINE_DIR, ORIGINAL_GALTRANS_JSON_DIR)
    extract_name_table(TEXT_WORK_DIR, ORIGINAL_TRILINE_DIR, ORIGINAL_NAME_TABLE_DIR)
    print("unpack completed")


if __name__ == "__main__":
    main()
