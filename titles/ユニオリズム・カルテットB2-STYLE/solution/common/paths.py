from __future__ import annotations

from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

README_FILE = PROJECT_ROOT / "README.md"
GAME_DIR = PROJECT_ROOT / "game"
TOOLS_DIR = PROJECT_ROOT / "tools"
TMP_DIR = PROJECT_ROOT / "tmp"
OUT_DIR = PROJECT_ROOT / "out"
DOCS_DIR = PROJECT_ROOT / "docs"
GAME_SCRIPT_DIR = PROJECT_ROOT / "game_script"
SOLUTION_DIR = PROJECT_ROOT / "solution"

ORIGINAL_SCRIPT_DIR = GAME_SCRIPT_DIR / "original_script"
TRANSLATED_SCRIPT_DIR = GAME_SCRIPT_DIR / "translated_script"

ORIGINAL_TRILINE_DIR = ORIGINAL_SCRIPT_DIR / "triline"
ORIGINAL_GALTRANS_JSON_DIR = ORIGINAL_SCRIPT_DIR / "galtrans_json"
ORIGINAL_NAME_TABLE_DIR = ORIGINAL_SCRIPT_DIR / "name_table"

TRANSLATED_TRILINE_DIR = TRANSLATED_SCRIPT_DIR / "triline"
TRANSLATED_GALTRANS_JSON_DIR = TRANSLATED_SCRIPT_DIR / "galtrans_json"
TRANSLATED_NAME_TABLE_DIR = TRANSLATED_SCRIPT_DIR / "name_table"

DECRYPT_DIR = SOLUTION_DIR / "decrypt"
UNPACK_DIR = SOLUTION_DIR / "unpack"
BUILD_DIR = SOLUTION_DIR / "build"
RUNTIME_DIR = SOLUTION_DIR / "runtime"
PATCH_DIR = SOLUTION_DIR / "patch"
TESTS_DIR = SOLUTION_DIR / "tests"

KEY_FILE = DECRYPT_DIR / "key.txt"

WORK_DIR = TMP_DIR / "work"
TEXT_WORK_DIR = TMP_DIR / "work_text"
PACK_TEST_DIR = TMP_DIR / "pack_test"
RUN_GAME_DIR = TMP_DIR / "run_game"

YURIS_TOOLS_DIR = TOOLS_DIR / "YURIS_TOOLS-main"
RXYURIS_DIR = TOOLS_DIR / "RxYuris-main"
GPPCLI_DIR = TOOLS_DIR / "GPPCLI"
YURIS_PATCH_DIR = TOOLS_DIR / "yuris"

BASE_EXE_NAME = "UQB2S.exe"
PATCH_EXE_NAME = "UQB2S_chs.exe"
PATCH_DLL_NAME = "patch_chs.dll"
PATCH_FOLDER_NAME = "patch_chs"
PATCH_PACK_NAME = "update1.ypf"

PACK_PATH = GAME_DIR / "pac" / PATCH_PACK_NAME
GAME_EXE_PATH = GAME_DIR / BASE_EXE_NAME

NAME_DEFINE_FILENAME = "キャラ名定義.txt"
NAME_DEFINE_REL_PATH = Path("data") / "script" / "userdefine" / NAME_DEFINE_FILENAME


def ensure_base_dirs() -> None:
    for path in (
        DOCS_DIR,
        OUT_DIR,
        ORIGINAL_TRILINE_DIR,
        ORIGINAL_GALTRANS_JSON_DIR,
        ORIGINAL_NAME_TABLE_DIR,
        TRANSLATED_TRILINE_DIR,
        TRANSLATED_GALTRANS_JSON_DIR,
        TRANSLATED_NAME_TABLE_DIR,
        DECRYPT_DIR,
        UNPACK_DIR,
        BUILD_DIR,
        RUNTIME_DIR / "src",
        PATCH_DIR,
        TESTS_DIR,
        TMP_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")
