#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from nejii.rk1 import pack_rk1, parse_rk1, unpack_rk1
from nejii.script_bin import compile_script_bin, parse_nejsrc, parse_script_bin, render_nejsrc


def run_rk1_roundtrip(game_dir: Path, tmp_dir: Path, archives: list[str]) -> None:
    for archive_name in archives:
        src = game_dir / archive_name
        if not src.is_file():
            raise RuntimeError(f"Archive not found: {src}")
        unpack_dir = tmp_dir / f"unpack_{src.stem}"
        manifest = unpack_rk1(src, unpack_dir)
        out_path = tmp_dir / f"{src.name}.repack"
        pack_rk1(manifest, out_path)
        if out_path.read_bytes() != src.read_bytes():
            raise RuntimeError(f"RK1 roundtrip failed: {archive_name}")


def _iter_script_bins(script_archive_data: bytes) -> list[tuple[str, bytes]]:
    doc = parse_rk1(script_archive_data)
    out: list[tuple[str, bytes]] = []
    for entry in list(doc.get("entries", [])):
        name = str(entry["name"])
        if not name.lower().endswith(".bin"):
            continue
        out.append((name, bytes(entry["unpacked_blob"])))
    return out


def run_script_json_roundtrip(game_dir: Path) -> None:
    archive = game_dir / "script.dat"
    data = archive.read_bytes()
    samples = _iter_script_bins(data)
    if not samples:
        raise RuntimeError("No .BIN script entries found in script.dat.")
    for name, blob in samples:
        doc = parse_script_bin(blob, text_encoding="cp932")
        rebuilt = compile_script_bin(doc)
        if rebuilt != blob:
            raise RuntimeError(f"Script JSON roundtrip failed: {name}")


def run_script_nejsrc_roundtrip(game_dir: Path) -> None:
    archive = game_dir / "script.dat"
    data = archive.read_bytes()
    samples = _iter_script_bins(data)
    for name, blob in samples:
        doc = parse_script_bin(blob, text_encoding="cp932")
        src = render_nejsrc(doc)
        doc2 = parse_nejsrc(src)
        rebuilt = compile_script_bin(doc2)
        if rebuilt != blob:
            raise RuntimeError(f"Script NEJSRC roundtrip failed: {name}")


def run_script_text_mutation(game_dir: Path) -> None:
    archive = game_dir / "script.dat"
    data = archive.read_bytes()
    samples = _iter_script_bins(data)
    for name, blob in samples:
        doc = parse_script_bin(blob, text_encoding="cp932")
        target = next((c for c in list(doc["commands"]) if bool(c.get("str1_editable", False))), None)
        if target is None:
            continue
        target["str1_text"] = str(target.get("str1_text", "")) + "【LEN_TEST】"
        rebuilt = compile_script_bin(doc)
        reparsed = parse_script_bin(rebuilt, text_encoding="cp932")
        if not any("【LEN_TEST】" in str(c.get("str1_text", "")) for c in list(reparsed["commands"])):
            raise RuntimeError(f"Script text mutation failed: {name}")
        return
    raise RuntimeError("No editable script command found for mutation test.")


def run_script_encoding_override(game_dir: Path) -> None:
    archive = game_dir / "script.dat"
    data = archive.read_bytes()
    samples = _iter_script_bins(data)
    for name, blob in samples:
        doc = parse_script_bin(blob, text_encoding="cp932")
        target = next((c for c in list(doc["commands"]) if bool(c.get("str1_editable", False))), None)
        if target is None:
            continue
        target["str1_text"] = "编码回写GBK测试"
        rebuilt = compile_script_bin(doc, text_encoding="gbk")
        reparsed = parse_script_bin(rebuilt, text_encoding="gbk")
        if not any("编码回写GBK测试" in str(c.get("str1_text", "")) for c in list(reparsed["commands"])):
            raise RuntimeError(f"Script GBK override mutation failed: {name}")
        return
    raise RuntimeError("No editable script command found for GBK override test.")


def run_script_filter_fallback(game_dir: Path, tmp_dir: Path) -> None:
    marker = ""
    for code in range(0x20, 0xFFFE):
        ch = chr(code)
        try:
            ch.encode("cp932")
        except UnicodeEncodeError:
            continue
        try:
            ch.encode("gbk")
        except UnicodeEncodeError:
            marker = ch
            break
    if not marker:
        raise RuntimeError("No CP932-only marker found for filter fallback test.")

    archive = game_dir / "script.dat"
    data = archive.read_bytes()
    samples = _iter_script_bins(data)
    for name, blob in samples:
        doc = parse_script_bin(blob, text_encoding="cp932")
        target = next((c for c in list(doc["commands"]) if bool(c.get("str1_editable", False))), None)
        if target is None:
            continue

        text_value = str(target.get("str1_text", "")) + marker
        target["str1_text"] = text_value
        case_dir = tmp_dir / "filter_case"
        case_dir.mkdir(parents=True, exist_ok=True)
        src_json = case_dir / "case.bin.json"
        src_json.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        (case_dir / "filter_text.txt").write_text(f"{marker}\n", encoding="utf-8")
        out_bin = case_dir / "case.out.bin"

        cmd = [
            sys.executable,
            "nejii_compile.py",
            str(src_json),
            str(out_bin),
            "--input-format",
            "json",
            "--text-encoding",
            "gbk",
        ]
        proc = subprocess.run(cmd, cwd=Path.cwd(), capture_output=True, text=True)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"Filter fallback compile failed: {name}; {detail}")

        reparsed = parse_script_bin(out_bin.read_bytes(), text_encoding="cp932")
        target_id = int(target["index"])
        rebuilt_cmd = next((c for c in list(reparsed["commands"]) if int(c["index"]) == target_id), None)
        if rebuilt_cmd is None:
            raise RuntimeError(f"Filter fallback command not found: {name}")
        rebuilt_text = str(rebuilt_cmd.get("str1_text", ""))
        if rebuilt_text != text_value:
            raise RuntimeError(f"Filter fallback text mismatch: {name}")
        expected_prefix = text_value.encode("cp932") + b"\x00"
        rebuilt_raw = bytes.fromhex(str(rebuilt_cmd["str1_raw_hex"]))
        if not rebuilt_raw.startswith(expected_prefix):
            raise RuntimeError(f"Filter fallback raw bytes mismatch: {name}")
        return
    raise RuntimeError("No editable script command found for filter fallback test.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Regression test for NEJII tools.")
    parser.add_argument("--game-dir", default="game", help="Game directory. Default: ./game")
    parser.add_argument("--tmp-dir", default="_regression_tmp", help="Temporary directory. Default: ./_regression_tmp")
    parser.add_argument(
        "--archives",
        nargs="*",
        default=["script.dat", "se.pdt"],
        help="Archives for RK1 unpack->pack roundtrip. Default: script.dat se.pdt",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path.cwd()
    game_dir = (root / args.game_dir).resolve()
    tmp_dir = (root / args.tmp_dir).resolve()

    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    run_rk1_roundtrip(game_dir, tmp_dir, list(args.archives))
    run_script_json_roundtrip(game_dir)
    run_script_nejsrc_roundtrip(game_dir)
    run_script_text_mutation(game_dir)
    run_script_encoding_override(game_dir)
    run_script_filter_fallback(game_dir, tmp_dir)
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
