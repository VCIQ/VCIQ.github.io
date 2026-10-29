"""Read-only path and production-integrity guards for a trusted local operator.

These checks are not an OS sandbox. Future writers must recheck immediately
before an atomic write; no adversarial concurrent path mutation is supported.
PR-01 creates no state directories and supplies no write or subprocess command.
"""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Iterable


class GuardError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _absolute(value: Path | str) -> Path:
    try:
        path = Path(value)
        if not path.is_absolute() or ".." in path.parts or "\x00" in str(path):
            raise GuardError("absolute_path_required")
        return path
    except (TypeError, ValueError) as exc:
        if isinstance(exc, GuardError):
            raise
        raise GuardError("invalid_path") from None


def _no_symlinks(path: Path) -> None:
    try:
        for component in (path, *path.parents):
            if component.is_symlink():
                raise GuardError("symlink_forbidden")
    except (OSError, RuntimeError):
        raise GuardError("unresolvable_path") from None


def state_path(state_dir: Path | str, *, repo_roots: Iterable[Path | str]) -> Path:
    """Resolve a non-overlapping state directory without creating or chmoding it."""
    path = _absolute(state_dir)
    _no_symlinks(path)
    try:
        resolved = path.resolve(strict=False)
        roots = [Path(root).resolve(strict=True) for root in repo_roots]
        if not roots or not all(root.is_dir() for root in roots):
            raise GuardError("repository_roots_required")
        if any(resolved == root or resolved.is_relative_to(root) or root.is_relative_to(resolved) for root in roots):
            raise GuardError("state_overlaps_repository")
        if resolved.exists() and not resolved.is_dir():
            raise GuardError("state_not_directory")
        # An existing regular file in a prospective parent chain is invalid too.
        if any(parent.exists() and not parent.is_dir() for parent in resolved.parents):
            raise GuardError("state_parent_not_directory")
        return resolved
    except (OSError, RuntimeError):
        raise GuardError("unresolvable_path") from None


def output_path(state_dir: Path | str, relative: str, *, repo_roots: Iterable[Path | str]) -> Path:
    """Validate an explicit future output. No file or directory is written."""
    root = state_path(state_dir, repo_roots=repo_roots)
    if not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative:
        raise GuardError("invalid_relative_path")
    parts = relative.split("/")
    if PurePosixPath(relative).is_absolute() or any(p in {"", ".", ".."} for p in parts) or ":" in parts[0]:
        raise GuardError("invalid_relative_path")
    candidate = root.joinpath(*parts)
    _no_symlinks(candidate)
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root) or resolved == root:
        raise GuardError("output_outside_state")
    if resolved.exists() and (not resolved.is_file() or resolved.stat().st_nlink > 1):
        raise GuardError("unsafe_output_target")
    return resolved


def runtime_paths(runtime: dict, *, repo_root: Path | str, runtime_file: Path | str | None = None) -> Path:
    roots = [Path(repo_root)]
    upstream = runtime.get("mediacrawlerDir")
    if upstream is not None:
        upstream_path = _absolute(upstream)
        _no_symlinks(upstream_path)
        if not upstream_path.is_dir():
            raise GuardError("upstream_directory_missing")
        roots.append(upstream_path)
    root = state_path(runtime["stateDir"], repo_roots=roots)
    profile = _absolute(runtime["profileRoot"])
    _no_symlinks(profile)
    if profile.resolve(strict=False) != root / "profiles":
        raise GuardError("dedicated_profile_required")
    if runtime_file is not None:
        selected = _absolute(runtime_file)
        _no_symlinks(selected)
        if not selected.resolve(strict=True).is_relative_to(root):
            raise GuardError("runtime_outside_state")
    return root


def protected_snapshot(repo_root: Path | str) -> dict[str, str]:
    """Hash protected production/configuration paths, including additions/removals.

Symlink content is recorded as a link, not dereferenced. Existing symlinked
subdirectories are not traversed. No Git command or network call is used.
"""
    root = Path(repo_root).resolve(strict=True)
    paths: set[Path] = {root / ".gitignore", root / "tools/__init__.py"}
    paths.update((root / "tools").glob("*.py"))
    for directory in ("public/data", "config", ".github/workflows"):
        start = root / directory
        if start.is_symlink():
            paths.add(start)
        elif start.exists():
            paths.update(start.rglob("*"))
    snapshot: dict[str, str] = {}
    for path in sorted(paths):
        if path.is_symlink():
            payload = b"symlink:" + str(path.readlink()).encode("utf-8")
        elif path.is_file():
            payload = path.read_bytes()
        else:
            continue
        snapshot[path.relative_to(root).as_posix()] = hashlib.sha256(payload).hexdigest()
    return snapshot


def assert_unchanged(before: dict[str, str], *, repo_root: Path | str) -> None:
    if before != protected_snapshot(repo_root):
        raise GuardError("production_modified")
