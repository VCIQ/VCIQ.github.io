"""Crash-visible, opt-in local receipt journal for a reviewed company crawl pilot.

No CLI or workflow integration. A caller explicitly authorizes one local run,
supplies a private directory outside the checkout and *then* executes a
validated, isolated runner. An exclusive run reservation is written and synced
before any subprocess; each verified receipt is appended with an exclusive
create, fsync and a hash link. Incomplete runs are never resumed automatically.

This is neither immutable external storage nor an authentication of HTTP
responses or runner identity. An operator with filesystem access can rewrite
these files. Production needs durable externally anchored evidence and an
independent review/recovery protocol.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path

from .company_profile_writer_crawl_receipt import (
    CrawlReceiptError, MAX_SELECTED, SLUG, _time,
)

_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}\Z")
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_DOC = 32 * 1024
_EMPTY = "0" * 64


class JournalError(ValueError):
    """Fixed error codes; never include source content or environment."""


def _digest(value) -> str:
    return hashlib.sha256(_encode(value)).hexdigest()


def _pairs(rows):
    data = {}
    for key, val in rows:
        if key in data:
            raise JournalError("JOURNAL_DUPLICATE_KEY")
        data[key] = val
    return data


def _reject_constant(_):
    raise JournalError("JOURNAL_NONFINITE_NUMBER")


def _encode(obj) -> bytes:
    try:
        raw = json.dumps(obj, sort_keys=True, ensure_ascii=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise JournalError("JOURNAL_SERIALIZATION_INVALID") from None
    if len(raw) > _MAX_DOC:
        raise JournalError("JOURNAL_RECORD_OVERSIZED")
    return raw + b"\n"


def _decode(data: bytes) -> dict:
    if len(data) > _MAX_DOC:
        raise JournalError("JOURNAL_RECORD_OVERSIZED")
    try:
        result = json.loads(
            data.decode("utf-8"), object_pairs_hook=_pairs,
            parse_constant=_reject_constant)
    except JournalError:
        raise
    except (TypeError, UnicodeError, ValueError, RecursionError):
        raise JournalError("JOURNAL_FORMAT_INVALID") from None
    if not isinstance(result, dict):
        raise JournalError("JOURNAL_FORMAT_INVALID")
    return result


def _strict_dir(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError:
        raise JournalError("JOURNAL_DIRECTORY_INVALID") from None
    if (not stat.S_ISDIR(info.st_mode)
        or path.is_symlink()
        or info.st_uid != os.geteuid()
        or info.st_mode & 0o077):
        raise JournalError("JOURNAL_DIRECTORY_UNSAFE")


def _sync_dir(path: Path):
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        os.fsync(fd)
    except OSError:
        raise JournalError("JOURNAL_SYNC_FAILED") from None
    finally:
        if fd is not None:
            os.close(fd)


def _write_new(path: Path, value) -> None:
    raw = _encode(value)
    fd = None
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as out:
            fd = None
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        _sync_dir(path.parent)
    except FileExistsError:
        raise JournalError("JOURNAL_DUPLICATE_RECORD") from None
    except JournalError:
        raise
    except OSError:
        raise JournalError("JOURNAL_WRITE_FAILED") from None
    finally:
        if fd is not None:
            os.close(fd)


def _read_file(path: Path) -> dict:
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as inp:
            fd = None
            info = os.fstat(inp.fileno())
            if (not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o077):
                raise JournalError("JOURNAL_FILE_UNSAFE")
            raw = inp.read(_MAX_DOC + 1)
    except JournalError:
        raise
    except OSError:
        raise JournalError("JOURNAL_READ_FAILED") from None
    finally:
        if fd is not None:
            os.close(fd)
    return _decode(raw)


def _validate_id(run_id: str):
    if type(run_id) is not str or not _RUN_ID.fullmatch(run_id):
        raise JournalError("JOURNAL_ID_INVALID")


def _validate_sha(value: str, *, commit=False):
    regex = _SHA40 if commit else _SHA256
    if type(value) is not str or not regex.fullmatch(value):
        raise JournalError("JOURNAL_DIGEST_INVALID")


def _validate_slugs(slugs) -> tuple[str, ...]:
    if (not isinstance(slugs, (tuple, list))
        or not 1 <= len(slugs) <= MAX_SELECTED
        or any(type(s) is not str or not SLUG.fullmatch(s) for s in slugs)
        or len(set(slugs)) != len(slugs)):
        raise JournalError("JOURNAL_SELECTION_INVALID")
    return tuple(slugs)


def _stamp(value):
    try:
        return _time(value)
    except CrawlReceiptError:
        raise JournalError("JOURNAL_TIME_INVALID") from None


class RunReceiptJournal:
    """One-shot journal. Any failure is final; use inspect for human triage."""

    def __init__(self, private_parent: Path, *, authorized: bool = False):
        if authorized is not True:
            raise JournalError("JOURNAL_EXPLICIT_APPROVAL_REQUIRED")
        try:
            parent = Path(private_parent)
        except (ValueError, TypeError):
            raise JournalError("JOURNAL_DIRECTORY_INVALID") from None
        _strict_dir(parent)
        self.parent = parent.resolve(strict=True)
        self.directory: Path | None = None
        self.slugs: tuple[str, ...] = ()
        self.next_index = 0
        self.previous_digest = _EMPTY
        self.failed = False
        self.finished = False

    def begin(self, *, run_id: str, base_sha: str, selected_slugs,
              selection_sha256: str, official_urls_sha256: str,
              run_started_at: str):
        if self.failed or self.directory is not None:
            raise JournalError("JOURNAL_ALREADY_STARTED")
        self.failed = True
        _validate_id(run_id)
        _validate_sha(base_sha, commit=True)
        _validate_sha(selection_sha256)
        _validate_sha(official_urls_sha256)
        selected = _validate_slugs(selected_slugs)
        started = _stamp(run_started_at)
        path = self.parent / ("run-" + run_id)
        try:
            os.mkdir(path, 0o700)  # Atomic cross-process run-ID reservation.
        except FileExistsError:
            raise JournalError("JOURNAL_RUN_RESERVED") from None
        except OSError:
            raise JournalError("JOURNAL_RESERVE_FAILED") from None
        self.directory = path
        _sync_dir(self.parent)
        _strict_dir(path)
        manifest = {
            "schemaVersion": 1,
            "runId": run_id,
            "baseSha": base_sha,
            "selectedSlugs": list(selected),
            "selectionSha256": selection_sha256,
            "officialUrlsSha256": official_urls_sha256,
            "runStartedAt": started.isoformat(timespec="seconds"),
            "automaticResumeAuthorized": False,
            "markProcessedAuthorized": False,
            "mergeAuthorized": False,
            "publicationAuthorized": False,
        }
        _write_new(path / "manifest.json", manifest)
        self.slugs = selected
        self.failed = False

    def record(self, receipt: dict):
        if self.failed or self.finished or self.directory is None:
            raise JournalError("JOURNAL_NOT_RECORDABLE")
        self.failed = True
        if (not isinstance(receipt, dict)
            or set(receipt) != {"slug", "exitCode", "capturedAt",
                               "statusSha256", "profileSha256"}
            or self.next_index >= len(self.slugs)
            or receipt.get("slug") != self.slugs[self.next_index]
            or type(receipt.get("exitCode")) is not int
            or receipt["exitCode"] != 0):
            raise JournalError("JOURNAL_RECEIPT_INVALID")
        _validate_sha(receipt["statusSha256"])
        _validate_sha(receipt["profileSha256"])
        _stamp(receipt["capturedAt"])
        payload = {
            "index": self.next_index,
            "previousDigest": self.previous_digest,
            "receipt": receipt,
        }
        entry = {"payload": payload, "digest": _digest(payload)}
        path = self.directory / f"receipt-{self.next_index:02d}.json"
        _write_new(path, entry)
        self.previous_digest = entry["digest"]
        self.next_index += 1
        self.failed = False
        return entry["digest"]

    def complete(self, *, final_snapshot_sha256: str, completed_at: str):
        if (self.failed or self.finished or self.directory is None
            or self.next_index != len(self.slugs)):
            raise JournalError("JOURNAL_INCOMPLETE")
        self.failed = True
        _validate_sha(final_snapshot_sha256)
        ended = _stamp(completed_at)
        manifest = _read_file(self.directory / "manifest.json")
        if ended < _stamp(manifest.get("runStartedAt")):
            raise JournalError("JOURNAL_TIME_INVALID")
        final = {
            "schemaVersion": 1,
            "runId": manifest["runId"],
            "entryCount": self.next_index,
            "headDigest": self.previous_digest,
            "finalSnapshotSha256": final_snapshot_sha256,
            "completedAt": ended.isoformat(timespec="seconds"),
            "automaticResumeAuthorized": False,
            "markProcessedAuthorized": False,
            "mergeAuthorized": False,
            "publicationAuthorized": False,
        }
        _write_new(self.directory / "complete.json", final)
        self.finished = True
        return self.previous_digest


def inspect_run(private_parent: Path, run_id: str) -> dict:
    """Read-only check. Incomplete/corrupt runs never become automatic retries."""
    _validate_id(run_id)
    path = Path(private_parent)
    _strict_dir(path)
    directory = path.resolve(strict=True) / ("run-" + run_id)
    _strict_dir(directory)
    manifest = _read_file(directory / "manifest.json")
    selected = _validate_slugs(manifest.get("selectedSlugs"))
    if (manifest.get("schemaVersion") != 1 or manifest.get("runId") != run_id
        or manifest.get("automaticResumeAuthorized") is not False
        or manifest.get("markProcessedAuthorized") is not False
        or manifest.get("mergeAuthorized") is not False
        or manifest.get("publicationAuthorized") is not False):
        raise JournalError("JOURNAL_MANIFEST_INVALID")
    _validate_sha(manifest.get("baseSha"), commit=True)
    _validate_sha(manifest.get("selectionSha256"))
    _validate_sha(manifest.get("officialUrlsSha256"))
    start = _stamp(manifest.get("runStartedAt"))
    names = []
    try:
        names = [entry.name for entry in directory.iterdir()]
    except OSError:
        raise JournalError("JOURNAL_READ_FAILED") from None
    allowed = {"manifest.json", "complete.json"} | {
        f"receipt-{index:02d}.json" for index in range(len(selected))}
    if any(name not in allowed for name in names):
        raise JournalError("JOURNAL_UNEXPECTED_RECORD")
    head = _EMPTY
    last_time = start
    count = 0
    for index, slug in enumerate(selected):
        if f"receipt-{index:02d}.json" not in names:
            if any(f"receipt-{i:02d}.json" in names for i in range(index + 1, len(selected))):
                raise JournalError("JOURNAL_RECEIPT_GAP")
            break
        entry = _read_file(directory / f"receipt-{index:02d}.json")
        payload = entry.get("payload")
        if (not isinstance(payload, dict)
            or set(entry) != {"payload", "digest"}
            or set(payload) != {"index", "previousDigest", "receipt"}
            or type(payload["index"]) is not int
            or payload["index"] != index
            or payload["previousDigest"] != head
            or not isinstance(payload["receipt"], dict)
            or set(payload["receipt"]) != {"slug", "exitCode", "capturedAt",
                                          "statusSha256", "profileSha256"}
            or payload["receipt"]["slug"] != slug
            or payload["receipt"]["exitCode"] != 0
            or type(payload["receipt"]["exitCode"]) is not int
            or entry.get("digest") != _digest(payload)):
            raise JournalError("JOURNAL_CHAIN_INVALID")
        _validate_sha(payload["receipt"].get("statusSha256"))
        _validate_sha(payload["receipt"].get("profileSha256"))
        receipt_time = _stamp(payload["receipt"].get("capturedAt"))
        if receipt_time < last_time:
            raise JournalError("JOURNAL_TIME_INVALID")
        last_time = receipt_time
        head = entry["digest"]
        count += 1
    if "complete.json" not in names:
        return {
            "state": "incomplete", "runId": run_id, "recordedCompanies": count,
            "requiredCompanies": len(selected), "manualTriageRequired": True,
            "automaticResumeAuthorized": False, "mergeAuthorized": False,
        }
    completed = _read_file(directory / "complete.json")
    if (count != len(selected) or completed.get("schemaVersion") != 1
        or completed.get("runId") != run_id or completed.get("entryCount") != count
        or completed.get("headDigest") != head
        or completed.get("automaticResumeAuthorized") is not False
        or completed.get("markProcessedAuthorized") is not False
        or completed.get("mergeAuthorized") is not False
        or completed.get("publicationAuthorized") is not False):
        raise JournalError("JOURNAL_COMPLETION_INVALID")
    _validate_sha(completed.get("finalSnapshotSha256"))
    if _stamp(completed.get("completedAt")) < last_time:
        raise JournalError("JOURNAL_TIME_INVALID")
    return {
        "state": "recorded", "runId": run_id, "recordedCompanies": count,
        "requiredCompanies": len(selected), "journalHeadSha256": head,
        "finalSnapshotSha256": completed["finalSnapshotSha256"],
        "manualReviewRequired": True, "automaticResumeAuthorized": False,
        "markProcessedAuthorized": False, "mergeAuthorized": False,
        "publicationAuthorized": False, "externalIntegrityAttested": False,
    }
