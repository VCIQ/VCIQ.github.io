"""Explicit GC; current content and any review-referenced revision are protected."""
from datetime import UTC, datetime, timedelta
from .contracts import ContractError


def collect(store, *, now=None, days=90, apply=False):
    if type(days) is not int or days < 1:
        raise ContractError("invalid_retention")
    cutoff = ((now or datetime.now(UTC)) - timedelta(days=days)).astimezone(UTC).isoformat(timespec="microseconds")
    with store.transaction():
        rows = store.db.execute("""SELECT r.signal_id,r.content_hash FROM social_content_revisions r
            JOIN social_content_signals s ON s.signal_id=r.signal_id
            WHERE r.last_seen<? AND r.content_hash<>s.current_hash
            AND NOT EXISTS(SELECT 1 FROM social_evidence_refs e WHERE e.signal_id=r.signal_id AND e.content_hash=r.content_hash)
            ORDER BY r.signal_id,r.content_hash""", (cutoff,)).fetchall()
        candidates = [{"signalId": row[0], "contentHash": row[1]} for row in rows]
        if apply:
            for row in rows:
                # Receipts and batch audit records remain immutable.
                store.db.execute("DELETE FROM social_content_observations WHERE signal_id=? AND content_hash=?", tuple(row))
                store.db.execute("DELETE FROM social_content_revisions WHERE signal_id=? AND content_hash=?", tuple(row))
        return {"dryRun": not apply, "eligibleRevisions": len(candidates), "deletedRevisions": len(candidates) if apply else 0,
                "protectedCurrentAndReviewed": True, "candidates": candidates}
