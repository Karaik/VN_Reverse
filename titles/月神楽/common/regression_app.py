from __future__ import annotations

import json
import os
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path

from archive.tev2_archive import unpack_pak0, write_probe_manifest
from script.tev2_bttext import compile_bttext, parse_bttext_text, probe_bttext, rebuild_bttext
from script.tev2_check_text_fit import check_text_fit
from script.tev2_fit_report import build_fit_report
from script.tev2_patch_text import patch_text_doc
from script.tev2_scan_text import build_text_scan
from script.tev2_scr import (
    _iter_command_string_slots,
    _select_translatable_slots,
    compile_scr_text,
    parse_scr_commands,
    parse_scr_sections,
    parse_scr_text,
    parse_scr_text_bytes,
    probe_scr,
    probe_scr_bytes,
    rebuild_scr,
)
from script.tev2_text_tables import compile_table, parse_table, parse_table_bytes


def make_temp_dir(title_root: Path, name: str) -> Path:
    base_root = Path(tempfile.gettempdir()) / "vn_reverse" / title_root.name
    base_root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{name}_", dir=base_root))


def cleanup_temp_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def _make_ascii_patch(tag: str, index: int = 0, *, extra: int = 0) -> str:
    base = f"{tag}_{index:02X}"
    if extra > 0:
        base += "X" * extra
    return base


def _make_cp932_patch(tag: str, index: int = 0, *, extra: int = 0) -> str:
    base = f"\u30a2{tag}{index:02X}\u7532"
    if extra > 0:
        base += "\u30a2" * extra
    return base


def _make_gbk_patch(tag: str, index: int = 0, *, extra: int = 0) -> str:
    base = f"\u6c49{tag}{index:02X}\u7532"
    if extra > 0:
        base += "\u6c49" * extra
    return base


def _make_fit_text(byte_length: int, *, fill: str = "A") -> str:
    if byte_length <= 0:
        return ""
    return fill * byte_length


def _is_patchable_scr_entry(entry: dict[str, object]) -> bool:
    text = str(entry.get("text", ""))
    if not text:
        return False
    return any(ord(ch) >= 0x20 for ch in text)


def _scr_entries_by_usage(doc, *usages: str) -> list[dict[str, object]]:
    allowed = set(usages)
    return [entry for entry in doc.entries if str(entry.get("usage", "")) in allowed]


def _scr_content_entries(doc) -> list[dict[str, object]]:
    return _scr_entries_by_usage(doc, "text", "dialogue", "choice", "name", "system")


def _first_entries(doc, count: int, *usages: str, min_length: int = 1) -> list[dict[str, object]]:
    entries = [entry for entry in _scr_entries_by_usage(doc, *usages) if int(entry.get("length", 0)) >= min_length]
    if len(entries) < count:
        raise AssertionError(f"Expected at least {count} SCR entries for usages={usages!r}")
    return entries[:count]


def _find_scr_doc(title_root: Path, *, min_entries: int = 1, usages: tuple[str, ...] = ("text",)) -> tuple[Path, object]:
    for script_root in _iter_script_roots(title_root):
        for source_path in sorted(script_root.glob("*.scr")):
            doc = parse_scr_text(source_path, text_encoding="cp932")
            if len(_scr_entries_by_usage(doc, *usages)) >= min_entries:
                return source_path, doc
    raise AssertionError(f"No SCR document found for usages={usages!r}")


def _find_scr_docs(title_root: Path, *, min_entries: int = 1, usages: tuple[str, ...] = ("text",), limit: int = 1) -> list[tuple[Path, object]]:
    matches: list[tuple[Path, object]] = []
    for script_root in _iter_script_roots(title_root):
        for source_path in sorted(script_root.glob("*.scr")):
            doc = parse_scr_text(source_path, text_encoding="cp932")
            if len(_scr_entries_by_usage(doc, *usages)) >= min_entries:
                matches.append((source_path, doc))
                if len(matches) >= limit:
                    return matches
    if not matches:
        raise AssertionError(f"No SCR documents found for usages={usages!r}")
    return matches


def _longer_scr_patch(entry: dict[str, object], tag: str, index: int) -> str:
    return f"{entry['text']}{_make_cp932_patch(tag, index, extra=8)}"


def _ensure_unpacked_archive(title_root: Path, archive_name: str, cache_name: str) -> Path:
    source_path = title_root / "game" / archive_name
    if not source_path.is_file():
        raise AssertionError(f"Expected source archive at game/{archive_name}")
    cache_root = Path(tempfile.gettempdir()) / "vn_reverse" / title_root.name / "_inputs" / cache_name
    manifest_path = cache_root / "manifest.json"
    files_root = cache_root / "files"
    if not manifest_path.is_file() or not files_root.is_dir():
        if cache_root.exists():
            shutil.rmtree(cache_root, ignore_errors=True)
        unpack_pak0(source_path, cache_root)
    return files_root


def _get_game00_files_root(title_root: Path) -> Path:
    return _ensure_unpacked_archive(title_root, "game00.dat", "game00")


def _get_game01_files_root(title_root: Path) -> Path:
    return _ensure_unpacked_archive(title_root, "game01.dat", "game01")


def _iter_script_roots(title_root: Path) -> list[Path]:
    roots: list[Path] = []
    for getter in (_get_game00_files_root, _get_game01_files_root):
        files_root = getter(title_root)
        script_root = files_root / "script"
        if script_root.is_dir():
            roots.append(script_root)
    return roots


def run_archive_probe_regression(title_root: Path) -> None:
    game_dir = title_root / "game"
    out_dir = make_temp_dir(title_root, "archive_probe")
    try:
        manifest_path = write_probe_manifest(game_dir, out_dir)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("format") != "TE_V2_ARCHIVE_PROBE":
            raise AssertionError("Unexpected archive probe manifest format")
        if int(manifest.get("archive_count", 0)) < 5:
            raise AssertionError("Expected at least 5 gameXX.dat archives")
    finally:
        cleanup_temp_dir(out_dir)


