from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


TITLE_ROOT = Path(__file__).resolve().parents[1]
LEGACY_ROOT = TITLE_ROOT / "tmp" / "legacy_20260326_snapshot"


def load_legacy_module(entry_name: str):
    entry_path = LEGACY_ROOT / entry_name
    if not entry_path.is_file():
        raise FileNotFoundError(f"Legacy entry not found: {entry_path}")

    spec = importlib.util.spec_from_file_location(f"legacy_{entry_path.stem}", entry_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load legacy entry: {entry_path}")

    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(LEGACY_ROOT))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def run_legacy_entry(entry_name: str) -> int:
    module = load_legacy_module(entry_name)
    main = getattr(module, "main", None)
    if main is None:
        raise RuntimeError(f"Legacy entry does not expose main(): {entry_name}")

    result = main()
    return 0 if result is None else int(result)
