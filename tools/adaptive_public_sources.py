#!/usr/bin/env python3
"""Unified multi-stage adapter kernel for user-added public sources.

Every public website enters the same pipeline. Site differences are represented
as small profiles that provide canonical URLs, additional public entry points,
request headers, decoding candidates and optional public search templates.
Profiles do not own separate crawler implementations; candidate discovery,
article parsing, filtering and quality control remain in the shared stages.

Some sites need a stricter publisher after common discovery. Those profiles use
an explicit handoff: the adaptive pipeline still probes public surfaces and
records diagnostics, while one downstream plugin owns the published article
batch. This prevents duplicate source identities without bypassing the shared
adapter.

The adapter is intentionally best-effort for public pages. Login-only content,
CAPTCHAs, paywalls and sites that expose no public HTML/feed/search surface are
reported as unavailable rather than fabricated as successful crawls.
"""

from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from typing import Any, Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 VCIQPublicResearch/1.0"
)
DEFAULT_HISTORY_LIMIT = 20
MAX_ADAPTIVE_TIMEOUT = 12
MAX_ADAPTIVE_ATTEMPTS = 2
MIN_USEFUL_YIELD = 3
YAHOO_VOLATILE_QUERY_KEYS = {
    "guccounter",
    "guce_referrer",
    "guce_referrer_sig",
    "soc_src",
    "soc_trk",
    "ncid",
    "fr",
    "from",
}
CHARSET_PATTERN = re.compile(
    br"charset\s*=\s*[\"']?\s*([a-zA-Z0-9._-]+)",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class SourceProfile:
    id: str
    host_suffixes: tuple[str, ...]
    default_language: str = ""
    encodings: tuple[str, ...] = ("utf-8",)
    accept_language: str = "zh-CN,zh;q=0.9,en;q=0.6"
    native_search_templates: tuple[str, ...] = ()
    publisher_handoff: str = ""
    handoff_status_id: str = ""


PROFILES = (
    SourceProfile(
        id="eastmoney",
        host_suffixes=("eastmoney.com",),
        default_language="zh-Hans",
        encodings=("utf-8", "gb18030"),
        accept_language="zh-CN,zh;q=0.9,en;q=0.5",
        publisher_handoff="eastmoney-strict-detail",
        handoff_status_id="official-user-东方财富",
    ),
    SourceProfile(
        id="yahoo-tw",
        host_suffixes=("tw.yahoo.com", "tw.news.yahoo.com", "tw.stock.yahoo.com"),
        default_language="zh-Hant",
        encodings=("utf-8", "big5", "cp950"),
        accept_language="zh-TW,zh-Hant;q=0.9,en-US;q=0.7,en;q=0.5",
        native_search_templates=("https://tw.news.yahoo.com/search?p={query}",),
    ),
    SourceProfile(
        id="yahoo-sg",
        host_suffixes=("sg.yahoo.com", "sg.news.yahoo.com", "sg.finance.yahoo.com"),
        default_language="en",
        encodings=("utf-8",),
        accept_language="en-SG,en;q=0.9,zh-TW;q=0.5",
        native_search_templates=("https://sg.news.yahoo.com/search?p={query}",),
    ),
)
DEFAULT_PROFILE = SourceProfile(id="default", host_suffixes=())


def _host(url: str) -> str:
    return (urlsplit(str(url or "")).hostname or "").casefold().removeprefix("www.")


def profile_for(url: str) -> SourceProfile:
    host = _host(url)
    if host.endswith(".yahoo.com"):
        labels = host.split(".")
        if "tw" in labels[:-2]:
            return next(profile for profile in PROFILES if profile.id == "yahoo-tw")
        if "sg" in labels[:-2]:
            return next(profile for profile in PROFILES if profile.id == "yahoo-sg")
    for profile in PROFILES:
        if any(host == suffix or host.endswith(f".{suffix}") for suffix in profile.host_suffixes):
            return profile
    return DEFAULT_PROFILE


def _drop_query_parameter(
    profile: SourceProfile,
    path: str,
    key: str,
    value: str,
) -> bool:
    folded_key = key.casefold()
    if folded_key.startswith("utm_"):
        return True
    if not profile.id.startswith("yahoo-"):
        return False
    if folded_key in YAHOO_VOLATILE_QUERY_KEYS:
        return True
    if (
        folded_key == "p"
        and path in {"", "/"}
        and value.casefold() in {"", "us", "tw", "home"}
    ):
        return True
    return False


def canonical_source_url(url: str) -> str:
    """Remove tracking noise without breaking meaningful route/search parameters."""

    parts = urlsplit(html.unescape(str(url or "")).strip())
    if parts.scheme.casefold() not in {"http", "https"} or not parts.netloc:
        return str(url or "").strip()
    profile = profile_for(url)
    path = parts.path or "/"
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not _drop_query_parameter(profile, path, key, value)
        )
    )
    if path in {"/default.html", "/index.html", "/index.htm"}:
        path = "/"
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            path.rstrip("/") or "/",
            query,
            "",
        )
    )


