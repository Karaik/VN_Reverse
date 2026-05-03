"""Binary helpers for SAISYS SSB files."""

from __future__ import annotations

import codecs
import struct
from pathlib import Path

from .constants import CODE_FILE_NAME, DATA_FILE_NAME, DEFAULT_TEXT_ENCODING, TEXT_ENCODING_ALIASES, XOR_KEY


def xor_aa(data: bytes) -> bytes:
    return bytes(byte ^ XOR_KEY for byte in data)


def normalize_text_encoding(text_encoding: str) -> str:
    key = str(text_encoding).strip().lower()
    if not key:
        key = DEFAULT_TEXT_ENCODING
    normalized = TEXT_ENCODING_ALIASES.get(key, key)
    try:
        codecs.lookup(normalized)
    except LookupError as exc:
        raise ValueError(f"Unsupported text encoding: {text_encoding}") from exc
    return normalized


def load_script_pair(script_dir: Path) -> tuple[bytes, bytes]:
    code_path = script_dir / CODE_FILE_NAME
    data_path = script_dir / DATA_FILE_NAME
    return code_path.read_bytes(), data_path.read_bytes()


def load_code_words(code_bytes: bytes) -> list[int]:
    if len(code_bytes) % 4 != 0:
        raise ValueError("CODE.SSB size is not divisible by 4")
    return list(struct.unpack(f"<{len(code_bytes) // 4}I", code_bytes))


def pack_code_words(words: list[int]) -> bytes:
    normalized = [word & 0xFFFFFFFF for word in words]
    return struct.pack(f"<{len(normalized)}I", *normalized)


def to_signed_u32(value: int) -> int:
    return value if value < 0x80000000 else value - 0x100000000


def write_script_pair(output_dir: Path, code_bytes: bytes, data_bytes: bytes) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / CODE_FILE_NAME).write_bytes(code_bytes)
    (output_dir / DATA_FILE_NAME).write_bytes(data_bytes)
