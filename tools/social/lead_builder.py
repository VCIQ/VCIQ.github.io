"""Conservative discovery leads: quoted claims, unresolved subjects, no promotion."""
from __future__ import annotations

import re
from .contracts import ContractError, digest, validate

TRIGGERS = {
    "funding": r"融资|投资|募资|funding|financing",
    "product": r"发布|产品|新品|launch|product",
    "technology": r"技术|研究|模型|算法|论文|technology|research|model",
    "listing": r"上市|辅导|科创板|创业板|\bIPO\b|港交所",
}
LEGAL_NAME = re.compile(r"([A-Za-z0-9\u3400-\u9fff（）()·&＋+\-]{2,50}?(?:股份有限公司|有限责任公司|有限公司))")


def factual_projection(item):
    return {"leadId": item["leadId"], "leadType": item["leadType"], "subject": item["subject"],
            "claims": list(item["claims"]),
            "evidence": sorted(item["evidence"], key=lambda row: (row["signalId"], row["contentHash"]))}


def bind_fingerprint(item):
    projection = factual_projection(item)
    revision = digest(projection)
    key = "shadow-social:" + item["leadId"] + ":" + revision
    return {**item, "revisionKey": revision, "candidateKey": key,
            "candidateFingerprint": digest({"candidateKey": key, **projection})}


def verify_fingerprint(item):
    validate(item, expected_kind="review_item")
    expected = bind_fingerprint(item)
    if any(item[key] != expected[key] for key in ("revisionKey", "candidateKey", "candidateFingerprint")):
        raise ContractError("review_fingerprint")


def _subject(row):
    candidates = [item for item in row["entityCandidates"] if item["kind"] == "company"]
    confirmed = [item for item in candidates if item["status"] == "matched" and item["entityId"]]
    if len(confirmed) == 1 and len(candidates) == 1:
        return {"companyId": confirmed[0]["entityId"], "companyName": confirmed[0]["label"], "resolution": "matched"}
    names = list(dict.fromkeys(item["label"] for item in candidates))
    names.extend(name for name in LEGAL_NAME.findall(row["title"] + " " + row["excerpt"]) if name not in names)
    return {"companyId": None, "companyName": names[0] if len(names) == 1 else None,
            "resolution": "ambiguous" if len(names) > 1 or candidates else "unresolved"}


def build_leads(observations, production_snapshot=None):
    snapshot = production_snapshot or {}
    if not isinstance(snapshot, dict):
        raise ContractError("production_snapshot_shape")
    projects = snapshot.get("projects", [])
    if not isinstance(projects, list):
        raise ContractError("production_snapshot_shape")
    known = {str(item.get("id") or item.get("companyId")) for item in projects if isinstance(item, dict) and (item.get("id") or item.get("companyId"))}
    result, updates = {}, []
    for row in observations:
        validate(row, expected_kind="signal_observation")
        visible = " ".join(part for part in (row["title"], row["excerpt"]) if part)
        if not visible:
            continue
        subject = _subject(row)
        if subject["companyId"] in known:
            updates.append({"signalId": row["signalId"], "contentHash": row["contentHash"], "companyId": subject["companyId"], "action": "existing-project-evidence-only"})
            continue
        lead_types = [kind for kind, pattern in TRIGGERS.items() if re.search(pattern, visible, re.IGNORECASE)]
        if subject["companyName"]:
            lead_types.insert(0, "company_discovery")
        for kind in lead_types:
            lead_id = "lead-" + digest({"signalId": row["signalId"], "leadType": kind})[:40]
            item = {"schemaVersion": 1, "kind": "review_item", "leadId": lead_id, "leadType": kind,
                "subject": subject, "claims": [visible[:400]],
                "evidence": [{"signalId": row["signalId"], "contentHash": row["contentHash"],
                    "canonicalUrl": row["canonicalUrl"], "publishedAt": row["publishedAt"], "level": "待交叉验证"}],
                "status": "pending", "evidenceClass": "discovery-only", "promotionStatus": "not-reviewed", "queueVersion": "0" * 64}
            item = bind_fingerprint(item)
            validate(item, expected_kind="review_item")
            result[item["candidateKey"]] = item
    return [result[key] for key in sorted(result)], sorted(updates, key=lambda row: row["signalId"])
