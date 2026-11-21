"""Bilibili video descriptions, not transcripts, normalized as discovery evidence."""
from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from html.parser import HTMLParser

from ..contracts import ContractError, assert_safe, content_hash, validate
from ..scheduler import instant
from .xhs import REASONS, error_envelope, metric

VERSION = "bili-shadow-v1"


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}: self.hidden += 1
        if not self.hidden and tag in {"br", "p", "div", "li"}: self.parts.append(" ")
    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden: self.hidden -= 1
        if not self.hidden and tag in {"p", "div", "li"}: self.parts.append(" ")
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


def plain(value, limit):
    if value is None: return ""
    if not isinstance(value, str) or len(value) > 100000: raise ContractError("bili_text_type_or_size")
    assert_safe(value)
    parser = PlainText()
    parser.feed(value)
    result = " ".join("".join(parser.parts).split())
    assert_safe(result)
    return result[:limit]


def seconds(value, observed):
    if value in (None, "", 0, "0") and not isinstance(value, bool): return None
    if type(value) is not int and not (isinstance(value, str) and re.fullmatch(r"[0-9]+", value)):
        raise ContractError("bili_timestamp_type")
    number = int(value)
    if not 946684800 <= number <= int(observed.timestamp()):
        raise ContractError("bili_timestamp_unit_or_future")
    return datetime.fromtimestamp(number, UTC).isoformat(timespec="seconds")


