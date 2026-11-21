"""Typed Zhihu discovery observations; question IDs never identify answers."""
from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime

from ..contracts import ContractError, assert_safe, content_hash, validate
from ..scheduler import instant
from .weibo import plain
from .xhs import metric, error_envelope, REASONS

VERSION = "zhihu-shadow-v1"
TYPES = frozenset({"answer", "article", "zvideo"})


def seconds(value, observed):
    if isinstance(value, bool):
        raise ContractError("zhihu_timestamp_type")
    if value in (None, "", 0, "0"):
        return None
    if not (type(value) is int or isinstance(value, str) and value.isdigit()):
        raise ContractError("zhihu_timestamp_type")
    number = int(value)
    if not 946684800 <= number <= int(observed.timestamp()):
        raise ContractError("zhihu_timestamp_unit_or_future")
    return datetime.fromtimestamp(number, UTC).isoformat(timespec="seconds")


def timestamp_aliases(row, fields, observed):
    values = [seconds(row.get(field), observed) for field in fields]
    values = [value for value in values if value is not None]
    if len(set(values)) > 1:
        raise ContractError("zhihu_timestamp_conflict")
    return values[0] if values else None


def normalize_record(row, job, context, *, observed_at, original_title=True):
    validate(job, expected_kind="crawl_job")
    if job["platform"] != "zhihu" or not isinstance(row, dict) or row.get("content_type") not in TYPES:
        raise ContractError("zhihu_record_type")
    kind, native = row["content_type"], row.get("content_id")
    if not isinstance(native, str) or not re.fullmatch(r"[1-9][0-9]{0,39}", native):
        raise ContractError("zhihu_native_id_string_required")
    if type(original_title) is not bool:
        raise ContractError("zhihu_title_provenance")
    parent = row.get("question_id")
    if parent is not None and (kind != "answer" or not isinstance(parent, str) or not re.fullmatch(r"[1-9][0-9]{0,39}", parent)):
        raise ContractError("zhihu_question_id")
    observed = instant(observed_at)
    title = plain(row.get("title"))[:220]
    description = plain(row.get("description")) or plain(row.get("excerpt"))
    body = description if kind == "zvideo" else plain(row.get("content")) or description
    excerpt = body[:500]
    origin = "upstream" if title and original_title else "derived" if title else "missing"
    if not title:
        title = (plain(row.get("question_title")) if kind == "answer" else "")[:220] or excerpt[:120]
        origin = "derived" if title else "missing"
    if kind == "article":
        published = timestamp_aliases(row, ("created_time", "created"), observed)
        updated = timestamp_aliases(row, ("updated_time", "updated"), observed)
    elif kind == "answer":
        published = seconds(row.get("created_time"), observed)
        updated = seconds(row.get("updated_time"), observed)
    else:
        # Upload creation and public publication can differ; they are not aliases.
        published = seconds(row.get("published_at"), observed) or seconds(row.get("created_at"), observed)
        updated = seconds(row.get("updated_at"), observed)
    if published and updated and instant(updated) < instant(published):
        raise ContractError("zhihu_update_before_publication")
    if kind == "answer":
        url = f"https://www.zhihu.com/question/{parent}/answer/{native}" if parent else None
    elif kind == "article":
        url = f"https://zhuanlan.zhihu.com/p/{native}"
    else:
        url = f"https://www.zhihu.com/zvideo/{native}"
    terms = sorted({entry["text"] for entry in context["terms"]})
    if not terms or any(not isinstance(term, str) or not term.strip() or len(term) > 500 for term in terms):
        raise ContractError("zhihu_query_terms")
    assert_safe(terms)
    visible = unicodedata.normalize("NFKC", title + " " + excerpt).casefold()
    matches = []
    for term in terms:
        needle = unicodedata.normalize("NFKC", term).casefold()
        found = bool(re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", visible)) if re.fullmatch(r"[a-z0-9 ._-]+", needle) else needle in visible
        if found:
            matches.append(term)
    nickname = plain(row.get("nickname"))[:120]
    creator = row.get("creator_hash")
    if not isinstance(creator, str) or not re.fullmatch(r"[0-9a-f]{16,128}", creator):
        creator = None
    doc = {"schemaVersion": 1, "kind": "signal_observation", "signalId": f"zhihu:{kind}:{native}",
        "platform": "zhihu", "nativeId": native, "contentType": kind, "nativeAliases": [],
        "canonicalUrl": url, "accessStatus": "unverified", "title": title, "titleOrigin": origin,
        "excerpt": excerpt, "textScope": {"answer": "answer_excerpt", "article": "article_excerpt", "zvideo": "video_description"}[kind],
        "publishedAt": published, "publishedPrecision": "second" if published else "unknown",
        "updatedAt": updated, "observedAt": observed.astimezone(UTC).isoformat(timespec="seconds"),
        "author": {"displayName": nickname[:1] + "***" if nickname else None,
            "maskStatus": "masked" if nickname else "unknown", "creatorKey": creator},
        **{key: job[key] for key in ("queryId", "jobId", "runId", "attemptId")},
        "trackRefs": list(job["trackRefs"]), "queryTerms": terms, "matchedTerms": matches,
        "entityCandidates": [], "metrics": {"likes": metric(row.get("voteup_count")),
            "comments": metric(row.get("comment_count")), "shares": {"value": None, "approximate": False},
            "views": {"value": None, "approximate": False}},
        "evidence": {"grade": "D", "role": "discovery", "verification": "unverified"}}
    doc["contentHash"] = content_hash(doc)
    return validate(doc, expected_kind="signal_observation")


def finalize(job, captured, context, *, patchset_hash):
    validate(job, expected_kind="crawl_job")
    required = set(error_envelope(job, "schema_error", "ERROR", "", ""))
    if (job["platform"] != "zhihu" or not isinstance(captured, dict) or not required <= set(captured)
        or set(captured) - required - {"excludedItems"} or type(captured["version"]) is not int or captured["version"] != 1):
        raise ContractError("zhihu_envelope_fields")
    if any(captured[key] != job[key] for key in ("attemptId", "queryId")):
        raise ContractError("zhihu_envelope_identity")
    pages, records = captured["pages"], captured["records"]
    if not isinstance(pages, list) or len(pages) > job["limits"]["maxSearchPages"] or not isinstance(records, list) or len(records) > job["limits"]["maxRecords"]:
        raise ContractError("zhihu_envelope_budget")
    for key in ("detailFailures", "searchDuplicates", "detailsNotRequested", "excludedItems"):
        value = captured.get(key, 0)
        if type(value) is not int or not 0 <= value <= 10000:
            raise ContractError("zhihu_envelope_counts")
    retry = captured["retryAfter"]
    if retry is not None and (type(retry) is not int or retry < 0):
        raise ContractError("zhihu_retry_after")
    for index, page in enumerate(pages, 1):
        if (not isinstance(page, dict) or set(page) != {"pageIndex", "schemaValid", "contentItems", "processed", "hasMore"}
            or type(page["pageIndex"]) is not int or page["pageIndex"] != index
            or type(page["contentItems"]) is not int or not 0 <= page["contentItems"] <= 100
            or page["schemaValid"] is not True or type(page["processed"]) is not bool
            or page["hasMore"] is not None and type(page["hasMore"]) is not bool):
            raise ContractError("zhihu_page_shape")
        if index < len(pages) and page["hasMore"] is False:
            raise ContractError("zhihu_page_after_end")
    status = captured["status"]
    if status not in {*REASONS, "ok", "empty"}:
        raise ContractError("zhihu_envelope_status")
    total = sum(page["contentItems"] for page in pages)
    accounted = len(records) + captured["searchDuplicates"] + captured["detailsNotRequested"] + captured["detailFailures"]
    if accounted > total or status in {"ok", "empty"} and accounted != total:
        raise ContractError("zhihu_search_accounting")
    if status == "empty" and captured.get("excludedItems", 0):
        raise ContractError("zhihu_empty_unproven")
    start, end = instant(captured["startedAt"]), instant(captured["completedAt"])
    observations, identities, rejected, duplicates, invalid = [], {}, 0, 0, False
    for entry in records:
        try:
            if not isinstance(entry, dict) or set(entry) != {"record", "originalTitle", "observedAt"} or type(entry["originalTitle"]) is not bool:
                raise ContractError("zhihu_record_envelope")
            if not start <= instant(entry["observedAt"]) <= end:
                raise ContractError("zhihu_observation_time")
            doc = normalize_record(entry["record"], job, context, observed_at=entry["observedAt"], original_title=entry["originalTitle"])
            if doc["signalId"] in identities and identities[doc["signalId"]] != doc["canonicalUrl"]:
                raise ContractError("zhihu_answer_parent_conflict")
        except (ContractError, ValueError, TypeError, KeyError):
            rejected += 1; invalid = True
            continue
        window = job["window"]
        day = doc["publishedAt"][:10] if doc["publishedAt"] else None
        if window["filterMode"] == "post_filter" and (not day or window["from"] and day < window["from"] or window["to"] and day > window["to"]):
            rejected += 1
            continue
        if doc["signalId"] in identities:
            duplicates += 1
            continue
        identities[doc["signalId"]] = doc["canonicalUrl"]
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
        "counts": {"searchItems": total, "rawRows": len(records), "emittedRows": len(observations),
            "rejectedRows": rejected, "duplicateRows": duplicates, "budgetSkipped": 0, "detailFailures": captured["detailFailures"]},
        "pageReceipts": pages, "normalizerVersion": VERSION, "patchsetHash": patchset_hash}
    validate(receipt, expected_kind="query_receipt")
    result = {"receipt": receipt, "observations": observations, "hints": [],
        "diagnostics": {"searchDuplicates": captured["searchDuplicates"], "nonTargetSearchRows": captured.get("excludedItems", 0),
            "searchItemsNotProjected": captured["detailsNotRequested"], "retryAfterSeconds": retry,
            "fullTextFetched": False, "transcriptFetched": False, "batchIntegrityChecked": False}}
    assert_safe(result)
    return result
