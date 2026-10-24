"""WeChat shadow search. Production parsers are reused without installing wrappers."""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..contracts import ContractError, assert_safe, content_hash, digest, validate
from ..query_compile import search_url
from ..scheduler import utc
from .wechat_transport import FetchError, checked_url, decode_url

REASONS = {"auth_required": "auth", "verification_required": "verification", "rate_limited": "rate_limit",
           "network_error": "network", "timeout": "timeout", "schema_error": "schema",
           "unsupported": "unsupported", "cancelled": "cancelled"}
NORMALIZER_VERSION = "wechat-shadow-v1"


def identity(url: str) -> tuple[str, str]:
    url = checked_url(url)
    parts = urlsplit(url)
    if parts.hostname != "mp.weixin.qq.com":
        raise FetchError("schema_error", "NOT_WECHAT_ORIGINAL")
    if parts.path.startswith("/s/"):
        return "opaque-" + parts.path[3:], urlunsplit(("https", parts.netloc, parts.path, "", ""))
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    fields = {}
    for key, value in pairs:
        if key in {"__biz", "mid", "idx"}:
            if key in fields:
                raise FetchError("schema_error", "AMBIGUOUS_ARTICLE_ID")
            fields[key] = value
    if not fields.get("__biz") or not re.fullmatch(r"\d+", fields.get("mid", "")) or not re.fullmatch(r"\d+", fields.get("idx", "")):
        raise FetchError("schema_error", "ARTICLE_ID_UNAVAILABLE")
    native = digest(fields)
    canonical = "https://mp.weixin.qq.com/s?" + urlencode([(k, fields[k]) for k in ("__biz", "mid", "idx")])
    return native, canonical


def _blocked(body: str) -> None:
    from tools.wechat_public_sources import BLOCK_PAGE_MARKERS
    if any(marker in body for marker in BLOCK_PAGE_MARKERS) or re.search(r"antispider|VerifyCode|请输入验证码|正常行为不是自动程序", body, re.I):
        raise FetchError("verification_required", "VERIFICATION_REQUIRED")
    if re.search(r'<(?:form|input)[^>]+(?:login|password)', body, re.I):
        raise FetchError("auth_required", "LOGIN_PAGE")


def _search_page(provider: str, body: str, url: str) -> tuple[list[dict], bool | None]:
    _blocked(body)
    if provider == "bing-rss":
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            raise FetchError("schema_error", "INVALID_SEARCH_FEED") from None
        if root.tag != "rss" or root.find("channel") is None:
            raise FetchError("schema_error", "INVALID_SEARCH_FEED")
        rows = [{"url": (row.findtext("link") or "").strip(), "title": row.findtext("title") or "",
                 "summary": row.findtext("description") or "", "account": ""} for row in root.findall("./channel/item")]
        return rows, False if not rows else None
    from tools.wechat_sogou_index import parse_search_results
    rows = parse_search_results(body, url)
    if not rows:
        if re.search(r"没有找到|未找到相关|没有相关结果", body):
            return [], False
        raise FetchError("schema_error", "UNRECOGNIZED_SEARCH_PAGE")
    more = True if re.search(r'(?:id=["\']sogou_next["\']|>\s*下一页\s*<)', body) else None
    return rows, more


def _resolve(row_url: str, transport) -> str:
    url = checked_url(row_url)
    if urlsplit(url).hostname == "mp.weixin.qq.com":
        return url
    if urlsplit(url).hostname != "weixin.sogou.com" or urlsplit(url).path != "/link":
        raise FetchError("schema_error", "UNSUPPORTED_RESULT_LINK")
    response = transport.get(url)
    if urlsplit(response.url).hostname == "mp.weixin.qq.com":
        return checked_url(response.url)
    _blocked(response.body)
    # Only concatenate literal redirect strings. Never evaluate the site's JavaScript.
    chunks = re.findall(r'''(?:var\s+)?(?:url|jump_url)\s*\+=\s*['"](.*?)['"]\s*;?''', response.body, re.I | re.S)
    if chunks:
        target = decode_url("".join(chunks))
    else:
        match = re.search(r'''https://mp\.weixin\.qq\.com/s[^'"<>\s]+''', response.body)
        target = decode_url(match.group()) if match else ""
    if not target:
        raise FetchError("schema_error", "ORIGINAL_LINK_UNRESOLVED")
    return checked_url(target)


