"""Remove only inventoried outputs owned by a title's build pipeline."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass, field
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
from typing import Callable, Iterable, Iterator


MARKER_NAME = ".vn-build-output.json"
OUTPUT_NAME = re.compile(r"(?:package|release|build|validation|verify|smoke)(?:[-_][A-Za-z0-9][A-Za-z0-9._-]{0,119})?\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
PROTECTED = {"game", "game_script", "solution", "patch", "runtime", "save", "saves", "savedata", "savedata_cn", "cache", "unpack", "input", "inputs", "translations", "resources", ".git"}
KINDS = {"package", "release", "build", "validation"}


class CleanupError(ValueError):
    """The cleanup request or one of its paths is unsafe."""


@dataclass(frozen=True)
class PreservedOutput:
    path: Path
    reason: str


@dataclass(frozen=True)
class CleanupPlan:
    project_root: Path
    output_roots: tuple[Path, ...]
    builder_id: str
    current_run_id: str | None
    exclude_paths: tuple[Path, ...]
    remove: tuple[Path, ...]
    preserve: tuple[PreservedOutput, ...]
    _markers: tuple[str, ...] = field(repr=False)


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise CleanupError(f"Invalid {label}: {value!r}")
    return value


def _no_reparse(path: Path) -> os.stat_result:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        raise CleanupError(f"Refusing symlink, junction or reparse point: {path}")
    return info


def _absolute(path: Path | str, base: Path | None = None) -> Path:
    raw = Path(path)
    if ".." in raw.parts:
        raise CleanupError(f"Parent traversal is not allowed: {path}")
    if not raw.is_absolute():
        raw = (base or Path.cwd()) / raw
    absolute = Path(os.path.abspath(raw))
    for node in (*reversed(absolute.parents), absolute):
        if node.exists() or node.is_symlink():
            _no_reparse(node)
    return absolute


def _project(path: Path | str) -> Path:
    root = _absolute(path)
    if not root.is_dir() or root == Path(root.anchor):
        raise CleanupError(f"A non-root project directory is required: {root}")
    return root.resolve(strict=True)


def _inside(path: Path | str, root: Path) -> Path:
    candidate = _absolute(path, root)
    if candidate == root or not candidate.is_relative_to(root):
        raise CleanupError(f"Path must be strictly inside the project: {candidate}")
    for part in candidate.relative_to(root).parts:
        if part.casefold() in PROTECTED or part.endswith((".", " ")) or ":" in part:
            raise CleanupError(f"Refusing protected or abnormal path: {candidate}")
    resolved = candidate.resolve(strict=False)
    if resolved != candidate or not resolved.is_relative_to(root):
        raise CleanupError(f"Path resolution changed the project boundary: {candidate}")
    return candidate


def _roots(paths: Iterable[Path | str], root: Path) -> tuple[Path, ...]:
    result = tuple(sorted({_inside(path, root) for path in paths}))
    if not result:
        raise CleanupError("At least one explicit output root is required.")
    for index, path in enumerate(result):
        if path.exists() and not path.is_dir():
            raise CleanupError(f"Output root must be a directory: {path}")
        if any(path.is_relative_to(other) for other in result[:index]):
            raise CleanupError(f"Overlapping output roots are not allowed: {path}")
    return result


def _output_location(path: Path | str, root: Path, roots: tuple[Path, ...]) -> Path:
    candidate = _inside(path, root)
    if candidate.parent not in roots or not OUTPUT_NAME.fullmatch(candidate.name) or candidate.name.endswith((".", " ")):
        raise CleanupError(f"Expected a recognized top-level generated output: {candidate}")
    return candidate


def _output(path: Path | str, root: Path, roots: tuple[Path, ...]) -> Path:
    candidate = _output_location(path, root, roots)
    if not candidate.is_dir():
        raise CleanupError(f"Generated output must be a directory: {candidate}")
    return candidate


def _mutable_paths(patterns: Iterable[str]) -> tuple[str, ...]:
    result = []
    for value in patterns:
        if not isinstance(value, str) or "\\" in value:
            raise CleanupError(f"Invalid mutable path: {value!r}")
        prefix = value[:-3] if value.endswith("/**") else value
        parts = prefix.split("/")
        if not prefix or PurePosixPath(prefix).is_absolute() or any(part in {"", ".", ".."} or any(char in part for char in "*?[:") or part.endswith((".", " ")) for part in parts):
            raise CleanupError(f"Mutable paths must name a relative file or explicit subtree: {value!r}")
        if prefix == MARKER_NAME:
            raise CleanupError("The ownership marker cannot be mutable.")
        result.append(value)
    return tuple(sorted(set(result)))


def _mutable(relative: str, directory: bool, patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        subtree = pattern.endswith("/**")
        prefix = pattern[:-3] if subtree else pattern
        if relative == prefix or (subtree and relative.startswith(prefix + "/")):
            return True
        if directory and prefix.startswith(relative + "/"):
            return True
    return False


def _inventory(output: Path, mutable_paths: tuple[str, ...]) -> list[dict]:
    entries = []

    def visit(directory: Path) -> None:
        for child in sorted(directory.iterdir()):
            info = _no_reparse(child)
            relative = child.relative_to(output).as_posix()
            if relative == MARKER_NAME:
                if not stat.S_ISREG(info.st_mode):
                    raise CleanupError(f"Ownership marker must be a regular file: {child}")
                continue
            is_directory = stat.S_ISDIR(info.st_mode)
            if not is_directory and not stat.S_ISREG(info.st_mode):
                raise CleanupError(f"Refusing special filesystem entry: {child}")
            if not _mutable(relative, is_directory, mutable_paths):
                entry = {"path": relative, "type": "directory" if is_directory else "file"}
                if not is_directory:
                    entry.update(size=info.st_size, mtime_ns=info.st_mtime_ns)
                entries.append(entry)
            if is_directory:
                visit(child)

    visit(output)
    return entries


def mark_generated_output(
    output_dir: Path | str, *, project_root: Path | str,
    output_roots: Iterable[Path | str], builder_id: str, run_id: str,
    kind: str, mutable_paths: Iterable[str] = (),
) -> Path:
    """Seal a newly generated output before runtime tests modify registered paths."""
    root = _project(project_root)
    roots = _roots(output_roots, root)
    output = _output(output_dir, root, roots)
    _identifier(builder_id, "builder id")
    _identifier(run_id, "run id")
    if kind not in KINDS:
        raise CleanupError(f"Invalid output kind: {kind!r}")
    mutable = _mutable_paths(mutable_paths)
    marker = {
        "schema": 1, "builder_id": builder_id, "run_id": run_id,
        "kind": kind, "project_root": str(root),
        "relative_path": output.relative_to(root).as_posix(),
        "mutable_paths": list(mutable), "inventory": _inventory(output, mutable),
    }
    marker_path = output / MARKER_NAME
    with marker_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(marker, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return marker_path


def _owned(output: Path, root: Path, builder_id: str, current_run_id: str | None) -> tuple[str | None, str]:
    marker_path = output / MARKER_NAME
    if not marker_path.exists():
        return None, "No ownership marker"
    info = _no_reparse(marker_path)
    if not stat.S_ISREG(info.st_mode):
        raise CleanupError(f"Ownership marker must be a regular file: {marker_path}")
    try:
        raw = marker_path.read_text(encoding="utf-8")
        marker = json.loads(raw)
        if not isinstance(marker, dict) or marker.get("schema") != 1 or marker.get("builder_id") != builder_id:
            return None, "Unknown marker schema or builder"
        if marker.get("project_root") != str(root) or marker.get("relative_path") != output.relative_to(root).as_posix():
            return None, "Ownership marker belongs to another path"
        _identifier(marker["run_id"], "recorded run id")
        if marker.get("kind") not in KINDS:
            return None, "Unknown output kind"
        if current_run_id is not None and marker["run_id"] == current_run_id:
            return None, "Current build run"
        mutable = _mutable_paths(marker.get("mutable_paths", []))
    except (OSError, KeyError, TypeError, json.JSONDecodeError, UnicodeError) as error:
        return None, f"Unreadable ownership marker: {error}"
    if _inventory(output, mutable) != marker.get("inventory"):
        return None, "Unknown or modified content"
    return raw, "Owned generated output"


@contextmanager
def generated_output(
    output_dir: Path | str, *, project_root: Path | str,
    output_roots: Iterable[Path | str], builder_id: str, run_id: str,
    kind: str, mutable_paths: Iterable[str] = (),
    log: Callable[[str], None] = print,
) -> Iterator[Path]:
    """Create a fresh output and seal its actual contents on success or failure."""
    root = _project(project_root)
    roots = _roots(output_roots, root)
    output = _output_location(output_dir, root, roots)
    _identifier(builder_id, "builder id")
    _identifier(run_id, "run id")
    if kind not in KINDS:
        raise CleanupError(f"Invalid output kind: {kind!r}")
    mutable = _mutable_paths(mutable_paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    _roots(roots, root)
    output.mkdir(exist_ok=False)
    created = _no_reparse(output)

    def seal() -> None:
        try:
            current = output.lstat()
        except FileNotFoundError:
            return
        _output(output, root, roots)
        if not os.path.samestat(created, current):
            raise CleanupError(f"Refusing to claim a replaced output directory: {output}")
        marker_path = output / MARKER_NAME
        if marker_path.exists() or marker_path.is_symlink():
            raw, reason = _owned(output, root, builder_id, None)
            if raw is None:
                raise CleanupError(f"Existing output marker cannot be reused: {output} ({reason})")
            recorded = json.loads(raw)
            if recorded["run_id"] != run_id or recorded["kind"] != kind or tuple(recorded["mutable_paths"]) != mutable:
                raise CleanupError(f"Existing output marker belongs to another build: {output}")
            return
        mark_generated_output(output, project_root=root, output_roots=roots, builder_id=builder_id, run_id=run_id, kind=kind, mutable_paths=mutable)

    try:
        yield output
    except BaseException as original:
        try:
            seal()
        except BaseException as sealing_error:
            message = f"Failed to seal generated output {output}: {sealing_error}"
            if hasattr(original, "add_note"):
                original.add_note(message)
            try:
                log(message)
            except BaseException:
                pass
        raise
    else:
        seal()


def plan_cleanup(
    *, project_root: Path | str, output_roots: Iterable[Path | str],
    builder_id: str, current_run_id: str | None = None,
    exclude_paths: Iterable[Path | str] = (),
) -> CleanupPlan:
    """Validate the whole cleanup scope without deleting or creating anything."""
    root = _project(project_root)
    roots = _roots(output_roots, root)
    _identifier(builder_id, "builder id")
    if current_run_id is not None:
        _identifier(current_run_id, "current run id")
    excluded = tuple(sorted({_inside(path, root) for path in exclude_paths}))
    remove, preserve, markers = [], [], []
    for output_root in roots:
        if not output_root.exists():
            continue
        for child in sorted(output_root.iterdir()):
            if not OUTPUT_NAME.fullmatch(child.name) or child.name.endswith((".", " ")):
                preserve.append(PreservedOutput(child, "Unrecognized output name"))
                continue
            _no_reparse(child)
            if not child.is_dir():
                preserve.append(PreservedOutput(child, "Standalone files are preserved"))
                continue
            candidate = _output(child, root, roots)
            if any(candidate == path or candidate.is_relative_to(path) or path.is_relative_to(candidate) for path in excluded):
                preserve.append(PreservedOutput(child, "Explicitly excluded output"))
                continue
            marker, reason = _owned(candidate, root, builder_id, current_run_id)
            if marker is None:
                preserve.append(PreservedOutput(child, reason))
            else:
                remove.append(candidate)
                markers.append(marker)
    return CleanupPlan(root, roots, builder_id, current_run_id, excluded, tuple(remove), tuple(preserve), tuple(markers))


def execute_cleanup(
    plan: CleanupPlan, *, dry_run: bool = False,
    keep_previous_outputs: bool = False, log: Callable[[str], None] = print,
) -> CleanupPlan:
    """Revalidate every target, then delete through Python only."""
    fresh = plan_cleanup(project_root=plan.project_root, output_roots=plan.output_roots, builder_id=plan.builder_id, current_run_id=plan.current_run_id, exclude_paths=plan.exclude_paths)
    if fresh.remove != plan.remove or fresh._markers != plan._markers:
        raise CleanupError("Cleanup plan changed; no output was removed.")
    for item in fresh.preserve:
        log(f"Preserve: {item.path} ({item.reason})")
    for path in fresh.remove:
        action = "Keep" if keep_previous_outputs else "Would remove" if dry_run else "Remove"
        log(f"{action}: {path}")
    if not dry_run and not keep_previous_outputs:
        for path, expected_marker in zip(fresh.remove, fresh._markers):
            _output(path, fresh.project_root, fresh.output_roots)
            marker, _ = _owned(path, fresh.project_root, fresh.builder_id, fresh.current_run_id)
            if marker != expected_marker:
                raise CleanupError(f"Output changed immediately before removal: {path}")
            shutil.rmtree(path)
    return fresh


def cleanup_previous_outputs(
    *, project_root: Path | str, output_roots: Iterable[Path | str],
    builder_id: str, current_run_id: str | None = None,
    exclude_paths: Iterable[Path | str] = (), keep_previous_outputs: bool = False,
    dry_run: bool = False, log: Callable[[str], None] = print,
) -> CleanupPlan:
    plan = plan_cleanup(project_root=project_root, output_roots=output_roots, builder_id=builder_id, current_run_id=current_run_id, exclude_paths=exclude_paths)
    return execute_cleanup(plan, dry_run=dry_run, keep_previous_outputs=keep_previous_outputs, log=log)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output-root", action="append", required=True)
    parser.add_argument("--builder-id", required=True)
    parser.add_argument("--current-run-id")
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--keep-previous-outputs", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        cleanup_previous_outputs(project_root=args.project_root, output_roots=args.output_root, builder_id=args.builder_id, current_run_id=args.current_run_id, exclude_paths=args.exclude, keep_previous_outputs=args.keep_previous_outputs, dry_run=args.dry_run)
    except (CleanupError, OSError) as error:
        parser.exit(2, f"Cleanup failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