def run_cli_batch_decompile_regression(title_root: Path) -> None:
    source_root = _get_game00_files_root(title_root)
    if not source_root.is_dir():
        raise AssertionError("Expected unpacked files root at _pak0_game00/files")
    temp_root = make_temp_dir(title_root, "cli_batch_decompile")
    try:
        from script.tev2_decompile_app import _discover_inputs, _write_single
        out_dir = temp_root / "out"
        inputs = _discover_inputs(source_root)
        for input_path in inputs:
            relative = input_path.relative_to(source_root)
            output_path = out_dir / relative.with_suffix('.json')
            _write_single(input_path, output_path, text_encoding='cp932', mode='decoded')
        for rel in [Path("script") / "add_t.json", Path("data") / "BtText.json", Path("data") / "tiNameSp.json"]:
            if not (out_dir / rel).is_file():
                raise AssertionError(f"Batch decompile did not produce {rel}")
    finally:
        cleanup_temp_dir(temp_root)


def run_cli_batch_compile_regression(title_root: Path) -> None:
    source_root = _get_game00_files_root(title_root)
    if not source_root.is_dir():
        raise AssertionError("Expected unpacked files root at _pak0_game00/files")
    temp_root = make_temp_dir(title_root, "cli_batch_compile")
    try:
        from script.tev2_decompile_app import _discover_inputs, _write_single
        from script.tev2_compile_app import _compile_single, _infer_output_suffix
        dump_dir = temp_root / "dump"
        rebuild_dir = temp_root / "rebuild"
        inputs = _discover_inputs(source_root)
        for input_path in inputs:
            relative = input_path.relative_to(source_root)
            output_path = dump_dir / relative.with_suffix('.json')
            _write_single(input_path, output_path, text_encoding='cp932', mode='decoded')
        json_inputs = sorted(path for path in dump_dir.rglob("*.json") if path.is_file())
        for input_path in json_inputs:
            doc = json.loads(input_path.read_text(encoding='utf-8'))
            fmt = str(doc.get('format'))
            if not fmt.startswith('TE_V2_'):
                continue
            relative = input_path.relative_to(dump_dir)
            output_path = rebuild_dir / relative.with_suffix(_infer_output_suffix(doc))
            _compile_single(input_path, output_path, text_encoding='cp932', mode='decoded')
        for rel in [Path("script") / "add_t.scr", Path("data") / "BtText.dat", Path("data") / "tiNameSp.dat"]:
            if not (rebuild_dir / rel).is_file():
                raise AssertionError(f"Batch compile did not produce {rel}")
    finally:
        cleanup_temp_dir(temp_root)


def run_cli_raw_binary_mode_regression(title_root: Path) -> None:
    source_scr = _get_game00_files_root(title_root) / "script" / "add_t.scr"
    source_table = _get_game00_files_root(title_root) / "data" / "tiNameSp.dat"
    if not source_scr.is_file() or not source_table.is_file():
        raise AssertionError("Expected unpacked SCR/table files for raw-binary regression")
    temp_root = make_temp_dir(title_root, "cli_raw_binary")
    try:
        from script.tev2_decompile_app import _write_single
        from script.tev2_compile_app import _compile_single
        decoded_scr = temp_root / "add_t.decoded.bin"
        decoded_table = temp_root / "tiNameSp.decoded.bin"
        raw_scr_json = temp_root / "add_t.raw.json"
        rebuilt_scr = temp_root / "add_t.rebuilt.scr"
        _write_single(source_scr, decoded_scr, text_encoding='cp932', mode='decoded-binary')
        _write_single(source_table, decoded_table, text_encoding='cp932', mode='decoded-binary')
        _write_single(source_scr, raw_scr_json, text_encoding='cp932', mode='raw')
        _compile_single(raw_scr_json, rebuilt_scr, text_encoding='cp932', mode='raw')
        if decoded_scr.read_bytes() != probe_scr(source_scr).decoded_payload_bytes:
            raise AssertionError("decoded-binary SCR output mismatch")
        if decoded_table.read_bytes() != source_table.read_bytes():
            raise AssertionError("decoded-binary table output mismatch")
        if rebuilt_scr.read_bytes() != source_scr.read_bytes():
            raise AssertionError("raw SCR rebuild mismatch")

        batch_decoded_root = temp_root / "decoded"
        batch_output_root = temp_root / "rebuilt"
        batch_source_root = temp_root / "source"
        (batch_source_root / "script").mkdir(parents=True, exist_ok=True)
        (batch_source_root / "data").mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_scr, batch_source_root / "script" / "add_t.scr")
        shutil.copy2(source_table, batch_source_root / "data" / "tiNameSp.dat")
        (batch_decoded_root / "script").mkdir(parents=True, exist_ok=True)
        (batch_decoded_root / "data").mkdir(parents=True, exist_ok=True)
        decoded_scr_batch = batch_decoded_root / "script" / "add_t.scr"
        decoded_table_batch = batch_decoded_root / "data" / "tiNameSp.dat"
        decoded_scr_batch.write_bytes(decoded_scr.read_bytes())
        decoded_table_batch.write_bytes(decoded_table.read_bytes())
        from script.tev2_compile_app import main as compile_main
        old_argv = os.sys.argv[:]
        try:
            os.sys.argv = [
                "tev2_compile.py",
                str(batch_decoded_root),
                str(batch_output_root),
                "--batch",
                "--mode",
                "decoded-binary",
                "--source",
                str(batch_source_root),
                "--text-encoding",
                "cp932",
            ]
            compile_main()
        finally:
            os.sys.argv = old_argv
        if (batch_output_root / "script" / "add_t.scr").read_bytes() != source_scr.read_bytes():
            raise AssertionError("batch decoded-binary SCR rebuild mismatch")
        if (batch_output_root / "data" / "tiNameSp.dat").read_bytes() != source_table.read_bytes():
            raise AssertionError("batch decoded-binary table rebuild mismatch")
    finally:
        cleanup_temp_dir(temp_root)


