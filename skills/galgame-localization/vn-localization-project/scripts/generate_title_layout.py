from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_DIRS = [
    Path('game'),
    Path('game_script'),
    Path('game_script') / 'translated_script',
    Path('game_script') / 'translated_script' / 'scn',
    Path('solution'),
    Path('solution') / 'decrypt',
    Path('solution') / 'unpack',
    Path('solution') / 'build',
    Path('solution') / 'patch',
    Path('solution') / 'patch' / 'base',
    Path('solution') / 'patch' / 'base' / 'chs_patch',
    Path('solution') / 'runtime',
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate the standard VN localization title layout.')
    parser.add_argument('title_root', help='Target title root directory to create or extend.')
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def main() -> int:
    args = parse_args()
    root = Path(args.title_root).resolve()
    ensure_dir(root)

    for rel_path in DEFAULT_DIRS:
        ensure_dir(root / rel_path)

    print(root)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
