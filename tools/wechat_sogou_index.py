"""Low-rate public discovery through Sogou's WeChat article search.

Only server-rendered public pages are used. CAPTCHA pages are never solved or
bypassed; a process-local circuit breaker lets the caller retain old data.
"""

from __future__ import annotations

import html
import http.cookiejar
import re
import threading
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener

SOGOU_HOME = "https://weixin.sogou.com/"
MIN_REQUEST_INTERVAL_SECONDS = 1.25
CIRCUIT_BREAKER_SECONDS = 300.0
MAX_SEARCH_RESULTS = 10
CAPTCHA_MARKERS = ("请输入验证码", "antispider", "VerifyCode", "正常行为不是自动程序")
GENERIC_QUERY_TERMS = {
    "ai", "agi", "人工智能", "技术", "科技", "行业", "产业", "公司", "研究", "产品", "平台",
}

_cookie_jar = http.cookiejar.CookieJar()
_opener = build_opener(HTTPCookieProcessor(_cookie_jar))
_lock = threading.Lock()
_next_request_at = 0.0
_blocked_until = 0.0
_session_ready = False


class SogouUnavailable(RuntimeError):
    pass


def _clean(value: Any, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()[:limit]


def _strip_markup(value: str, limit: int = 500) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value or "")
    return _clean(re.sub(r"(?s)<[^>]+>", " ", value), limit)


def _url_entity_unescape(value: str) -> str:
    return (
        str(value or "")
        .replace("&amp;", "&")
        .replace("&#38;", "&")
        .replace("&#x26;", "&")
        .replace("&#X26;", "&")
    )


