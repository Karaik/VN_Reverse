from __future__ import annotations

import re
from pathlib import Path

from archive.csaf_raw import hash_archive_relative_name, qualify_output_name


_PATH_TOKEN_RE = re.compile(
    r"(?i)(?:[A-Za-z0-9_]+\\)+[A-Za-z0-9_./-]+\.(?:adb|adv|csv|png|ogg|wav|anm)"
)
_C_WIDE_STRING_RE = re.compile(r'L"([^"\r\n]+)"')
_FILENAME_TOKEN_RE = re.compile(r"(?i)\b[A-Za-z0-9_./-]+\.(?:adb|adv|csv|png|ogg|wav|anm)\b")


def _classify_path_evidence(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    rel = path.as_posix()
    if suffix == ".c":
        return "运行时路径", rel
    if suffix == ".csv":
        return "系统表", rel
    if suffix == ".txt":
        return "外部索引", rel
    if suffix == ".adb":
        return "脚本引用", rel
    return "其他来源", rel


def _iter_decompile_path_tokens(decompile_root: Path) -> list[tuple[str, str, str]]:
    records: list[tuple[str, str, str]] = []
    if not decompile_root.is_dir():
        return records

    for source in sorted(decompile_root.glob("*.c")):
        source_rel = source.as_posix()
        text = source.read_text(encoding="utf-8", errors="ignore")
        for match in _C_WIDE_STRING_RE.finditer(text):
            token = match.group(1).replace("\\\\", "\\")
            if "\\" in token and _PATH_TOKEN_RE.fullmatch(token):
                records.append((token, "运行时路径", source_rel))
            elif _FILENAME_TOKEN_RE.fullmatch(token):
                records.append((token, "运行时路径", source_rel))
    return records


def _collect_known_dirs(tokens: set[str], archive_name: str) -> list[str]:
    dirs: set[str] = set()
    prefix = archive_name.lower() + "\\"
    for token in tokens:
        norm = token.replace("/", "\\")
        lower = norm.lower()
        if lower.startswith(prefix):
            rel = norm[len(prefix) :]
        else:
            rel = norm
        if "\\" in rel:
            parent = rel.rsplit("\\", 1)[0].strip("\\")
            if parent:
                dirs.add(parent)
    return sorted(dirs)


def _iter_candidate_relative_names(token: str, archive_name: str, known_dirs: list[str]) -> list[str]:
    norm = token.replace("/", "\\")
    lower = norm.lower()
    prefix = archive_name.lower() + "\\"
    candidates: list[str] = []

    if lower.startswith(prefix):
        candidates.append(norm[len(prefix) :])
    else:
        candidates.append(norm)

    if "\\" not in norm:
        for parent in known_dirs:
            candidates.append(parent + "\\" + norm)

    seen: set[str] = set()
    deduped: list[str] = []
    for candidate in candidates:
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _iter_hashable_relative_names(rel: str) -> list[str]:
    variants = [rel]
    if rel.lower().endswith(".adv"):
        variants.append(rel[:-1] + "b")

    seen: set[str] = set()
    deduped: list[str] = []
    for variant in variants:
        key = variant.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(variant)
    return deduped


def _iter_text_file_path_tokens(files_root: Path) -> list[tuple[str, str, str]]:
    records: list[tuple[str, str, str]] = []
    if not files_root.is_dir():
        return records

    for path in sorted(files_root.rglob("*")):
        if not path.is_file():
            continue

        try:
            data = path.read_bytes()
        except OSError:
            continue

        if not data or b"\\" not in data:
            continue

        try:
            text = data.decode("cp932", errors="ignore")
        except LookupError:
            continue

        source_kind, source_file = _classify_path_evidence(path.relative_to(files_root))
        for match in _PATH_TOKEN_RE.finditer(text):
            records.append((match.group(0), source_kind, source_file))
        for match in _FILENAME_TOKEN_RE.finditer(text):
            records.append((match.group(0), source_kind, source_file))
    return records


def _candidate_search_roots(
    title_root: Path,
    archive_name: str,
    current_out_dir: Path | None,
    extra_roots: list[Path] | None = None,
) -> list[Path]:
    roots: list[Path] = []
    if current_out_dir is not None:
        roots.append(current_out_dir / "files")
        roots.append(current_out_dir / "final")
        roots.append(current_out_dir / "_internal_pending")
        roots.append(current_out_dir / archive_name)
        roots.append(current_out_dir / "unknown" / archive_name)
        roots.append(current_out_dir / "_pending" / archive_name)

    system_root = title_root / "out" / "system_decoded"
    if archive_name.lower() != "system" and system_root.is_dir():
        roots.append(system_root / "files")
        roots.append(system_root / "final")
        roots.append(system_root / "_internal_pending")

    for base in extra_roots or []:
        roots.append(base / archive_name)
        roots.append(base / "unknown" / archive_name)
        roots.append(base / "_pending" / archive_name)
        if archive_name.lower() != "system":
            roots.append(base / "system")
            roots.append(base / "unknown" / "system")
            roots.append(base / "_pending" / "system")

    return roots


def _merge_catalog_entry(
    catalog: dict[str, dict],
    rel_hash: str,
    output_name: str,
    evidence_source: str,
    evidence_file: str,
) -> None:
    entry = catalog.setdefault(
        rel_hash,
        {
            "path": output_name,
            "evidence_sources": [],
            "evidence_files": [],
        },
    )
    if entry["path"] != output_name:
        return
    if evidence_source and evidence_source not in entry["evidence_sources"]:
        entry["evidence_sources"].append(evidence_source)
    if evidence_file and evidence_file not in entry["evidence_files"]:
        entry["evidence_files"].append(evidence_file)


def build_auto_name_catalog(
    title_root: Path,
    archive_name: str,
    *,
    current_out_dir: Path | None = None,
    seed_map: dict[str, str] | None = None,
    target_hashes: set[str] | None = None,
    extra_roots: list[Path] | None = None,
) -> dict[str, dict]:
    catalog: dict[str, dict] = {}
    for rel_hash, output_name in (seed_map or {}).items():
        catalog[rel_hash] = {
            "path": output_name,
            "evidence_sources": ["其他来源"],
            "evidence_files": [],
        }

    archive_name = archive_name.lower()
    decompile_root = title_root / "analysis" / "ida_reverse" / "export-for-ai" / "decompile"
    token_records = _iter_decompile_path_tokens(decompile_root)

    for files_root in _candidate_search_roots(title_root, archive_name, current_out_dir, extra_roots):
        token_records.extend(_iter_text_file_path_tokens(files_root))

    token_texts = {token for token, _, _ in token_records}
    known_dirs = _collect_known_dirs(token_texts, archive_name)

    for token, evidence_source, evidence_file in token_records:
        for rel in _iter_candidate_relative_names(token, archive_name, known_dirs):
            for hashable_rel in _iter_hashable_relative_names(rel):
                rel_hash = hash_archive_relative_name(hashable_rel)
                if target_hashes and rel_hash not in target_hashes:
                    continue
                output_name = qualify_output_name(hashable_rel, archive_name)
                _merge_catalog_entry(catalog, rel_hash, output_name, evidence_source, evidence_file)

    return catalog


def build_auto_name_map(
    title_root: Path,
    archive_name: str,
    *,
    current_out_dir: Path | None = None,
    seed_map: dict[str, str] | None = None,
    target_hashes: set[str] | None = None,
    extra_roots: list[Path] | None = None,
) -> dict[str, str]:
    catalog = build_auto_name_catalog(
        title_root,
        archive_name,
        current_out_dir=current_out_dir,
        seed_map=seed_map,
        target_hashes=target_hashes,
        extra_roots=extra_roots,
    )
    return {rel_hash: entry["path"] for rel_hash, entry in catalog.items()}
