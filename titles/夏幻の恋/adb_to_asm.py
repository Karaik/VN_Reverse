#!/usr/bin/env python3
from __future__ import annotations

import sys

from adb_decompile import main


if __name__ == "__main__":
    argv = list(sys.argv[1:])
    if "--output-format" not in argv:
        argv.extend(["--output-format", "adbsrc"])
    if "--mode" not in argv:
        argv.extend(["--mode", "ir"])
    sys.argv = [sys.argv[0], *argv]
    raise SystemExit(main())
