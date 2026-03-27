#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from archive.csaf_decoded import TITLE_SEED_TEXT
from archive.csaf_raw import pack_raw_archive
from archive.resource_tree_pack import pack_resource_tree_archive


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repack CSAF archive from raw manifest or recovered resource tree.")
    parser.add_argument("arg1", help="Raw manifest.json, or source archive when packing from resource tree.")
    parser.add_argument("arg2", help="Output archive path, or recovered resource tree root when packing from resource tree.")
    parser.add_argument("arg3", nargs="?", help="Output archive path when packing from resource tree.")
    parser.add_argument("--update-checksum", action="store_true", help="Recalculate header MD5 in raw manifest mode.")
    parser.add_argument("--seed-text", default=TITLE_SEED_TEXT, help=argparse.SUPPRESS)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    arg1 = Path(args.arg1)
    arg2 = Path(args.arg2)

    if arg1.suffix.lower() == ".json":
        if args.arg3 is not None:
            raise ValueError("Raw manifest mode only accepts two positional arguments: manifest and output.")
        pack_raw_archive(arg1, arg2, args.update_checksum)
        return 0

    if args.arg3 is None:
        raise ValueError("Resource-tree pack mode requires: source_archive resource_tree_root output_archive")

    source_archive = arg1
    resource_tree_root = arg2
    output_archive = Path(args.arg3)
    pack_resource_tree_archive(source_archive, resource_tree_root, output_archive, seed_text=args.seed_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