def run_protagonist_name_scr_regression(title_root: Path) -> None:
    sampled_docs = _find_scr_docs(title_root, min_entries=2, usages=("name",), limit=2)
    case_index = 0
    for source_path, doc in sampled_docs:
        name_entries = _first_entries(doc, min(3, len(_scr_entries_by_usage(doc, "name"))), "name")
        for target_entry in name_entries:
            target_index = int(target_entry["index"])
            replacement_text = _make_cp932_patch("NM", case_index)
            case_index += 1
            work_entries = deepcopy(doc.entries)
            for entry in work_entries:
                if int(entry["index"]) == target_index:
                    entry["text"] = replacement_text
                    break
            rebuilt = compile_scr_text(
                {
                    "format": doc.format,
                    "source_path": doc.source_path,
                    "text_encoding": doc.text_encoding,
                    "raw_header": doc.raw_header,
                    "entries": work_entries,
                },
                text_encoding="cp932",
            )
            reparsed = parse_scr_text_bytes(
                rebuilt,
                source_path=f"{source_path.name}:patched:{target_index}",
                text_encoding="cp932",
                include_impact=False,
            )
            reparsed_entry = next((entry for entry in reparsed.entries if int(entry["index"]) == target_index), None)
            if reparsed_entry is None:
                raise AssertionError(f"Patched SCR entry index {target_index} was not recovered in {source_path.name}")
            if str(reparsed_entry["text"]) != replacement_text:
                raise AssertionError(f"Patched SCR entry text was not recovered in {source_path.name} index {target_index}")
            if int(reparsed_entry["offset"]) != int(target_entry["offset"]):
                raise AssertionError(f"Patched SCR entry offset changed during safe rewrite in {source_path.name} index {target_index}")


def run_ti_name_roundtrip_regression(title_root: Path) -> None:
    source_path = _get_game00_files_root(title_root) / "data" / "tiNameSp.dat"
    if not source_path.is_file():
        raise AssertionError("Expected unpacked tiNameSp.dat at _pak0_game00/files/data/tiNameSp.dat")
    doc = parse_table(source_path, text_encoding="cp932")
    rebuilt = compile_table(
        {
            "format": doc.format,
            "table_name": doc.table_name,
            "source_path": doc.source_path,
            "key_mode": doc.key_mode,
            "key_seed_u32": doc.key_seed_u32,
            "record_size": doc.record_size,
            "entries": doc.entries,
        },
        text_encoding="cp932",
    )
    original = source_path.read_bytes()
    if rebuilt != original:
        raise AssertionError("tiNameSp.dat roundtrip mismatch")


def run_ti_name_patch_regression(title_root: Path) -> None:
    source_path = _get_game00_files_root(title_root) / "data" / "tiNameSp.dat"
    if not source_path.is_file():
        raise AssertionError("Expected unpacked tiNameSp.dat at _pak0_game00/files/data/tiNameSp.dat")
    doc = parse_table(source_path, text_encoding="cp932")
    target = next((entry for entry in doc.entries if entry["decoded"] and entry["text"]), None)
    if target is None:
        raise AssertionError("No decoded tiNameSp.dat entry found")
    replacement = _make_cp932_patch("TN", 1)
    target["text"] = replacement
    rebuilt = compile_table(
        {
            "format": doc.format,
            "table_name": doc.table_name,
            "source_path": doc.source_path,
            "key_mode": doc.key_mode,
            "key_seed_u32": doc.key_seed_u32,
            "record_size": doc.record_size,
            "entries": doc.entries,
        },
        text_encoding="cp932",
    )
    reparsed = parse_table_bytes(
        rebuilt,
        table_name=doc.table_name,
        source_path=doc.source_path,
        text_encoding="cp932",
    )
    if not any(entry["text"] == replacement for entry in reparsed.entries):
        raise AssertionError("Patched tiNameSp.dat text not recovered after reparse")


def run_ti_name_target_encoding_regression(title_root: Path) -> None:
    source_path = _get_game00_files_root(title_root) / "data" / "tiNameSp.dat"
    if not source_path.is_file():
        raise AssertionError("Expected unpacked tiNameSp.dat at _pak0_game00/files/data/tiNameSp.dat")
    doc = parse_table(source_path, text_encoding="cp932")
    target = next((entry for entry in doc.entries if entry["decoded"] and entry["text"]), None)
    if target is None:
        raise AssertionError("No decoded tiNameSp.dat entry found")
    replacement = _make_gbk_patch("TN", 2)
    target["text"] = replacement
    rebuilt = compile_table(
        {
            "format": doc.format,
            "table_name": doc.table_name,
            "source_path": doc.source_path,
            "key_mode": doc.key_mode,
            "key_seed_u32": doc.key_seed_u32,
            "record_size": doc.record_size,
            "entries": doc.entries,
        },
        text_encoding="gbk",
    )
    reparsed = parse_table_bytes(
        rebuilt,
        table_name=doc.table_name,
        source_path=doc.source_path,
        text_encoding="gbk",
    )
    if not any(entry["text"] == replacement for entry in reparsed.entries):
        raise AssertionError("GBK write-back text not recovered after reparse")


def run_ti_name_game01_roundtrip_regression(title_root: Path) -> None:
    source_path = _get_game01_files_root(title_root) / "data" / "tiName.dat"
    if not source_path.is_file():
        raise AssertionError("Expected unpacked tiName.dat at _pak0_game01_verify/files/data/tiName.dat")
    doc = parse_table(source_path, text_encoding="cp932")
    rebuilt = compile_table(
        {
            "format": doc.format,
            "table_name": doc.table_name,
            "source_path": doc.source_path,
            "key_mode": doc.key_mode,
            "key_seed_u32": doc.key_seed_u32,
            "record_size": doc.record_size,
            "entries": doc.entries,
        },
        text_encoding="cp932",
    )
    if rebuilt != source_path.read_bytes():
        raise AssertionError("tiName.dat roundtrip mismatch")


def run_ti_name_game01_target_encoding_regression(title_root: Path) -> None:
    source_path = _get_game01_files_root(title_root) / "data" / "tiName.dat"
    if not source_path.is_file():
        raise AssertionError("Expected unpacked tiName.dat at _pak0_game01_verify/files/data/tiName.dat")
    doc = parse_table(source_path, text_encoding="cp932")
    target = next((entry for entry in doc.entries if entry["decoded"] and entry["text"]), None)
    if target is None:
        raise AssertionError("No decoded tiName.dat entry found")
    replacement = _make_gbk_patch("TN", 3)
    target["text"] = replacement
    rebuilt = compile_table(
        {
            "format": doc.format,
            "table_name": doc.table_name,
            "source_path": doc.source_path,
            "key_mode": doc.key_mode,
            "key_seed_u32": doc.key_seed_u32,
            "record_size": doc.record_size,
            "entries": doc.entries,
        },
        text_encoding="gbk",
    )
    reparsed = parse_table_bytes(
        rebuilt,
        table_name=doc.table_name,
        source_path=doc.source_path,
        text_encoding="gbk",
    )
    if not any(entry["text"] == replacement for entry in reparsed.entries):
        raise AssertionError("GBK write-back text not recovered after tiName.dat reparse")


