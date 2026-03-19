from __future__ import annotations

import argparse
from pathlib import Path

from solution.common.hxp import build_him4, build_him5, load_manifest, load_entry_for_pack


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Masquerade HXP repack tool")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("out_file", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--rebuild-uncompressed", action="store_true")
    mode.add_argument("--rebuild-compressed", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    manifest = load_manifest(args.manifest)
    root = args.manifest.parent
    entries = [
        load_entry_for_pack(
            root,
            entry,
            args.rebuild_uncompressed,
            args.rebuild_compressed,
        )
        for entry in manifest["entries"]
    ]
    if manifest["magic"] == "Him4":
        data = build_him4(entries)
    else:
        data = build_him5(entries, manifest["bucket_count"])
    args.out_file.write_bytes(data)
    print(f"[ok] packed: {args.out_file}")
    print(f"[ok] size: {len(data)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
