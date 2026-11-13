"""Crawl the public Toutiao PC feed with original-domain article links.

The previous per-track route depended on Google News RSS wrappers. This adapter
uses Toutiao's public PC feed directly, sends the browser headers required by the
endpoint, retains only short metadata/abstracts, and emits canonical
``toutiao.com/group/<item_id>/`` links.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime
from typing import Any, Sequence
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

FEED_ENDPOINT = "https://www.toutiao.com/api/pc/feed/"
REFERER = "https://www.toutiao.com/"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)
DEFAULT_CATEGORIES = ("news_tech", "__all__")
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
REQUEST_TIMEOUT = 24
REQUEST_ATTEMPTS = 3
MIN_REQUEST_INTERVAL_SECONDS = 0.55
_CACHE_TTL_SECONDS = 8 * 60
_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_LOCK = threading.Lock()
_NEXT_REQUEST_AT = 0.0


def _pace() -> None:
    global _NEXT_REQUEST_AT
    with _LOCK:
        wait = _NEXT_REQUEST_AT - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _NEXT_REQUEST_AT = time.monotonic() + MIN_REQUEST_INTERVAL_SECONDS


def _feed_url(category: str) -> str:
    query = urlencode(
        {
            "category": category,
            "utm_source": "toutiao",
            "wid": "1",
            "max_behot_time": "0",
        }
    )
    return f"{FEED_ENDPOINT}?{query}"


def _fetch_category(category: str) -> list[dict[str, Any]]:
    cached = _CACHE.get(category)
    if cached and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
        return list(cached[1])

    last_error: Exception | None = None
    for attempt in range(REQUEST_ATTEMPTS):
        _pace()
        request = Request(
            _feed_url(category),
            headers={
                "User-Agent": BROWSER_USER_AGENT,
                "Referer": REFERER,
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
                "Cache-Control": "no-cache",
            },
        )
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
                if len(payload) > MAX_RESPONSE_BYTES:
                    raise ValueError("Toutiao feed response exceeded size limit")
                charset = response.headers.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace")
            decoded = json.loads(body)
            rows = decoded.get("data", []) if isinstance(decoded, dict) else []
            if not isinstance(rows, list):
                raise ValueError("Toutiao feed data is not an array")
            normalized = [row for row in rows if isinstance(row, dict)]
            _CACHE[category] = (time.monotonic(), normalized)
            return list(normalized)
        except HTTPError as exc:
            last_error = exc
            if exc.code != 429 and exc.code < 500:
                break
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
        if attempt + 1 < REQUEST_ATTEMPTS:
            time.sleep(min(4.0, 0.8 * (2**attempt)))
    assert last_error is not None
    raise last_error


def _canonical_url(row: dict[str, Any]) -> str:
    item_id = str(
        row.get("item_id")
        or row.get("group_id")
        or row.get("id")
        or ""
    ).strip()
    if item_id.isdigit():
        return f"https://www.toutiao.com/group/{item_id}/"
    for key in ("display_url", "article_url", "url"):
        value = str(row.get(key) or "").strip()
        host = (urlsplit(value).hostname or "").casefold()
        if host == "toutiao.com" or host.endswith(".toutiao.com"):
            return value
    return ""


def _published_at(row: dict[str, Any], crawler: Any) -> str | None:
    for key in ("behot_time", "publish_time", "create_time"):
        raw = row.get(key)
        try:
            timestamp = int(raw or 0)
        except (TypeError, ValueError):
            timestamp = 0
        if timestamp > 10_000_000_000:
            timestamp //= 1000
        if timestamp > 0:
            try:
                return datetime.fromtimestamp(timestamp, UTC).date().isoformat()
            except (OverflowError, OSError, ValueError):
                pass
    return crawler.normalize_date(
        row.get("datetime") or row.get("date") or row.get("publish_date")
    )


def _row_article(
    row: dict[str, Any],
    spec: dict[str, Any],
    crawler: Any,
) -> dict[str, Any] | None:
    title = crawler.clean_title(str(row.get("title") or ""))
    summary = crawler.strip_html(
        str(row.get("abstract") or row.get("summary") or row.get("description") or "")
    )
    url = _canonical_url(row)
    published_at = _published_at(row, crawler)
    if not title or len(title) < 6 or not url or not published_at:
        return None
    if not crawler._matches_keywords(
        title,
        summary,
        spec.get("keywords", []),
        title_only=bool(spec.get("strictTitleKeywords")),
    ):
        return None
    if not crawler._matches_required_keywords(
        title,
        summary,
        spec.get("requiredKeywords", []),
        title_only=bool(spec.get("strictRequiredTitleKeywords")),
    ):
        return None
    source_name = crawler.clean_text(str(row.get("source") or spec.get("name") or "今日头条"))
    return crawler._external_article(
        spec,
        title=title,
        summary=summary or f"{source_name} 在今日头条发布相关公开信息，完整内容见原文。",
        url=url,
        published_at=published_at,
        source_name=source_name,
        source_level=spec.get("sourceLevel", "媒体报道"),
        platform="今日头条",
    )


def crawl_toutiao_source(
    spec: dict[str, Any],
    user_agent: str,
    crawler: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    del user_agent
    categories: Sequence[str] = spec.get("categories") or DEFAULT_CATEGORIES
    accepted: list[dict[str, Any]] = []
    seen: set[str] = set()
    scanned = 0
    failures = 0
    errors: list[str] = []
    for category in categories:
        try:
            rows = _fetch_category(str(category))
        except Exception as exc:  # noqa: BLE001 - represented in source status.
            failures += 1
            errors.append(f"{category}: {type(exc).__name__}: {exc}")
            continue
        for row in rows:
            scanned += 1
            article = _row_article(row, spec, crawler)
            if not article:
                continue
            source = article.get("source") if isinstance(article.get("source"), dict) else {}
            url = str(source.get("url", ""))
            if not url or url in seen:
                continue
            accepted.append(article)
            seen.add(url)
            if len(accepted) >= int(spec.get("maxItems", 8)):
                break
        if len(accepted) >= int(spec.get("maxItems", 8)):
            break

    status = (
        "partial" if accepted and failures
        else "ok" if accepted
        else "error" if failures
        else "empty"
    )
    return accepted, crawler._status(
        spec["id"],
        spec["name"],
        status,
        scanned,
        len(accepted),
        failed=failures,
        platform="今日头条",
        error=("; ".join(errors)[:240] if errors else None)
        or (None if status in {"ok", "empty"} else "Toutiao feed request failed"),
    )


def install(tracking: Any) -> None:
    """Install the adapter after all standard runtime source overrides."""

    original_install = tracking._install_runtime_overrides
    if getattr(original_install, "_toutiao_public_feed", False):
        return

    def install_runtime(
        merged: dict[str, Any],
        sec_specs: dict[str, tuple[str, str, str, str]],
        active_ids: set[str],
    ) -> None:
        original_install(merged, sec_specs, active_ids)
        original_crawl_source = tracking.crawler._crawl_config_source
        if getattr(original_crawl_source, "_toutiao_public_feed_dispatch", False):
            return

        def crawl_source(
            spec: dict[str, Any], user_agent: str
        ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            if spec.get("adapter") == "toutiao_feed":
                return crawl_toutiao_source(spec, user_agent, tracking.crawler)
            return original_crawl_source(spec, user_agent)

        setattr(crawl_source, "_toutiao_public_feed_dispatch", True)
        tracking.crawler._crawl_config_source = crawl_source

    setattr(install_runtime, "_toutiao_public_feed", True)
    tracking._install_runtime_overrides = install_runtime