def run_ti_balloon_roundtrip_regression(title_root: Path) -> None:
    source_path = _get_game00_files_root(title_root) / "data" / "tiBalloonSp.dat"
    if not source_path.is_file():
        raise AssertionError("Expected unpacked tiBalloonSp.dat at _pak0_game00/files/data/tiBalloonSp.dat")
    doc = parse_table(source_path, text_encoding="cp932")
    rebuilt = compile_table(
        {
            "format": doc.format,
            "table_name": doc.table_name,
            "source_path": doc.source_path,
            "key_mode": doc.key_mode,
            "key_seed_u32": doc.key_seed_u32,
            "record_size": doc.record_size,
            "entries": doc.entries,
        },
        text_encoding="cp932",
    )
    if rebuilt != source_path.read_bytes():
        raise AssertionError("tiBalloonSp.dat roundtrip mismatch")


def run_ti_balloon_target_encoding_regression(title_root: Path) -> None:
    source_path = _get_game00_files_root(title_root) / "data" / "tiBalloonSp.dat"
    if not source_path.is_file():
        raise AssertionError("Expected unpacked tiBalloonSp.dat at _pak0_game00/files/data/tiBalloonSp.dat")
    doc = parse_table(source_path, text_encoding="cp932")
    target = next((entry for entry in doc.entries if entry["decoded"]), None)
    if target is None:
        raise AssertionError("No decoded tiBalloonSp.dat entry found")
    replacement = _make_gbk_patch("TB", 4)
    target["text"] = replacement
    rebuilt = compile_table(
        {
            "format": doc.format,
            "table_name": doc.table_name,
            "source_path": doc.source_path,
            "key_mode": doc.key_mode,
            "key_seed_u32": doc.key_seed_u32,
            "record_size": doc.record_size,
            "entries": doc.entries,
        },
        text_encoding="gbk",
    )
    reparsed = parse_table_bytes(
        rebuilt,
        table_name=doc.table_name,
        source_path=doc.source_path,
        text_encoding="gbk",
    )
    if not any(entry["text"] == replacement for entry in reparsed.entries):
        raise AssertionError("GBK write-back text not recovered after tiBalloonSp.dat reparse")


def run_ti_balloon_game01_roundtrip_regression(title_root: Path) -> None:
    source_path = _get_game01_files_root(title_root) / "data" / "tiBalloon.dat"
    if not source_path.is_file():
        raise AssertionError("Expected unpacked tiBalloon.dat at _pak0_game01_verify/files/data/tiBalloon.dat")
    doc = parse_table(source_path, text_encoding="cp932")
    rebuilt = compile_table(
        {
            "format": doc.format,
            "table_name": doc.table_name,
            "source_path": doc.source_path,
            "key_mode": doc.key_mode,
            "key_seed_u32": doc.key_seed_u32,
            "record_size": doc.record_size,
            "entries": doc.entries,
        },
        text_encoding="cp932",
    )
    if rebuilt != source_path.read_bytes():
        raise AssertionError("tiBalloon.dat roundtrip mismatch")


def run_ti_balloon_game01_target_encoding_regression(title_root: Path) -> None:
    source_path = _get_game01_files_root(title_root) / "data" / "tiBalloon.dat"
    if not source_path.is_file():
        raise AssertionError("Expected unpacked tiBalloon.dat at _pak0_game01_verify/files/data/tiBalloon.dat")
    doc = parse_table(source_path, text_encoding="cp932")
    target = next((entry for entry in doc.entries if entry["decoded"]), None)
    if target is None:
        raise AssertionError("No decoded tiBalloon.dat entry found")
    replacement = _make_gbk_patch("TB", 5)
    target["text"] = replacement
    rebuilt = compile_table(
        {
            "format": doc.format,
            "table_name": doc.table_name,
            "source_path": doc.source_path,
            "key_mode": doc.key_mode,
            "key_seed_u32": doc.key_seed_u32,
            "record_size": doc.record_size,
            "entries": doc.entries,
        },
        text_encoding="gbk",
    )
    reparsed = parse_table_bytes(
        rebuilt,
        table_name=doc.table_name,
        source_path=doc.source_path,
        text_encoding="gbk",
    )
    if not any(entry["text"] == replacement for entry in reparsed.entries):
        raise AssertionError("GBK write-back text not recovered after tiBalloon.dat reparse")


def run_bttext_outer_regression(title_root: Path) -> None:
    source_path = _get_game00_files_root(title_root) / "data" / "BtText.dat"
    if not source_path.is_file():
        raise AssertionError("Expected unpacked BtText.dat at _pak0_game00/files/data/BtText.dat")
    doc = probe_bttext(source_path)
    if doc.raw_header["magic_ascii"] != "TSCR":
        raise AssertionError("BtText raw outer magic mismatch")
    if doc.tuta_header["magic_ascii"] != "TUTA":
        raise AssertionError("BtText decoded root magic mismatch")
    if doc.txt0_header["magic_ascii"] != "TXT0":
        raise AssertionError("BtText TXT0 string-pool magic mismatch")
    decoded_entries = [entry for entry in doc.txt0_strings if entry["decoded"]]
    if len(decoded_entries) < 3:
        raise AssertionError("BtText TXT0 string pool did not decode enough entries")
    if rebuild_bttext(doc) != source_path.read_bytes():
        raise AssertionError("BtText outer roundtrip mismatch")


def run_bttext_text_roundtrip_regression(title_root: Path) -> None:
    source_path = _get_game00_files_root(title_root) / "data" / "BtText.dat"
    if not source_path.is_file():
        raise AssertionError("Expected unpacked BtText.dat at _pak0_game00/files/data/BtText.dat")
    doc = parse_bttext_text(source_path, text_encoding="cp932")
    rebuilt = compile_bttext(
        {
            "format": doc.format,
            "source_path": doc.source_path,
            "source_text_encoding": doc.source_text_encoding,
            "raw_header": doc.raw_header,
            "tuta_header": doc.tuta_header,
            "txt0_header": doc.txt0_header,
            "entries": doc.entries,
        },
        text_encoding="cp932",
    )
    if rebuilt != source_path.read_bytes():
        raise AssertionError("BtText text roundtrip mismatch")