def _date_value(value) -> str | None:
    if not value:
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            number = int(value)
            if number > 10_000_000_000:
                number //= 1000
            return datetime.fromtimestamp(number, UTC).date().isoformat() if number > 0 else None
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _normalize_original(job: dict, context: dict, url: str, body: str, observed: datetime) -> dict:
    from tools import crawl_articles as crawler
    from tools import wechat_public_sources as original
    from tools.wechat_source_registry import account_matches
    _blocked(body)
    if not re.search(r'id=["\']js_content["\']', body):
        raise FetchError("schema_error", "ORIGINAL_BODY_MISSING")
    parser = original.WeChatPageParser()
    parser.feed(body)
    account = parser.account or original._js_value(body, ("nickname", "profile_nickname", "account_name"))
    expected = context.get("expectedAccounts", [])
    if job["query"]["scope"] == "account" and (not expected or not account or not account_matches({"expectedAccounts": expected}, account)):
        raise FetchError("schema_error", "ACCOUNT_MISMATCH")
    title = crawler.clean_title(parser.meta.get("og:title") or parser.title or original._js_value(body, ("msg_title", "title")))
    text = parser.content
    if len(title) < 6 or not text:
        raise FetchError("schema_error", "ORIGINAL_CONTENT_MISSING")
    published = original._published_at(parser, body, SimpleNamespace(normalize_date=_date_value))
    if not published:
        raise FetchError("schema_error", "ORIGINAL_DATE_UNKNOWN")
    source_day = date.fromisoformat(published)
    if source_day > (observed + timedelta(hours=14)).date():
        raise FetchError("schema_error", "FUTURE_PUBLICATION")
    if source_day < observed.date() - timedelta(days=45):
        raise FetchError("schema_error", "ARTICLE_TOO_OLD")
    terms = context["terms"]
    query_terms = sorted({term["text"] for term in terms})
    matched = [term for term in query_terms if crawler._keyword_in_text(term, f"{title} {text}".casefold())]
    spec = {"keywords": query_terms,
            "trackedCompanies": [term["text"] for term in terms if term["kind"] == "company"],
            "trackedPeople": [term["text"] for term in terms if term["kind"] == "person"]}
    companies, people, keywords = original._relevance_entities(title, text[:500], text, spec, crawler)
    if not matched or not (companies or people or keywords):
        raise FetchError("schema_error", "IRRELEVANT_ORIGINAL")
    native, canonical = identity(url)
    window = job["window"]
    if (window["from"] and published < window["from"]) or (window["to"] and published > window["to"]):
        raise FetchError("schema_error", "OUTSIDE_POST_FILTER_WINDOW")
    observation = {"schemaVersion": 1, "kind": "signal_observation", "signalId": f"wechat:article:{native}",
        "platform": "wechat", "nativeId": native, "contentType": "article", "nativeAliases": [],
        "canonicalUrl": canonical, "accessStatus": "verified_public", "title": title[:220], "titleOrigin": "upstream",
        "excerpt": text[:500], "textScope": "article_excerpt", "publishedAt": published, "publishedPrecision": "day",
        "updatedAt": None, "observedAt": utc(observed),
        "author": {"displayName": account or None, "maskStatus": "unknown", "creatorKey": None},
        **{key: job[key] for key in ("jobId", "queryId", "runId", "attemptId", "trackRefs")},
        "queryTerms": query_terms, "matchedTerms": matched,
        "entityCandidates": [{"kind": term["kind"], "label": term["text"], "entityId": None,
                              "status": "candidate", "basis": "literal_query_term_in_original"}
                             for term in terms if term["kind"] in {"company", "person"} and term["text"] in matched and len(term["text"]) <= 200],
        "metrics": {key: {"value": None, "approximate": False} for key in ("likes", "comments", "shares", "views")},
        "evidence": {"grade": "D", "role": "discovery", "verification": "unverified"}}
    observation["contentHash"] = content_hash(observation)
    return validate(observation, expected_kind="signal_observation")


def error_result(job: dict, status: str, code: str, started: datetime, completed: datetime) -> dict:
    receipt = {"schemaVersion": 1, "kind": "query_receipt",
        **{key: job[key] for key in ("jobId", "queryId", "runId", "attemptId", "platform", "provider", "upstreamCommit")},
        "startedAt": utc(started), "completedAt": utc(completed), "status": status, "completeness": "unknown",
        "stopReason": REASONS[status], "counts": {key: 0 for key in ("searchItems", "rawRows", "emittedRows", "rejectedRows", "duplicateRows", "budgetSkipped", "detailFailures")},
        "pageReceipts": [], "normalizerVersion": NORMALIZER_VERSION, "patchsetHash": digest([]), "errorCode": code}
    validate(receipt, expected_kind="query_receipt")
    return {"receipt": receipt, "observations": [], "hints": [], "diagnostics": {"requests": 0, "retryAfterSeconds": 0}}