def normalize_record(row, job, context, *, observed_at, original_title):
    validate(job, expected_kind="crawl_job")
    if job["platform"] != "bili" or not isinstance(row, dict): raise ContractError("bili_record_expected")
    native = row.get("video_id")
    if not isinstance(native, str) or not re.fullmatch(r"[1-9][0-9]{0,29}", native): raise ContractError("bili_aid")
    bv = row.get("bvid")
    if bv is not None and (not isinstance(bv, str) or not re.fullmatch(r"BV[0-9A-Za-z]{10}", bv)):
        raise ContractError("bili_bvid")
    observed = instant(observed_at)
    title, excerpt = plain(row.get("title"), 220), plain(row.get("desc"), 500)
    origin = "upstream" if title and original_title else "derived" if title else "missing"
    if not title and excerpt: title, origin = excerpt[:120], "derived"
    terms = sorted({item["text"] for item in context["terms"]})
    if not terms or any(not isinstance(t, str) or not t or len(t) > 500 for t in terms): raise ContractError("bili_terms")
    haystack = unicodedata.normalize("NFKC", title + " " + excerpt).casefold()
    matches = []
    for term in terms:
        needle = unicodedata.normalize("NFKC", term).casefold()
        present = bool(re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", haystack)) if re.fullmatch(r"[a-z0-9 ._-]+", needle) else needle in haystack
        if present: matches.append(term)
    nickname = plain(row.get("nickname"), 120)
    creator = row.get("creator_hash")
    if not isinstance(creator, str) or not re.fullmatch(r"[0-9a-f]{16,128}", creator): creator = None
    published = seconds(row.get("create_time"), observed)
    doc = {"schemaVersion": 1, "kind": "signal_observation", "signalId": "bili:video:" + native,
        "platform": "bili", "nativeId": native, "contentType": "video",
        "nativeAliases": ["bvid:" + bv] if bv else [],
        "canonicalUrl": "https://www.bilibili.com/video/av" + native, "accessStatus": "unverified",
        "title": title, "titleOrigin": origin, "excerpt": excerpt, "textScope": "video_description",
        "publishedAt": published, "publishedPrecision": "second" if published else "unknown", "updatedAt": None,
        "observedAt": observed.astimezone(UTC).isoformat(timespec="seconds"),
        "author": {"displayName": nickname[:1] + "***" if nickname else None, "maskStatus": "masked" if nickname else "unknown", "creatorKey": creator},
        **{k: job[k] for k in ("queryId", "jobId", "runId", "attemptId")},
        "trackRefs": list(job["trackRefs"]), "queryTerms": terms, "matchedTerms": matches, "entityCandidates": [],
        "metrics": {"likes": metric(row.get("liked_count")), "comments": metric(row.get("video_comment")),
                    "shares": metric(row.get("video_share_count")), "views": metric(row.get("video_play_count"))},
        "evidence": {"grade": "D", "role": "discovery", "verification": "unverified"}}
    doc["contentHash"] = content_hash(doc)
    return validate(doc, expected_kind="signal_observation")


def finalize(job, captured, context, *, patchset_hash):
    validate(job, expected_kind="crawl_job")
    required = set(error_envelope(job, "schema_error", "ERROR", "", ""))
    if not isinstance(captured, dict) or set(captured) != required or type(captured["version"]) is not int or captured["version"] != 1:
        raise ContractError("bili_envelope_fields")
    if any(captured[k] != job[k] for k in ("attemptId", "queryId")): raise ContractError("bili_envelope_identity")
    pages, rows = captured["pages"], captured["records"]
    if not isinstance(pages, list) or len(pages) > job["limits"]["maxSearchPages"] or not isinstance(rows, list) or len(rows) > job["limits"]["maxRecords"]:
        raise ContractError("bili_envelope_budget")
    for key in ("detailFailures", "searchDuplicates", "detailsNotRequested"):
        if type(captured[key]) is not int or not 0 <= captured[key] <= 10000: raise ContractError("bili_envelope_counts")
    status, reason, code = captured["status"], captured["stopReason"], captured["errorCode"]
    if status not in {*REASONS, "ok", "empty"}: raise ContractError("bili_envelope_status")
    start, end = instant(captured["startedAt"]), instant(captured["completedAt"])
    observations, seen, aliases, aid_aliases, rejected, duplicates, invalid = [], set(), {}, {}, 0, 0, False
    for entry in rows:
        try:
            if not isinstance(entry, dict) or set(entry) != {"record", "originalTitle", "observedAt"} or type(entry["originalTitle"]) is not bool:
                raise ContractError("bili_record_envelope")
            if not start <= instant(entry["observedAt"]) <= end: raise ContractError("bili_observation_time")
            doc = normalize_record(entry["record"], job, context, observed_at=entry["observedAt"], original_title=entry["originalTitle"])
            for alias in doc["nativeAliases"]:
                if alias in aliases and aliases[alias] != doc["signalId"]: raise ContractError("bili_alias_conflict")
                if doc["nativeId"] in aid_aliases and aid_aliases[doc["nativeId"]] != alias: raise ContractError("bili_alias_conflict")
                aliases[alias] = doc["signalId"]
                aid_aliases[doc["nativeId"]] = alias
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
    if invalid and status in {"ok", "empty"}: status, reason, code = "schema_error", "schema", "NORMALIZATION_REJECTED"
    if observations and status in {"network_error", "timeout", "schema_error", "cancelled"}: status = "partial"
    receipt = {"schemaVersion": 1, "kind": "query_receipt",
        **{k: job[k] for k in ("jobId", "queryId", "runId", "attemptId", "platform", "provider", "upstreamCommit")},
        "startedAt": captured["startedAt"], "completedAt": captured["completedAt"], "status": status,
        "completeness": ("exhausted" if reason == "exhausted" else "bounded") if status in {"ok", "empty"} else "incomplete",
        "stopReason": reason, "errorCode": code,
        "counts": {"searchItems": sum(p["contentItems"] for p in pages), "rawRows": len(rows), "emittedRows": len(observations),
                   "rejectedRows": rejected, "duplicateRows": duplicates, "budgetSkipped": 0, "detailFailures": captured["detailFailures"]},
        "pageReceipts": pages, "normalizerVersion": VERSION, "patchsetHash": patchset_hash}
    if len(rows) > receipt["counts"]["searchItems"]: raise ContractError("bili_search_accounting")
    validate(receipt, expected_kind="query_receipt")
    result = {"receipt": receipt, "observations": observations, "hints": [],
        "diagnostics": {"searchDuplicates": captured["searchDuplicates"], "detailsNotRequested": captured["detailsNotRequested"],
            "retryAfterSeconds": captured["retryAfter"], "transcriptFetched": False, "batchIntegrityChecked": False}}
    assert_safe(result)
    return result
