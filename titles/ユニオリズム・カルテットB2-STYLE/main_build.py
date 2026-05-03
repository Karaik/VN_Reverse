from pathlib import Path

from solution.build.build_release import build_outputs
from solution.build.import_galtrans_json import import_galtrans_json
from solution.build.import_name_define import import_name_define
from solution.build.import_triline import import_triline
from solution.build.patch_update1 import patch_pack
from solution.common.paths import (
    PACK_PATH,
    PACK_TEST_DIR,
    TEXT_WORK_DIR,
    TRANSLATED_GALTRANS_JSON_DIR,
    TRANSLATED_TRILINE_DIR,
    ensure_base_dirs,
)


def main() -> None:
    ensure_base_dirs()
    if any(TRANSLATED_GALTRANS_JSON_DIR.glob("*.json")):
        import_galtrans_json(TRANSLATED_GALTRANS_JSON_DIR, out_dir=TRANSLATED_TRILINE_DIR)
    patched_ysbin_dir = import_triline(TRANSLATED_TRILINE_DIR, TEXT_WORK_DIR)
    import_name_define(out_dir=patched_ysbin_dir)
    PACK_TEST_DIR.mkdir(parents=True, exist_ok=True)
    patched_pack = PACK_TEST_DIR / "update1_build.ypf"
    patch_pack(PACK_PATH, patched_pack, patched_ysbin_dir)
    release_dir, package_dir = build_outputs(patched_pack)
    print(release_dir)
    print(package_dir)


if __name__ == "__main__":
    main()
