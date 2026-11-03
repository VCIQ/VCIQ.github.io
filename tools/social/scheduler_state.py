"""Private SQLite leases/checkpoints. Receipts and next-due state commit together."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from .contracts import ContractError, assert_safe, canonical_bytes, digest, validate
from .guard import GuardError, output_path, state_path
from .scheduler import instant, utc

DDL = """
CREATE TABLE IF NOT EXISTS social_query_state (
 query_id TEXT PRIMARY KEY, platform TEXT NOT NULL, provider TEXT NOT NULL,
 entry TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
 last_attempt TEXT, last_success TEXT, last_covered TEXT, next_due TEXT,
 failures INTEGER NOT NULL DEFAULT 0, lease_attempt TEXT, lease_until TEXT,
 lease_job TEXT
);
CREATE TABLE IF NOT EXISTS social_platform_state (
 platform TEXT PRIMARY KEY, lease_attempt TEXT, lease_until TEXT,
 pause_reason TEXT, pause_until TEXT
);
CREATE TABLE IF NOT EXISTS social_query_results (
 attempt_id TEXT PRIMARY KEY, query_id TEXT NOT NULL, result_hash TEXT NOT NULL,
 result TEXT NOT NULL, completed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS social_wechat_quota (
 id TEXT PRIMARY KEY, window_start TEXT NOT NULL, window_end TEXT NOT NULL,
 grant_hash TEXT NOT NULL, available INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS social_request_usage (
 attempt_id TEXT PRIMARY KEY, requests INTEGER NOT NULL DEFAULT 0
);
"""


def _db_path(state_dir: Path, roots: tuple[Path, ...]) -> Path:
    for suffix in ("", "-journal", "-wal", "-shm"):
        output_path(state_dir, "state.sqlite3" + suffix, repo_roots=roots)
    return output_path(state_dir, "state.sqlite3", repo_roots=roots)


def _snapshot(connection: sqlite3.Connection) -> dict:
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "social_query_state" not in tables:
        return {"queries": {}, "platforms": {}}
    queries = {}
    for row in connection.execute("SELECT * FROM social_query_state"):
        queries[row["query_id"]] = {"active": bool(row["active"]), "lastAttemptAt": row["last_attempt"],
            "lastSuccessAt": row["last_success"], "lastCoveredAt": row["last_covered"],
            "nextDueAt": row["next_due"], "consecutiveFailures": row["failures"],
            "leaseUntil": row["lease_until"], "leaseAttemptId": row["lease_attempt"]}
    platforms = {row["platform"]: {"pauseReason": row["pause_reason"], "pauseUntil": row["pause_until"],
                 "leaseAttemptId": row["lease_attempt"], "leaseUntil": row["lease_until"]}
                 for row in connection.execute("SELECT * FROM social_platform_state")}
    return {"queries": queries, "platforms": platforms}


def read_state(state_dir: Path | str, *, repo_roots: tuple[Path, ...]) -> dict:
    root = state_path(state_dir, repo_roots=repo_roots)
    path = _db_path(root, repo_roots)
    if not path.exists():
        return {"queries": {}, "platforms": {}}
    connection = sqlite3.connect("file:" + quote(str(path), safe="/") + "?mode=ro", uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        return _snapshot(connection)
    finally:
        connection.close()


class SchedulerStore:
    def __init__(self, state_dir: Path | str, *, repo_roots: tuple[Path, ...]):
        self.roots = repo_roots
        self.root = state_path(state_dir, repo_roots=repo_roots)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name == "posix" and self.root.stat().st_mode & 0o077:
            raise GuardError("private_state_permissions_required")
        self.path = _db_path(self.root, self.roots)
        if not self.path.exists():
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                os.close(os.open(self.path, flags, 0o600))
            except FileExistsError:
                pass
        _db_path(self.root, self.roots)
        if os.name == "posix" and self.path.stat().st_mode & 0o077:
            raise GuardError("private_database_permissions_required")
        self.db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(DDL)

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def transaction(self):
        _db_path(self.root, self.roots)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    def sync(self, registry) -> None:
        with self.transaction():
            for platform, provider in registry.scope:
                self.db.execute("UPDATE social_query_state SET active=0 WHERE platform=? AND provider=?", (platform, provider))
            for entry in registry.entries:
                assert_safe(entry)
                self.db.execute("""INSERT INTO social_query_state(query_id,platform,provider,entry,active)
                    VALUES(?,?,?,?,?) ON CONFLICT(query_id) DO UPDATE SET entry=excluded.entry,active=excluded.active""",
                    (entry["queryId"], entry["platform"], entry["provider"], canonical_bytes(entry).decode(), int(not entry["excludedReason"])))

    def snapshot(self) -> dict:
        return _snapshot(self.db)

    def claim(self, job: dict, now: datetime) -> bool:
        validate(job, expected_kind="crawl_job")
        stamp = utc(now)
        expires = utc(instant(stamp) + timedelta(seconds=job["limits"]["maxWallSeconds"] + 30))
        with self.transaction():
            if self.db.execute("SELECT 1 FROM social_query_results WHERE attempt_id=?", (job["attemptId"],)).fetchone():
                return False
            row = self.db.execute("SELECT * FROM social_query_state WHERE query_id=?", (job["queryId"],)).fetchone()
            if row is None or not row["active"]:
                raise ContractError("unregistered_query")
            entry = json.loads(row["entry"])
            if entry["query"] != job["query"] or entry["trackRefs"] != job["trackRefs"]:
                raise ContractError("stale_query_plan")
            if (row["lease_until"] and instant(row["lease_until"]) > instant(stamp)) or (row["next_due"] and instant(row["next_due"]) > instant(stamp)):
                return False
            self.db.execute("INSERT OR IGNORE INTO social_platform_state(platform) VALUES(?)", (job["platform"],))
            platform = self.db.execute("SELECT * FROM social_platform_state WHERE platform=?", (job["platform"],)).fetchone()
            if platform["pause_reason"] and (not platform["pause_until"] or instant(platform["pause_until"]) > instant(stamp)):
                return False
            if platform["lease_until"] and instant(platform["lease_until"]) > instant(stamp):
                return False
            self.db.execute("UPDATE social_query_state SET lease_attempt=?,lease_until=?,lease_job=?,last_attempt=? WHERE query_id=?",
                            (job["attemptId"], expires, canonical_bytes(job).decode(), stamp, job["queryId"]))
            self.db.execute("UPDATE social_platform_state SET lease_attempt=?,lease_until=? WHERE platform=?",
                            (job["attemptId"], expires, job["platform"]))
        return True

    def finish(self, job: dict, result: dict, now: datetime, *, cadence_hours: int) -> bool:
        receipt = validate(result["receipt"], expected_kind="query_receipt")
        assert_safe(result)
        if set(result) != {"receipt", "observations", "hints", "diagnostics"}:
            raise ContractError("result_fields")
        for key in ("jobId", "queryId", "runId", "attemptId", "platform", "provider", "upstreamCommit"):
            if receipt[key] != job[key]:
                raise ContractError("receipt_job_mismatch")
        if receipt["counts"]["emittedRows"] != len(result["observations"]):
            raise ContractError("observation_count")
        for observation in result["observations"]:
            validate(observation, expected_kind="signal_observation")
            if any(observation[k] != job[k] for k in ("jobId", "queryId", "runId", "attemptId", "platform")):
                raise ContractError("observation_job_mismatch")
        if cadence_hours < 1:
            raise ContractError("invalid_cadence")
        payload = canonical_bytes(result).decode()
        hashed = digest(result)
        stamp = utc(now)
        with self.transaction():
            previous = self.db.execute("SELECT result_hash FROM social_query_results WHERE attempt_id=?", (job["attemptId"],)).fetchone()
            if previous:
                if previous[0] != hashed:
                    raise ContractError("attempt_result_conflict")
                return False
            row = self.db.execute("SELECT * FROM social_query_state WHERE query_id=?", (job["queryId"],)).fetchone()
            if row is None or row["lease_attempt"] != job["attemptId"] or instant(row["lease_until"]) < instant(stamp):
                raise ContractError("stale_lease")
            if json.loads(row["lease_job"]) != job:
                raise ContractError("lease_job_mismatch")
            success = receipt["status"] in {"ok", "empty"}
            failures = 0 if success else row["failures"] + 1
            retry_after = result["diagnostics"].get("retryAfterSeconds", 0) or 0
            if type(retry_after) is not int or retry_after < 0:
                raise ContractError("invalid_retry_after")
            delay = cadence_hours * 3600 if success else max(min(86400, 60 * 2 ** min(failures - 1, 11)), retry_after)
            next_due = utc(instant(stamp) + timedelta(seconds=delay))
            self.db.execute("INSERT INTO social_query_results VALUES(?,?,?,?,?)",
                            (job["attemptId"], job["queryId"], hashed, payload, receipt["completedAt"]))
            self.db.execute("""UPDATE social_query_state SET last_success=?,last_covered=?,next_due=?,failures=?,
                lease_attempt=NULL,lease_until=NULL,lease_job=NULL WHERE query_id=?""",
                (stamp if success else row["last_success"], stamp if success else row["last_covered"], next_due, failures, job["queryId"]))
            reason, until = None, None
            if receipt["stopReason"] in {"auth", "verification"}:
                reason = receipt["stopReason"]
            elif receipt["stopReason"] == "rate_limit":
                reason, until = "rate_limit", utc(instant(stamp) + timedelta(seconds=max(300, retry_after)))
            self.db.execute("""UPDATE social_platform_state SET lease_attempt=NULL,lease_until=NULL,
                pause_reason=?,pause_until=? WHERE platform=? AND lease_attempt=?""",
                (reason, until, job["platform"], job["attemptId"]))
        return True

    def resume(self, platform: str, now: datetime) -> None:
        with self.transaction():
            row = self.db.execute("SELECT * FROM social_platform_state WHERE platform=?", (platform,)).fetchone()
            if row and row["lease_until"] and instant(row["lease_until"]) > now:
                raise ContractError("platform_busy")
            if row and row["pause_reason"] == "rate_limit" and row["pause_until"] and instant(row["pause_until"]) > now:
                raise ContractError("retry_after_not_elapsed")
            self.db.execute("UPDATE social_platform_state SET pause_reason=NULL,pause_until=NULL WHERE platform=?", (platform,))

    def consume_request(self, grant: dict, attempt_id: str, now: datetime) -> None:
        expected = {"windowStart", "windowEnd", "combinedMaxRequests", "productionReservedRequests"}
        if set(grant) != expected or any(type(grant[k]) is not int or grant[k] < 0 for k in ("combinedMaxRequests", "productionReservedRequests")):
            raise ContractError("invalid_combined_budget")
        start, end = instant(grant["windowStart"]), instant(grant["windowEnd"])
        if not start <= now < end or (end - start).total_seconds() > 86400:
            raise ContractError("budget_window")
        available = grant["combinedMaxRequests"] - grant["productionReservedRequests"]
        if available < 1 or available > 1000:
            raise ContractError("invalid_combined_budget")
        key = digest({"start": utc(start), "end": utc(end)})
        with self.transaction():
            overlapping = self.db.execute("SELECT id FROM social_wechat_quota WHERE window_start<? AND window_end>? AND id<>?",
                                          (utc(end), utc(start), key)).fetchone()
            if overlapping:
                raise ContractError("overlapping_budget_window")
            self.db.execute("INSERT OR IGNORE INTO social_wechat_quota VALUES(?,?,?,?,?,0)",
                            (key, utc(start), utc(end), digest(grant), available))
            row = self.db.execute("SELECT * FROM social_wechat_quota WHERE id=?", (key,)).fetchone()
            if row["grant_hash"] != digest(grant):
                raise ContractError("budget_grant_changed")
            if row["used"] >= row["available"]:
                raise ContractError("request_budget_exhausted")
            self.db.execute("UPDATE social_wechat_quota SET used=used+1 WHERE id=?", (key,))
            self.db.execute("INSERT INTO social_request_usage VALUES(?,1) ON CONFLICT(attempt_id) DO UPDATE SET requests=requests+1", (attempt_id,))

    def request_count(self, attempt_id: str) -> int:
        row = self.db.execute("SELECT requests FROM social_request_usage WHERE attempt_id=?", (attempt_id,)).fetchone()
        return row[0] if row else 0

    def request_slot(self, now: datetime) -> float:
        """Reserve cross-process spacing; a crash may waste a slot, never speed it up."""
        with self.transaction():
            self.db.execute("CREATE TABLE IF NOT EXISTS social_request_gate (id INTEGER PRIMARY KEY, next_at REAL NOT NULL)")
            row = self.db.execute("SELECT next_at FROM social_request_gate WHERE id=1").fetchone()
            stamp = now.timestamp()
            slot = max(stamp, row[0] if row else stamp)
            self.db.execute("INSERT INTO social_request_gate VALUES(1,?) ON CONFLICT(id) DO UPDATE SET next_at=excluded.next_at", (slot + 1.25,))
            return slot - stamp
