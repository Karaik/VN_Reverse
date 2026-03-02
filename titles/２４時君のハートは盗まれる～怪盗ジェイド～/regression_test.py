#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from yuka.ykdat import pack_ykdat, parse_ykdat, unpack_ykdat
from yuka.yks import compile_yks, parse_yks, parse_ykssrc, render_ykssrc


def run_ykdat_roundtrip(game_dir: Path, tmp_dir: Path, archive_name: str) -> None:
    src = game_dir / archive_name
    if not src.is_file():
        raise RuntimeError(f"Archive not found: {src}")
    unpack_dir = tmp_dir / "unpack"
    manifest = unpack_ykdat(src, unpack_dir)
    repacked = tmp_dir / f"{archive_name}.repack"
    pack_ykdat(manifest, repacked)
    if repacked.read_bytes() != src.read_bytes():
        raise RuntimeError("YKC roundtrip failed.")


def _iter_yks_from_archive(archive_data: bytes) -> list[tuple[str, bytes]]:
    doc = parse_ykdat(archive_data)
    out: list[tuple[str, bytes]] = []
    for item in list(doc.get("entries", [])):
        name = str(item["name"])
        if not name.lower().endswith(".yks"):
            continue
        off = int(item["data_off_u32"])
        size = int(item["data_len_u32"])
        out.append((name, archive_data[off : off + size]))
    return out


def run_yks_roundtrip(game_dir: Path) -> None:
    archive = game_dir / "jade01.dat"
    data = archive.read_bytes()
    samples = _iter_yks_from_archive(data)
    if not samples:
        raise RuntimeError("No .yks files found in archive.")

    editable_hits = 0
    for name, blob in samples:
        doc = parse_yks(blob)
        rebuilt = compile_yks(doc)
        if rebuilt != blob:
            raise RuntimeError(f"YKS JSON roundtrip failed: {name}")
        src = render_ykssrc(doc)
        doc2 = parse_ykssrc(src)
        rebuilt2 = compile_yks(doc2)
        if rebuilt2 != blob:
            raise RuntimeError(f"YKS YKSRC roundtrip failed: {name}")
        if any(bool(t.get("editable_text", False)) for t in list(doc.get("tokens", []))):
            editable_hits += 1

    if editable_hits == 0:
        raise RuntimeError("No editable text tokens detected in any YKS file.")


def run_yks_text_mutation(game_dir: Path) -> None:
    archive = game_dir / "jade01.dat"
    data = archive.read_bytes()
    samples = _iter_yks_from_archive(data)
    for name, blob in samples:
        doc = parse_yks(blob)
        tokens = list(doc.get("tokens", []))
        target = next((t for t in tokens if bool(t.get("editable_text", False))), None)
        if target is None:
            continue

        target["text"] = str(target.get("text", "")) + "【LEN_TEST】"
        rebuilt = compile_yks(doc)
        reparsed = parse_yks(rebuilt)
        if not any("【LEN_TEST】" in str(t.get("text", "")) for t in list(reparsed.get("tokens", []))):
            raise RuntimeError(f"YKS text mutation failed: {name}")

        src = render_ykssrc(doc)
        doc2 = parse_ykssrc(src)
        rebuilt2 = compile_yks(doc2)
        reparsed2 = parse_yks(rebuilt2)
        if not any("【LEN_TEST】" in str(t.get("text", "")) for t in list(reparsed2.get("tokens", []))):
            raise RuntimeError(f"YKSRC text mutation failed: {name}")
        return
    raise RuntimeError("No editable YKS file found for mutation test.")


def run_yks_encoding_override(game_dir: Path) -> None:
    archive = game_dir / "jade01.dat"
    data = archive.read_bytes()
    samples = _iter_yks_from_archive(data)
    for name, blob in samples:
        doc = parse_yks(blob, text_encoding="cp932")
        tokens = list(doc.get("tokens", []))
        target = next((t for t in tokens if bool(t.get("editable_text", False))), None)
        if target is None:
            continue

        target["text"] = "编码回写GBK测试"
        rebuilt = compile_yks(doc, text_encoding="gbk")
        reparsed = parse_yks(rebuilt, text_encoding="gbk")
        if not any("编码回写GBK测试" in str(t.get("text", "")) for t in list(reparsed.get("tokens", []))):
            raise RuntimeError(f"YKS GBK override mutation failed: {name}")

        src = render_ykssrc(doc)
        doc2 = parse_ykssrc(src)
        rebuilt2 = compile_yks(doc2, text_encoding="gbk")
        reparsed2 = parse_yks(rebuilt2, text_encoding="gbk")
        if not any("编码回写GBK测试" in str(t.get("text", "")) for t in list(reparsed2.get("tokens", []))):
            raise RuntimeError(f"YKSRC GBK override mutation failed: {name}")
        return
    raise RuntimeError("No editable YKS file found for GBK override test.")


def run_yks_filter_fallback(game_dir: Path, tmp_dir: Path) -> None:
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

    archive = game_dir / "jade01.dat"
    data = archive.read_bytes()
    samples = _iter_yks_from_archive(data)
    for name, blob in samples:
        doc = parse_yks(blob, text_encoding="cp932")
        tokens = list(doc.get("tokens", []))
        target = next((t for t in tokens if bool(t.get("editable_text", False))), None)
        if target is None:
            continue

        text_value = str(target.get("text", "")) + marker

        target["text"] = text_value
        case_dir = tmp_dir / "filter_case"
        case_dir.mkdir(parents=True, exist_ok=True)
        src_json = case_dir / "case.yks.json"
        src_json.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        (case_dir / "filter_text.txt").write_text(f"{marker}\n", encoding="utf-8")
        out_yks = case_dir / "case.out.yks"

        cmd = [
            sys.executable,
            "yks_compile.py",
            str(src_json),
            str(out_yks),
            "--input-format",
            "json",
            "--text-encoding",
            "gbk",
        ]
        proc = subprocess.run(cmd, cwd=Path.cwd(), capture_output=True, text=True)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"Filter fallback compile failed: {name}; {detail}")

        reparsed = parse_yks(out_yks.read_bytes(), text_encoding="cp932")
        target_id = int(target["token_id"])
        rebuilt_token = next((t for t in list(reparsed.get("tokens", [])) if int(t["token_id"]) == target_id), None)
        if rebuilt_token is None:
            raise RuntimeError(f"Filter fallback token not found: {name}")

        rebuilt_text = str(rebuilt_token.get("text", ""))
        if rebuilt_text != text_value:
            raise RuntimeError(f"Filter fallback text mismatch: {name}")

        expected_raw = text_value.encode("cp932").hex()
        if str(rebuilt_token.get("raw_hex", "")) != expected_raw:
            raise RuntimeError(f"Filter fallback raw bytes mismatch: {name}")
        return
    raise RuntimeError("No editable YKS file found for filter fallback test.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Regression test for Yuka engine tools.")
    parser.add_argument("--game-dir", default="game", help="Game directory. Default: ./game")
    parser.add_argument("--tmp-dir", default="_regression_tmp", help="Temporary directory. Default: ./_regression_tmp")
    parser.add_argument("--archive", default="jade01.dat", help="Archive file for YKC roundtrip.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path.cwd()
    game_dir = (root / args.game_dir).resolve()
    tmp_dir = (root / args.tmp_dir).resolve()

    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    run_ykdat_roundtrip(game_dir, tmp_dir, args.archive)
    run_yks_roundtrip(game_dir)
    run_yks_text_mutation(game_dir)
    run_yks_encoding_override(game_dir)
    run_yks_filter_fallback(game_dir, tmp_dir)
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
