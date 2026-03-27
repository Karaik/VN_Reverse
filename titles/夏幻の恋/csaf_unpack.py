#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from archive.resource_recovery import recover_resource_tree, unpack_raw_internal


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recover original resource tree from CSAF archive.")
    parser.add_argument("archive", help="Input archive file, e.g. game/adv.")
    parser.add_argument("out_dir", help="Output directory for recovered resource tree.")
    parser.add_argument(
        "--_internal-layer",
        choices=["raw", "decoded"],
        default="decoded",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--_internal-seed-text",
        default="\u590f\u5e7b\u306e\u604b",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--_internal-name-list",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--_internal-name-dir",
        help=argparse.SUPPRESS,
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    archive_path = Path(args.archive)
    out_dir = Path(args.out_dir)
    title_root = Path(__file__).resolve().parent
    name_list = Path(args._internal_name_list) if args._internal_name_list else None
    name_dir = Path(args._internal_name_dir) if args._internal_name_dir else None

    if args._internal_layer == "decoded":
        manifest_path = recover_resource_tree(
            title_root,
            archive_path,
            out_dir,
            name_list=name_list,
            name_dir=name_dir,
            seed_text=args._internal_seed_text,
        )
    else:
        manifest_path = unpack_raw_internal(
            title_root,
            archive_path,
            out_dir,
            name_list=name_list,
            name_dir=name_dir,
        )
    print(manifest_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
