#!/usr/bin/env python3
"""Apply one final human review decision to an innovation-listing candidate.

The human decision is immutable and fingerprint-bound. Accepted means the
candidate has passed the one required human review. It does not bypass factual
quality gates: the formal innovation_listing_watchlist remains unchanged until
an automated evidence/promotion step can validate the required listing facts.

Rejected candidates remain rejected even if later discovery sees the same
evidence again. A changed candidate fingerprint requires a fresh review.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_PATH = ROOT / "config" / "innovation_listing_candidate_review_queue.json"
DECISIONS_PATH = ROOT / "config" / "innovation_listing_candidate_decisions.json"

VALID_ACTIONS = {"accepted", "rejected"}
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")


class InnovationListingReviewError(ValueError):
    pass


def clean(value: Any, limit: int = 2_000) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InnovationListingReviewError(
            f"{path.name} is missing; wait for the discovery queue to be generated"
        ) from exc
    if not isinstance(payload, dict):
        raise InnovationListingReviewError(f"{path.name} must contain a JSON object")
    return payload


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0).isoformat()


def candidate_index(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("candidates", [])
    if not isinstance(rows, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = clean(row.get("decisionKey"), 320)
        if key:
            result[key] = row
    return result


def decision_index(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("decisions", {})
    if not isinstance(rows, dict):
        return {}
    return {
        clean(key, 320): value
        for key, value in rows.items()
        if clean(key, 320) and isinstance(value, dict)
    }


def validate_request(
    *,
    candidate_key: Any,
    candidate_fingerprint: Any,
    decision: Any,
    note: Any,
    reviewed_by: Any,
) -> dict[str, str]:
    key = clean(candidate_key, 320)
    if len(key) < 3:
        raise InnovationListingReviewError("candidate key is invalid")

    fingerprint = clean(candidate_fingerprint, 64).casefold()
    if not FINGERPRINT_RE.fullmatch(fingerprint):
        raise InnovationListingReviewError(
            "candidate fingerprint must be a SHA-256 hex digest"
        )

    action = clean(decision, 30).casefold()
    if action not in VALID_ACTIONS:
        raise InnovationListingReviewError("decision must be accepted or rejected")

    public_note = clean(note, 600)
    if len(public_note) < 2:
        public_note = (
            "人工确认该项目应继续进入自动证据校验；不需要第二次人工审核。"
            if action == "accepted"
            else "人工确认该发现不应进入科创项目储备池。"
        )

    actor = clean(reviewed_by, 160)
    if not actor or "@" in actor:
        raise InnovationListingReviewError(
            "reviewedBy must be a public audit actor label, not an email address"
        )

    return {
        "candidateKey": key,
        "candidateFingerprint": fingerprint,
        "decision": action,
        "note": public_note,
        "reviewedBy": actor,
    }


def apply_decision(
    candidates_payload: Mapping[str, Any],
    decisions_payload: Mapping[str, Any],
    request: Mapping[str, str],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = candidate_index(candidates_payload)
    candidate = candidates.get(request["candidateKey"])
    if candidate is None:
        raise InnovationListingReviewError(
            "candidate is no longer present in the innovation listing review queue"
        )

    current_status = clean(candidate.get("status"), 30) or "pending"
    persisted = decision_index(decisions_payload).get(request["candidateKey"])
    if current_status != "pending":
        if (
            persisted
            and clean(persisted.get("status"), 30) == request["decision"]
            and clean(persisted.get("candidateFingerprint"), 64)
            == request["candidateFingerprint"]
        ):
            return copy.deepcopy(dict(decisions_payload)), {
                "ok": True,
                "changed": False,
                "decision": request["decision"],
                "candidateKey": request["candidateKey"],
                "company": clean(candidate.get("company"), 240),
                "message": "candidate already has the requested final human decision",
                "promotionStatus": clean(
                    persisted.get("promotionStatus"), 80
                ) or (
                    "awaiting-broker-evidence"
                    if (
                        request["decision"] == "accepted"
                        and clean(candidate.get("candidateClass"), 40)
                        == "mature-opportunity"
                        and not clean(candidate.get("broker"), 160)
                    )
                    else "awaiting-primary-evidence"
                    if request["decision"] == "accepted"
                    else "rejected"
                ),
            }
        raise InnovationListingReviewError(
            f"candidate is no longer pending; current status is {current_status}"
        )

    actual_fingerprint = clean(candidate.get("candidateFingerprint"), 64).casefold()
    if actual_fingerprint != request["candidateFingerprint"]:
        raise InnovationListingReviewError(
            "candidate evidence changed; refresh the candidate before reviewing"
        )

    if persisted:
        existing_status = clean(persisted.get("status"), 30)
        if existing_status in VALID_ACTIONS:
            raise InnovationListingReviewError(
                f"candidate already has immutable decision {existing_status}"
            )

    root = copy.deepcopy(dict(decisions_payload))
    root["schemaVersion"] = max(1, int(root.get("schemaVersion", 1) or 1))
    if not isinstance(root.get("decisions"), dict):
        root["decisions"] = {}

    evidence_class = clean(candidate.get("evidenceClass"), 40)
    candidate_class = clean(candidate.get("candidateClass"), 40) or "listing-candidate"
    broker = clean(candidate.get("broker"), 160)
    promotion_status = (
        "awaiting-broker-evidence"
        if (
            request["decision"] == "accepted"
            and candidate_class == "mature-opportunity"
            and not broker
        )
        else "ready-for-mechanical-promotion"
        if request["decision"] == "accepted" and evidence_class == "primary-backed"
        else "awaiting-primary-evidence"
        if request["decision"] == "accepted"
        else "rejected"
    )
    root["decisions"][request["candidateKey"]] = {
        "status": request["decision"],
        "note": request["note"],
        "decidedAt": now_iso(now),
        "reviewedBy": request["reviewedBy"],
        "candidateFingerprint": request["candidateFingerprint"],
        "promotionStatus": promotion_status,
        "evidenceClassAtReview": evidence_class or "discovery-only",
    }

    return root, {
        "ok": True,
        "changed": True,
        "decision": request["decision"],
        "candidateKey": request["candidateKey"],
        "company": clean(candidate.get("company"), 240),
        "broker": clean(candidate.get("broker"), 160),
        "promotionStatus": promotion_status,
        "message": (
            "final human acceptance recorded; only mechanical evidence gates remain"
            if request["decision"] == "accepted"
            else "final human rejection recorded"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["validate", "apply"], required=True)
    parser.add_argument("--candidate-key", required=True)
    parser.add_argument("--candidate-fingerprint", required=True)
    parser.add_argument("--decision", choices=sorted(VALID_ACTIONS), required=True)
    parser.add_argument("--note", default="")
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES_PATH)
    parser.add_argument("--decisions", type=Path, default=DECISIONS_PATH)
    args = parser.parse_args()

    request = validate_request(
        candidate_key=args.candidate_key,
        candidate_fingerprint=args.candidate_fingerprint,
        decision=args.decision,
        note=args.note,
        reviewed_by=args.reviewed_by,
    )
    decisions, report = apply_decision(
        load_json(args.candidates),
        load_json(args.decisions),
        request,
    )
    if args.mode == "apply" and report["changed"]:
        write_json(args.decisions, decisions)
    report["mode"] = args.mode
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
