from __future__ import annotations

from pathlib import Path

from common.regression_app import (
    run_archive_probe_regression,
    run_cli_batch_compile_regression,
    run_cli_batch_decompile_regression,
    run_cli_raw_binary_mode_regression,
    run_bttext_outer_regression,
    run_bttext_game01_roundtrip_regression,
    run_bttext_target_encoding_regression,
    run_bttext_text_patch_regression,
    run_bttext_text_roundtrip_regression,
    run_scr_full_rewrite_regression,
    run_scr_full_coverage_regression,
    run_scr_outer_regression,
    run_scr_text_candidate_regression,
    run_scr_text_patch_regression,
    run_protagonist_name_scr_regression,
    run_text_fit_report_regression,
    run_text_patch_helper_regression,
    run_text_fit_helper_regression,
    run_text_scan_regression,
    run_ti_balloon_game01_roundtrip_regression,
    run_ti_balloon_game01_target_encoding_regression,
    run_ti_balloon_roundtrip_regression,
    run_ti_balloon_target_encoding_regression,
    run_ti_name_game01_roundtrip_regression,
    run_ti_name_game01_target_encoding_regression,
    run_ti_name_patch_regression,
    run_ti_name_roundtrip_regression,
    run_ti_name_target_encoding_regression,
)


def main() -> int:
    title_root = Path(__file__).resolve().parent
    run_archive_probe_regression(title_root)
    run_cli_batch_decompile_regression(title_root)
    run_cli_batch_compile_regression(title_root)
    run_cli_raw_binary_mode_regression(title_root)
    run_ti_name_roundtrip_regression(title_root)
    run_ti_name_patch_regression(title_root)
    run_ti_name_target_encoding_regression(title_root)
    run_ti_name_game01_roundtrip_regression(title_root)
    run_ti_name_game01_target_encoding_regression(title_root)
    run_ti_balloon_roundtrip_regression(title_root)
    run_ti_balloon_target_encoding_regression(title_root)
    run_ti_balloon_game01_roundtrip_regression(title_root)
    run_ti_balloon_game01_target_encoding_regression(title_root)
    run_bttext_outer_regression(title_root)
    run_bttext_text_roundtrip_regression(title_root)
    run_bttext_text_patch_regression(title_root)
    run_bttext_target_encoding_regression(title_root)
    run_bttext_game01_roundtrip_regression(title_root)
    run_scr_outer_regression(title_root)
    run_scr_text_candidate_regression(title_root)
    run_scr_text_patch_regression(title_root)
    run_protagonist_name_scr_regression(title_root)
    run_scr_full_coverage_regression(title_root)
    run_scr_full_rewrite_regression(title_root)
    run_text_fit_report_regression(title_root)
    run_text_patch_helper_regression(title_root)
    run_text_fit_helper_regression(title_root)
    run_text_scan_regression(title_root)
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
