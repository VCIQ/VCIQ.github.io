"""Synthetic review fixtures; no real company claim or account data."""
from uuid import uuid4

from tests.social_storage_fixtures import sample, SEALED_AT
from tools.social.batch import build_batch
from tools.social.contracts import content_hash
from tools.social.lead_builder import company_index


def rows(*, title="合成测试机器人 融资", at="2026-10-23T12:00:00Z", platform="xhs", excerpt="测试材料，真实性未核验。"):
    values = sample(platform, at=at, keyword="机器人")
    doc = values[2][0]
    doc.update(title=title, excerpt=excerpt, titleOrigin="upstream", matchedTerms=["机器人"])
    doc["contentHash"] = content_hash(doc)
    return values


def add(source, values=None):
    values = values or rows()
    source.import_batch(build_batch(*values, created_at=SEALED_AT))
    return values[2][0]


def registry(*companies):
    return company_index({"companies": list(companies)})


def request(item, decision="accepted"):
    return {"schemaVersion": 1, "kind": "decision_request", "requestId": str(uuid4()),
        "candidateKey": item["candidateKey"], "candidateFingerprint": item["candidateFingerprint"],
        "decision": decision, "reviewedBy": "synthetic-reviewer", "note": "只接受为待核验线索，不确认事实。",
        "seenQueueVersion": item["queueVersion"]}
