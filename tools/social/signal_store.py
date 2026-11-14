"""Transactional private content/versions/provenance; no production replacement.

Batch tombstones and query receipts survive explicit retention. Re-importing a
previously committed batch cannot resurrect removed, unpinned historical text.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from .batch import ROOT, VerifiedBatch, private_root, verify_payloads
from .contracts import CONTENT_FIELDS, ContractError, assert_safe, canonical_bytes, digest
from .guard import GuardError, output_path
from .identity import identity_facts, merge_facts

DB_NAME = "signals.sqlite3"
APPLICATION_ID = 1447252785
MIGRATION = Path(__file__).parent / "migrations/001_signals.sql"
TABLES = ("batches", "attempts", "signals", "versions", "observations", "aliases", "evidence_pins", "retention_events")


class StoreError(ContractError):
    pass


def stamp(value=None):
    if value is None:
        return datetime.now(UTC).isoformat(timespec="microseconds")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None: raise ValueError
        return parsed.astimezone(UTC).isoformat(timespec="microseconds")
    except (ValueError, AttributeError, OverflowError):
        raise StoreError("store_timestamp") from None


def sql_error(exc):
    return StoreError("store_busy" if getattr(exc, "sqlite_errorcode", None) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED} else "store_database_error")


def db_path(root, roots):
    for suffix in ("", "-journal", "-wal", "-shm"):
        candidate = output_path(root, DB_NAME + suffix, repo_roots=roots)
        if candidate.exists() and os.name == "posix" and candidate.stat().st_mode & 0o077:
            raise GuardError("private_database_permissions_required")
    return output_path(root, DB_NAME, repo_roots=roots)


class SignalStore:
    def __init__(self, state_dir, *, repo_roots=(ROOT,), readonly=False, timeout=5):
        self.roots = tuple(repo_roots)
        self.root = private_root(state_dir, self.roots)
        self.path = db_path(self.root, self.roots)
        self.readonly = readonly
        if not self.path.exists():
            if readonly: raise StoreError("store_missing")
            try:
                os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600))
            except FileExistsError:
                pass
        db_path(self.root, self.roots)
        self.db = None
        try:
            self.db = sqlite3.connect("file:" + quote(str(self.path), safe="/") + ("?mode=ro" if readonly else "?mode=rw"), uri=True, timeout=timeout, isolation_level=None)
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.execute("PRAGMA trusted_schema=OFF")
            migration = MIGRATION.read_text(encoding="utf-8")
            expected = hashlib.sha256(migration.encode()).hexdigest()
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            app = self.db.execute("PRAGMA application_id").fetchone()[0]
            tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if version == 0 and app == 0 and not tables and not readonly:
                self.db.execute("PRAGMA journal_mode=DELETE")
                self.db.execute("PRAGMA synchronous=FULL")
                # Only repository-owned SQL and a locally computed hex digest.
                self.db.executescript("BEGIN IMMEDIATE;\n" + migration +
                    "\nINSERT INTO storage_meta VALUES(1,'" + expected + "');\nPRAGMA application_id=" + str(APPLICATION_ID) + ";\nPRAGMA user_version=1;\nCOMMIT;")
            elif version != 1 or app != APPLICATION_ID or tables != set(TABLES) | {"storage_meta"}:
                raise StoreError("store_schema_version")
            if self.db.execute("SELECT migration_hash FROM storage_meta WHERE singleton=1").fetchone()[0] != expected:
                raise StoreError("store_migration_mismatch")
            if readonly:
                self.db.execute("PRAGMA query_only=ON")
            else:
                self.db.execute("PRAGMA journal_mode=DELETE")
                self.db.execute("PRAGMA synchronous=FULL")
        except BaseException as exc:
            if self.db is not None:
                self.db.close()
            if isinstance(exc, sqlite3.Error): raise sql_error(exc) from None
            raise

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def transaction(self):
        if self.readonly: raise StoreError("store_readonly")
        db_path(self.root, self.roots)
        try:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.execute("COMMIT")
            except BaseException:
                if self.db.in_transaction: self.db.execute("ROLLBACK")
                raise
        except sqlite3.Error as exc:
            raise sql_error(exc) from None

    def counts(self):
        return {name: self.db.execute("SELECT COUNT(*) FROM " + name).fetchone()[0] for name in TABLES}

    def get_signal(self, signal_id):
        row = self.db.execute("SELECT * FROM signals WHERE signal_id=?", (signal_id,)).fetchone()
        if not row: return None
        return {"signalId": signal_id, "firstSeenAt": row["first_seen"], "lastSeenAt": row["last_seen"],
                "latest": json.loads(row["latest_json"]), "identity": json.loads(row["identity_json"]),
                "aliases": [r[0] for r in self.db.execute("SELECT alias FROM aliases WHERE signal_id=? ORDER BY alias", (signal_id,))]}

    def _add_observation(self, doc):
        identity, native = doc["signalId"], identity_facts(doc)
        payload = canonical_bytes(doc).decode()
        moment = stamp(doc["observedAt"])
        latest_key = moment + "|" + doc["attemptId"] + "|" + digest(doc)
        current = self.db.execute("SELECT * FROM signals WHERE signal_id=?", (identity,)).fetchone()
        if current:
            if (current["platform"], current["native_id"], current["content_type"]) != (doc["platform"], doc["nativeId"], doc["contentType"]):
                raise StoreError("store_identity_conflict")
            native = merge_facts(json.loads(current["identity_json"]), native)
            newer = latest_key > current["latest_key"]
            self.db.execute("""UPDATE signals SET identity_json=?,first_seen=?,last_seen=?,latest_key=?,latest_hash=?,latest_json=? WHERE signal_id=?""",
                (canonical_bytes(native).decode(), min(moment, current["first_seen"]), max(moment, current["last_seen"]),
                 latest_key if newer else current["latest_key"], doc["contentHash"] if newer else current["latest_hash"],
                 payload if newer else current["latest_json"], identity))
        else:
            self.db.execute("INSERT INTO signals VALUES(?,?,?,?,?,?,?,?,?,?)", (identity, doc["platform"], doc["nativeId"], doc["contentType"],
                canonical_bytes(native).decode(), moment, moment, latest_key, doc["contentHash"], payload))
        known = {r[0] for r in self.db.execute("SELECT alias FROM aliases WHERE signal_id=?", (identity,))}
        if doc["platform"] == "bili" and known and doc["nativeAliases"] and known != set(doc["nativeAliases"]):
            raise StoreError("store_aid_alias_conflict")
        for alias in doc["nativeAliases"]:
            previous = self.db.execute("SELECT signal_id FROM aliases WHERE platform=? AND alias=?", (doc["platform"], alias)).fetchone()
            if previous and previous[0] != identity: raise StoreError("store_alias_identity_conflict")
            self.db.execute("INSERT OR IGNORE INTO aliases VALUES(?,?,?)", (doc["platform"], alias, identity))
        content = canonical_bytes({key: doc[key] for key in CONTENT_FIELDS}).decode()
        old = self.db.execute("SELECT content_json FROM versions WHERE signal_id=? AND content_hash=?", (identity, doc["contentHash"])).fetchone()
        if old and old[0] != content: raise StoreError("store_content_hash_conflict")
        self.db.execute("""INSERT INTO versions VALUES(?,?,?,?,?) ON CONFLICT(signal_id,content_hash)
            DO UPDATE SET first_seen=MIN(first_seen,excluded.first_seen),last_seen=MAX(last_seen,excluded.last_seen)""",
            (identity, doc["contentHash"], content, moment, moment))
        observation_id = digest({"attemptId": doc["attemptId"], "signalId": identity})
        self.db.execute("INSERT INTO observations VALUES(?,?,?,?,?,?,?)", (observation_id, doc["attemptId"], identity, doc["contentHash"], moment, digest(doc), payload))

    def import_batch(self, bundle):
        if not isinstance(bundle, VerifiedBatch): raise StoreError("verified_batch_required")
        checked = verify_payloads(bundle.manifest_bytes, dict(bundle.payloads))
        manifest, fingerprint = checked.manifest, checked.fingerprint
        jobs, receipts = checked.records("jobs.jsonl"), checked.records("query_receipts.jsonl")
        observations = checked.records("observations.jsonl")
        receipt_map = {r["attemptId"]: r for r in receipts}
        with self.transaction():
            previous = self.db.execute("SELECT manifest_hash FROM batches WHERE run_id=?", (manifest["runId"],)).fetchone()
            if previous:
                if previous[0] != fingerprint: raise StoreError("store_run_conflict")
                return {"ok": True, "duplicate": True, "batchIntegrityChecked": True,
                        "insertedSignals": 0, "insertedVersions": 0, "insertedObservations": 0, "manifestHash": fingerprint}
            before = self.counts()
            self.db.execute("INSERT INTO batches VALUES(?,?,?,?)", (manifest["runId"], fingerprint, checked.manifest_bytes.decode(), stamp()))
            for job in jobs:
                if self.db.execute("SELECT 1 FROM attempts WHERE attempt_id=?", (job["attemptId"],)).fetchone():
                    raise StoreError("store_attempt_reuse")
                self.db.execute("INSERT INTO attempts VALUES(?,?,?,?,?)", (job["attemptId"], job["runId"], job["queryId"],
                    canonical_bytes(job).decode(), canonical_bytes(receipt_map[job["attemptId"]]).decode()))
            for doc in sorted(observations, key=lambda d: (stamp(d["observedAt"]), d["attemptId"], d["signalId"])):
                self._add_observation(doc)
            after = self.counts()
        return {"ok": True, "duplicate": False, "batchIntegrityChecked": True,
                "insertedSignals": after["signals"] - before["signals"], "insertedVersions": after["versions"] - before["versions"],
                "insertedObservations": after["observations"] - before["observations"], "manifestHash": fingerprint}

    def pin_evidence(self, reference_id, signal_id, content_hash):
        assert_safe([reference_id, signal_id, content_hash])
        if not isinstance(reference_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:._-]{0,199}", reference_id):
            raise StoreError("store_reference_id")
        with self.transaction():
            previous = self.db.execute("SELECT signal_id,content_hash FROM evidence_pins WHERE reference_id=?", (reference_id,)).fetchone()
            if previous:
                if tuple(previous) != (signal_id, content_hash): raise StoreError("store_reference_conflict")
                return False
            if not self.db.execute("SELECT 1 FROM versions WHERE signal_id=? AND content_hash=?", (signal_id, content_hash)).fetchone():
                raise StoreError("store_evidence_missing")
            self.db.execute("INSERT INTO evidence_pins VALUES(?,?,?,?)", (reference_id, signal_id, content_hash, stamp()))
        return True

    def retention_plan(self, before):
        cutoff = stamp(before)
        if cutoff > stamp(): raise StoreError("retention_future_cutoff")
        rows = self.db.execute("""SELECT v.signal_id,v.content_hash,v.last_seen,
            (SELECT COUNT(*) FROM observations o WHERE o.signal_id=v.signal_id AND o.content_hash=v.content_hash) AS observations
            FROM versions v JOIN signals s ON s.signal_id=v.signal_id
            WHERE v.last_seen < ? AND v.content_hash != s.latest_hash
              AND NOT EXISTS(SELECT 1 FROM evidence_pins p WHERE p.signal_id=v.signal_id AND p.content_hash=v.content_hash)
            ORDER BY v.signal_id,v.content_hash""", (cutoff,)).fetchall()
        result = {"cutoff": cutoff, "candidates": [dict(row) for row in rows]}
        return {**result, "planHash": digest(result), "versions": len(rows), "observations": sum(r["observations"] for r in rows)}

    def apply_retention(self, before, expected_plan_hash):
        with self.transaction():
            plan = self.retention_plan(before)
            if plan["planHash"] != expected_plan_hash: raise StoreError("retention_stale_plan")
            for row in plan["candidates"]:
                self.db.execute("DELETE FROM versions WHERE signal_id=? AND content_hash=?", (row["signal_id"], row["content_hash"]))
            self.db.execute("INSERT OR IGNORE INTO retention_events VALUES(?,?,?,?,?)", (plan["planHash"], plan["cutoff"], stamp(), plan["versions"], plan["observations"]))
        return {"ok": True, "applied": True, "versionsRemoved": plan["versions"], "observationsRemoved": plan["observations"], "planHash": plan["planHash"]}
