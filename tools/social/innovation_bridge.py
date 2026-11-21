"""Reuse the existing listing decision pure function; never invoke its CLI/writer."""
from __future__ import annotations

from .contracts import ContractError, validate
from .lead_builder import validate_item


def final_decision(item, request, *, now=None):
    validate_item(item)
    validate(request, expected_kind="decision_request")
    if request["candidateKey"] != item["candidateKey"] or request["candidateFingerprint"] != item["candidateFingerprint"]:
        raise ContractError("review_evidence_changed")
    action = request["decision"]
    promotion = "awaiting-primary-evidence" if action == "accepted" else "rejected"
    if item["leadType"] == "listing":
        from tools.innovation_listing_candidate_review import apply_decision, validate_request
        safe = validate_request(candidate_key=request["candidateKey"], candidate_fingerprint=request["candidateFingerprint"],
            decision=action, reviewed_by=request["reviewedBy"], note=request["note"])
        candidates = {"candidates": [{"decisionKey": item["candidateKey"], "candidateFingerprint": item["candidateFingerprint"],
            "status": "pending", "company": item["subject"]["companyName"] or "未消歧主体",
            "candidateClass": "listing-candidate", "evidenceClass": "discovery-only", "broker": ""}]}
        _, result = apply_decision(candidates, {"decisions": {}}, safe, now=now)
        if result["promotionStatus"] != promotion:
            raise ContractError("review_promotion_forbidden")
    # Other lead types are not disguised as IPO candidates or primary-backed sources.
    return {"decision": action, "promotionStatus": promotion, "productionChanged": False,
            "factVerified": False, "entityConfirmed": False}
