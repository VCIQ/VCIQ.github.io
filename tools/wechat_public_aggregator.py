"""Use a public WeChat article index when Sogou/Bing discovery yields no links.

The fallback reads only the public server-rendered homepage at
``weixin.imaseo.com``. It does not call the site's credentialed management API,
does not solve CAPTCHAs, and accepts only direct ``mp.weixin.qq.com/s`` links.
Original WeChat pages are still fetched and parsed by the existing strict path.
"""

from __future__ import annotations

import html
import re
import threading
import time
from datetime import UTC, datetime
from typing import Any, Iterable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

try:
    from . import wechat_url_compat
except ImportError:
    import wechat_url_compat

INDEX_URL = "https://weixin.imaseo.com/"
MAX_RESPONSE_BYTES = 12 * 1024 * 1024
REQUEST_TIMEOUT = 24
CACHE_TTL_SECONDS = 10 * 60
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)
_LINK_PATTERN = re.compile(
    r"<a\b[^>]*href=[\"'](https?://mp\.weixin\.qq\.com/[^\"']+)[\"'][^>]*>(.*?)</a>",
    flags=re.IGNORECASE | re.DOTALL,
)
_DATE_PATTERN = re.compile(
    r"(?<!\d)(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})(?:日)?"
    r"(?:[ T]+\d{1,2}:\d{2}(?::\d{2})?)?",
    flags=re.IGNORECASE,
)
_CACHE: tuple[float, str] | None = None
_LOCK = threading.Lock()


def _clean(value: Any, limit: int = 500) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", str(value or ""))
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()[:limit]


def _is_direct_wechat(url: str) -> bool:
    parts = urlsplit(wechat_url_compat.decode_public_url(url))
    path = parts.path.rstrip("/")
    return (
        parts.scheme.casefold() == "https"
        and (parts.hostname or "").casefold() == "mp.weixin.qq.com"
        and (path == "/s" or path.startswith("/s/"))
    )


def _fetch_index() -> str:
    global _CACHE
    now = time.monotonic()
    with _LOCK:
        if _CACHE and now - _CACHE[0] < CACHE_TTL_SECONDS:
            return _CACHE[1]
        request = Request(
            INDEX_URL,
            headers={
                "User-Agent": BROWSER_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            },
        )
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                raise ValueError("public WeChat index exceeded size limit")
            charset = response.headers.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
        _CACHE = (time.monotonic(), body)
        return body


def _expected_accounts(spec: dict[str, Any]) -> list[str]:
    values: Iterable[Any] = [
        *spec.get("expectedAccounts", []),
        spec.get("queryIdentity"),
        spec.get("name"),
    ]
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clean(value, 100)
        key = item.casefold()
        if not item or key in seen or item.startswith("微信公众号 ·"):
            continue
        result.append(item)
        seen.add(key)
    return result


def _published_at(text: str) -> str | None:
    match = _DATE_PATTERN.search(text)
    if not match:
        return None
    try:
        value = datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            tzinfo=UTC,
        )
        return value.date().isoformat()
    except ValueError:
        return None


def parse_public_index(body: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract account-matched rows with original WeChat article URLs."""

    expected = _expected_accounts(spec)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in _LINK_PATTERN.finditer(body or ""):
        url = wechat_url_compat.decode_public_url(match.group(1))
        if not _is_direct_wechat(url) or url in seen:
            continue
        title = _clean(match.group(2), 260)
        if not title or title in {"打开原文", "原文", "查看原文"}:
            continue
        window = _clean((body or "")[match.end() : match.end() + 900], 800)
        account = next(
            (value for value in expected if value.casefold() in window.casefold()),
            "",
        )
        if expected and not account:
            continue
        published_at = _published_at(window)
        rows.append(
            {
                "url": url,
                "directUrl": url,
                "title": title,
                "summary": title,
                "account": account or _clean(spec.get("queryIdentity") or spec.get("name"), 100),
                "publishedAt": published_at,
            }
        )
        seen.add(url)
        if len(rows) >= max(10, int(spec.get("maxItems", 6)) * 3):
            break
    return rows


def discover(spec: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = parse_public_index(_fetch_index(), spec)
    return rows, {
        "provider": "public-wechat-aggregator",
        "query": str(spec.get("queryIdentity") or spec.get("name") or ""),
        "scanned": len(rows),
        "resolved": len(rows),
        "failed": 0,
    }


def install(index: Any) -> None:
    """Append the public index only when the primary route resolved nothing."""

    original = index.discover
    if getattr(original, "_public_aggregator_fallback", False):
        return

    def discover_with_fallback(
        spec: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        primary_rows: list[dict[str, Any]] = []
        primary_meta: dict[str, Any] = {}
        primary_error = ""
        try:
            primary_rows, primary_meta = original(spec)
        except Exception as exc:  # noqa: BLE001 - public fallback remains bounded.
            primary_error = f"{type(exc).__name__}: {exc}"
        if any(row.get("directUrl") for row in primary_rows):
            return primary_rows, primary_meta
        fallback_rows, fallback_meta = discover(spec)
        if fallback_rows:
            fallback_meta["primaryProvider"] = primary_meta.get("provider", "sogou-weixin")
            fallback_meta["primaryScanned"] = int(primary_meta.get("scanned", 0) or 0)
            if primary_error:
                fallback_meta["primaryError"] = primary_error[:240]
            return fallback_rows, fallback_meta
        if primary_error:
            raise RuntimeError(
                f"primary WeChat discovery failed ({primary_error}); public index returned no account match"
            )
        return primary_rows, primary_meta

    setattr(discover_with_fallback, "_public_aggregator_fallback", True)
    index.discover = discover_with_fallback
