"""Resolve public index navigation pages to original WeChat article URLs.

Third-party indexes are discovery-only. A candidate is accepted only after its
original endpoint resolves to a public ``mp.weixin.qq.com`` article URL. Proxy,
preview, snapshot, and aggregation URLs must never become article sources.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

try:
    from . import wechat_url_compat
except ImportError:
    import wechat_url_compat

WECHAT_HOST = "mp.weixin.qq.com"
INDEX_HOSTS = {"jintiankansha.com", "jintiankansha.me"}
ORIGINAL_ENDPOINT_PATTERN = re.compile(
    r"href\s*=\s*['\"]([^'\"]*/t_original/[A-Za-z0-9_-]+/?(?:\?[^'\"]*)?)['\"]",
    flags=re.IGNORECASE,
)
DIRECT_WECHAT_PATTERN = re.compile(
    r"https?://mp\.weixin\.qq\.com/s(?:\?|/)[^'\"<>\s]+",
    flags=re.IGNORECASE,
)


def _host(url: str) -> str:
    return (urlsplit(str(url or "")).hostname or "").casefold().removeprefix("www.")


def is_direct_wechat_url(url: str) -> bool:
    parts = urlsplit(str(url or ""))
    host = (parts.hostname or "").casefold()
    path = parts.path.rstrip("/")
    return (
        parts.scheme.casefold() == "https"
        and host == WECHAT_HOST
        and (path == "/s" or path.startswith("/s/"))
    )


def is_public_index_proxy_url(url: str) -> bool:
    parts = urlsplit(str(url or ""))
    host = (parts.hostname or "").casefold().removeprefix("www.")
    path = parts.path.rstrip("/")
    return host in INDEX_HOSTS and path.startswith(("/t/", "/t_original/", "/t_snapshot/"))


def _decode_candidate(value: str) -> str:
    return wechat_url_compat.decode_public_url(value)


def _direct_url_from_body(body: str) -> str:
    match = DIRECT_WECHAT_PATTERN.search(_decode_candidate(body))
    if not match:
        return ""
    candidate = _decode_candidate(match.group(0))
    return candidate if is_direct_wechat_url(candidate) else ""


def _original_endpoint(detail_url: str, body: str) -> str:
    match = ORIGINAL_ENDPOINT_PATTERN.search(body or "")
    return urljoin(detail_url, _decode_candidate(match.group(1))) if match else ""


def _follow_original_endpoint(
    endpoint_url: str,
    user_agent: str,
    *,
    timeout: int = 18,
) -> str:
    request = Request(
        endpoint_url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Referer": endpoint_url,
        },
    )
    with urlopen(request, timeout=timeout) as response:
        final_url = _decode_candidate(str(response.geturl() or ""))
        if is_direct_wechat_url(final_url):
            return final_url
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read(512_000).decode(charset, errors="replace")
    return _direct_url_from_body(body)


def resolve_detail_url(
    detail_url: str,
    body: str,
    user_agent: str,
) -> str:
    """Resolve one discovery page to the original public WeChat article URL."""

    if is_direct_wechat_url(detail_url):
        return detail_url
    direct = _direct_url_from_body(body)
    if direct:
        return direct
    endpoint = (
        detail_url
        if _host(detail_url) in INDEX_HOSTS
        and urlsplit(detail_url).path.startswith("/t_original/")
        else _original_endpoint(detail_url, body)
    )
    if not endpoint:
        return ""
    try:
        return _follow_original_endpoint(endpoint, user_agent)
    except Exception:  # noqa: BLE001 - unresolved proxies are rejected by design.
        return ""


def install(wechat: Any, bridge: Any) -> None:
    """Install original-link resolution and a final direct-URL acceptance guard."""

    original_resolve = bridge._resolve_detail_row
    if not getattr(original_resolve, "_wechat_original_redirect", False):

        def resolve_detail_row(
            row: dict[str, str],
            spec: dict[str, Any],
            user_agent: str,
            crawler: Any,
        ) -> list[dict[str, str]]:
            if row.get("kind") != "detail":
                return original_resolve(row, spec, user_agent, crawler)
            try:
                body = bridge._fetch_cached(row["url"], user_agent, crawler)
            except Exception:  # noqa: BLE001 - original resolver records failure upstream.
                return []
            direct_url = resolve_detail_url(row["url"], body, user_agent)
            if direct_url:
                return [
                    {
                        **row,
                        "url": direct_url,
                        "kind": "wechat",
                        "discoveryUrl": row["url"],
                    }
                ]
            return original_resolve(row, spec, user_agent, crawler)

        setattr(resolve_detail_row, "_wechat_original_redirect", True)
        bridge._resolve_detail_row = resolve_detail_row

    original_parse = wechat.parse_wechat_article
    if getattr(original_parse, "_wechat_direct_url_guard", False):
        return

    def parse_wechat_article(
        spec: dict[str, Any],
        url: str,
        body: str,
        crawler: Any,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        if not is_direct_wechat_url(url):
            return None
        article = original_parse(spec, url, body, crawler, **kwargs)
        if not article:
            return None
        source = article.get("source")
        if not isinstance(source, dict) or not is_direct_wechat_url(str(source.get("url", ""))):
            return None
        article["wechatContentMode"] = "original-page"
        return article

    setattr(parse_wechat_article, "_wechat_direct_url_guard", True)
    wechat.parse_wechat_article = parse_wechat_article
