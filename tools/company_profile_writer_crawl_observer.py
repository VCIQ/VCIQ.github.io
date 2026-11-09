"""Opt-in, non-deployed observer for selected-company crawl subprocesses.

This module is NOT wired into production Actions and has no CLI.  A future
reviewed orchestrator must supply an authenticated, isolated checkout, its
Git-pinned selection, a trustworthy command runner and a bounded job clock.
The observer checks process results and hashes the immediate per-slug output,
then verifies the final snapshot with the existing offline receipt gate.

A subprocess exit code or SHA-256 digest cannot attest the external HTTP
response, runner identity, or the provenance of caller-supplied metadata.
Even a passing observation never authorizes mark-processed, merge or publish.
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from .company_profile_writer_crawl_receipt import (
    CrawlReceiptError,
    MAX_RUN_DURATION,
    MAX_SELECTED,
    SLUG,
    _host,
    _time,
    check_selected_crawl_receipts,
    stable_sha256,
)

PROFILE_PATH = Path("public/data/venture_profiles.json")
MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024
MAX_COMMAND_SECONDS = 600
RUN_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,119}\Z")
COMMIT_SHA = re.compile(r"[0-9a-f]{40}\Z")


class ObservedCrawlError(ValueError):
    """Stable error code only; never include source URLs or subprocess output."""


def _strict_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ObservedCrawlError("CRAWL_OBSERVER_DUPLICATE_JSON_KEY")
        value[key] = item
    return value


def _reject_constant(_):
    raise ObservedCrawlError("CRAWL_OBSERVER_NONFINITE_JSON")


def _snapshot(root: Path) -> dict:
    target = root / PROFILE_PATH
    if any(part.is_symlink() for part in (
        root, root / "public", root / "public/data", target
    )):
        raise ObservedCrawlError("CRAWL_OBSERVER_SYMLINK_SNAPSHOT")
    # Nonblocking open is necessary: opening a FIFO can block before fstat.
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        fd = os.open(target, flags)
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ObservedCrawlError("CRAWL_OBSERVER_NOT_REGULAR_FILE")
            raw = stream.read(MAX_SNAPSHOT_BYTES + 1)
    except ObservedCrawlError:
        raise
    except (OSError, ValueError):
        raise ObservedCrawlError("CRAWL_OBSERVER_SNAPSHOT_UNREADABLE") from None
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise ObservedCrawlError("CRAWL_OBSERVER_SNAPSHOT_OVERSIZED")
    try:
        doc = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except ObservedCrawlError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise ObservedCrawlError("CRAWL_OBSERVER_SNAPSHOT_INVALID") from None
    if (not isinstance(doc, dict)
        or not isinstance(doc.get("companies"), dict)
        or not isinstance(doc.get("sourceStatus"), list)
        or not isinstance(doc.get("qualityGate"), dict)):
        raise ObservedCrawlError("CRAWL_OBSERVER_SCHEMA_INVALID")
    return doc


def _company_rows(snapshot: dict, slug: str) -> tuple[dict, dict]:
    profile = snapshot["companies"].get(slug)
    rows = [
        row for row in snapshot["sourceStatus"]
        if isinstance(row, dict)
        and row.get("kind") == "company"
        and row.get("slug") == slug
    ]
    if not isinstance(profile, dict) or len(rows) != 1:
        raise ObservedCrawlError("CRAWL_OBSERVER_COMPANY_EVIDENCE_MISSING")
    return profile, rows[0]


def _timestamp(clock) -> str:
    try:
        observed = clock()
        if not isinstance(observed, datetime) or observed.tzinfo is None:
            raise ValueError()
        return observed.astimezone(UTC).isoformat(timespec="seconds")
    except (ValueError, TypeError, OverflowError, OSError):
        raise ObservedCrawlError("CRAWL_OBSERVER_CLOCK_INVALID") from None


def crawl_argv(slug: str) -> tuple[str, ...]:
    """One fixed executable/module; ignore Python env and user site packages."""
    if type(slug) is not str or not SLUG.fullmatch(slug):
        raise ObservedCrawlError("CRAWL_OBSERVER_SELECTION_INVALID")
    return (sys.executable, "-E", "-s", "-B", "-m", "tools.crawl_venture_profiles",
            "--kind", "company", "--slug", slug,
            "--workers", "1", "--max-pages", "6")


def _verify_receipts(selected, urls, snapshot, receipts, started, ended):
    try:
        return check_selected_crawl_receipts(
            list(selected), urls, snapshot, receipts,
            run_started_at=started, run_completed_at=ended,
        )
    except CrawlReceiptError as exc:
        code = str(exc)
        if not re.fullmatch(r"CRAWL_RECEIPT_[A-Z_]{1,80}", code):
            code = "CRAWL_OBSERVER_RECEIPT_INVALID"
        raise ObservedCrawlError(code) from None


def observe_selected_company_crawls(
    *,
    checkout_root: Path,
    pre_crawl_selection: dict,
    pinned_official_urls: dict,
    base_sha: str,
    run_id: str,
    run_started_at: str,
    run_command,
    clock,
    authorized: bool = False,
) -> dict:
    """Capture exact subprocess exit status and immediate post-crawl digests.

    No implicit subprocess runner or CLI is provided.  The caller owns the
    trusted executor, selection provenance, run identity, rollback and receipt
    persistence.  Unit tests inject a fake runner that never contacts sources.
    """
    if authorized is not True:
        raise ObservedCrawlError("CRAWL_OBSERVER_NOT_AUTHORIZED")
    if (not isinstance(base_sha, str) or not COMMIT_SHA.fullmatch(base_sha)
        or not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id)):
        raise ObservedCrawlError("CRAWL_OBSERVER_IDENTITY_INVALID")
    if not isinstance(pre_crawl_selection, dict):
        raise ObservedCrawlError("CRAWL_OBSERVER_SELECTION_INVALID")
    # Do not let an injected runner or another caller mutate the selection
    # or official-source mapping while the observer is iterating over it.
    try:
        raw = json.dumps([pre_crawl_selection, pinned_official_urls], allow_nan=False)
        if len(raw.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
            raise ValueError()
        pre_crawl_selection, pinned_official_urls = json.loads(raw)
    except (TypeError, ValueError, RecursionError):
        raise ObservedCrawlError("CRAWL_OBSERVER_SELECTION_INVALID") from None
    selected = pre_crawl_selection.get("selectedSlugs")
    if (not isinstance(selected, list) or not 1 <= len(selected) <= MAX_SELECTED
        or len(set(map(str, selected))) != len(selected)
        or any(type(slug) is not str or not SLUG.fullmatch(slug)
               for slug in selected)
        or type(pre_crawl_selection.get("selectedCount")) is not int
        or pre_crawl_selection["selectedCount"] != len(selected)
        or not isinstance(pinned_official_urls, dict)
        or set(pinned_official_urls) != set(selected)):
        raise ObservedCrawlError("CRAWL_OBSERVER_SELECTION_INVALID")
    try:
        for slug in selected:
            _host(pinned_official_urls[slug])
        started = _time(run_started_at)
        selection_at = _time(pre_crawl_selection.get("generatedAt"))
    except (CrawlReceiptError, TypeError, ValueError):
        raise ObservedCrawlError("CRAWL_OBSERVER_SOURCE_OR_TIME_INVALID") from None
    if selection_at < started:
        raise ObservedCrawlError("CRAWL_OBSERVER_STALE_SELECTION")
    try:
        root = Path(checkout_root)
        if root.is_symlink() or not root.is_dir():
            raise ValueError()
        root = root.resolve(strict=True)
        if not (root / "tools/crawl_venture_profiles.py").is_file():
            raise ValueError()
    except (TypeError, ValueError, OSError):
        raise ObservedCrawlError("CRAWL_OBSERVER_CHECKOUT_INVALID") from None
    if not callable(run_command) or not callable(clock):
        raise ObservedCrawlError("CRAWL_OBSERVER_RUNNER_INVALID")

    current = _time(_timestamp(clock))
    if not started <= selection_at <= current or current - started > MAX_RUN_DURATION:
        raise ObservedCrawlError("CRAWL_OBSERVER_RUN_WINDOW_INVALID")

    receipts = []
    for slug in selected:
        command_started_at = _timestamp(clock)
        command_started = _time(command_started_at)
        remaining = (started + MAX_RUN_DURATION - command_started).total_seconds()
        if command_started < current or remaining < 1:
            raise ObservedCrawlError("CRAWL_OBSERVER_RUN_WINDOW_INVALID")
        before = _snapshot(root)
        before_profile = before["companies"].get(slug)
        before_digest = stable_sha256(before_profile) if isinstance(before_profile, dict) else None
        command = crawl_argv(slug)
        try:
            process = run_command(command, cwd=root,
                                  timeout=min(MAX_COMMAND_SECONDS, int(remaining)))
        except Exception:
            raise ObservedCrawlError("CRAWL_OBSERVER_PROCESS_FAILED") from None
        if (not isinstance(process, subprocess.CompletedProcess)
            or not isinstance(process.args, (list, tuple))
            or tuple(process.args) != command
            or type(process.returncode) is not int
            or process.returncode != 0):
            raise ObservedCrawlError("CRAWL_OBSERVER_PROCESS_FAILED")

        # Hash before proceeding to the next slug: later jobs must not alter
        # any selected status/profile without making final verification fail.
        after = _snapshot(root)
        profile, status = _company_rows(after, slug)
        digest = stable_sha256(profile)
        if digest == before_digest:
            raise ObservedCrawlError("CRAWL_OBSERVER_UNCHANGED_PROFILE")
        captured_at = _timestamp(clock)
        captured = _time(captured_at)
        if captured < command_started or captured - started > MAX_RUN_DURATION:
            raise ObservedCrawlError("CRAWL_OBSERVER_RUN_WINDOW_INVALID")
        receipt = {
            "slug": slug,
            "exitCode": process.returncode,
            "capturedAt": captured_at,
            "statusSha256": stable_sha256(status),
            "profileSha256": digest,
        }
        # Check this company before any later command, using its command
        # window rather than merely the much wider whole-job window.
        _verify_receipts([slug], {slug: pinned_official_urls[slug]}, after,
                         [receipt], command_started_at, captured_at)
        receipts.append(receipt)
        _verify_receipts(selected[:len(receipts)],
                         {s: pinned_official_urls[s] for s in selected[:len(receipts)]},
                         after, receipts, run_started_at, captured_at)
        current = captured

    final_snapshot = _snapshot(root)
    completed = _timestamp(clock)
    if _time(completed) < current:
        raise ObservedCrawlError("CRAWL_OBSERVER_RUN_WINDOW_INVALID")
    verification = _verify_receipts(selected, pinned_official_urls, final_snapshot,
                                     receipts, run_started_at, completed)
    return {
        "ok": True,
        "runId": run_id,
        "baseSha": base_sha,
        "selectionSha256": stable_sha256(pre_crawl_selection),
        "officialUrlsSha256": stable_sha256(pinned_official_urls),
        "runStartedAt": started.isoformat(timespec="seconds"),
        "runCompletedAt": completed,
        "receipts": receipts,
        "verifiedCompanyCount": verification["verifiedCompanyCount"],
        "markProcessedAuthorized": False,
        "mergeAuthorized": False,
        "publicationAuthorized": False,
        "sourceFetchCryptographicallyAttested": False,
    }