def _origin_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    return urlunsplit((parts.scheme, parts.netloc, "/", "", ""))


def _unique_urls(values: Iterable[str], limit: int = 12) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        normalized = canonical_source_url(raw)
        if not normalized or normalized in seen:
            continue
        result.append(normalized)
        seen.add(normalized)
        if len(result) >= limit:
            break
    return result


def source_seed_urls(url: str) -> list[str]:
    """Return bounded public entry points for the selected site profile."""

    canonical = canonical_source_url(url)
    profile = profile_for(canonical)
    seeds = [canonical]
    root = _origin_url(canonical)
    if root and root != canonical:
        seeds.append(root)
    if profile.id == "yahoo-tw":
        seeds.extend(
            (
                "https://tw.yahoo.com/",
                "https://tw.news.yahoo.com/",
                "https://tw.stock.yahoo.com/",
            )
        )
    elif profile.id == "yahoo-sg":
        seeds.extend(
            (
                "https://sg.yahoo.com/",
                "https://sg.news.yahoo.com/",
                "https://sg.finance.yahoo.com/",
            )
        )
    elif profile.id == "eastmoney":
        seeds.extend(
            (
                "https://www.eastmoney.com/",
                "https://finance.eastmoney.com/",
                "https://stock.eastmoney.com/",
                "https://fund.eastmoney.com/",
            )
        )
    return _unique_urls(seeds, 6)


def _preferred_search_term(keywords: Sequence[str]) -> str:
    values = [re.sub(r"\s+", " ", str(term or "")).strip() for term in keywords]
    values = [value for value in values if value]
    for value in values:
        folded = value.casefold()
        if folded in {"ai", "ai / agi", "artificial intelligence", "人工智能", "人工智慧"}:
            return "AI"
    for value in values:
        if (
            2 <= len(value) <= 40
            and not value.startswith(("http://", "https://"))
            and not re.search(r"\b(?:AND|OR|NOT)\b|site:", value, flags=re.IGNORECASE)
        ):
            return value
    return "technology"


def native_search_seed_urls(url: str, keywords: Sequence[str]) -> list[str]:
    """Build profile-defined public search pages without site-specific crawlers."""

    profile = profile_for(url)
    if not profile.native_search_templates:
        return []
    query = quote_plus(_preferred_search_term(keywords))
    return _unique_urls(
        (template.format(query=query) for template in profile.native_search_templates),
        4,
    )


def _normalize_charset(value: str | None) -> str:
    charset = (value or "").strip().strip("\"'").casefold().replace("_", "-")
    return {
        "gb2312": "gb18030",
        "gb-2312": "gb18030",
        "gbk": "gb18030",
        "x-gbk": "gb18030",
        "cp936": "gb18030",
        "utf8": "utf-8",
        "big-5": "big5",
    }.get(charset, charset)


def decode_public_bytes(
    payload: bytes,
    url: str,
    header_charset: str | None = None,
) -> str:
    """Decode public HTML/XML using HTTP, in-document and profile evidence."""

    candidates: list[str] = []

    def add(value: str | None) -> None:
        normalized = _normalize_charset(value)
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    add(header_charset)
    match = CHARSET_PATTERN.search(payload[:32768])
    if match:
        add(match.group(1).decode("ascii", errors="ignore"))
    if payload.startswith(b"\xef\xbb\xbf"):
        add("utf-8-sig")
    for encoding in profile_for(url).encodings:
        add(encoding)
    add("utf-8")
    add("gb18030")
    add("big5")

    for charset in candidates:
        try:
            return payload.decode(charset, errors="strict")
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode(candidates[0] if candidates else "utf-8", errors="replace")


