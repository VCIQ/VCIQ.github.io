"""Resolve modern Google News article wrappers to publisher URLs.

Google's current RSS article IDs are opaque. This resolver uses the article-page
signature plus the Fbv4je batchexecute response. The endpoint is undocumented;
callers must rate-limit, retain unresolved wrappers, and never treat failure as
proof that an article does not exist.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
CONSENT_COOKIE = "CONSENT=YES+cb; SOCS=CAI"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def _read(url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None) -> str:
    request_headers = {
        "User-Agent": USER_AGENT,
        "Cookie": CONSENT_COOKIE,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    }
    request_headers.update(headers or {})
    request = Request(url, data=data, headers=request_headers)
    with urlopen(request, timeout=20) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError("Google News response exceeded size limit")
        charset = response.headers.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")


def resolve_google_news_url(url: str) -> dict[str, Any]:
    """Return publisher URL and method; preserve wrapper when unresolved."""
    parts = urlsplit(url)
    if parts.hostname not in {"news.google.com", "www.news.google.com"}:
        return {"resolved": True, "url": url, "method": "already-publisher-url"}

    segments = [part for part in parts.path.split("/") if part]
    if len(segments) < 2 or segments[-2] not in {"articles", "read"}:
        return {"resolved": False, "url": url, "method": "unsupported-google-url"}

    article_id = segments[-1]
    page_url = f"https://news.google.com/articles/{article_id}"
    page = _read(page_url)
    signature = re.search(r'data-n-a-sg="([^"]+)"', page)
    timestamp = re.search(r'data-n-a-ts="([^"]+)"', page)
    if not signature or not timestamp:
        return {"resolved": False, "url": url, "method": "signature-missing"}

    inner = (
        '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,'
        'null,null,null,null,null,0,1],"X","X",1,[1,1],1,1,null,0,0,null,0],'
        f'{json.dumps(article_id)},{timestamp.group(1)},{json.dumps(signature.group(1))}]'
    )
    form = urlencode({
        "f.req": json.dumps([[["Fbv4je", inner, None, "generic"]]], separators=(",", ":"))
    }).encode("utf-8")
    raw = _read(
        "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
    )
    chunks = raw.split("\n\n", 1)
    if len(chunks) != 2:
        return {"resolved": False, "url": url, "method": "rpc-response-unexpected"}
    decoded = None
    for line in chunks[1].splitlines():
        try:
            outer = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(outer, list):
            for item in outer:
                if isinstance(item, list) and len(item) >= 3 and item[0] == "wrb.fr":
                    try:
                        decoded = json.loads(item[2])
                    except (TypeError, json.JSONDecodeError):
                        pass
    if not decoded or not isinstance(decoded, list) or len(decoded) < 2:
        return {"resolved": False, "url": url, "method": "publisher-url-missing"}
    publisher_url = str(decoded[1] or "").strip()
    publisher_host = (urlsplit(publisher_url).hostname or "").lower()
    if not publisher_url.startswith(("https://", "http://")) or not publisher_host:
        return {"resolved": False, "url": url, "method": "publisher-url-invalid"}
    return {
        "resolved": True,
        "url": publisher_url,
        "method": "google-news-rpc",
        "publisherDomain": publisher_host.removeprefix("www."),
    }
