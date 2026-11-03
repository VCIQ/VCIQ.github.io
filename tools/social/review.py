"""Fingerprint-bound private decisions. Final decisions are append-only."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from .contracts import ContractError, canonical_bytes, digest, validate
from .innovation_bridge import check_listing_decision
from .lead_builder import build_leads, verify_fingerprint

DDL = """
CREATE TABLE IF NOT EXISTS social_review_items (
 candidate_key TEXT PRIMARY KEY, lead_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
 payload TEXT NOT NULL, status TEXT NOT NULL, active INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS social_review_decisions (
 candidate_key TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, decision TEXT NOT NULL,
 reviewed_by TEXT NOT NULL, note TEXT NOT NULL, decided_at TEXT NOT NULL, fingerprint TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS social_review_requests (
 request_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, payload TEXT NOT NULL, result TEXT NOT NULL
);
"""


def initialize(store):
    store.db.executescript(DDL)


def _queue(store, *, updates=None):
    rows = [json.loads(row[0]) for row in store.db.execute("SELECT payload FROM social_review_items WHERE active=1 ORDER BY candidate_key")]
    version = digest([{key: item[key] for key in ("candidateKey", "candidateFingerprint", "status")} for item in rows])
    for item in rows:
        item["queueVersion"] = version
        verify_fingerprint(item)
    return {"schemaVersion": 1, "mode": "shadow", "publish": False, "queueVersion": version,
            "candidates": rows, "existingProjectUpdates": updates or [], "liveEvidenceVerified": False}


def build_review_queue(store, production_snapshot=None):
    initialize(store)
    with store.transaction():
        candidates, updates = build_leads(store.latest(), production_snapshot)
        store.db.execute("UPDATE social_review_items SET active=0")
        for item in candidates:
            prior = store.db.execute("SELECT status FROM social_review_items WHERE candidate_key=?", (item["candidateKey"],)).fetchone()
            if prior:
                item["status"] = prior[0]
                item["promotionStatus"] = {"pending": "not-reviewed", "accepted": "awaiting-primary-evidence", "rejected": "rejected"}[prior[0]]
            verify_fingerprint(item)
            for evidence in item["evidence"]:
                if store.evidence(evidence["signalId"], evidence["contentHash"]) is None:
                    raise ContractError("review_evidence_missing")
                store.db.execute("INSERT OR IGNORE INTO social_evidence_refs VALUES(?,?,?)",
                    (item["candidateKey"], evidence["signalId"], evidence["contentHash"]))
            store.db.execute("""INSERT INTO social_review_items VALUES(?,?,?,?,?,1)
                ON CONFLICT(candidate_key) DO UPDATE SET payload=excluded.payload,active=1""",
                (item["candidateKey"], item["leadId"], item["candidateFingerprint"], canonical_bytes(item).decode(), item["status"]))
        return _queue(store, updates=updates)


def current_queue(store):
    initialize(store)
    with store.transaction():
        return _queue(store)


def apply_shadow_decision(store, request, *, now=None):
    validate(request, expected_kind="decision_request")
    if not request["reviewedBy"].strip():
        raise ContractError("review_actor_required")
    initialize(store)
    request_hash = digest(request)
    with store.transaction():
        prior_request = store.db.execute("SELECT * FROM social_review_requests WHERE request_id=?", (request["requestId"],)).fetchone()
        if prior_request:
            if prior_request["request_hash"] != request_hash:
                raise ContractError("review_request_conflict")
            return {**json.loads(prior_request["result"]), "changed": False, "replayed": True}
        row = store.db.execute("SELECT * FROM social_review_items WHERE candidate_key=?", (request["candidateKey"],)).fetchone()
        if row is None or not row["active"]:
            raise ContractError("review_candidate_stale")
        item = json.loads(row["payload"])
        verify_fingerprint(item)
        if request["candidateFingerprint"] != row["fingerprint"]:
            raise ContractError("review_candidate_stale")
        for evidence in item["evidence"]:
            current = store.db.execute("SELECT current_hash FROM social_content_signals WHERE signal_id=?", (evidence["signalId"],)).fetchone()
            if current is None or current[0] != evidence["contentHash"]:
                raise ContractError("review_evidence_changed_rebuild_queue")
        if row["status"] not in {"pending", request["decision"]}:
            raise ContractError("review_final_decision_immutable")
        changed = row["status"] == "pending"
        if changed:
            check_listing_decision(item, request, now=now)
            item["status"] = request["decision"]
            item["promotionStatus"] = "awaiting-primary-evidence" if item["status"] == "accepted" else "rejected"
            decided = (now or datetime.now(UTC)).astimezone(UTC).isoformat()
            store.db.execute("INSERT INTO social_review_decisions VALUES(?,?,?,?,?,?,?)",
                (item["candidateKey"], request["requestId"], item["status"], request["reviewedBy"], request["note"], decided, item["candidateFingerprint"]))
            cursor = store.db.execute("UPDATE social_review_items SET status=?,payload=? WHERE candidate_key=? AND status='pending' AND fingerprint=?",
                (item["status"], canonical_bytes(item).decode(), item["candidateKey"], item["candidateFingerprint"]))
            if cursor.rowcount != 1:
                raise ContractError("review_compare_and_swap_failed")
        receipt = {"ok": True, "changed": changed, "replayed": False, "candidateKey": item["candidateKey"],
            "decision": item["status"], "promotionStatus": item["promotionStatus"], "publish": False, "productionModified": False}
        store.db.execute("INSERT INTO social_review_requests VALUES(?,?,?,?)",
            (request["requestId"], request_hash, canonical_bytes(request).decode(), canonical_bytes(receipt).decode()))
        return receipt
