"""Normalize pinned MediaCrawler XHS output into VCIQ discovery observations."""
from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from ..contracts import ContractError, assert_safe, content_hash, validate
from ..scheduler import instant

VERSION = "xhs-shadow-v1"
REASONS = {"auth_required": "auth", "verification_required": "verification",
    "rate_limited": "rate_limit", "network_error": "network", "timeout": "timeout",
    "schema_error": "schema", "unsupported": "unsupported", "cancelled": "cancelled"}


def text(value, limit: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ContractError("xhs_text_type")
    assert_safe(value)
    return " ".join(value.split())[:limit]


def metric(value) -> dict:
    if value in (None, "", "--"):
        return {"value": None, "approximate": False}
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ContractError("xhs_metric_type")
    token = str(value).strip()
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", token):
        token = token.replace(",", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([万亿kKmMwW]?)(\+?)", token)
    if not match:
        return {"value": None, "approximate": False}
    multipliers = {"": 1, "万": 10000, "亿": 100000000, "k": 1000, "m": 1000000, "w": 10000}
    try:
        number = Decimal(match[1]) * multipliers[match[2].lower()]
        if not number.is_finite() or number < 0 or number > 10**15:
            raise ValueError
        count = int(number) if number == int(number) else float(number)
    except (InvalidOperation, ValueError, OverflowError):
        raise ContractError("xhs_metric_range") from None
    return {"value": count, "approximate": bool(match[2] or match[3])}


def milliseconds(value, observed: datetime) -> str | None:
    if value in (None, "", 0, "0"):
        return None
    if isinstance(value, bool) or not (isinstance(value, int) or isinstance(value, str) and value.isdigit()):
        raise ContractError("xhs_timestamp_type")
    number = int(value)
    # Pinned XHS output uses milliseconds. Do not guess seconds by magnitude.
    if not 1_000_000_000_000 <= number <= int(observed.timestamp() * 1000):
        raise ContractError("xhs_timestamp_unit_or_future")
    return datetime.fromtimestamp(number / 1000, UTC).isoformat(timespec="seconds")


def normalize_record(row: dict, job: dict, context: dict, *, observed_at: str, original_title: bool) -> dict:
    validate(job, expected_kind="crawl_job")
    if job["platform"] != "xhs" or not isinstance(row, dict):
        raise ContractError("xhs_record_expected")
    native = row.get("note_id")
    if not isinstance(native, str) or not re.fullmatch(r"[0-9a-fA-F]{24}", native):
        raise ContractError("xhs_native_id")
    observed = instant(observed_at)
    title, excerpt = text(row.get("title"), 220), text(row.get("desc"), 500)
    origin = "upstream" if title and original_title else "derived" if title else "missing"
    if not title and excerpt:
        title, origin = excerpt[:120], "derived"
    terms = sorted({text(item["text"], 500) for item in context["terms"]})
    if not terms or any(not term for term in terms):
        raise ContractError("xhs_query_terms")
    haystack = unicodedata.normalize("NFKC", title + " " + excerpt).casefold()
    matches = []
    for term in terms:
        needle = unicodedata.normalize("NFKC", term).casefold()
        present = bool(re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", haystack)) if re.fullmatch(r"[a-z0-9 ._-]+", needle) else needle in haystack
        if present:
            matches.append(term)
    nickname = text(row.get("nickname"), 120)
    creator = row.get("creator_hash")
    if not isinstance(creator, str) or not re.fullmatch(r"[0-9a-f]{16,128}", creator):
        creator = None
    published = milliseconds(row.get("time"), observed)
    updated = milliseconds(row.get("last_update_time"), observed)
    if published and updated and instant(updated) < instant(published):
        raise ContractError("xhs_update_before_publication")
    doc = {"schemaVersion": 1, "kind": "signal_observation", "signalId": f"xhs:note:{native}",
        "platform": "xhs", "nativeId": native, "contentType": "note", "nativeAliases": [],
        "canonicalUrl": f"https://www.xiaohongshu.com/explore/{native}", "accessStatus": "unverified",
        "title": title, "titleOrigin": origin, "excerpt": excerpt,
        "textScope": "post_text" if excerpt else "title_only",
        "publishedAt": published, "publishedPrecision": "second" if published else "unknown",
        "updatedAt": updated, "observedAt": observed.astimezone(UTC).isoformat(timespec="seconds"),
        "author": {"displayName": nickname[:1] + "***" if nickname else None,
                   "maskStatus": "masked" if nickname else "unknown", "creatorKey": creator},
        **{key: job[key] for key in ("queryId", "jobId", "runId", "attemptId")},
        "trackRefs": list(job["trackRefs"]), "queryTerms": terms, "matchedTerms": matches,
        "entityCandidates": [], "metrics": {"likes": metric(row.get("liked_count")),
            "comments": metric(row.get("comment_count")), "shares": metric(row.get("share_count")),
            "views": {"value": None, "approximate": False}},
        "evidence": {"grade": "D", "role": "discovery", "verification": "unverified"}}
    doc["contentHash"] = content_hash(doc)
    return validate(doc, expected_kind="signal_observation")


def error_envelope(job, status, code, started, completed):
    return {"version": 1, "attemptId": job["attemptId"], "queryId": job["queryId"],
        "startedAt": started, "completedAt": completed, "pages": [], "records": [],
        "detailFailures": 0, "searchDuplicates": 0, "detailsNotRequested": 0,
        "status": status, "stopReason": REASONS[status], "errorCode": code, "retryAfter": None}


def finalize(job: dict, captured: dict, context: dict, *, patchset_hash: str) -> dict:
    validate(job, expected_kind="crawl_job")
    required = set(error_envelope(job, "schema_error", "ERROR", "", ""))
    if not isinstance(captured, dict) or set(captured) != required or type(captured["version"]) is not int or captured["version"] != 1:
        raise ContractError("xhs_envelope_fields")
    if any(captured[key] != job[key] for key in ("attemptId", "queryId")):
        raise ContractError("xhs_envelope_identity")
    pages, records = captured["pages"], captured["records"]
    if not isinstance(pages, list) or len(pages) > job["limits"]["maxSearchPages"] or not isinstance(records, list) or len(records) > job["limits"]["maxRecords"]:
        raise ContractError("xhs_envelope_budget")
    for key in ("detailFailures", "searchDuplicates", "detailsNotRequested"):
        if type(captured[key]) is not int or not 0 <= captured[key] <= 10000:
            raise ContractError("xhs_envelope_counts")
    status = captured["status"]
    if status not in {*REASONS, "ok", "empty"}:
        raise ContractError("xhs_envelope_status")
    observations, seen, rejected, duplicates, invalid = [], set(), 0, 0, False
    start, end = instant(captured["startedAt"]), instant(captured["completedAt"])
    for entry in records:
        try:
            if not isinstance(entry, dict) or set(entry) != {"record", "originalTitle", "observedAt"} or type(entry["originalTitle"]) is not bool:
                raise ContractError("xhs_record_envelope")
            if not start <= instant(entry["observedAt"]) <= end:
                raise ContractError("xhs_observation_time")
            doc = normalize_record(entry["record"], job, context, observed_at=entry["observedAt"], original_title=entry["originalTitle"])
        except (ContractError, ValueError, TypeError, KeyError):
            rejected += 1
            invalid = True
            continue
        window = job["window"]
        day = doc["publishedAt"][:10] if doc["publishedAt"] else None
        if window["filterMode"] == "post_filter" and (not day or window["from"] and day < window["from"] or window["to"] and day > window["to"]):
            rejected += 1
            continue
        if doc["signalId"] in seen:
            duplicates += 1
            continue
        seen.add(doc["signalId"])
        observations.append(doc)
    reason, code = captured["stopReason"], captured["errorCode"]
    if invalid and status in {"ok", "empty"}:
        status, reason, code = "schema_error", "schema", "NORMALIZATION_REJECTED"
    if observations and status in {"network_error", "timeout", "schema_error", "cancelled"}:
        status = "partial"
    receipt = {"schemaVersion": 1, "kind": "query_receipt",
        **{key: job[key] for key in ("jobId", "queryId", "runId", "attemptId", "platform", "provider", "upstreamCommit")},
        "startedAt": captured["startedAt"], "completedAt": captured["completedAt"],
        "status": status, "completeness": ("exhausted" if reason == "exhausted" else "bounded") if status in {"ok", "empty"} else "incomplete",
        "stopReason": reason, "errorCode": code,
        "counts": {"searchItems": sum(page["contentItems"] for page in pages), "rawRows": len(records),
                   "emittedRows": len(observations), "rejectedRows": rejected, "duplicateRows": duplicates,
                   "budgetSkipped": 0, "detailFailures": captured["detailFailures"]},
        "pageReceipts": pages, "normalizerVersion": VERSION, "patchsetHash": patchset_hash}
    validate(receipt, expected_kind="query_receipt")
    result = {"receipt": receipt, "observations": observations, "hints": [],
              "diagnostics": {"searchDuplicates": captured["searchDuplicates"],
                "detailsNotRequested": captured["detailsNotRequested"], "retryAfterSeconds": captured["retryAfter"],
                "batchIntegrityChecked": False}}
    assert_safe(result)
    return result
