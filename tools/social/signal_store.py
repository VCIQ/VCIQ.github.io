"""Private transactional content store sharing the scheduler's guarded SQLite DB."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .contracts import ContractError, canonical_bytes, digest
from .guard import output_path
from .identity import checked_aliases, observation_id
from .scheduler import instant
from .scheduler_state import SchedulerStore

MIGRATION = Path(__file__).with_name("migrations") / "001_signals.sql"


def timestamp(value):
    return instant(value).isoformat(timespec="microseconds")


class SignalStore(SchedulerStore):
    def __init__(self, state_dir, *, repo_roots):
        super().__init__(state_dir, repo_roots=repo_roots)
        try:
            exists = self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='social_content_schema'").fetchone()
            if exists and [row[0] for row in self.db.execute("SELECT version FROM social_content_schema")] != [1]:
                raise ContractError("unsupported_content_migration")
            self.db.executescript("BEGIN IMMEDIATE;\n" + MIGRATION.read_text(encoding="utf-8") + "\nCOMMIT;")
        except BaseException:
            self.close()
            raise

    def counts(self):
        tables = {"batches": "social_batches", "attempts": "social_content_attempts", "signals": "social_content_signals",
                  "revisions": "social_content_revisions", "observations": "social_content_observations", "aliases": "social_content_aliases"}
        return {key: self.db.execute("SELECT count(*) FROM " + table).fetchone()[0] for key, table in tables.items()}

    def import_validated(self, batch, *, now=None):
        from .batch import validate_links
        validate_links(batch["jobs"], batch["observations"], batch["receipts"], run_id=batch["manifest"]["runId"])
        grouped = {job["attemptId"]: [] for job in batch["jobs"]}
        for row in batch["observations"]:
            grouped[row["attemptId"]].append(row)
        receipts = {row["attemptId"]: row for row in batch["receipts"]}
        imported = (now or datetime.now(UTC)).isoformat()
        with self.transaction():
            before = self.counts()
            if self.db.execute("SELECT 1 FROM social_batches WHERE batch_hash=?", (batch["batchHash"],)).fetchone():
                return {"changed": False, "batchHash": batch["batchHash"], "insertedObservations": 0, "counts": before}
            for job in batch["jobs"]:
                attempt, receipt = job["attemptId"], receipts[job["attemptId"]]
                payload_hash = digest({"job": job, "receipt": receipt, "observations": grouped[attempt]})
                prior = self.db.execute("SELECT payload_hash FROM social_content_attempts WHERE attempt_id=?", (attempt,)).fetchone()
                if prior and prior[0] != payload_hash:
                    raise ContractError("content_attempt_conflict")
                self.db.execute("INSERT OR IGNORE INTO social_content_attempts VALUES(?,?,?,?)",
                    (attempt, payload_hash, canonical_bytes(job).decode(), canonical_bytes(receipt).decode()))
                self.db.execute("INSERT INTO social_batch_attempts VALUES(?,?)", (batch["batchHash"], attempt))
            for row in batch["observations"]:
                oid, sid, chash = observation_id(row), row["signalId"], row["contentHash"]
                observed = timestamp(row["observedAt"])
                payload = canonical_bytes(row).decode()
                prior = self.db.execute("SELECT payload FROM social_content_observations WHERE observation_id=?", (oid,)).fetchone()
                if prior and prior[0] != payload:
                    raise ContractError("observation_payload_conflict")
                self.db.execute("INSERT OR IGNORE INTO social_content_observations VALUES(?,?,?,?,?,?)",
                    (oid, row["attemptId"], sid, chash, observed, payload))
                self.db.execute("""INSERT INTO social_content_revisions VALUES(?,?,?,?,?)
                    ON CONFLICT(signal_id,content_hash) DO UPDATE SET
                    first_seen=min(first_seen,excluded.first_seen),last_seen=max(last_seen,excluded.last_seen)""",
                    (sid, chash, payload, observed, observed))
                current = self.db.execute("SELECT * FROM social_content_signals WHERE signal_id=?", (sid,)).fetchone()
                if current is None:
                    self.db.execute("INSERT INTO social_content_signals VALUES(?,?,?,?,?,?,?,?)",
                        (sid, row["platform"], row["nativeId"], row["contentType"], observed, observed, chash, oid))
                else:
                    newer = (observed, oid) > (current["last_seen"], current["current_observation"])
                    self.db.execute("UPDATE social_content_signals SET first_seen=?,last_seen=?,current_hash=?,current_observation=? WHERE signal_id=?",
                        (min(current["first_seen"], observed), max(current["last_seen"], observed), chash if newer else current["current_hash"],
                         oid if newer else current["current_observation"], sid))
                for alias in checked_aliases(row):
                    prior_alias = self.db.execute("SELECT signal_id FROM social_content_aliases WHERE alias=?", (alias,)).fetchone()
                    if prior_alias and prior_alias[0] != sid:
                        raise ContractError("alias_conflict_requires_review")
                    self.db.execute("INSERT OR IGNORE INTO social_content_aliases VALUES(?,?,?)", (alias, sid, oid))
            self.db.execute("INSERT INTO social_batches VALUES(?,?,?,?)",
                (batch["batchHash"], batch["manifest"]["runId"], canonical_bytes(batch["manifest"]).decode(), imported))
            after = self.counts()
            return {"changed": True, "batchHash": batch["batchHash"], "insertedObservations": after["observations"] - before["observations"], "counts": after}

    def latest(self):
        rows = self.db.execute("""SELECT o.payload FROM social_content_signals s JOIN social_content_observations o
            ON s.current_observation=o.observation_id ORDER BY s.signal_id""")
        return [json.loads(row[0]) for row in rows]

    def resolve_alias(self, alias):
        row = self.db.execute("SELECT signal_id FROM social_content_aliases WHERE alias=?", (alias,)).fetchone()
        return row[0] if row else None

    def evidence(self, signal_id, content_hash):
        row = self.db.execute("SELECT payload FROM social_content_revisions WHERE signal_id=? AND content_hash=?", (signal_id, content_hash)).fetchone()
        return json.loads(row[0]) if row else None

    def backup(self):
        path = output_path(self.root, f"backups/content-{uuid4()}.sqlite3", repo_roots=self.roots)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.close(fd)
        connection = sqlite3.connect(path)
        try:
            self.db.backup(connection)
        finally:
            connection.close()
        return path
