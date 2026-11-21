"""Private immutable review ledger. Pin first; no production promotion or network."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from .batch import ROOT, private_root
from .contracts import ContractError, assert_safe, canonical_bytes, digest, validate
from .guard import GuardError, output_path
from .innovation_bridge import final_decision
from .lead_builder import build_leads, fingerprint, proposal_hash, select_leads, validate_item
from .signal_store import stamp

DB_NAME = "reviews.sqlite3"
APPLICATION_ID = 1447252786
MIGRATION = Path(__file__).parent / "migrations/001_reviews.sql"
TABLES = {"review_meta", "candidates", "decisions", "requests"}


class ReviewError(ContractError):
    pass


def db_path(root, roots):
    for suffix in ("", "-journal", "-wal", "-shm"):
        path = output_path(root, DB_NAME + suffix, repo_roots=roots)
        if path.exists() and os.name == "posix" and path.stat().st_mode & 0o077:
            raise GuardError("private_review_permissions_required")
    return output_path(root, DB_NAME, repo_roots=roots)


def pin_reference(item, evidence):
    return "social-review:" + digest({"candidateKey": item["candidateKey"], "signalId": evidence["signalId"], "contentHash": evidence["contentHash"]})


class ReviewStore:
    def __init__(self, state_dir, *, repo_roots=(ROOT,), readonly=False, timeout=5):
        self.roots, self.readonly = tuple(repo_roots), readonly
        self.root = private_root(state_dir, self.roots)
        path = db_path(self.root, self.roots)
        if not path.exists():
            if readonly: raise ReviewError("review_store_missing")
            try: os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600))
            except FileExistsError: pass
        db_path(self.root, self.roots)
        self.db = None
        try:
            self.db = sqlite3.connect("file:" + quote(str(path), safe="/") + ("?mode=ro" if readonly else "?mode=rw"), uri=True, timeout=timeout, isolation_level=None)
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
                self.db.executescript("BEGIN IMMEDIATE;\n" + migration + "\nINSERT INTO review_meta VALUES(1,'" + expected + "');\nPRAGMA application_id=" + str(APPLICATION_ID) + ";\nPRAGMA user_version=1;\nCOMMIT;")
            elif version != 1 or app != APPLICATION_ID or tables != TABLES:
                raise ReviewError("review_store_schema")
            meta = self.db.execute("SELECT migration_hash FROM review_meta WHERE singleton=1").fetchone()
            if not meta or meta[0] != expected: raise ReviewError("review_migration_mismatch")
            if readonly: self.db.execute("PRAGMA query_only=ON")
            else:
                self.db.execute("PRAGMA journal_mode=DELETE")
                self.db.execute("PRAGMA synchronous=FULL")
        except BaseException as exc:
            if self.db is not None: self.db.close()
            if isinstance(exc, sqlite3.Error): raise ReviewError("review_database_error") from None
            raise

    def close(self): self.db.close()
    def __enter__(self): return self
    def __exit__(self, *_): self.close()

    @contextmanager
    def transaction(self):
        if self.readonly: raise ReviewError("review_readonly")
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
            code = "review_busy" if getattr(exc, "sqlite_errorcode", None) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED} else "review_database_error"
            raise ReviewError(code) from None

    def queue_version(self):
        rows = self.db.execute("""SELECT c.candidate_key,c.fingerprint,COALESCE(d.decision,'pending')
            FROM candidates c LEFT JOIN decisions d USING(candidate_key) WHERE c.active=1 ORDER BY c.candidate_key""").fetchall()
        return digest([list(row) for row in rows])

    def _write_item(self, proposal):
        item, snapshot = proposal["item"], proposal["snapshot"]
        validate_item(item); assert_safe(snapshot)
        if len(canonical_bytes(snapshot)) > 128 * 1024: raise ReviewError("review_snapshot_limit")
        previous = self.db.execute("SELECT item_json FROM candidates WHERE candidate_key=?", (item["candidateKey"],)).fetchone()
        payload = canonical_bytes(item).decode()
        if previous and previous[0] != payload: raise ReviewError("review_revision_conflict")
        self.db.execute("""INSERT INTO candidates VALUES(?,?,?,?,?,1,?) ON CONFLICT(candidate_key) DO UPDATE SET active=1""",
            (item["candidateKey"], item["leadId"], item["candidateFingerprint"], payload, canonical_bytes(snapshot).decode(), stamp()))

    def materialize(self, source, registry):
        if self.readonly: raise ReviewError("review_readonly")
        if source.root != self.root: raise ReviewError("review_state_mismatch")
        with source.transaction(): proposals = select_leads(source, registry)
        initial = proposal_hash(proposals)
        # Cross-database protocol deliberately fails safe: orphan pins may remain
        # after interruption, but a visible review can never reference unpinned text.
        for proposal in proposals:
            for evidence in proposal["item"]["evidence"]:
                source.pin_evidence(pin_reference(proposal["item"], evidence), evidence["signalId"], evidence["contentHash"])
        # Consistent lock order: content first, review second. Retention/import
        # cannot race this final current-evidence check and queue publication.
        with source.transaction():
            if initial != proposal_hash(select_leads(source, registry)):
                raise ReviewError("review_source_changed")
            with self.transaction():
                before = self.queue_version()
                self.db.execute("UPDATE candidates SET active=0")
                for proposal in proposals: self._write_item(proposal)
                after = self.queue_version()
        return {"ok": True, "candidateCount": len(proposals), "queueVersion": after,
                "changed": before != after, "evidencePinned": True, "productionChanged": False}

    def view(self, *, offset=0, limit=50, history=False):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ReviewError("review_page_bounds")
        own = not self.db.in_transaction
        if own: self.db.execute("BEGIN")
        try:
            version = self.queue_version()
            where = "c.active=0" if history else "c.active=1"
            total = self.db.execute("SELECT COUNT(*) FROM candidates c WHERE " + where).fetchone()[0]
            rows = self.db.execute("""SELECT c.*,d.decision,d.request_json,d.decided_at,d.result_json
                FROM candidates c LEFT JOIN decisions d USING(candidate_key) WHERE """ + where +
                " ORDER BY c.candidate_key LIMIT ? OFFSET ?", (limit, offset)).fetchall()
            result = []
            for row in rows:
                item = json.loads(row["item_json"])
                item["queueVersion"] = version
                if row["decision"]:
                    item["status"] = row["decision"]
                    item["promotionStatus"] = "awaiting-primary-evidence" if row["decision"] == "accepted" else "rejected"
                validate_item(item)
                snapshot = json.loads(row["snapshot_json"])
                validate(snapshot["observation"], expected_kind="signal_observation")
                decision = None if not row["decision"] else {"request": json.loads(row["request_json"]), "decidedAt": row["decided_at"]}
                result.append({"item": item, "snapshot": snapshot, "decision": decision, "active": bool(row["active"])})
            response = {"ok": True, "mode": "shadow", "publish": False, "queueVersion": version,
                "history": history, "offset": offset, "total": total, "nextOffset": offset + limit if offset + limit < total else None, "items": result}
            assert_safe(response)
            return response
        finally:
            if own: self.db.execute("ROLLBACK")

    def decide(self, source, registry, request, *, apply=False):
        validate(request, expected_kind="decision_request")
        if not request["reviewedBy"].strip() or request["reviewedBy"] != request["reviewedBy"].strip():
            raise ReviewError("review_actor_required")
        if source.root != self.root: raise ReviewError("review_state_mismatch")
        if self.readonly and apply: raise ReviewError("review_readonly")
        # Preview may open both databases read-only; actual writes acquire content
        # lock first so evidence cannot change between validation and decision.
        source_context = source.transaction() if apply else read_transaction(source.db)
        review_context = self.transaction() if apply else read_transaction(self.db)
        with source_context, review_context:
            previous = self.db.execute("SELECT request_hash,result_json FROM requests WHERE request_id=?", (request["requestId"],)).fetchone()
            if previous:
                if previous[0] != digest(request): raise ReviewError("review_request_id_conflict")
                return {**json.loads(previous[1]), "changed": False, "replayed": True, "applied": apply}
            row = self.db.execute("SELECT * FROM candidates WHERE candidate_key=?", (request["candidateKey"],)).fetchone()
            if not row or not row["active"]: raise ReviewError("review_candidate_stale")
            item = validate_item(json.loads(row["item_json"]))
            if item["candidateFingerprint"] != request["candidateFingerprint"]: raise ReviewError("review_evidence_changed")
            # Check live stored content even when no queue rebuild has happened yet.
            evidence = item["evidence"][0]
            current = source.get_signal(evidence["signalId"])
            rebuilt = build_leads(current["latest"], registry) if current else []
            if not any(p["item"]["candidateFingerprint"] == item["candidateFingerprint"] for p in rebuilt):
                raise ReviewError("review_evidence_changed")
            for evidence in item["evidence"]:
                pinned = source.db.execute("SELECT signal_id,content_hash FROM evidence_pins WHERE reference_id=?", (pin_reference(item, evidence),)).fetchone()
                if not pinned or tuple(pinned) != (evidence["signalId"], evidence["contentHash"]):
                    raise ReviewError("review_evidence_not_pinned")
            persisted = self.db.execute("SELECT * FROM decisions WHERE candidate_key=?", (item["candidateKey"],)).fetchone()
            if persisted:
                if persisted["decision"] != request["decision"]: raise ReviewError("review_final_decision_conflict")
                result = {**json.loads(persisted["result_json"]), "changed": False, "replayed": True, "applied": apply}
            else:
                if request["seenQueueVersion"] != self.queue_version(): raise ReviewError("review_queue_stale")
                result = {"ok": True, "changed": True, "replayed": False, "applied": apply,
                    "candidateKey": item["candidateKey"], "candidateFingerprint": item["candidateFingerprint"],
                    **final_decision(item, request, now=datetime.now(UTC))}
                if apply:
                    self.db.execute("INSERT INTO decisions VALUES(?,?,?,?,?,?)", (item["candidateKey"], item["candidateFingerprint"],
                        request["decision"], canonical_bytes(request).decode(), stamp(), canonical_bytes(result).decode()))
            if apply:
                self.db.execute("INSERT INTO requests VALUES(?,?,?)", (request["requestId"], digest(request), canonical_bytes(result).decode()))
            return result


@contextmanager
def read_transaction(db):
    own = not db.in_transaction
    if own: db.execute("BEGIN")
    try: yield
    finally:
        if own: db.execute("ROLLBACK")
