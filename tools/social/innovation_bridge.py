"""Pure compatibility projection; never invokes the production review CLI."""
from .contracts import ContractError


def check_listing_decision(item, request, *, now=None):
    if item["leadType"] != "listing":
        return None
    from tools.innovation_listing_candidate_review import apply_decision
    candidate = {"decisionKey": item["candidateKey"], "candidateFingerprint": item["candidateFingerprint"],
        "company": item["subject"]["companyName"] or "待消歧主体", "broker": "", "status": "pending",
        "candidateClass": "listing-candidate", "evidenceClass": "discovery-only"}
    # Independent in-memory payloads. No real queue or decision file is loaded.
    _, receipt = apply_decision({"candidates": [candidate]}, {"decisions": {}},
        {key: request[key] for key in ("candidateKey", "candidateFingerprint", "decision", "reviewedBy", "note")}, now=now)
    expected = "awaiting-primary-evidence" if request["decision"] == "accepted" else "rejected"
    if receipt.get("promotionStatus") != expected:
        raise ContractError("legacy_review_semantics_changed")
    return receipt
