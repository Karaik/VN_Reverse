#!/usr/bin/env python3
from __future__ import annotations

from adb_decompile import main
from nbda.decompile import parse_adb, parse_adb_editable, parse_adb_ir, validate_magic


if __name__ == "__main__":
    raise SystemExit(main())
