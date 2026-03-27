from __future__ import annotations

import base64
import hashlib
import json
import re
import struct
from pathlib import Path


HEADER_STRUCT = struct.Struct("<4sIII16s")
ENTRY_STRUCT = struct.Struct("<16sII")
BLOCK_SIZE = 0x1000
_SAFE_LABEL_RE = re.compile(r"[^A-Za-z0-9._-]+")
PENDING_NAME_DIR = "待补原名"
PENDING_PATH_AND_NAME_DIR = "待补原目录与原名"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _from_b64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def _hash_name(name: str) -> str:
    normalized = name.replace("/", "\\").lower()
    return hashlib.md5(normalized.encode("utf-16le")).hexdigest()


def _guess_ext(data: bytes) -> str:
    if data.startswith(b"NBDA"):
        return ".adb"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WAVE":
        return ".wav"
    if data.startswith(b"OggS"):
        return ".ogg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    return ".bin"


def _normalize_rel_name(name: str) -> str:
    raw = name.replace("\\", "/").lstrip("/").strip()
    parts = [p for p in raw.split("/") if p]
    if any(p == ".." for p in parts):
        raise ValueError(f"Invalid path: {name}")
    return "/".join(parts)


def guess_payload_ext(data: bytes) -> str:
    return _guess_ext(data)


def normalize_rel_name(name: str) -> str:
    return _normalize_rel_name(name)


def hash_archive_relative_name(name: str) -> str:
    return _hash_name(_normalize_rel_name(name).replace("/", "\\"))


def qualify_output_name(name: str, archive_name: str | None = None) -> str:
    normalized = _normalize_rel_name(name).replace("/", "\\")
    if normalized.lower().endswith(".adv"):
        normalized = normalized[:-1] + "b"
    if archive_name and not normalized.lower().startswith(archive_name.lower() + "\\"):
        normalized = archive_name + "\\" + normalized
    return normalized


def _safe_label(text: str) -> str:
    text = text.strip().replace("\\", "_").replace("/", "_")
    text = _SAFE_LABEL_RE.sub("_", text)
    text = text.strip("._-")
    return text[:80] if text else ""