def _normalized_url(value: str) -> str:
    parts = urlsplit(_url_entity_unescape(value))
    query = urlencode(parse_qsl(parts.query, keep_blank_values=True))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def _request(url: str, *, referer: str = "", timeout: int = 16) -> str:
    global _next_request_at, _blocked_until, _session_ready
    with _lock:
        now = time.monotonic()
        if now < _blocked_until:
            raise SogouUnavailable("Sogou CAPTCHA cooldown is active")
        wait = _next_request_at - now
        if wait > 0:
            time.sleep(wait)

        def fetch(target: str, source: str = "") -> str:
            request = Request(target, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
                **({"Referer": source} if source else {}),
            })
            with _opener.open(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")

        try:
            if not _session_ready:
                home = fetch(SOGOU_HOME)
                if any(marker.casefold() in home.casefold() for marker in CAPTCHA_MARKERS):
                    _blocked_until = time.monotonic() + CIRCUIT_BREAKER_SECONDS
                    raise SogouUnavailable("Sogou returned an anti-spider page")
                _session_ready = True
                time.sleep(0.2)
            body = fetch(url, referer or SOGOU_HOME)
        finally:
            _next_request_at = time.monotonic() + MIN_REQUEST_INTERVAL_SECONDS

        if any(marker.casefold() in body.casefold() for marker in CAPTCHA_MARKERS):
            _blocked_until = time.monotonic() + CIRCUIT_BREAKER_SECONDS
            raise SogouUnavailable("Sogou returned an anti-spider page")
        return body


def _identity_term(spec: dict[str, Any]) -> str:
    expected = spec.get("expectedAccounts") or []
    sector = _clean(spec.get("sector"), 30)
    if spec.get("genericDiscovery"):
        return _clean(spec.get("queryIdentity") or sector, 30)
    return _clean(
        spec.get("queryIdentity")
        or (expected[0] if expected else spec.get("name", "")),
        30,
    )


def _topic_term(spec: dict[str, Any], identity: str) -> str:
    sector = _clean(spec.get("sector"), 30)
    keywords = [
        _clean(value, 30)
        for value in spec.get("keywords", [])
        if _clean(value, 30).casefold() not in GENERIC_QUERY_TERMS
        and len(_clean(value, 30)) >= 2
        and _clean(value, 30).casefold() != identity.casefold()
    ]
    return keywords[0] if keywords else sector


def _query_term(spec: dict[str, Any]) -> str:
    identity = _identity_term(spec)
    topic = _topic_term(spec, identity)
    sector = _clean(spec.get("sector"), 30)
    return _clean(f"{identity} {topic}", 38) or sector


def _query_terms(spec: dict[str, Any]) -> list[str]:
    """Return conservative query fallbacks for an account-scoped source.

    Generic discovery keeps a single query. Configured publishers try the
    existing publisher+topic query first, then publisher+sector, and finally
    publisher-only. Broader fallbacks run only when the previous query returns
    zero server-rendered article rows; downstream account verification is
    unchanged.
    """

    primary = _query_term(spec)
    if spec.get("genericDiscovery"):
        return [primary] if primary else []

    identity = _identity_term(spec)
    sector = _clean(spec.get("sector"), 30)
    candidates = [
        primary,
        _clean(f"{identity} {sector}", 38) if identity and sector else "",
        identity,
    ]
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate = _clean(candidate, 38)
        key = candidate.casefold()
        if not candidate or key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result


def build_search_url(
    spec: dict[str, Any],
    page: int = 1,
    *,
    query: str | None = None,
) -> str:
    term = _clean(query, 38) if query is not None else _query_term(spec)
    return (
        "https://weixin.sogou.com/weixin?"
        f"type=2&s_from=input&query={quote(term)}&page={max(1, page)}&ie=utf8"
    )


def _result_blocks(body: str) -> list[str]:
    anchors = list(re.finditer(
        r'<a(?=[^>]*(?:id="sogou_vr_11002601_title_\d+"|uigs="article_title_\d+"))[^>]*href="[^"]+"[^>]*>',
        body, flags=re.IGNORECASE | re.DOTALL,
    ))
    blocks: list[str] = []
    for anchor in anchors[:MAX_SEARCH_RESULTS]:
        start = body.rfind("<li", 0, anchor.start())
        end = body.find("</li>", anchor.end())
        if start < 0:
            start = body.rfind('<div class="txt-box"', 0, anchor.start())
        if end < 0:
            end = body.find('<div class="txt-box"', anchor.end())
        if start >= 0 and end > start:
            blocks.append(body[start : end + 5])
    return blocks


def _first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else ""


def parse_search_results(body: str, search_url: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for block in _result_blocks(body):
        href = _first_match(
            r'<a(?=[^>]*(?:id="sogou_vr_11002601_title_\d+"|uigs="article_title_\d+"))[^>]*href="([^"]+)"[^>]*>', block
        )
        if not href:
            continue
        result_url = _normalized_url(urljoin(search_url, _url_entity_unescape(href)))
        if not result_url or result_url in seen:
            continue
        title_html = _first_match(
            r'<a(?=[^>]*(?:id="sogou_vr_11002601_title_\d+"|uigs="article_title_\d+"))[^>]*>(.*?)</a>', block
        )
        description = _strip_markup(
            _first_match(r'<p[^>]*class="[^"]*txt-info[^"]*"[^>]*>(.*?)</p>', block), 500
        )
        account = _strip_markup(
            _first_match(r'<a(?=[^>]*(?:class="[^"]*account[^"]*"|uigs="article_account_\d+"))[^>]*>(.*?)</a>', block), 100
        )
        timestamp = _first_match(r"timeConvert\(\s*['\"]?(\d{10,13})['\"]?\s*\)", block) or _first_match(r'\b(?:t|time)="(\d{10,13})"', block)
        published_at = None
        if timestamp:
            number = int(timestamp)
            if number > 10_000_000_000:
                number //= 1000
            try:
                published_at = datetime.fromtimestamp(number, UTC).date().isoformat()
            except (OSError, OverflowError, ValueError):
                pass
        results.append({
            "url": result_url,
            "title": _strip_markup(title_html, 260),
            "summary": description,
            "account": account,
            "publishedAt": published_at,
        })
        seen.add(result_url)
    return results


def resolve_script_url(body: str) -> str:
    chunks = re.findall(
        r"(?:var\s+)?(?:url|jump_url)\s*\+=\s*['\"](.*?)['\"]\s*;?",
        body or "", flags=re.IGNORECASE | re.DOTALL,
    )
    if chunks:
        value = "".join(chunks)
    else:
        direct = re.search(
            r"https?://mp\.weixin\.qq\.com/(?:s|s\?)[^'\"<>\s]+",
            html.unescape(body or ""), flags=re.IGNORECASE,
        )
        value = direct.group(0) if direct else ""
    value = _url_entity_unescape(value).replace("\\/", "/").replace("\\x26", "&").replace("@", "")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or parts.hostname != "mp.weixin.qq.com":
        return ""
    return _normalized_url(value)


def resolve_result_url(result_url: str, search_url: str) -> str:
    return resolve_script_url(_request(_normalized_url(result_url), referer=search_url))


def discover(spec: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query_attempts: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    search_url = ""
    query_used = ""

    for query in _query_terms(spec):
        candidate_url = build_search_url(spec, query=query)
        candidate_rows = parse_search_results(_request(candidate_url), candidate_url)
        query_attempts.append({"query": query, "scanned": len(candidate_rows)})
        search_url = candidate_url
        query_used = query
        rows = candidate_rows
        if rows:
            break

    resolved = 0
    failures = 0
    for row in rows:
        try:
            direct = resolve_result_url(row["url"], search_url)
        except Exception:
            direct = ""
            failures += 1
        if direct:
            row["directUrl"] = direct
            resolved += 1
    return rows, {
        "provider": "sogou-weixin",
        "query": query_used or _query_term(spec),
        "queryAttempts": query_attempts,
        "queryFallbackUsed": len(query_attempts) > 1,
        "scanned": len(rows),
        "resolved": resolved,
        "failed": failures,
    }