def fetch_public_text(
    url: str,
    user_agent: str,
    timeout: int = MAX_ADAPTIVE_TIMEOUT,
    attempts: int = MAX_ADAPTIVE_ATTEMPTS,
) -> str:
    """Fetch one public page with a globally bounded request budget."""

    timeout = max(3, min(int(timeout), MAX_ADAPTIVE_TIMEOUT))
    attempts = max(1, min(int(attempts), MAX_ADAPTIVE_ATTEMPTS))
    profile = profile_for(url)
    parts = urlsplit(url)
    referer = f"{parts.scheme}://{parts.netloc}/" if parts.scheme and parts.netloc else url
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = Request(
            url,
            headers={
                "User-Agent": BROWSER_USER_AGENT if profile.id != "default" else (user_agent or BROWSER_USER_AGENT),
                "Accept": "text/html,application/xhtml+xml,application/json,application/xml,text/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": profile.accept_language,
                "Accept-Encoding": "identity",
                "Cache-Control": "no-cache",
                "Referer": referer,
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                return decode_public_bytes(
                    response.read(),
                    response.geturl() or url,
                    response.headers.get_content_charset(),
                )
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.5 * (2**attempt))
    assert last_error is not None
    raise last_error


class CrawlerProxy:
    """Delegate crawler helpers while replacing only public-web transport."""

    def __init__(self, crawler: Any) -> None:
        self._crawler = crawler

    def __getattr__(self, name: str) -> Any:
        return getattr(self._crawler, name)

    def fetch_text(
        self,
        url: str,
        user_agent: str,
        timeout: int = MAX_ADAPTIVE_TIMEOUT,
        attempts: int = MAX_ADAPTIVE_ATTEMPTS,
    ) -> str:
        return fetch_public_text(url, user_agent, timeout=timeout, attempts=attempts)


def _article_url(article: dict[str, Any]) -> str:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return str(source.get("url") or "").strip()


def _dedupe_articles(items: Iterable[dict[str, Any]], crawler: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        url = crawler.normalize_url(_article_url(item))
        if not url or url in seen:
            continue
        result.append(item)
        seen.add(url)
    return result


def _article_sort_key(article: dict[str, Any]) -> tuple[str, int, str]:
    try:
        importance = int(article.get("importance", 0) or 0)
    except (TypeError, ValueError):
        importance = 0
    return (
        str(article.get("publishedAt") or ""),
        importance,
        str(article.get("id") or ""),
    )


def merge_adaptive_history(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    crawler: Any,
    default_limit: int = DEFAULT_HISTORY_LIMIT,
) -> list[dict[str, Any]]:
    """Keep a bounded history for successful directly published website batches."""

    adaptive_statuses = {
        str(status.get("id") or ""): status
        for status in statuses
        if status.get("adapter") == "adaptive-public-v1"
        and not status.get("publisherHandoff")
        and status.get("status") in {"ok", "partial"}
        and int(status.get("accepted", 0) or 0) > 0
    }
    if not adaptive_statuses:
        return list(incoming)

    source_ids = set(adaptive_statuses)
    merged_incoming = [
        article
        for article in incoming
        if str(article.get("sourceId") or "") not in source_ids
    ]
    for source_id, status in adaptive_statuses.items():
        new_group = [
            article for article in incoming if str(article.get("sourceId") or "") == source_id
        ]
        old_group = [
            article for article in existing if str(article.get("sourceId") or "") == source_id
        ]
        new_urls = {
            crawler.normalize_url(_article_url(article)) for article in new_group
        }
        by_url: dict[str, dict[str, Any]] = {}
        for article in old_group:
            key = crawler.normalize_url(_article_url(article))
            if key:
                by_url[key] = article
        for article in new_group:
            key = crawler.normalize_url(_article_url(article))
            if key:
                by_url[key] = article
        try:
            limit = int(status.get("historyLimit", default_limit) or default_limit)
        except (TypeError, ValueError):
            limit = default_limit
        history = sorted(
            by_url.values(),
            key=_article_sort_key,
            reverse=True,
        )[: max(1, min(60, limit))]
        retained = sum(
            crawler.normalize_url(_article_url(article)) not in new_urls
            for article in history
        )
        status["newAccepted"] = len(new_group)
        status["retainedCount"] = len(history)
        status["accepted"] = len(new_group)
        if retained:
            status["retainedPrevious"] = True
            status["retainedPreviousCount"] = retained
        else:
            status.pop("retainedPrevious", None)
            status.pop("retainedPreviousCount", None)
        merged_incoming.extend(history)
    return merged_incoming


def crawl_adaptive_source(
    spec: dict[str, Any],
    user_agent: str,
    crawler: Any,
    generic: Any,
    robust: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run all public sources through the same bounded multi-entry pipeline."""

    original_url = str(spec.get("sourceUrl") or spec.get("url") or "").strip()
    canonical = canonical_source_url(original_url)
    profile = profile_for(canonical)
    proxy = CrawlerProxy(crawler)
    max_items = max(1, int(spec.get("maxItems", 10)))
    useful_yield = 1 if profile.publisher_handoff else min(MIN_USEFUL_YIELD, max_items)
    seed_limit = 2 if profile.publisher_handoff else 6
    seed_max_items = min(max_items, MIN_USEFUL_YIELD) if profile.publisher_handoff else max_items
    all_items: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    strategies: list[str] = []
    language = str(spec.get("sourceLanguage") or profile.default_language)
    localized_keywords = generic.localize_keywords(spec.get("keywords", []), language)
    profile_search_seeds = native_search_seed_urls(canonical, localized_keywords)
    configured_seeds = _unique_urls(
        [*profile_search_seeds, *source_seed_urls(canonical)],
        seed_limit,
    )
    attempted_seeds: list[str] = []

    for seed in configured_seeds:
        if len(_dedupe_articles(all_items, crawler)) >= useful_yield:
            break
        attempted_seeds.append(seed)
        seed_spec = {
            **spec,
            "url": seed,
            "sourceUrl": seed,
            "sourceLanguage": language,
            "maxItems": seed_max_items,
        }
        items, status = robust.crawl_with_second_stage(
            seed_spec,
            user_agent,
            proxy,
            generic,
        )
        all_items.extend(items)
        statuses.append(status)
        for strategy in status.get("strategies", []):
            if strategy not in strategies:
                strategies.append(strategy)

    items = _dedupe_articles(all_items, crawler)[:max_items]
    transport_requests = sum(
        int(status.get("transportRequests", status.get("scanned", 0)) or 0)
        for status in statuses
    )
    record_scanned = max(
        len(items),
        sum(int(status.get("accepted", 0) or 0) for status in statuses),
    )
    failed = sum(int(status.get("failed", 0) or 0) for status in statuses)
    has_clean_attempt = any(status.get("status") in {"ok", "empty"} for status in statuses)
    status_name = (
        "ok"
        if items and failed == 0
        else "partial"
        if items
        else "error"
        if failed or not has_clean_attempt
        else "empty"
    )
    result = crawler._status(
        spec["id"],
        generic.platform_name({**spec, "sourceUrl": canonical}),
        status_name,
        record_scanned,
        len(items),
        failed=failed,
        platform=generic.platform_name({**spec, "sourceUrl": canonical}),
        error=(
            "; ".join(
                str(status.get("error"))
                for status in statuses
                if status.get("error")
            )[:600]
            or None
        ) if not items else None,
    )
    result.update(
        {
            "adapter": "adaptive-public-v1",
            "profile": profile.id,
            "canonicalSourceUrl": canonical,
            "configuredSeeds": configured_seeds,
            "attemptedSeeds": attempted_seeds,
            "nativeSearchSeeds": profile_search_seeds,
            "strategies": strategies,
            "historyLimit": max(DEFAULT_HISTORY_LIMIT, max_items),
            "transportRequests": transport_requests,
            "requestBudget": {
                "timeoutSeconds": MAX_ADAPTIVE_TIMEOUT,
                "attempts": MAX_ADAPTIVE_ATTEMPTS,
                "seedLimit": seed_limit,
                "stopAfterAccepted": useful_yield,
            },
        }
    )

    if profile.publisher_handoff:
        discovered_count = len(items)
        result["discoveredAccepted"] = discovered_count
        result["accepted"] = 0
        result["publisherHandoff"] = profile.publisher_handoff
        result["handoffStatusId"] = profile.handoff_status_id
        if discovered_count and result.get("status") == "ok":
            result["status"] = "partial"
        return [], result

    return items, result