def infer_pending_output_name(*, archive_name: str, entry_index: int, suffix: str, data: bytes | None) -> tuple[Path, str]:
    suffix = suffix.lower()
    data = data or b""
    archive_display = archive_name
    archive_name = archive_name.lower()

    def infer_system_dir(text: str) -> str | None:
        low = text.lower()
        if "flashback\\" in low or "fb_" in low:
            return "flashback"
        if "album\\" in low or "album_" in low or "cg_" in low:
            return "album"
        if "config\\" in low or "conf_" in low:
            return "config"
        if "save\\" in low or "sl_" in low:
            return "save"
        if "title\\" in low or "title_" in low or "ttl_" in low or "btn2.png" in low:
            return "title"
        if "log\\" in low or "log_" in low:
            return "log"
        if (
            "window\\" in low
            or "menu_" in low
            or "message" in low
            or "keywait" in low
            or "sys_btn" in low
            or "select" in low
            or "parts.png" in low
        ):
            return "window"
        return None

    def archive_root(*parts: str) -> Path:
        return Path(archive_display, *parts)

    def system_root(dir_hint: str | None, *, state: str) -> Path:
        if dir_hint:
            return Path("system") / dir_hint / state
        return Path("system") / "_unknown_dir" / state

    if suffix == ".adb":
        if archive_name == "system":
            return Path("system") / "scripts" / PENDING_NAME_DIR, f"script_{entry_index:05d}.adb"
        if archive_name == "adv":
            return Path("adv") / PENDING_NAME_DIR, f"script_{entry_index:05d}.adb"
        return archive_root(PENDING_NAME_DIR, "scripts"), f"script_{entry_index:05d}.adb"

    if suffix == ".png":
        if archive_name in {"bg", "ch", "ev"}:
            return archive_root(PENDING_NAME_DIR, "images"), f"image_{entry_index:05d}.png"
        if archive_name == "system":
            return system_root(None, state=PENDING_PATH_AND_NAME_DIR) / "images", f"image_{entry_index:05d}.png"
        return archive_root(PENDING_NAME_DIR, "images"), f"image_{entry_index:05d}.png"

    if suffix in {".ogg", ".wav"}:
        return archive_root(PENDING_NAME_DIR, "audio"), f"audio_{entry_index:05d}{suffix}"

    if suffix == ".csv":
        if archive_name == "system":
            return system_root(None, state=PENDING_PATH_AND_NAME_DIR) / "tables", f"table_{entry_index:05d}.csv"
        return archive_root(PENDING_NAME_DIR, "tables"), f"table_{entry_index:05d}.csv"

    if suffix == ".anm":
        if archive_name == "system":
            return Path("system") / "window" / PENDING_NAME_DIR / "animations", f"anim_{entry_index:05d}.anm"
        return archive_root(PENDING_NAME_DIR, "animations"), f"anim_{entry_index:05d}.anm"

    if archive_name == "voice":
        return archive_root(PENDING_NAME_DIR, "clips"), f"clip_{entry_index:05d}.bin"
    if archive_name in {"bgm", "song", "se"}:
        return archive_root(PENDING_NAME_DIR, "audio"), f"track_{entry_index:05d}.bin"
    if archive_name in {"bg", "ch", "ev"}:
        return archive_root(PENDING_NAME_DIR, "images"), f"image_{entry_index:05d}.bin"

    text = data.decode("cp932", errors="ignore") if data else ""
    if text:
        system_dir = infer_system_dir(text) if archive_name == "system" else None
        if "adv\\SNR.adv" in text and "dat01,adv" in text:
            return Path(), "setting.csv"
        if "album\\" in text and "ev\\" in text:
            return Path("album"), "list.csv"
        if "FRAME" in text and "SPRITE" in text and 'FILE "' in text:
            match = re.search(r'FILE "([^"]+)"', text)
            stem = _safe_label(Path(match.group(1)).stem) if match else ""
            base = f"{stem}_anim" if stem else f"anim_{entry_index:05d}"
            if system_dir:
                return Path("system") / system_dir / PENDING_NAME_DIR / "layouts", base + ".txt"
            return archive_root(PENDING_NAME_DIR, "layouts"), base + ".txt"
        if "CONTROL" in text and ('BG "' in text or 'IMAGE "' in text):
            bg_match = re.search(r'BG "([^"]+)"', text)
            img_match = re.search(r'IMAGE "([^"]+)"', text)
            stem = ""
            if bg_match:
                stem = _safe_label(Path(bg_match.group(1)).stem)
            elif img_match:
                stem = _safe_label(Path(img_match.group(1)).stem)
            base = f"{stem}_layout" if stem else f"layout_{entry_index:05d}"
            if system_dir:
                return Path("system") / system_dir / PENDING_NAME_DIR / "layouts", base + ".txt"
            return archive_root(PENDING_NAME_DIR, "layouts"), base + ".txt"
        if text.count(",") >= 5 and text.count("\n") >= 2:
            if system_dir:
                return Path("system") / system_dir / PENDING_NAME_DIR / "tables", f"table_{entry_index:05d}.csv"
            return archive_root(PENDING_NAME_DIR, "tables"), f"table_{entry_index:05d}.csv"

    if archive_name == "system":
        return system_root(None, state=PENDING_PATH_AND_NAME_DIR) / "payloads", f"payload_{entry_index:05d}.bin"
    return archive_root(PENDING_NAME_DIR, "payloads"), f"payload_{entry_index:05d}.bin"


def infer_output_class(rel_path: Path, resolved_name: bool) -> str:
    if PENDING_PATH_AND_NAME_DIR in rel_path.parts:
        return "pending_unresolved_name_and_dir"
    if PENDING_NAME_DIR in rel_path.parts:
        return "pending_unresolved_name"
    if resolved_name:
        return "final"
    return "partial"


def infer_resource_kind(rel_path: Path) -> str:
    suffix = rel_path.suffix.lower()
    if suffix == ".adb":
        return "script"
    if suffix == ".png":
        return "image"
    if suffix in {".ogg", ".wav"}:
        return "audio"
    if suffix == ".csv":
        return "table"
    if suffix in {".anm", ".txt"}:
        return "layout"
    return "payload"


def build_output_relpath(
    archive_name: str,
    *,
    entry_index: int,
    hash_hex: str,
    data: bytes | None,
    suffix: str,
    original_path: str | None,
) -> Path:
    if original_path:
        return Path(_normalize_rel_name(original_path))

    pending_dir, pending_name = infer_pending_output_name(
        archive_name=archive_name,
        entry_index=entry_index,
        suffix=suffix,
        data=data,
    )
    return pending_dir / pending_name


