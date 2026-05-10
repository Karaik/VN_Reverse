from __future__ import annotations

import argparse
import json
from pathlib import Path

from script.tev2_bttext import parse_bttext_text, probe_bttext, write_text_doc
from script.tev2_scr import parse_scr_text, probe_scr, write_probe as write_scr_probe, write_text_doc as write_scr_text_doc
from script.tev2_text_tables import decrypt_words, detect_table_mode, parse_table, write_doc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Decompile TE_V2 text carrier.")
    parser.add_argument("input", type=Path, help="Input text table file.")
    parser.add_argument("output", type=Path, help="Output JSON file.")
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Batch mode. Scan input recursively and mirror decompile outputs under output.",
    )
    parser.add_argument(
        "--mode",
        choices=("decoded", "raw", "decoded-binary", "raw-binary"),
        default="decoded",
        help="decoded: editable decoded text JSON. raw: structural outer-container JSON. decoded-binary: export decoded/decrypted binary payload. raw-binary: export original bytes unchanged.",
    )
    parser.add_argument(
        "--text-encoding",
        default="cp932",
        help="Encoding used to decode text table entries. Supports aliases: win-31j/sjis/cp932.",
    )
    return parser


def _write_single(input_path: Path, output_path: Path, *, text_encoding: str, mode: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = input_path.read_bytes()
    head = data[:4]
    if mode == "raw-binary":
        output_path.write_bytes(data)
        return
    if mode == "raw":
        if head == b"TSCR":
            try:
                doc = probe_bttext(input_path, text_encoding=text_encoding)
                payload = {
                    "format": doc.format,
                    "source_path": doc.source_path,
                    "raw_header": doc.raw_header,
                    "tuta_header": doc.tuta_header,
                    "txt0_header": doc.txt0_header,
                    "txt0_strings": doc.txt0_strings,
                    "decoded_root_preview_hex": doc.decoded_root_preview_hex,
                    "decoded_root_sha256": doc.decoded_root_sha256,
                    "known_container_magics": doc.known_container_magics,
                    "container_summary": doc.container_summary,
                }
                output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                return
            except ValueError:
                return
        if head == b"SCR ":
            write_scr_probe(input_path, output_path)
            return
    if mode == "decoded-binary":
        if head == b"TSCR":
            try:
                doc = probe_bttext(input_path, text_encoding=text_encoding)
                output_path.write_bytes(doc.decoded_root_bytes)
                return
            except ValueError:
                return
        if head == b"SCR ":
            doc = probe_scr(input_path)
            output_path.write_bytes(doc.decoded_payload_bytes)
            return
        mode_u32, seed_u32 = detect_table_mode(data)
        output_path.write_bytes(decrypt_words(data, mode_u32, seed_u32))
        return
    if head == b"TSCR":
        try:
            doc = parse_bttext_text(input_path, text_encoding=text_encoding)
            write_text_doc(output_path, doc)
        except ValueError:
            doc = parse_table(input_path, text_encoding=text_encoding)
            write_doc(output_path, doc)
    elif head == b"SCR ":
        doc = parse_scr_text(input_path, text_encoding=text_encoding)
        write_scr_text_doc(output_path, doc)
    else:
        doc = parse_table(input_path, text_encoding=text_encoding)
        write_doc(output_path, doc)


def _discover_inputs(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    matches: list[Path] = []
    for pattern in ("*.dat", "*.scr"):
        matches.extend(sorted(root.rglob(pattern)))
    return [path for path in matches if path.is_file()]


def _infer_output_suffix(input_path: Path, mode: str) -> str:
    if mode == "decoded-binary":
        return ".bin"
    if mode == "raw-binary":
        return input_path.suffix
    return ".json"


def main() -> int:
    args = build_parser().parse_args()
    if args.batch:
        if not args.input.is_dir():
            raise ValueError("--batch requires input to be a directory")
        inputs = _discover_inputs(args.input)
        for input_path in inputs:
            relative = input_path.relative_to(args.input)
            output_path = args.output / relative.with_suffix(_infer_output_suffix(input_path, args.mode))
            _write_single(input_path, output_path, text_encoding=args.text_encoding, mode=args.mode)
            print(f"[batch-decompile] {input_path} -> {output_path}")
        print(f"[batch-decompile] processed {len(inputs)} files")
    else:
        _write_single(args.input, args.output, text_encoding=args.text_encoding, mode=args.mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
