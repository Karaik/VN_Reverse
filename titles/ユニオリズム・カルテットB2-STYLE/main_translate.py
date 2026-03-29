import shutil

from solution.build.build_name_dict import build_name_dict
from solution.common.paths import (
    ORIGINAL_GALTRANS_JSON_DIR,
    ORIGINAL_NAME_TABLE_DIR,
    TRANSLATED_GALTRANS_JSON_DIR,
    TRANSLATED_NAME_TABLE_DIR,
    ensure_base_dirs,
)


def main() -> None:
    ensure_base_dirs()

    if not TRANSLATED_GALTRANS_JSON_DIR.exists() or not any(TRANSLATED_GALTRANS_JSON_DIR.iterdir()):
        if TRANSLATED_GALTRANS_JSON_DIR.exists():
            shutil.rmtree(TRANSLATED_GALTRANS_JSON_DIR)
        shutil.copytree(ORIGINAL_GALTRANS_JSON_DIR, TRANSLATED_GALTRANS_JSON_DIR)

    translated_name_table = TRANSLATED_NAME_TABLE_DIR / "name_table.json"
    if not translated_name_table.exists():
        shutil.copy2(ORIGINAL_NAME_TABLE_DIR / "name_table.json", translated_name_table)

    print(build_name_dict(translated_name_table))


if __name__ == "__main__":
    main()
