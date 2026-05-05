from __future__ import annotations

from pathlib import Path

from common.regression_app import (
    run_ssb_character_name_patch_regression,
    run_ssb_roundtrip_regression,
    run_ssb_target_encoding_regression,
    run_ssb_text_patch_regression,
    run_ssb_translation_coverage_regression,
    run_ssb_variable_length_patch_regression,
)


def main() -> int:
    title_root = Path(__file__).resolve().parent
    run_ssb_roundtrip_regression(title_root)
    run_ssb_translation_coverage_regression(title_root)
    run_ssb_character_name_patch_regression(title_root)
    run_ssb_text_patch_regression(title_root)
    run_ssb_variable_length_patch_regression(title_root)
    run_ssb_target_encoding_regression(title_root)
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