def load_name_map(name_list: Path | None, name_dir: Path | None, archive_name: str | None = None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if name_list:
        for line in name_list.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            output_name = qualify_output_name(line, archive_name)
            rel = (
                output_name.split("\\", 1)[1]
                if archive_name and output_name.lower().startswith(archive_name.lower() + "\\")
                else output_name
            )
            mapping[hash_archive_relative_name(rel)] = output_name
    if name_dir:
        base = name_dir.resolve()
        for file_path in sorted(base.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(base).as_posix().replace("/", "\\")
            output_name = qualify_output_name(rel, archive_name)
            rel_name = (
                output_name.split("\\", 1)[1]
                if archive_name and output_name.lower().startswith(archive_name.lower() + "\\")
                else output_name
            )
            mapping[hash_archive_relative_name(rel_name)] = output_name
    return mapping


def read_archive_hashes(archive_path: Path) -> set[str]:
    data = archive_path.read_bytes()
    if len(data) < HEADER_STRUCT.size:
        raise ValueError("File is smaller than CSAF header size.")

    magic, version_flags, file_count, extra_size, checksum = HEADER_STRUCT.unpack_from(data, 0)
    if magic != b"CSAF":
        raise ValueError(f"Magic is not CSAF: {magic!r}")

    entry_table_off = HEADER_STRUCT.size
    hashes: set[str] = set()
    for i in range(file_count):
        off = entry_table_off + i * ENTRY_STRUCT.size
        hash_bytes, start_block, size = ENTRY_STRUCT.unpack_from(data, off)
        hashes.add(hash_bytes.hex())
    return hashes


def unpack_raw_archive(archive_path: Path, out_dir: Path, name_map: dict[str, str]) -> Path:
    archive_name = archive_path.name
    data = archive_path.read_bytes()
    if len(data) < HEADER_STRUCT.size:
        raise ValueError("File is smaller than CSAF header size.")

    magic, version_flags, file_count, extra_size, checksum = HEADER_STRUCT.unpack_from(data, 0)
    if magic != b"CSAF":
        raise ValueError(f"Magic is not CSAF: {magic!r}")

    table_size = ((24 * file_count + 31) & 0xFFFFF000) + 4064
    entry_table_off = HEADER_STRUCT.size
    entry_table_end = entry_table_off + file_count * ENTRY_STRUCT.size
    table_region_end = entry_table_off + table_size
    extra_end = table_region_end + extra_size
    if extra_end > len(data):
        raise ValueError("Table/extra region declared in header exceeds file length.")

    entries = []
    for i in range(file_count):
        off = entry_table_off + i * ENTRY_STRUCT.size
        hash_bytes, start_block, size = ENTRY_STRUCT.unpack_from(data, off)
        entries.append(
            {
                "index": i,
                "hash_hex": hash_bytes.hex(),
                "start_block": start_block,
                "size": size,
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)

    total_blocks = len(data) // BLOCK_SIZE
    sorted_starts = sorted({e["start_block"] for e in entries})
    next_start_map: dict[int, int] = {}
    for i, start in enumerate(sorted_starts):
        next_start_map[start] = sorted_starts[i + 1] if i + 1 < len(sorted_starts) else total_blocks

    for entry in entries:
        start = entry["start_block"]
        end = next_start_map[start]
        allocated = (end - start) * BLOCK_SIZE
        blob_off = start * BLOCK_SIZE
        blob = data[blob_off : blob_off + allocated]
        file_bytes = blob[: entry["size"]]
        padding = blob[entry["size"] :]

        known_name = name_map.get(entry["hash_hex"])
        suffix = _guess_ext(file_bytes)
        rel_path = build_output_relpath(
            archive_name,
            entry_index=entry["index"],
            hash_hex=entry["hash_hex"],
            data=file_bytes,
            suffix=suffix,
            original_path=known_name,
        )
        abs_path = out_dir / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(file_bytes)

        entry["file"] = rel_path.as_posix()
        entry["original_path"] = known_name
        entry["resolved_name"] = bool(known_name)
        entry["output_class"] = infer_output_class(rel_path, bool(known_name))
        entry["resource_kind"] = infer_resource_kind(rel_path)
        entry["evidence_sources"] = ["包内目录项"]
        entry["evidence_files"] = []
        entry["allocated_blocks"] = end - start
        entry["padding_base64"] = _b64(padding)

    manifest = {
        "format": "CSAF",
        "semantic_layer": "raw",
        "archive_name": archive_path.name,
        "magic": "CSAF",
        "version_flags": version_flags,
        "version": version_flags & 0x7FFFFFFF,
        "encrypted": bool(version_flags & 0x80000000),
        "file_count": file_count,
        "extra_size": extra_size,
        "checksum_hex": checksum.hex(),
        "table_size": table_size,
        "table_padding_base64": _b64(data[entry_table_end:table_region_end]),
        "extra_region_base64": _b64(data[table_region_end:extra_end]),
        "entries": entries,
    }

    manifest_path = out_dir / "raw_index.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def rewrite_output_tree(manifest_path: Path, archive_name: str, name_catalog: dict[str, dict]) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base_dir = manifest_path.parent
    changed = False

    for entry in manifest.get("entries", []):
        current_rel = Path(entry["file"])
        current_abs = base_dir / current_rel
        name_info = name_catalog.get(entry["hash_hex"], {})
        known_name = name_info.get("path")
        suffix = current_rel.suffix or ".bin"
        target_rel = build_output_relpath(
            archive_name,
            entry_index=int(entry["index"]),
            hash_hex=entry["hash_hex"],
            data=current_abs.read_bytes(),
            suffix=suffix,
            original_path=known_name,
        )
        target_abs = base_dir / target_rel
        if current_abs != target_abs:
            target_abs.parent.mkdir(parents=True, exist_ok=True)
            if target_abs.exists():
                raise ValueError(f"Recovered path collision: {target_abs}")
            current_abs.rename(target_abs)
            entry["file"] = target_rel.as_posix()
            changed = True
        entry["original_path"] = known_name
        entry["resolved_name"] = bool(known_name)
        entry["output_class"] = infer_output_class(target_rel, bool(known_name))
        entry["resource_kind"] = infer_resource_kind(target_rel)
        evidence_sources = ["包内目录项"]
        for source in name_info.get("evidence_sources", []):
            if source not in evidence_sources:
                evidence_sources.append(source)
        entry["evidence_sources"] = evidence_sources
        entry["evidence_files"] = list(name_info.get("evidence_files", []))

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def pack_raw_archive(manifest_path: Path, output_path: Path, update_checksum: bool) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    semantic_layer = manifest.get("semantic_layer", "raw")
    if semantic_layer != "raw":
        raise ValueError(f"Unsupported manifest semantic_layer for raw pack: {semantic_layer!r}")

    entries = list(manifest["entries"])
    file_count = len(entries)
    version_flags = int(manifest["version_flags"])

    table_size = ((24 * file_count + 31) & 0xFFFFF000) + 4064
    table_padding = _from_b64(manifest.get("table_padding_base64", ""))
    expected_padding_len = table_size - file_count * ENTRY_STRUCT.size
    if len(table_padding) != expected_padding_len:
        raise ValueError("manifest.table_padding_base64 length does not match file_count.")

    extra_region = _from_b64(manifest.get("extra_region_base64", ""))
    extra_size = len(extra_region)
    metadata_size = HEADER_STRUCT.size + table_size + extra_size
    if metadata_size % BLOCK_SIZE != 0:
        raise ValueError("Metadata region is not aligned to 4096 bytes.")

    table_blob = bytearray(file_count * ENTRY_STRUCT.size)
    file_blobs = []
    max_end_block = metadata_size // BLOCK_SIZE
    base_dir = manifest_path.parent

    for i, entry in enumerate(entries):
        hash_bytes = bytes.fromhex(entry["hash_hex"])
        start_block = int(entry["start_block"])
        allocated_blocks = int(entry["allocated_blocks"])
        file_rel = Path(entry["file"])
        file_data = (base_dir / file_rel).read_bytes()
        padding = _from_b64(entry.get("padding_base64", ""))
        allocated_bytes = allocated_blocks * BLOCK_SIZE
        payload = file_data + padding
        if len(payload) > allocated_bytes:
            raise ValueError(f"File exceeds allocated blocks: {file_rel.as_posix()}")
        if len(payload) < allocated_bytes:
            payload += b"\x00" * (allocated_bytes - len(payload))

        ENTRY_STRUCT.pack_into(table_blob, i * ENTRY_STRUCT.size, hash_bytes, start_block, len(file_data))
        file_blobs.append((start_block, payload))
        end_block = start_block + allocated_blocks
        if end_block > max_end_block:
            max_end_block = end_block

    archive = bytearray(max_end_block * BLOCK_SIZE)
    table_off = HEADER_STRUCT.size
    table_end = table_off + len(table_blob)
    table_region_end = table_off + table_size
    extra_off = table_region_end
    extra_end = extra_off + extra_size

    archive[table_off:table_end] = table_blob
    archive[table_end:table_region_end] = table_padding
    archive[extra_off:extra_end] = extra_region

    for start_block, payload in file_blobs:
        data_off = start_block * BLOCK_SIZE
        archive[data_off : data_off + len(payload)] = payload

    checksum = bytes.fromhex(manifest["checksum_hex"])
    if update_checksum:
        checksum = hashlib.md5(archive[table_off:extra_end]).digest()

    header = HEADER_STRUCT.pack(b"CSAF", version_flags, file_count, extra_size, checksum)
    archive[: HEADER_STRUCT.size] = header
    output_path.write_bytes(archive)
