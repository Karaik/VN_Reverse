from __future__ import annotations

from pathlib import Path

from script.nbda.decompile import parse_adb, parse_adb_ir, validate_magic
from script.adb_decompile_app import build_parser, iter_adb_files, resolve_output, serialize_doc


def main() -> int:
    parser = build_parser(
        description="Export NBDA IR as ADBSRC.",
        default_mode="ir",
        default_output_format="adbsrc",
    )
    args = parser.parse_args()

    if args.output_format == "adbsrc" and args.mode != "ir":
        raise ValueError("ADBSRC output only supports ir mode.")

    input_path = Path(args.input)
    adb_files = iter_adb_files(input_path)
    pairs = resolve_output(input_path, args.output, adb_files, args.output_format)

    total_entries = 0
    editable_entries = 0
    for adb_file, output_path in pairs:
        data = adb_file.read_bytes()
        doc = parse_adb(data) if args.mode == "raw" else parse_adb_ir(data)
        validate_magic(doc)
        output_text = serialize_doc(doc, args.output_format)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
        if args.mode == "ir":
            total_entries += int(doc.get("entry_count", 0))
            editable_entries += int(doc.get("editable_entry_count", 0))
        if args.verbose:
            print(f"[ok] {adb_file} -> {output_path}")

    print(f"[done] converted {len(pairs)} file(s) to {args.output_format} (mode={args.mode}).")
    if args.mode == "ir":
        print(f"[stats] editable entries: {editable_entries}/{total_entries}")
    return 0
