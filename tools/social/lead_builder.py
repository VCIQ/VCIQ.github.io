"""Deterministic discovery-only leads. Labels/mentions never confirm an event or entity."""
from __future__ import annotations

import copy
import json
import re
import unicodedata

from .contracts import ContractError, assert_safe, digest, validate

VERSION = "social-review-v1"
MAX_SIGNALS = 5000
MAX_CANDIDATES = 2000
MARKERS = {
    "funding": ("融资", "投资", "funding", "financing"),
    "product": ("发布", "新产品", "量产", "launch"),
    "technology": ("技术", "论文", "专利", "开源", "research"),
    "listing": ("上市", "招股", "ipo", "辅导备案"),
}


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def mentioned(term, text):
    needle, haystack = normalized(term), normalized(text)
    if len(needle) < 2: return False
    if re.fullmatch(r"[a-z0-9 ._-]+", needle):
        return re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", haystack) is not None
    return needle in haystack


def company_index(payload):
    """Only names/slugs/explicit aliases from the existing registry are consumed."""
    if not isinstance(payload, dict) or not isinstance(payload.get("companies"), list) or len(payload["companies"]) > 10000:
        raise ContractError("review_company_registry")
    result, seen = [], set()
    for row in payload["companies"]:
        if not isinstance(row, dict): raise ContractError("review_company_registry")
        slug, name = row.get("slug"), row.get("name")
        if not isinstance(slug, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}", slug) or slug in seen:
            raise ContractError("review_company_identity")
        aliases = row.get("aliases", [])
        if not isinstance(aliases, list): raise ContractError("review_company_aliases")
        values = [name, *aliases]
        if row.get("englishName"): values.append(row["englishName"])
        if any(not isinstance(v, str) or not v.strip() or len(v) > 200 for v in values):
            raise ContractError("review_company_name")
        assert_safe(values)
        seen.add(slug)
        result.append({"slug": slug, "name": name, "aliases": sorted(set(values))})
    return sorted(result, key=lambda row: row["slug"])


def fingerprint(item):
    return digest({key: item[key] for key in ("leadId", "leadType", "candidateKey", "revisionKey", "subject", "claims", "evidence", "evidenceClass")})


def validate_item(item):
    validate(item, expected_kind="review_item")
    if item["candidateKey"] != "shadow-social:" + item["leadId"] + ":" + item["revisionKey"] or item["candidateFingerprint"] != fingerprint(item):
        raise ContractError("review_fingerprint")
    return item


def build_leads(document, registry):
    doc = copy.deepcopy(validate(document, expected_kind="signal_observation"))
    text = (doc["title"] + " " + doc["excerpt"]).strip()
    suggestions = [{"companyId": row["slug"], "companyName": row["name"],
        "matchedAliases": [alias for alias in row["aliases"] if mentioned(alias, text)]}
        for row in registry]
    suggestions = [row for row in suggestions if row["matchedAliases"]]
    if len(suggestions) > 50: raise ContractError("review_entity_suggestions_limit")
    if not text or not (suggestions or any(mentioned(term, text) for term in doc["matchedTerms"])):
        return []
    # A unique textual mention is still not an attribution of the claim to that company.
    subject = {"companyId": None, "companyName": suggestions[0]["companyName"] if len(suggestions) == 1 else None,
               "resolution": "ambiguous" if len(suggestions) > 1 else "unresolved"}
    kinds = [kind for kind, words in MARKERS.items() if any(mentioned(word, text) for word in words)] or ["company_discovery"]
    evidence = [{"signalId": doc["signalId"], "contentHash": doc["contentHash"], "canonicalUrl": doc["canonicalUrl"],
                 "publishedAt": doc["publishedAt"], "level": "待交叉验证"}]
    claims = ["原始材料摘录（真实性及主体归属未核验）：" + text[:350]]
    result = []
    for kind in kinds:
        lead_id = digest({"signalId": doc["signalId"], "leadType": kind})
        revision = digest({"builder": VERSION, "leadId": lead_id, "subject": subject,
                           "claims": claims, "evidence": evidence, "suggestions": suggestions})
        item = {"schemaVersion": 1, "kind": "review_item", "leadId": lead_id, "leadType": kind,
            "candidateKey": "shadow-social:" + lead_id + ":" + revision, "revisionKey": revision,
            "subject": subject, "claims": claims, "evidence": evidence, "status": "pending",
            "evidenceClass": "discovery-only", "promotionStatus": "not-reviewed", "queueVersion": "0" * 64}
        item["candidateFingerprint"] = fingerprint(item)
        snapshot = {"observation": doc, "companySuggestions": suggestions,
            "classification": "literal-keyword-heuristic", "factVerified": False, "entityConfirmed": False}
        result.append({"item": validate_item(item), "snapshot": snapshot})
    return result


def select_leads(source, registry):
    """Read the content database inside the caller's snapshot/transaction."""
    if source.db.execute("SELECT COUNT(*) FROM signals").fetchone()[0] > MAX_SIGNALS:
        raise ContractError("review_signal_limit")
    proposals = []
    for row in source.db.execute("SELECT latest_json FROM signals ORDER BY signal_id"):
        proposals.extend(build_leads(json.loads(row[0]), registry))
        if len(proposals) > MAX_CANDIDATES: raise ContractError("review_candidate_limit")
    return sorted(proposals, key=lambda row: row["item"]["candidateKey"])


def proposal_hash(proposals):
    # Observation time, engagement and unrelated registry additions do not cause re-review.
    return digest([(row["item"]["candidateKey"], row["item"]["candidateFingerprint"]) for row in proposals])
