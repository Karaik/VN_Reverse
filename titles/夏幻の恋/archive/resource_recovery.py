from __future__ import annotations

from pathlib import Path

from archive.csaf_decoded import unpack_decoded_archive
from archive.csaf_raw import load_name_map, read_archive_hashes, rewrite_output_tree, unpack_raw_archive
from archive.name_recovery import build_auto_name_catalog


def recover_resource_tree(
    title_root: Path,
    archive_path: Path,
    out_dir: Path,
    *,
    name_list: Path | None = None,
    name_dir: Path | None = None,
    seed_text: str = "夏幻の恋",
    extra_search_roots: list[Path] | None = None,
) -> Path:
    archive_name = archive_path.name
    target_hashes = read_archive_hashes(archive_path)
    manual_name_map = load_name_map(name_list, name_dir, archive_name)
    initial_name_catalog = build_auto_name_catalog(
        title_root,
        archive_name,
        seed_map=manual_name_map,
        target_hashes=target_hashes,
        extra_roots=extra_search_roots,
    )
    initial_name_map = {rel_hash: entry["path"] for rel_hash, entry in initial_name_catalog.items()}

    manifest_path = unpack_decoded_archive(
        archive_path,
        out_dir,
        initial_name_map,
        name_catalog=initial_name_catalog,
        seed_text=seed_text,
    )

    refined_name_catalog = build_auto_name_catalog(
        title_root,
        archive_name,
        current_out_dir=out_dir,
        seed_map=initial_name_map,
        target_hashes=target_hashes,
        extra_roots=extra_search_roots,
    )
    return rewrite_output_tree(manifest_path, archive_name, refined_name_catalog)


def unpack_raw_internal(
    title_root: Path,
    archive_path: Path,
    out_dir: Path,
    *,
    name_list: Path | None = None,
    name_dir: Path | None = None,
) -> Path:
    archive_name = archive_path.name
    target_hashes = read_archive_hashes(archive_path)
    manual_name_map = load_name_map(name_list, name_dir, archive_name)
    initial_name_catalog = build_auto_name_catalog(
        title_root,
        archive_name,
        seed_map=manual_name_map,
        target_hashes=target_hashes,
    )
    initial_name_map = {rel_hash: entry["path"] for rel_hash, entry in initial_name_catalog.items()}
    manifest_path = unpack_raw_archive(archive_path, out_dir, initial_name_map)
    refined_name_catalog = build_auto_name_catalog(
        title_root,
        archive_name,
        current_out_dir=out_dir,
        seed_map=initial_name_map,
        target_hashes=target_hashes,
    )
    return rewrite_output_tree(manifest_path, archive_name, refined_name_catalog)