def run_bttext_text_patch_regression(title_root: Path) -> None:
    source_path = _get_game00_files_root(title_root) / "data" / "BtText.dat"
    if not source_path.is_file():
        raise AssertionError("Expected unpacked BtText.dat at _pak0_game00/files/data/BtText.dat")
    doc = parse_bttext_text(source_path, text_encoding="cp932")
    decoded_indices = [entry["index"] for entry in doc.entries if entry["decoded"]]
    if len(decoded_indices) < 2:
        raise AssertionError("No stable BtText decoded entries found for cp932 patch regression")
    target_index = int(decoded_indices[0])
    neighbor_index = int(decoded_indices[1])
    target = next(entry for entry in doc.entries if int(entry["index"]) == target_index)
    replacement = _make_ascii_patch("BT", target_index)
    target["text"] = replacement
    rebuilt = compile_bttext(
        {
            "format": doc.format,
            "source_path": doc.source_path,
            "source_text_encoding": doc.source_text_encoding,
            "raw_header": doc.raw_header,
            "tuta_header": doc.tuta_header,
            "txt0_header": doc.txt0_header,
            "entries": doc.entries,
        },
        text_encoding="cp932",
    )
    temp_dir = make_temp_dir(title_root, "bttext_patch")
    try:
        rebuilt_path = temp_dir / "BtText_patched.dat"
        rebuilt_path.write_bytes(rebuilt)
        reparsed = parse_bttext_text(rebuilt_path, text_encoding="cp932")
    finally:
        cleanup_temp_dir(temp_dir)
    reparsed_target = next((entry for entry in reparsed.entries if int(entry["index"]) == target_index), None)
    reparsed_neighbor = next((entry for entry in reparsed.entries if int(entry["index"]) == neighbor_index), None)
    if reparsed_target is None or str(reparsed_target["text"]) != replacement:
        raise AssertionError("Patched BtText text not recovered after reparse")
    if reparsed_neighbor is None:
        raise AssertionError("Neighbor BtText text was not preserved after variable-length patch")


def run_bttext_target_encoding_regression(title_root: Path) -> None:
    source_path = _get_game00_files_root(title_root) / "data" / "BtText.dat"
    if not source_path.is_file():
        raise AssertionError("Expected unpacked BtText.dat at _pak0_game00/files/data/BtText.dat")
    doc = parse_bttext_text(source_path, text_encoding="cp932")
    decoded_indices = [entry["index"] for entry in doc.entries if entry["decoded"]]
    if not decoded_indices:
        raise AssertionError("No stable BtText decoded entry found for gbk patch regression")
    target_index = int(decoded_indices[0])
    target = next(entry for entry in doc.entries if int(entry["index"]) == target_index)
    replacement = _make_gbk_patch("BT", target_index)
    target["text"] = replacement
    rebuilt = compile_bttext(
        {
            "format": doc.format,
            "source_path": doc.source_path,
            "text_encoding": "gbk",
            "source_text_encoding": doc.source_text_encoding,
            "raw_header": doc.raw_header,
            "tuta_header": doc.tuta_header,
            "txt0_header": doc.txt0_header,
            "entries": doc.entries,
        },
        text_encoding="gbk",
    )
    temp_dir = make_temp_dir(title_root, "bttext_gbk")
    try:
        rebuilt_path = temp_dir / "BtText_gbk.dat"
        rebuilt_path.write_bytes(rebuilt)
        reparsed = parse_bttext_text(rebuilt_path, text_encoding="gbk")
    finally:
        cleanup_temp_dir(temp_dir)
    reparsed_target = next((entry for entry in reparsed.entries if int(entry["index"]) == target_index), None)
    if reparsed_target is None or str(reparsed_target["text"]) != replacement:
        raise AssertionError("GBK BtText text not recovered after reparse")


def run_bttext_game01_roundtrip_regression(title_root: Path) -> None:
    source_path = _get_game01_files_root(title_root) / "data" / "BtText.dat"
    if not source_path.is_file():
        raise AssertionError("Expected unpacked game01 BtText.dat at _pak0_game01_verify/files/data/BtText.dat")
    doc = parse_bttext_text(source_path, text_encoding="cp932")
    rebuilt = compile_bttext(
        {
            "format": doc.format,
            "source_path": doc.source_path,
            "source_text_encoding": doc.source_text_encoding,
            "raw_header": doc.raw_header,
            "tuta_header": doc.tuta_header,
            "txt0_header": doc.txt0_header,
            "entries": doc.entries,
        },
        text_encoding="cp932",
    )
    if rebuilt != source_path.read_bytes():
        raise AssertionError("game01 BtText.dat text roundtrip mismatch")


def run_scr_outer_regression(title_root: Path) -> None:
    checked = 0
    for script_root in _iter_script_roots(title_root):
        for source_path in sorted(script_root.glob("*.scr"))[:4]:
            doc = probe_scr(source_path)
            if doc.raw_header["magic_ascii"] != "SCR ":
                raise AssertionError(f"{source_path.name} raw outer magic mismatch")
            if int(doc.raw_header["codec_mode_u32"]) != 2:
                raise AssertionError(f"{source_path.name} codec mode mismatch")
            if not doc.ascii_literals:
                raise AssertionError(f"{source_path.name} decoded payload did not expose any ASCII literals")
            if rebuild_scr(doc) != source_path.read_bytes():
                raise AssertionError(f"{source_path.name} outer roundtrip mismatch")
            checked += 1
    if checked == 0:
        raise AssertionError("SCR outer regression did not check any script file")


