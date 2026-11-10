"""Explicitly opted-in POSIX runner for a reviewed isolated candidate checkout.

No CLI, scheduler hook, GitHub writes or receipt-publication logic. This can
execute the existing network crawler ONLY when explicitly instantiated by an
approved caller. Tests execute a disposable no-network fixture instead.

This is not an OS sandbox or proof of remote GitHub identity. A reviewed
checkout, authenticated expected SHA, exclusive workspace and trusted Python
runtime remain prerequisites. Git metadata/origin strings alone do not prove
that a caller obtained its sources from the authentic repository.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from pathlib import Path

from .company_profile_writer_crawl_observer import (
    COMMIT_SHA, MAX_COMMAND_SECONDS, MAX_RUN_DURATION, MAX_SELECTED, SLUG,
    crawl_argv,
)

ALLOWED_OUTPUTS = frozenset({
    "public/data/venture_profiles.json",
    "public/data/company_profile_refresh_queue.json",
})
ORIGINS = frozenset({
    "https://github.com/VCIQ/VCIQ.github.io.git",
    "https://github.com/VCIQ/VCIQ.github.io",
    "git@github.com:VCIQ/VCIQ.github.io.git",
})
MAX_GIT_BYTES = 1024 * 1024


class CrawlRunnerError(ValueError):
    """Fixed error codes; no subprocess output or credential values."""


def _environment(private_home: str) -> dict[str, str]:
    # Do not copy the operator's environment: notably GH_TOKEN, proxy auth,
    # PYTHONPATH, dynamic-loader settings and git credential overrides.
    return {
        "PATH": os.defpath,
        "HOME": private_home,
        "TMPDIR": private_home,
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
    }


class BoundedCrawlRunner:
    """Single-use-per-company executor; a failed attempt poisons this runner."""

    def __init__(self, checkout_root: Path, base_sha: str, selected_slugs,
                 *, authorized: bool = False):
        if authorized is not True:
            raise CrawlRunnerError("CRAWL_RUNNER_NOT_AUTHORIZED")
        if os.name != "posix":
            raise CrawlRunnerError("CRAWL_RUNNER_POSIX_REQUIRED")
        if (type(base_sha) is not str or not COMMIT_SHA.fullmatch(base_sha)
            or not isinstance(selected_slugs, (list, tuple))
            or not 1 <= len(selected_slugs) <= MAX_SELECTED
            or any(type(s) is not str or not SLUG.fullmatch(s) for s in selected_slugs)
            or len(set(selected_slugs)) != len(selected_slugs)):
            raise CrawlRunnerError("CRAWL_RUNNER_IDENTITY_INVALID")
        try:
            root = Path(checkout_root)
            if root.is_symlink() or not root.is_dir():
                raise ValueError()
            self.root = root.resolve(strict=True)
        except (ValueError, TypeError, OSError):
            raise CrawlRunnerError("CRAWL_RUNNER_CHECKOUT_INVALID") from None
        self.base_sha = base_sha
        self.selected = tuple(selected_slugs)
        self.completed = []
        self.failed = False
        self.deadline = time.monotonic() + MAX_RUN_DURATION.total_seconds()
        self.git = shutil.which("git", path=os.defpath)
        if self.git is None:
            raise CrawlRunnerError("CRAWL_RUNNER_GIT_UNAVAILABLE")

    def _git(self, env, *args, allowed=(0,)) -> bytes:
        try:
            result = subprocess.run(
                [self.git, "-c", "core.fsmonitor=false", *args],
                cwd=self.root, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=15, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise CrawlRunnerError("CRAWL_RUNNER_GIT_FAILED") from None
        if result.returncode not in allowed or len(result.stdout) > MAX_GIT_BYTES:
            raise CrawlRunnerError("CRAWL_RUNNER_GIT_FAILED")
        return result.stdout

    def _verify_checkout(self, env):
        if ((self.root / ".git").is_symlink()
            or not (self.root / ".git").is_dir()):
            raise CrawlRunnerError("CRAWL_RUNNER_ISOLATED_REPOSITORY_REQUIRED")
        if self._git(env, "rev-parse", "HEAD").strip() != self.base_sha.encode("ascii"):
            raise CrawlRunnerError("CRAWL_RUNNER_BASE_MOVED")
        # A detached HEAD returns exit 1 with no symbolic ref.
        if self._git(env, "symbolic-ref", "--quiet", "HEAD", allowed=(1,)):
            raise CrawlRunnerError("CRAWL_RUNNER_DETACHED_REQUIRED")
        origin = self._git(env, "remote", "get-url", "origin").strip()
        if origin not in {url.encode("ascii") for url in ORIGINS}:
            raise CrawlRunnerError("CRAWL_RUNNER_ORIGIN_INVALID")
        # Include ignored entries: a hidden ignored Python module must not
        # silently enter imports. Reject all staged/untracked changes.
        rows = self._git(env, "status", "--porcelain=v1", "-z",
                         "--untracked-files=all", "--ignored=matching").split(b"\0")
        for row in filter(None, rows):
            if row not in {b" M " + p.encode() for p in ALLOWED_OUTPUTS}:
                raise CrawlRunnerError("CRAWL_RUNNER_UNEXPECTED_CHANGE")
        code = self._git(env, "ls-tree", "-r", "-z", "HEAD", "--", "tools")
        if not code or any(not row.startswith((b"100644 blob ", b"100755 blob "))
                           for row in code.split(b"\0") if row):
            raise CrawlRunnerError("CRAWL_RUNNER_CODE_TREE_INVALID")
        if not (self.root / "tools/crawl_venture_profiles.py").is_file():
            raise CrawlRunnerError("CRAWL_RUNNER_CODE_TREE_INVALID")
        for name in ALLOWED_OUTPUTS:
            path = self.root / name
            if any(p.is_symlink() for p in (path, path.parent, path.parent.parent)):
                raise CrawlRunnerError("CRAWL_RUNNER_OUTPUT_UNSAFE")
            try:
                info = path.lstat()
            except OSError:
                raise CrawlRunnerError("CRAWL_RUNNER_OUTPUT_UNSAFE") from None
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_size > 16 * 1024 * 1024):
                raise CrawlRunnerError("CRAWL_RUNNER_OUTPUT_UNSAFE")

    def __call__(self, command, *, cwd, timeout):
        if self.failed or len(self.completed) >= len(self.selected):
            raise CrawlRunnerError("CRAWL_RUNNER_ALREADY_CONSUMED")
        # Any failure consumes the runner: no implicit retry or partial resume.
        self.failed = True
        slug = self.selected[len(self.completed)]
        if (not isinstance(command, (tuple, list)) or tuple(command) != crawl_argv(slug)
            or type(timeout) is not int or not 1 <= timeout <= MAX_COMMAND_SECONDS):
            raise CrawlRunnerError("CRAWL_RUNNER_COMMAND_INVALID")
        try:
            if Path(cwd).resolve(strict=True) != self.root:
                raise ValueError()
        except (TypeError, ValueError, OSError):
            raise CrawlRunnerError("CRAWL_RUNNER_CWD_INVALID") from None
        remaining = self.deadline - time.monotonic()
        if remaining < 1:
            raise CrawlRunnerError("CRAWL_RUNNER_DEADLINE_EXCEEDED")
        with tempfile.TemporaryDirectory(prefix="company-crawl-home-") as home:
            env = _environment(home)
            self._verify_checkout(env)
            queue = self.root / "public/data/company_profile_refresh_queue.json"
            queue_digest = hashlib.sha256(queue.read_bytes()).digest()
            remaining = self.deadline - time.monotonic()
            if remaining < 1:
                raise CrawlRunnerError("CRAWL_RUNNER_DEADLINE_EXCEEDED")
            process = None
            try:
                process = subprocess.Popen(
                    list(command), cwd=self.root, env=env, shell=False,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True,
                )
                exit_code = process.wait(timeout=min(timeout, remaining))
            except subprocess.TimeoutExpired:
                raise CrawlRunnerError("CRAWL_RUNNER_PROCESS_TIMEOUT") from None
            except OSError:
                raise CrawlRunnerError("CRAWL_RUNNER_PROCESS_FAILED") from None
            finally:
                if process is not None:
                    # Also terminate descendants left behind by an exited parent.
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=5)
            if exit_code != 0:
                raise CrawlRunnerError("CRAWL_RUNNER_NONZERO_EXIT")
            self._verify_checkout(env)
            if hashlib.sha256(queue.read_bytes()).digest() != queue_digest:
                raise CrawlRunnerError("CRAWL_RUNNER_QUEUE_CHANGED")
        self.completed.append(slug)
        self.failed = False
        return subprocess.CompletedProcess(tuple(command), exit_code)
