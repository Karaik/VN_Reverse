from __future__ import annotations

import unicodedata


def to_hex(data: bytes) -> str:
    return data.hex()


def from_hex(text: str) -> bytes:
    return bytes.fromhex(text)


def u16_words(data: bytes) -> list[int]:
    if len(data) % 2 != 0:
        raise ValueError("Expected even byte count for u16 words.")
    if not data:
        return []
    return list(int.from_bytes(data[i : i + 2], "little") for i in range(0, len(data), 2))


def text_quality(text: str) -> float:
    if not text:
        return 1.0
    good = 0
    for ch in text:
        if ch in "\r\n\t":
            good += 1
            continue
        if not unicodedata.category(ch).startswith("C"):
            good += 1
    return good / len(text)
