from __future__ import annotations

import argparse
from pathlib import Path

from solution.common.hxp import HxpArchive


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Masquerade HXP unpack tool")
    parser.add_argument("archive", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--dump-unpacked", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    archive = HxpArchive.load(args.archive)
    archive.unpack(args.out_dir, args.dump_unpacked)
    print(f"[ok] unpacked: {args.archive.name}")
    print(f"[ok] entries: {len(archive.entries)}")
    print(f"[ok] manifest: {args.out_dir / 'manifest.json'}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
