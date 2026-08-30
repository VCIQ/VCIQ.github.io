"""Low-rate compatibility fetcher for public WeChat article pages.

The fetcher is intentionally narrow: it accepts only public
``mp.weixin.qq.com/s`` URLs, presents a current WeChat in-app browser user
agent, never solves CAPTCHA challenges, never rotates proxies, and stops when
WeChat returns a block page.
"""

from __future__ import annotations

import threading
import time
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

MICROMESSENGER_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "MicroMessenger/8.0.34(0x16082222) NetType/WIFI Language/zh_CN"
)
MIN_REQUEST_INTERVAL_SECONDS = 1.35
MAX_RESPONSE_BYTES = 5_000_000
BLOCK_MARKERS = (
    "环境异常",
    "访问过于频繁",
    "当前环境存在异常",
    "请输入验证码",
    "请在微信客户端打开链接",
)

_lock = threading.Lock()
_next_request_at = 0.0


class WeChatOriginalUnavailable(RuntimeError):
    pass


def is_public_article_url(url: str) -> bool:
    parts = urlsplit(str(url or ""))
    path = parts.path.rstrip("/")
    return (
        parts.scheme.casefold() == "https"
        and (parts.hostname or "").casefold() == "mp.weixin.qq.com"
        and (path == "/s" or path.startswith("/s/"))
    )


def _wait_for_rate_limit() -> None:
    global _next_request_at
    with _lock:
        now = time.monotonic()
        wait = _next_request_at - now
        if wait > 0:
            time.sleep(wait)
        _next_request_at = time.monotonic() + MIN_REQUEST_INTERVAL_SECONDS


def fetch_public_wechat_page(
    url: str,
    timeout: int = 18,
    attempts: int = 2,
) -> str:
    """Fetch one original public article without CAPTCHA or proxy evasion."""

    if not is_public_article_url(url):
        raise ValueError("WeChat original fetch requires an mp.weixin.qq.com/s URL")
    last_error: Exception | None = None
    for attempt in range(max(1, min(int(attempts), 2))):
        _wait_for_rate_limit()
        request = Request(
            url,
            headers={
                "User-Agent": MICROMESSENGER_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
                "Referer": "https://mp.weixin.qq.com/",
                "Connection": "close",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                final_url = str(response.geturl() or url)
                if not is_public_article_url(final_url):
                    raise WeChatOriginalUnavailable(
                        f"WeChat original redirected outside the public article host: {final_url}"
                    )
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise WeChatOriginalUnavailable("WeChat article response exceeded size limit")
                text = body.decode(charset, errors="replace")
                if any(marker in text for marker in BLOCK_MARKERS):
                    raise WeChatOriginalUnavailable("WeChat returned a verification or block page")
                if "js_content" not in text and "activity-name" not in text and "og:title" not in text:
                    raise WeChatOriginalUnavailable("Response is not a recognizable WeChat article page")
                return text
        except WeChatOriginalUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - one bounded retry for transient I/O.
            last_error = exc
            if attempt + 1 < max(1, min(int(attempts), 2)):
                time.sleep(1.1 * (attempt + 1))
    assert last_error is not None
    raise last_error


def install(wechat: Any) -> None:
    """Replace only the original-page transport used by the WeChat parser."""

    current = wechat.fetch_public_wechat_page
    if getattr(current, "_micromessenger_compat", False):
        return
    setattr(fetch_public_wechat_page, "_micromessenger_compat", True)
    wechat.fetch_public_wechat_page = fetch_public_wechat_page