def run_scr_text_candidate_regression(title_root: Path) -> None:
    source_path, base_doc = _find_scr_doc(title_root, min_entries=2, usages=("text", "choice", "dialogue"))
    doc = parse_scr_text(source_path, text_encoding="cp932", include_impact=True)
    entries = _first_entries(doc, 2, "text", "choice", "dialogue")
    for entry in entries:
        if str(entry.get("patch_mode")) != "section_rebuild_expandable":
            raise AssertionError("Unexpected SCR text patch mode metadata")
        if int(entry.get("capacity_bytes", 0)) != int(entry["length"]):
            raise AssertionError("Unexpected SCR text capacity metadata")
        if int(entry.get("in_place_capacity_bytes", 0)) != int(entry["length"]):
            raise AssertionError("Unexpected SCR text in-place capacity metadata")
        if not bool(entry.get("supports_expansion_rebuild", False)):
            raise AssertionError("SCR text candidate is missing expansion rebuild capability metadata")
        rebuild_impact = entry.get("rebuild_impact")
        if not isinstance(rebuild_impact, dict):
            raise AssertionError("SCR text candidate is missing rebuild impact metadata")
        if "anchor_offset" not in rebuild_impact:
            raise AssertionError("SCR rebuild impact metadata is missing anchor offset")
        if "outer_decoded_payload_size_field_offset" not in rebuild_impact:
            raise AssertionError("SCR rebuild impact metadata is missing outer size field")
        if "sec3_length_field_offset" not in rebuild_impact:
            raise AssertionError("SCR rebuild impact metadata is missing sec3 length field")
        if "sec4_impacted_indices_if_expand" not in rebuild_impact or "sec5_impacted_indices_if_expand" not in rebuild_impact:
            raise AssertionError("SCR rebuild impact metadata is missing impacted index arrays")
        if "sec3_u32_in_range_count_if_expand" not in rebuild_impact:
            raise AssertionError("SCR rebuild impact metadata is missing sec3 in-range u32 count")
        if "sec3_impacted_u32_sample_positions_if_expand" not in rebuild_impact or "sec3_impacted_u32_sample_values_if_expand" not in rebuild_impact:
            raise AssertionError("SCR rebuild impact metadata is missing sec3 impacted u32 sample arrays")


def run_scr_text_patch_regression(title_root: Path) -> None:
    source_path, doc = _find_scr_doc(title_root, min_entries=2, usages=("text", "choice", "dialogue"))
    patchable_entries = _scr_content_entries(doc)
    if len(patchable_entries) < 4:
        raise AssertionError("Not enough SCR entries for patch regression")

    short_target = min((entry for entry in patchable_entries if int(entry["length"]) >= 4), key=lambda entry: int(entry["length"]))
    short_replacement = _make_ascii_patch("SCR", int(short_target["index"]))
    short_index = int(short_target["index"])

    work_entries = deepcopy(doc.entries)
    for entry in work_entries:
        if int(entry["index"]) == short_index:
            entry["text"] = short_replacement
            break
    rebuilt = compile_scr_text(
        {
            "format": doc.format,
            "source_path": doc.source_path,
            "text_encoding": doc.text_encoding,
            "raw_header": doc.raw_header,
            "entries": work_entries,
        },
        text_encoding="cp932",
    )
    temp_dir = make_temp_dir(title_root, "scr_patch")
    try:
        rebuilt_path = temp_dir / f"{source_path.stem}_patched.scr"
        rebuilt_path.write_bytes(rebuilt)
        reparsed = parse_scr_text(rebuilt_path, text_encoding="cp932")
        rebuilt_sec3 = parse_scr_sections(probe_scr(rebuilt_path).decoded_payload_bytes).sec3_bytes
    finally:
        cleanup_temp_dir(temp_dir)
    expected_bytes = short_replacement.encode("cp932")
    target_offset = int(short_target["offset"])
    patched_bytes = rebuilt_sec3[target_offset : target_offset + len(expected_bytes)]
    if patched_bytes != expected_bytes:
        raise AssertionError("Patched SCR in-place bytes not recovered after rebuild")
    reparsed_short = next((entry for entry in reparsed.entries if int(entry["index"]) == short_index), None)
    if reparsed_short is None or str(reparsed_short["text"]) != short_replacement:
        raise AssertionError("Patched SCR in-place text not recovered after rebuild")

    long_target = max((entry for entry in patchable_entries if int(entry["length"]) >= 4), key=lambda entry: int(entry["length"]))
    long_index = int(long_target["index"])
    long_replacement = _longer_scr_patch(long_target, "LONG", long_index)
    work_entries = deepcopy(doc.entries)
    for entry in work_entries:
        if int(entry["index"]) == long_index:
            entry["text"] = long_replacement
            break
    rebuilt_long = compile_scr_text(
        {
            "format": doc.format,
            "source_path": doc.source_path,
            "text_encoding": doc.text_encoding,
            "raw_header": doc.raw_header,
            "entries": work_entries,
        },
        text_encoding="cp932",
    )
    temp_dir = make_temp_dir(title_root, "scr_long_patch")
    try:
        rebuilt_path = temp_dir / f"{source_path.stem}_long.scr"
        rebuilt_path.write_bytes(rebuilt_long)
        reparsed_long = parse_scr_text(rebuilt_path, text_encoding="cp932")
    finally:
        cleanup_temp_dir(temp_dir)
    reparsed_long_target = next((entry for entry in reparsed_long.entries if int(entry["index"]) == long_index), None)
    if reparsed_long_target is None or str(reparsed_long_target["text"]) != long_replacement:
        raise AssertionError("Patched SCR long text was not recovered after rebuild")
    if len(reparsed_long.entries) != len(doc.entries):
        raise AssertionError("SCR long patch changed entry count")

    multi_targets = _first_entries(doc, 2, "choice", "dialogue", "text", min_length=4)
    expected_multi: dict[int, str] = {}
    work_entries = deepcopy(doc.entries)
    for order, target in enumerate(multi_targets):
        replacement = _longer_scr_patch(target, "PAIR", order)
        expected_multi[int(target["index"])] = replacement
        for entry in work_entries:
            if int(entry["index"]) == int(target["index"]):
                entry["text"] = replacement
                break
    rebuilt_multi = compile_scr_text(
        {
            "format": doc.format,
            "source_path": doc.source_path,
            "text_encoding": doc.text_encoding,
            "raw_header": doc.raw_header,
            "entries": work_entries,
        },
        text_encoding="cp932",
    )
    temp_dir = make_temp_dir(title_root, "scr_multi_patch")
    try:
        rebuilt_path = temp_dir / f"{source_path.stem}_multi.scr"
        rebuilt_path.write_bytes(rebuilt_multi)
        reparsed_multi = parse_scr_text(rebuilt_path, text_encoding="cp932")
    finally:
        cleanup_temp_dir(temp_dir)
    reparsed_multi_by_index = {int(entry["index"]): str(entry["text"]) for entry in reparsed_multi.entries}
    for target_index, replacement in expected_multi.items():
        if reparsed_multi_by_index.get(target_index) != replacement:
            raise AssertionError("Patched SCR multi-entry long text was not recovered after rebuild")
    if len(reparsed_multi.entries) != len(doc.entries):
        raise AssertionError("SCR multi-entry patch changed entry count")

    name_source, name_doc = _find_scr_doc(title_root, min_entries=2, usages=("name",))
    name_targets = _first_entries(name_doc, 2, "name")
    expected_name: dict[int, str] = {}
    work_entries = deepcopy(name_doc.entries)
    for order, target in enumerate(name_targets):
        replacement = _make_cp932_patch("NM", order)
        expected_name[int(target["index"])] = replacement
        for entry in work_entries:
            if int(entry["index"]) == int(target["index"]):
                entry["text"] = replacement
                break
    rebuilt_names = compile_scr_text(
        {
            "format": name_doc.format,
            "source_path": name_doc.source_path,
            "text_encoding": name_doc.text_encoding,
            "raw_header": name_doc.raw_header,
            "entries": work_entries,
        },
        text_encoding="cp932",
    )
    temp_dir = make_temp_dir(title_root, "scr_name_patch")
    try:
        rebuilt_path = temp_dir / f"{name_source.stem}_name.scr"
        rebuilt_path.write_bytes(rebuilt_names)
        reparsed_names = parse_scr_text(rebuilt_path, text_encoding="cp932")
    finally:
        cleanup_temp_dir(temp_dir)
    reparsed_name_by_index = {int(entry["index"]): str(entry["text"]) for entry in reparsed_names.entries}
    for target_index, replacement in expected_name.items():
        if reparsed_name_by_index.get(target_index) != replacement:
            raise AssertionError("Patched SCR name entries were not recovered after rebuild")
    if len(reparsed_names.entries) != len(name_doc.entries):
        raise AssertionError("SCR name patch changed entry count")