def run_job(job: dict, context: dict, transport, *, now=lambda: datetime.now(UTC), monotonic=time.monotonic) -> dict:
    validate(job, expected_kind="crawl_job")
    if job["platform"] != "wechat" or job["provider"] not in {"sogou-weixin", "bing-rss"} or job["window"]["filterMode"] == "native":
        return error_result(job, "unsupported", "UNSUPPORTED_SEARCH", now(), now())
    if context["queryId"] != job["queryId"] or context["query"] != job["query"]:
        raise ContractError("execution_context_mismatch")
    started = now()
    deadline = monotonic() + job["limits"]["maxWallSeconds"]
    result = error_result(job, "schema_error", "UNSTARTED", started, started)
    receipt, observations, hints = result["receipt"], result["observations"], result["hints"]
    counts, pages = receipt["counts"], receipt["pageReceipts"]
    seen = set()
    failure = None
    stop = "page_limit"
    for page in range(1, job["limits"]["maxSearchPages"] + 1):
        page_receipt = {"pageIndex": page, "schemaValid": False, "contentItems": 0, "processed": False, "hasMore": None}
        pages.append(page_receipt)
        try:
            if monotonic() >= deadline:
                raise FetchError("timeout", "JOB_DEADLINE")
            response = transport.get(search_url(job, page))
            rows, more = _search_page(job["provider"], response.body, response.url)
            page_receipt.update(schemaValid=True, contentItems=len(rows), hasMore=more)
            counts["searchItems"] += len(rows)
            for row in rows:
                if monotonic() >= deadline:
                    raise FetchError("timeout", "JOB_DEADLINE")
                counts["rawRows"] += 1
                if len(observations) >= job["limits"]["maxRecords"]:
                    counts["budgetSkipped"] += 1
                    continue
                direct = ""
                try:
                    direct = _resolve(row["url"], transport)
                    body_response = transport.get(direct)
                    record = _normalize_original(job, context, body_response.url, body_response.body, now())
                    if record["signalId"] in seen:
                        counts["duplicateRows"] += 1
                    else:
                        seen.add(record["signalId"])
                        observations.append(record)
                        counts["emittedRows"] += 1
                except (FetchError, ContractError) as exc:
                    counts["rejectedRows"] += 1
                    code = exc.code.upper()
                    content_reject = code in {"ACCOUNT_MISMATCH", "IRRELEVANT_ORIGINAL", "ARTICLE_TOO_OLD", "OUTSIDE_POST_FILTER_WINDOW"}
                    if not content_reject:
                        counts["detailFailures"] += 1
                        failure = exc if isinstance(exc, FetchError) else FetchError("schema_error", "UNSAFE_OR_INVALID_RECORD")
                    canonical = None
                    try:
                        _, canonical = identity(direct or row["url"])
                    except FetchError:
                        pass
                    hint = {"queryId": job["queryId"], "canonicalUrl": canonical,
                            "title": re.sub(r"<[^>]+>", "", row.get("title", ""))[:260], "reason": code[:120]}
                    try:
                        assert_safe(hint)
                        hints.append(hint)
                    except ContractError:
                        hints.append({"queryId": job["queryId"], "canonicalUrl": None, "title": "", "reason": "UNSAFE_HINT"})
                    if isinstance(exc, FetchError) and exc.status in {"auth_required", "verification_required", "rate_limited", "timeout", "cancelled"}:
                        raise
            page_receipt["processed"] = True
            if len(observations) >= job["limits"]["maxRecords"]:
                stop = "item_limit"
                break
            if more is False:
                stop = "exhausted"
                break
            if more is None or job["provider"] == "bing-rss":
                break
        except (FetchError, ContractError) as exc:
            failure = exc if isinstance(exc, FetchError) else FetchError("schema_error", "INVALID_SEARCH_CONTRACT")
            break
    if failure:
        receipt.update(status="partial" if observations else failure.status, completeness="incomplete",
                       stopReason=REASONS[failure.status], errorCode=failure.code)
        result["diagnostics"]["retryAfterSeconds"] = failure.retry_after
    else:
        receipt.update(status="ok" if counts["searchItems"] else "empty",
                       completeness="exhausted" if stop == "exhausted" else "bounded", stopReason=stop, errorCode=None)
    receipt["completedAt"] = utc(now())
    result["diagnostics"]["requests"] = getattr(transport, "requests", 0)
    validate(receipt, expected_kind="query_receipt")
    assert_safe(result)
    return result
