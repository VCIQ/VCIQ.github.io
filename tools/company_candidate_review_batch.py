#!/usr/bin/env python3
"""Apply modern batch company review semantics.

Pending candidates may receive one immutable human identity decision. Candidates
already accepted may later receive a verified-homepage *hint* without changing
the original identity decision. The hint is not a publication override: the
onboarding workflow still fetches the page and verifies identity + sector.
"""

from __future__ import annotations

import argparse
import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

try:
    from . import company_candidate_review_decision as review
except ImportError:  # pragma: no cover
    import company_candidate_review_decision as review  # type: ignore


def apply_batch(
    candidates_payload: Mapping[str, Any],
    decisions_payload: Mapping[str, Any],
    registry_payload: Mapping[str, Any],
    requests: list[Mapping[str, str]],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = review.candidate_index(candidates_payload)
    slugs = review.registry_slugs(registry_payload)
    root = copy.deepcopy(decisions_payload) if isinstance(decisions_payload, Mapping) else {}
    if not isinstance(root, dict):
        root = {}
    root["schemaVersion"] = max(1, int(root.get("schemaVersion", 1) or 1))
    if not isinstance(root.get("decisions"), dict):
        root["decisions"] = {}

    # Atomic preflight: no mutation until every row is valid against its own
    # reviewed evidence fingerprint.
    for request in requests:
        key = request["candidateKey"]
        candidate = candidates.get(key)
        if candidate is None:
            raise review.ReviewDecisionError(f"candidate {key} is no longer present in the review queue")
        expected = request.get("candidateFingerprint", "")
        if expected and review.candidate_review_fingerprint(candidate) != expected:
            raise review.ReviewDecisionError(f"candidate {key} evidence changed; refresh the review queue")
        status = review.clean(candidate.get("status"), 30)
        if status == "pending":
            if request["decision"] == "merged" and request["mergedSlug"] not in slugs:
                raise review.ReviewDecisionError(
                    f"merge target {request['mergedSlug']} does not exist in the company registry"
                )
            continue
        if status == "accepted" and request["decision"] == "accepted" and request.get("homepageHint"):
            existing = review.decision_index(root).get(key)
            if not existing or review.clean(existing[1].get("status"), 30) != "accepted":
                raise review.ReviewDecisionError(f"candidate {key} lacks an immutable accepted decision")
            continue
        raise review.ReviewDecisionError(f"candidate {key} is no longer eligible for this review action")

    reports: list[dict[str, Any]] = []
    timestamp = now or datetime.now(UTC)
    for request in requests:
        key = request["candidateKey"]
        candidate = candidates[key]
        status = review.clean(candidate.get("status"), 30)
        if status == "pending":
            root, report = review._apply_one(  # intentionally reuse the audited single-decision core
                candidates_payload,
                root,
                request,
                now=timestamp,
            )
            reports.append(report)
            continue

        existing = review.decision_index(root)[key]
        raw_key, row = existing
        next_row = copy.deepcopy(row)
        homepage = request.get("homepageHint", "")
        changed = review.clean(next_row.get("homepageHint"), 2_000) != homepage
        if changed:
            next_row["homepageHint"] = homepage
            next_row["homepageHintUpdatedAt"] = review.now_iso(timestamp)
            next_row["homepageHintReviewedBy"] = request["reviewedBy"]
            root["decisions"][raw_key] = next_row
        reports.append(
            {
                "ok": True,
                "changed": changed,
                "candidateKey": key,
                "name": review.clean(candidate.get("name"), 240),
                "decision": "accepted",
                "homepageHint": homepage,
                "message": "homepage hint attached to immutable accepted decision" if changed else "homepage hint already present",
                "requiresOnboarding": True,
            }
        )

    changed_count = sum(1 for report in reports if report.get("changed"))
    return root, {
        "ok": True,
        "changed": changed_count > 0,
        "changedCount": changed_count,
        "decisionCount": len(reports),
        "requiresOnboarding": any(report.get("requiresOnboarding") for report in reports),
        "reports": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["validate", "apply"], required=True)
    parser.add_argument("--batch-json", required=True)
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--candidates", default=str(review.CANDIDATES_PATH))
    parser.add_argument("--decisions", default=str(review.DECISIONS_PATH))
    parser.add_argument("--registry", default=str(review.REGISTRY_PATH))
    args = parser.parse_args()

    try:
        raw_batch = json.loads(args.batch_json)
    except json.JSONDecodeError as exc:
        raise review.ReviewDecisionError("batch JSON is invalid") from exc
    requests = review.validate_review_requests(raw_batch, reviewed_by=args.reviewed_by)
    decisions_path = Path(args.decisions)
    updated, report = apply_batch(
        review.load_json(Path(args.candidates)),
        review.load_json(decisions_path),
        review.load_json(Path(args.registry)),
        requests,
    )
    if args.mode == "apply" and report["changed"]:
        review.write_json(decisions_path, updated)
    report["mode"] = args.mode
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
