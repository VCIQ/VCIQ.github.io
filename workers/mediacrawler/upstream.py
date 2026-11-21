"""Read-only verification of an operator-installed, pinned upstream checkout."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

PIN = "8f583999006d5b692272c608440e193ca282e73b"
REPOSITORY = "NanmiCoder/MediaCrawler"


class UpstreamError(ValueError):
    pass


def load_lock(path: Path) -> dict:
    lock = json.loads(path.read_text(encoding="utf-8"))
    if set(lock) != {"schemaVersion", "repository", "commit", "patches", "patchsetHash"}:
        raise UpstreamError("LOCK_FIELDS")
    if type(lock["schemaVersion"]) is not int or lock["schemaVersion"] != 1 or lock["repository"] != REPOSITORY or lock["commit"] != PIN or lock["patches"] != []:
        raise UpstreamError("UPSTREAM_PIN_MISMATCH")
    if lock["patchsetHash"] != hashlib.sha256(b"[]").hexdigest():
        raise UpstreamError("PATCHSET_HASH")
    return lock


def verify_checkout(root: Path, lock: dict, *, runner=subprocess.run) -> None:
    if not root.is_absolute() or not root.is_dir() or any(p.is_symlink() for p in (root, *root.parents)):
        raise UpstreamError("UPSTREAM_PATH")
    if lock.get("commit") != PIN or lock.get("patches") != []:
        raise UpstreamError("UPSTREAM_PIN_MISMATCH")
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT") if key in os.environ}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    base = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull, "-C", str(root)]
    def read(*args):
        try:
            result = runner(base + list(args), capture_output=True, text=True,
                            timeout=15, check=False, env=env)
        except (OSError, subprocess.TimeoutExpired):
            raise UpstreamError("UPSTREAM_GIT_UNAVAILABLE") from None
        if result.returncode:
            raise UpstreamError("UPSTREAM_GIT_OR_DIRTY")
        return result.stdout.strip()
    if read("rev-parse", "HEAD") != lock["commit"] or Path(read("rev-parse", "--show-toplevel")).resolve() != root.resolve():
        raise UpstreamError("UPSTREAM_PIN_MISMATCH")
    read("diff", "--quiet", "--no-ext-diff", "HEAD", "--")
    for name in read("ls-files", "--others", "--exclude-standard").splitlines():
        if not name.startswith((".venv/", "__pycache__/", ".pytest_cache/")):
            raise UpstreamError("UPSTREAM_UNTRACKED_FILES")
    if any((root / name).exists() for name in (".env", ".env.local")):
        raise UpstreamError("UPSTREAM_ENV_FILE_FORBIDDEN")
    for name in ("config/__init__.py", "media_platform/xhs/core.py"):
        path = root / name
        if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
            raise UpstreamError("UPSTREAM_SOURCE_PATH")
