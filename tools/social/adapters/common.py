"""Pure, bounded normalization helpers. Imported without network or filesystem writes."""
from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from html.parser import HTMLParser

from ..contracts import ContractError, assert_safe, content_hash, normalize_query, validate


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "iframe", "object", "template"}:
            self.hidden += 1
        elif not self.hidden and tag in {"br", "p", "div", "section", "li"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "iframe", "object", "template"} and self.hidden:
            self.hidden -= 1
        elif not self.hidden:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def text(value, limit=500):
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > 2_000_000:
        raise ContractError("upstream_text_shape")
    parser = _Text()
    parser.feed(value)
    result = " ".join("".join(parser.parts).split())
    assert_safe(result)
    return result[:limit]


def native_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ContractError("native_id")
    result = str(value)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", result) or result.casefold() in {"null", "none", "undefined"}:
        raise ContractError("native_id")
    return result


def epoch(value, *, unit="seconds"):
    """Only explicitly supported units; never guess from digit count."""
    if value in (None, "", 0, "0"):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ContractError("timestamp_shape")
    try:
        numeric = float(value)
        if not math.isfinite(numeric) or numeric <= 0 or unit not in {"seconds", "milliseconds"}:
            raise ValueError
        seconds = numeric / (1000 if unit == "milliseconds" else 1)
        stamp = datetime.fromtimestamp(seconds, UTC)
        if not 2000 <= stamp.year <= 2100:
            raise ValueError
        return stamp.isoformat(timespec="seconds")
    except (ValueError, OverflowError, OSError):
        raise ContractError("timestamp_unit_or_range") from None


def metric(value):
    if value in (None, "", "--"):
        return {"value": None, "approximate": False}
    if isinstance(value, bool):
        raise ContractError("metric_shape")
    raw = str(value).strip().replace(",", "")
    matched = re.fullmatch(r"(\d+(?:\.\d+)?)([万亿kKwWmM]?)(\+?)", raw)
    if not matched:
        return {"value": None, "approximate": False}
    multiplier = {"": 1, "万": 10000, "亿": 100000000, "k": 1000, "w": 10000, "m": 1000000}[matched[2].lower()]
    number = float(matched[1]) * multiplier
    if not math.isfinite(number) or number > 1e15:
        raise ContractError("metric_range")
    return {"value": int(number) if number.is_integer() else number, "approximate": bool(matched[2] or matched[3])}


def observation(job, raw, *, observed_at, identifier, content_type, url, title, excerpt,
                title_origin="upstream", text_scope="post_text", published=None, updated=None,
                aliases=(), terms=None, metrics=None, author_masked=True):
    validate(job, expected_kind="crawl_job")
    identifier = native_id(identifier)
    title, excerpt = text(title, 220), text(excerpt, 500)
    query_terms = list(dict.fromkeys(terms or [job["query"]["text"]]))
    if any(not isinstance(t, str) or not t or len(t) > 500 for t in query_terms):
        raise ContractError("query_term_shape")
    visible = normalize_query(title + " " + excerpt).casefold()
    creator = raw.get("creator_hash")
    # Creator hashes are opaque local identifiers, never a real-world identity.
    if not isinstance(creator, str) or not re.fullmatch(r"[0-9a-fA-F]{16,128}", creator):
        creator = None
    display = text(raw.get("nickname", raw.get("user_nickname")), 120) or None
    values = {name: metric((metrics or {}).get(name)) for name in ("likes", "comments", "shares", "views")}
    doc = {
        "schemaVersion": 1, "kind": "signal_observation", "platform": job["platform"],
        "nativeId": identifier, "contentType": content_type,
        "signalId": f'{job["platform"]}:{content_type}:{identifier}',
        "nativeAliases": list(aliases), "canonicalUrl": url, "accessStatus": "unverified",
        "title": title, "titleOrigin": title_origin if title else "missing",
        "excerpt": excerpt, "textScope": text_scope,
        "publishedAt": published, "publishedPrecision": "second" if published else "unknown",
        "updatedAt": updated, "observedAt": observed_at,
        "author": {"displayName": display, "maskStatus": "masked" if display and author_masked else "unknown", "creatorKey": creator},
        **{key: job[key] for key in ("queryId", "jobId", "runId", "attemptId")},
        "trackRefs": list(job["trackRefs"]), "queryTerms": query_terms,
        "matchedTerms": [term for term in query_terms if normalize_query(term).casefold() in visible],
        "entityCandidates": [], "metrics": values,
        "evidence": {"grade": "D", "role": "discovery", "verification": "unverified"},
    }
    doc["contentHash"] = content_hash(doc)
    return validate(doc, expected_kind="signal_observation")
