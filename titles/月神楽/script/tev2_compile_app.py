from __future__ import annotations

import argparse
import json
from pathlib import Path

from script.tev2_bttext import build_bttext_from_decoded_root, compile_bttext, probe_bttext
from script.tev2_scr import compile_scr_from_decoded_payload, compile_scr_text, probe_scr
from script.tev2_text_tables import build_plain_table, compile_table, decrypt_words, detect_table_mode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile TE_V2 text carrier JSON.")
    parser.add_argument("input", type=Path, help="Input JSON file.")
    parser.add_argument("output", type=Path, help="Output table file.")
    parser.add_argument(
        "--source",
        type=Path,
        help="Original carrier file. Required when compiling from decoded-binary payload.",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Batch mode. Scan input recursively and mirror compile outputs under output.",
    )
    parser.add_argument(
        "--mode",
        choices=("decoded", "raw", "decoded-binary", "raw-binary"),
        default="decoded",
        help="decoded: compile editable decoded text JSON. raw/decoded-binary: rebuild from decoded container JSON. raw-binary: write original/plain binary bytes without container decode.",
    )
    parser.add_argument(
        "--text-encoding",
        default="cp932",
        help="Encoding used for write-back. Supports aliases: win-31j/sjis/cp932.",
    )
    return parser


def _compile_single(input_path: Path, output_path: Path, *, text_encoding: str, mode: str) -> None:
    if mode == "raw-binary":
        data = input_path.read_bytes()
    elif mode == "decoded-binary":
        raise ValueError("decoded-binary compile requires source-aware entrypoint")
    else:
        doc = json.loads(input_path.read_text(encoding="utf-8"))
        fmt = str(doc.get("format"))
        if mode == "raw":
            if fmt == "TE_V2_BTTEXT_OUTER":
                source_path = Path(str(doc["source_path"]))
                probe = probe_bttext(source_path, text_encoding=text_encoding)
                data = build_bttext_from_decoded_root(doc["raw_header"], probe.decoded_root_bytes)
            elif fmt == "TE_V2_SCR_OUTER":
                source_path = Path(str(doc["source_path"]))
                probe = probe_scr(source_path)
                data = compile_scr_from_decoded_payload(doc["raw_header"], probe.decoded_payload_bytes)
            else:
                raise ValueError(f"{mode} compile mode does not support format: {fmt}")
        else:
            if fmt == "TE_V2_BTTEXT_TEXT":
                data = compile_bttext(doc, text_encoding=text_encoding)
            elif fmt == "TE_V2_SCR_TEXT_CANDIDATES":
                data = compile_scr_text(doc, text_encoding=text_encoding)
            else:
                data = compile_table(doc, text_encoding=text_encoding)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)


def _compile_decoded_binary(input_path: Path, output_path: Path, source_path: Path, *, text_encoding: str) -> None:
    source_bytes = source_path.read_bytes()
    payload = input_path.read_bytes()
    head = source_bytes[:4]
    if head == b"TSCR":
        probe = probe_bttext(source_path, text_encoding=text_encoding)
        data = build_bttext_from_decoded_root(probe.raw_header, payload)
    elif head == b"SCR ":
        probe = probe_scr(source_path)
        data = compile_scr_from_decoded_payload(probe.raw_header, payload)
    else:
        mode, seed = detect_table_mode(source_bytes)
        data = decrypt_words(payload, mode, seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)


def _discover_json_inputs(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return [path for path in sorted(root.rglob("*.json")) if path.is_file()]


def _discover_binary_inputs(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return [path for path in sorted(root.rglob("*")) if path.is_file()]


def _resolve_decoded_binary_source(source_root: Path, relative: Path) -> Path:
    suffix = relative.suffix.lower()
    if suffix == ".bin":
        dat_candidate = source_root / relative.with_suffix(".dat")
        if dat_candidate.is_file():
            return dat_candidate
        scr_candidate = source_root / relative.with_suffix(".scr")
        if scr_candidate.is_file():
            return scr_candidate
    candidate = source_root / relative
    return candidate


def _infer_output_suffix(doc: dict[str, object]) -> str:
    fmt = str(doc.get("format"))
    source_path = Path(str(doc.get("source_path", "")))
    if source_path.suffix:
        return source_path.suffix
    if fmt.startswith("TE_V2_SCR"):
        return ".scr"
    return ".dat"


def main() -> int:
    args = build_parser().parse_args()
    if args.batch:
        if not args.input.is_dir():
            raise ValueError("--batch requires input to be a directory")
        if args.mode == "raw-binary":
            inputs = _discover_binary_inputs(args.input)
            count = 0
            for input_path in inputs:
                relative = input_path.relative_to(args.input)
                output_path = args.output / relative
                _compile_single(input_path, output_path, text_encoding=args.text_encoding, mode=args.mode)
                print(f"[batch-compile] {input_path} -> {output_path}")
                count += 1
            print(f"[batch-compile] processed {count} files")
            return 0
        if args.mode == "decoded-binary":
            if args.source is None or not args.source.is_dir():
                raise ValueError("--batch --mode decoded-binary requires --source to be a directory")
            inputs = _discover_binary_inputs(args.input)
            count = 0
            for input_path in inputs:
                relative = input_path.relative_to(args.input)
                source_path = _resolve_decoded_binary_source(args.source, relative)
                if not source_path.is_file():
                    raise ValueError(f"Missing source carrier for {relative}: {source_path}")
                output_path = args.output / relative.with_suffix(source_path.suffix)
                _compile_decoded_binary(input_path, output_path, source_path, text_encoding=args.text_encoding)
                print(f"[batch-compile] {input_path} -> {output_path}")
                count += 1
            print(f"[batch-compile] processed {count} files")
            return 0
        inputs = _discover_json_inputs(args.input)
        count = 0
        for input_path in inputs:
            try:
                doc = json.loads(input_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            fmt = str(doc.get("format"))
            if args.mode == "decoded" and not fmt.startswith("TE_V2_"):
                continue
            if args.mode == "raw" and fmt not in {"TE_V2_BTTEXT_OUTER", "TE_V2_SCR_OUTER"}:
                continue
            relative = input_path.relative_to(args.input)
            output_path = args.output / relative.with_suffix(_infer_output_suffix(doc))
            _compile_single(input_path, output_path, text_encoding=args.text_encoding, mode=args.mode)
            print(f"[batch-compile] {input_path} -> {output_path}")
            count += 1
        print(f"[batch-compile] processed {count} files")
    else:
        if args.mode == "decoded-binary":
            if args.source is None:
                raise ValueError("--mode decoded-binary requires --source")
            _compile_decoded_binary(args.input, args.output, args.source, text_encoding=args.text_encoding)
        else:
            _compile_single(args.input, args.output, text_encoding=args.text_encoding, mode=args.mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
