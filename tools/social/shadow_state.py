"""Private, checksummed orchestration journals; no import-time I/O."""
from __future__ import annotations

import os
import stat
from contextlib import contextmanager
from uuid import UUID, uuid4

from .batch import MAX_LINE, decode, private_root, read_private, write_private
from .contracts import ContractError, assert_safe, canonical_bytes, digest
from .guard import GuardError, output_path
from .wechat_runner import atomic_json

STOP_FILE = "shadow.stop"
MAX_JOURNAL = 4 * 1024 * 1024


def run_prefix(run_id):
    try:
        if str(UUID(run_id)) != run_id: raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ContractError("shadow_run_id") from None
    return "orchestration/" + run_id


def checked_payload(value):
    assert_safe(value)
    if len(canonical_bytes(value)) > MAX_JOURNAL:
        raise ContractError("shadow_journal_limit")
    return value


def save(root, relative, value, roots, *, exclusive=False):
    checked_payload(value)
    wrapped = {"schemaVersion": 1, "payload": value, "sha256": digest(value)}
    if exclusive:
        # Publish a fully fsynced inode without replacing a previous intent/result.
        # A crash may leave a staging file, never a half-written final journal.
        target = output_path(root, relative, repo_roots=roots)
        temp = str(target.relative_to(root).parent / (".tmp-" + str(uuid4())))
        staged = write_private(root, temp, canonical_bytes(wrapped) + b"\n", roots)
        try:
            output_path(root, relative, repo_roots=roots)
            os.link(staged, target, follow_symlinks=False)
        finally:
            staged.unlink()
    else:
        atomic_json(root, relative, wrapped, roots=roots)
    if os.name == "posix":
        parent = output_path(root, relative, repo_roots=roots).parent
        fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try: os.fsync(fd)
        finally: os.close(fd)


def load(root, relative, roots):
    wrapped = decode(read_private(root, relative, roots, maximum=MAX_JOURNAL + MAX_LINE))
    if (not isinstance(wrapped, dict) or set(wrapped) != {"schemaVersion", "payload", "sha256"}
            or type(wrapped["schemaVersion"]) is not int or wrapped["schemaVersion"] != 1
            or digest(wrapped["payload"]) != wrapped["sha256"]):
        raise ContractError("shadow_journal_checksum")
    return checked_payload(wrapped["payload"])


def stopped(root, roots):
    # A corrupt, linked or non-regular marker also stops execution; never follow it.
    try:
        path = output_path(root, STOP_FILE, repo_roots=roots)
        return path.exists()
    except (GuardError, OSError):
        return True


def request_stop(root, roots):
    private_root(root, roots)
    if stopped(root, roots): return False
    try:
        write_private(root, STOP_FILE, b"{\"stop\":true}\n", roots)
    except FileExistsError:
        return False
    return True


def clear_stop(root, roots):
    private_root(root, roots)
    path = output_path(root, STOP_FILE, repo_roots=roots)
    if not path.exists(): return False
    read_private(root, STOP_FILE, roots, maximum=MAX_LINE)
    path.unlink()
    return True


@contextmanager
def run_lock(root, roots):
    """One coordinator per state root. OS lock is released on process death."""
    if os.name != "posix": raise ContractError("shadow_posix_required")
    import fcntl
    path = output_path(root, "locks/orchestration.lock", repo_roots=roots)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output_path(root, "locks/orchestration.lock", repo_roots=roots)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_nlink != 1:
            raise GuardError("shadow_lock_permissions")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ContractError("shadow_run_busy") from None
        yield
    finally:
        os.close(fd)