def run_text_patch_helper_regression(title_root: Path) -> None:
    source_path = _get_game00_files_root(title_root) / "data" / "BtText.dat"
    if not source_path.is_file():
        raise AssertionError("Expected unpacked BtText.dat at _pak0_game00/files/data/BtText.dat")
    temp_root = make_temp_dir(title_root, "patch_helper")
    try:
        json_path = temp_root / "BtText.json"
        patched_json_path = temp_root / "BtText_patched.json"
        rebuilt_path = temp_root / "BtText_patched.dat"

        doc = parse_bttext_text(source_path, text_encoding="cp932")
        from script.tev2_bttext import write_text_doc

        write_text_doc(json_path, doc)
        decoded_indices = [int(entry["index"]) for entry in doc.entries if entry["decoded"]]
        if not decoded_indices:
            raise AssertionError("Patch helper did not find a decoded BtText entry")
        target_index = decoded_indices[0]
        replacement = _make_ascii_patch("HELP", target_index)
        patch_text_doc(
            json_path,
            patched_json_path,
            entry_index=target_index,
            text=replacement,
        )
        patched_doc = json.loads(patched_json_path.read_text(encoding="utf-8"))
        rebuilt = compile_bttext(patched_doc, text_encoding="cp932")
        rebuilt_path.write_bytes(rebuilt)
        reparsed = parse_bttext_text(rebuilt_path, text_encoding="cp932")
        if not any(entry["text"] == replacement for entry in reparsed.entries):
            raise AssertionError("Patch helper did not patch BtText entry as expected")
    finally:
        cleanup_temp_dir(temp_root)


def run_text_fit_helper_regression(title_root: Path) -> None:
    source_path, text_doc = _find_scr_doc(title_root, min_entries=1, usages=("text", "dialogue", "choice"))
    temp_root = make_temp_dir(title_root, "fit_helper")
    try:
        from script.tev2_scr import write_text_doc

        json_path = temp_root / "start.json"
        write_text_doc(json_path, text_doc)
        target = _first_entries(text_doc, 1, "text", "dialogue", "choice", min_length=4)[0]
        target_offset = int(target["offset"])
        fit_text = _make_fit_text(4)
        fit = check_text_fit(json_path, entry_offset=target_offset, text=fit_text, text_encoding="cp932")
        if not fit["fits"]:
            raise AssertionError("Text fit helper rejected a known fitting SCR replacement")
        if not fit["fits_in_place"]:
            raise AssertionError("Text fit helper unexpectedly rejected a known in-place SCR replacement")
        if fit["requires_expansion_rebuild"]:
            raise AssertionError("Text fit helper incorrectly marked a fitting SCR replacement as expansion-only")
        overflow_target = max(_scr_content_entries(text_doc), key=lambda entry: int(entry["in_place_capacity_bytes"]))
        overflow_offset = int(overflow_target["offset"])
        overflow_capacity = int(overflow_target["in_place_capacity_bytes"])
        overflow_text = _make_cp932_patch("OVER", 1, extra=max(1, overflow_capacity))
        while len(overflow_text.encode("cp932")) <= overflow_capacity:
            overflow_text += "\u30a2"
        overflow = check_text_fit(
            json_path,
            entry_offset=overflow_offset,
            text=overflow_text,
            text_encoding="cp932",
        )
        if overflow["fits"]:
            raise AssertionError("Text fit helper accepted a known overflowing SCR replacement as in-place")
        if overflow["fits_in_place"]:
            raise AssertionError("Text fit helper accepted a known overflowing SCR replacement as in-place")
        if not overflow["requires_expansion_rebuild"]:
            raise AssertionError("Text fit helper did not mark an overflowing SCR replacement as expansion rebuild")
        if not overflow["can_rebuild_with_expansion"]:
            raise AssertionError("Text fit helper did not expose expansion rebuild for overflowing SCR replacement")
    finally:
        cleanup_temp_dir(temp_root)


