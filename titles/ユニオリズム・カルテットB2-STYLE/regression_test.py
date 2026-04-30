from __future__ import annotations

import json

from solution.common.paths import (
    ORIGINAL_GALTRANS_JSON_DIR,
    ORIGINAL_NAME_TABLE_DIR,
    ORIGINAL_TRILINE_DIR,
    TMP_DIR,
)


def main() -> None:
    checks: list[tuple[str, bool]] = []
    checks.append(("ystl_entries", (TMP_DIR / "ystl_entries.json").exists()))
    checks.append(("triline_exists", (ORIGINAL_TRILINE_DIR / "yst00211.ybn.ori.txt").exists()))
    checks.append(("galtrans_json_exists", (ORIGINAL_GALTRANS_JSON_DIR / "yst00211.ybn.json").exists()))
    checks.append(("name_table_exists", (ORIGINAL_NAME_TABLE_DIR / "name_table.json").exists()))

    triline_ok = False
    triline_file = ORIGINAL_TRILINE_DIR / "yst00211.ybn.ori.txt"
    if triline_file.exists():
        text = triline_file.read_text(encoding="utf-8")
        triline_ok = "アキト" in text and "ライブスフィア" in text
    checks.append(("triline_content", triline_ok))

    json_ok = False
    json_file = ORIGINAL_GALTRANS_JSON_DIR / "yst00211.ybn.json"
    if json_file.exists():
        data = json.loads(json_file.read_text(encoding="utf-8"))
        json_ok = bool(data) and "message" in data[0]
    checks.append(("galtrans_json_content", json_ok))

    name_table_ok = False
    name_file = ORIGINAL_NAME_TABLE_DIR / "name_table.json"
    if name_file.exists():
        data = json.loads(name_file.read_text(encoding="utf-8"))
        name_table_ok = any(item.get("source_name") == "アキト" for item in data)
    checks.append(("name_table_content", name_table_ok))

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
    if failed:
        raise SystemExit(1)
    print("PASS")


if __name__ == "__main__":
    main()
