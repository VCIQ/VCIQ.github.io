"""Weibo observations: exact string identities, explicit time units, no inferred relations."""
from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime, timedelta, timezone
from html.parser import HTMLParser

from ..contracts import ContractError, assert_safe, content_hash, validate
from ..scheduler import instant
from .xhs import metric, error_envelope, REASONS

VERSION = "weibo-shadow-v1"
MONTHS = {name: index for index, name in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.blocked = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}: self.blocked += 1
        if tag in {"br", "p", "div", "li"}: self.parts.append(" ")
    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.blocked: self.blocked -= 1
        if tag in {"p", "div", "li"}: self.parts.append(" ")
    def handle_data(self, value):
        if not self.blocked: self.parts.append(value)


def plain(value):
    if value is None: return ""
    if not isinstance(value, str) or len(value) > 100000:
        raise ContractError("weibo_text_type_or_size")
    assert_safe(value)
    parser = PlainText()
    parser.feed(value)
    parser.close()
    text = " ".join("".join(parser.parts).split())
    assert_safe(text)
    return text


def publication(row, observed):
    """Pinned create_time is seconds, create_date_time carries its timezone.

    Relative platform labels remain unknown. last_modify_ts is a collection
    timestamp and is deliberately not used as publication or update evidence.
    """
    candidates = []
    epoch = row.get("create_time")
    if epoch not in (None, "", 0, "0"):
        if isinstance(epoch, bool) or not (type(epoch) is int or isinstance(epoch, str) and epoch.isdigit()):
            raise ContractError("weibo_timestamp_type")
        number = int(epoch)
        if not 946684800 <= number <= int(observed.timestamp()):
            raise ContractError("weibo_timestamp_unit_or_future")
        candidates.append(datetime.fromtimestamp(number, UTC))
    label = row.get("create_date_time")
    if label not in (None, ""):
        if not isinstance(label, str): raise ContractError("weibo_datetime_type")
        try:
            parsed = datetime.fromisoformat(label.replace("Z", "+00:00"))
            if parsed.utcoffset() is None: raise ValueError
            candidates.append(parsed.astimezone(UTC))
        except (ValueError, OverflowError):
            raise ContractError("weibo_datetime_offset_required") from None
    original = row.get("raw_created_at")
    if original not in (None, ""):
        if not isinstance(original, str): raise ContractError("weibo_datetime_type")
        match = re.fullmatch(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([A-Z][a-z]{2}) (\d{1,2}) (\d{2}):(\d{2}):(\d{2}) ([+-])(\d{2})(\d{2}) (\d{4})", original)
        if match:
            try:
                month, day, hour, minute, second, sign, oh, om, year = match.groups()
                if int(oh) > 23 or int(om) > 59: raise ValueError
                offset = timedelta(hours=int(oh), minutes=int(om)) * (1 if sign == "+" else -1)
                candidates.append(datetime(int(year), MONTHS[month], int(day), int(hour), int(minute), int(second), tzinfo=timezone(offset)).astimezone(UTC))
            except (ValueError, KeyError, OverflowError):
                raise ContractError("weibo_source_date_invalid") from None
        elif not re.fullmatch(r"(?:刚刚|\d+\s*(?:秒|分钟|小时|天)前|(?:今天|昨天|前天)(?:\s*\d{1,2}:\d{2})?|\d{2}-\d{2})", original):
            raise ContractError("weibo_source_date_unsupported")
    if not candidates: return None
    if any(value > observed for value in candidates):
        raise ContractError("weibo_future_publication")
    if any(value != candidates[0] for value in candidates[1:]):
        raise ContractError("weibo_publication_conflict")
    return candidates[0].isoformat(timespec="seconds")


def normalize_record(row, job, context, *, observed_at, original_title=False):
    validate(job, expected_kind="crawl_job")
    if job["platform"] != "wb" or not isinstance(row, dict):
        raise ContractError("weibo_record_expected")
    native = row.get("note_id")
    if not isinstance(native, str) or not re.fullmatch(r"[1-9][0-9]{0,39}", native):
        raise ContractError("weibo_native_id_string_required")
    if original_title is not False:
        raise ContractError("weibo_title_is_derived")
    observed = instant(observed_at)
    content = plain(row.get("content"))
    excerpt, title = content[:500], content[:120]
    terms = sorted({item["text"] for item in context["terms"]})
    if not terms or any(not isinstance(term, str) or not term.strip() or len(term) > 500 for term in terms):
        raise ContractError("weibo_query_terms")
    assert_safe(terms)
    visible = unicodedata.normalize("NFKC", excerpt).casefold()
    matches = []
    for term in terms:
        needle = unicodedata.normalize("NFKC", term).casefold()
        found = bool(re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", visible)) if re.fullmatch(r"[a-z0-9 ._-]+", needle) else needle in visible
        if found: matches.append(term)
    nickname = plain(row.get("nickname"))[:120]
    creator = row.get("creator_hash")
    if not isinstance(creator, str) or not re.fullmatch(r"[0-9a-f]{16,128}", creator): creator = None
    published = publication(row, observed)
    doc = {"schemaVersion": 1, "kind": "signal_observation", "signalId": "wb:post:" + native,
        "platform": "wb", "nativeId": native, "contentType": "post", "nativeAliases": [],
        "canonicalUrl": "https://m.weibo.cn/detail/" + native, "accessStatus": "unverified",
        "title": title, "titleOrigin": "derived" if title else "missing", "excerpt": excerpt,
        "textScope": "post_text" if excerpt else "title_only",
        "publishedAt": published, "publishedPrecision": "second" if published else "unknown",
        "updatedAt": None, "observedAt": observed.astimezone(UTC).isoformat(timespec="seconds"),
        "author": {"displayName": nickname[:1] + "***" if nickname else None,
            "maskStatus": "masked" if nickname else "unknown", "creatorKey": creator},
        **{key: job[key] for key in ("queryId", "jobId", "runId", "attemptId")},
        "trackRefs": list(job["trackRefs"]), "queryTerms": terms, "matchedTerms": matches,
        "entityCandidates": [], "metrics": {"likes": metric(row.get("liked_count")),
            "comments": metric(row.get("comments_count")), "shares": metric(row.get("shared_count")),
            "views": {"value": None, "approximate": False}},
        "evidence": {"grade": "D", "role": "discovery", "verification": "unverified"}}
    doc["contentHash"] = content_hash(doc)
    return validate(doc, expected_kind="signal_observation")


def finalize(job, captured, context, *, patchset_hash):
    validate(job, expected_kind="crawl_job")
    required = set(error_envelope(job, "schema_error", "ERROR", "", ""))
    if job["platform"] != "wb" or not isinstance(captured, dict) or set(captured) != required or type(captured["version"]) is not int or captured["version"] != 1:
        raise ContractError("weibo_envelope_fields")
    if any(captured[key] != job[key] for key in ("attemptId", "queryId")):
        raise ContractError("weibo_envelope_identity")
    pages, records = captured["pages"], captured["records"]
    if not isinstance(pages, list) or len(pages) > job["limits"]["maxSearchPages"] or not isinstance(records, list) or len(records) > job["limits"]["maxRecords"]:
        raise ContractError("weibo_envelope_budget")
    for key in ("detailFailures", "searchDuplicates", "detailsNotRequested"):
        if type(captured[key]) is not int or not 0 <= captured[key] <= 10000:
            raise ContractError("weibo_envelope_counts")
    retry = captured["retryAfter"]
    if retry is not None and (type(retry) is not int or retry < 0):
        raise ContractError("weibo_retry_after")
    status = captured["status"]
    if status not in {*REASONS, "ok", "empty"}:
        raise ContractError("weibo_envelope_status")
    if [page.get("pageIndex") for page in pages] != list(range(1, len(pages) + 1)):
        raise ContractError("weibo_page_order")
    if status in {"ok", "empty"} and sum(page["contentItems"] for page in pages) != len(records) + captured["searchDuplicates"] + captured["detailsNotRequested"]:
        raise ContractError("weibo_search_accounting")
    start, end = instant(captured["startedAt"]), instant(captured["completedAt"])
    observations, seen, rejected, duplicates, invalid = [], set(), 0, 0, False
    for entry in records:
        try:
            if not isinstance(entry, dict) or set(entry) != {"record", "originalTitle", "observedAt"} or entry["originalTitle"] is not False:
                raise ContractError("weibo_record_envelope")
            if not start <= instant(entry["observedAt"]) <= end:
                raise ContractError("weibo_observation_time")
            doc = normalize_record(entry["record"], job, context, observed_at=entry["observedAt"])
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
            "searchItemsNotProjected": captured["detailsNotRequested"], "retryAfterSeconds": retry,
            "fullTextFetched": False, "repostRelationshipsResolved": False, "batchIntegrityChecked": False}}
    assert_safe(result)
    return result