def run_text_fit_report_regression(title_root: Path) -> None:
    source_path, text_doc = _find_scr_doc(title_root, min_entries=2, usages=("text", "dialogue", "choice"))
    temp_root = make_temp_dir(title_root, "fit_report")
    try:
        from script.tev2_scr import write_text_doc

        json_path = temp_root / "start.json"
        report_path = temp_root / "start_fit_report.json"
        write_text_doc(json_path, text_doc)
        build_fit_report(json_path, report_path, extra_bytes=0, text_encoding="cp932")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        entries = report["entries"]
        sorted_entries = sorted(entries, key=lambda entry: int(entry["capacity_bytes"]))
        short = next((entry for entry in sorted_entries if int(entry["capacity_bytes"]) >= 4), None)
        long_entry = max(entries, key=lambda entry: int(entry["capacity_bytes"]), default=None)
        if short is None or long_entry is None:
            raise AssertionError("Fit report missing expected SCR entries")
        if not short["fits_estimate"]:
            raise AssertionError("Fit report unexpectedly rejected a short SCR entry")
        if not short["fits_in_place_estimate"]:
            raise AssertionError("Fit report unexpectedly rejected a short SCR entry as in-place")
        build_fit_report(json_path, report_path, extra_bytes=4, text_encoding="cp932")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        long_entry = max(report["entries"], key=lambda entry: int(entry["capacity_bytes"]), default=None)
        if long_entry is None:
            raise AssertionError("Fit report missing long SCR entry after growth report")
        if long_entry["fits_estimate"]:
            raise AssertionError("Fit report unexpectedly accepted a long SCR entry after extra byte growth")
        if long_entry["fits_in_place_estimate"]:
            raise AssertionError("Fit report unexpectedly accepted a long SCR entry as in-place after extra byte growth")
        if not long_entry["requires_expansion_rebuild_estimate"]:
            raise AssertionError("Fit report did not mark a long SCR entry as requiring expansion rebuild")
        if not long_entry["can_rebuild_with_expansion_estimate"]:
            raise AssertionError("Fit report did not expose expansion rebuild for a long SCR entry")
    finally:
        cleanup_temp_dir(temp_root)


def run_text_scan_regression(title_root: Path) -> None:
    checked_roots = 0
    for getter in (_get_game00_files_root, _get_game01_files_root):
        resource_root = getter(title_root)
        if not resource_root.is_dir():
            raise AssertionError("Expected unpacked files root")
        temp_root = make_temp_dir(title_root, f"text_scan_{checked_roots}")
        try:
            output_path = temp_root / "text_scan.json"
            build_text_scan(resource_root, output_path, text_encoding="cp932")
            report = json.loads(output_path.read_text(encoding="utf-8"))
            if report.get("format") != "TE_V2_TEXT_SCAN":
                raise AssertionError("Unexpected text scan report format")
            carriers = report.get("carriers", [])
            carrier_types = {str(entry.get("carrier_type")) for entry in carriers}
            for expected_type in {"fixed_table", "bttext", "scr_text_candidates"}:
                if expected_type not in carrier_types:
                    raise AssertionError(f"Text scan is missing expected carrier type {expected_type}")
            checked_roots += 1
        finally:
            cleanup_temp_dir(temp_root)
    if checked_roots < 2:
        raise AssertionError("Text scan regression did not cover both script roots")


def _build_scr_mixed_replacement(text: str, index: int) -> str:
    if len(text) > 2 and index % 2 == 0:
        shortened = text[: max(1, len(text) // 2)]
        shortened = shortened.encode("cp932", errors="ignore").decode("cp932", errors="ignore")
        if shortened and shortened != text:
            return shortened
    return f"{text}[{index:X}]"


def run_scr_full_coverage_regression(title_root: Path) -> None:
    misses: list[str] = []
    for script_root in _iter_script_roots(title_root):
        for source_path in sorted(script_root.glob("*.scr")):
            outer = probe_scr(source_path)
            sections = parse_scr_sections(outer.decoded_payload_bytes)
            for command in parse_scr_commands(sections.sec3_bytes):
                if command.kind != "command" or command.opcode_u32 is None:
                    continue
                slots = _iter_command_string_slots(command, text_encoding="cp932")
                selected = {(slot.text_start, slot.text_end) for slot, _usage in _select_translatable_slots(command, slots)}
                for slot in slots:
                    if not slot.decoded or not slot.text or all(ord(ch) < 0x20 for ch in slot.text):
                        continue
                    if any(ord(ch) >= 0x80 for ch in slot.text) and (slot.text_start, slot.text_end) not in selected:
                        misses.append(
                            f"{source_path.name}:0x{command.start:X}:op=0x{command.opcode_u32:02X}:slot=0x{slot.local_marker_pos:X}:{slot.text[:80]!r}"
                        )
                        if len(misses) >= 32:
                            break
                if len(misses) >= 32:
                    break
            if len(misses) >= 32:
                break
        if len(misses) >= 32:
            break
    if misses:
        raise AssertionError("SCR full coverage regression found untranslated non-ASCII slots:\n" + "\n".join(misses))


def run_scr_full_rewrite_regression(title_root: Path) -> None:
    for script_root in _iter_script_roots(title_root):
        for source_path in sorted(script_root.glob("*.scr")):
            base_doc = parse_scr_text(source_path, text_encoding="cp932")
            if not base_doc.entries:
                continue
            work_entries = deepcopy(base_doc.entries)
            expected_by_index: dict[int, str] = {}
            for entry in work_entries:
                target_index = int(entry["index"])
                replacement = _build_scr_mixed_replacement(str(entry["text"]), target_index)
                entry["text"] = replacement
                expected_by_index[target_index] = replacement
            rebuilt = compile_scr_text(
                {
                    "format": base_doc.format,
                    "source_path": base_doc.source_path,
                    "text_encoding": base_doc.text_encoding,
                    "raw_header": base_doc.raw_header,
                    "entries": work_entries,
                },
                text_encoding="cp932",
            )
            reparsed = parse_scr_text_bytes(
                rebuilt,
                source_path=f"{source_path}:full",
                text_encoding="cp932",
                include_impact=False,
            )
            if len(reparsed.entries) != len(base_doc.entries):
                raise AssertionError(
                    f"SCR full rewrite changed entry count for {source_path.name}: {len(base_doc.entries)}->{len(reparsed.entries)}"
                )
            reparsed_by_index = {int(entry["index"]): str(entry["text"]) for entry in reparsed.entries}
            for target_index, replacement in expected_by_index.items():
                if reparsed_by_index.get(target_index) != replacement:
                    raise AssertionError(
                        f"SCR full rewrite did not recover patched text for {source_path.name} index {target_index}"
                    )
