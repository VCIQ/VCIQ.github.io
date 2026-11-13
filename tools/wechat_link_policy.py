"""Distinguish durable WeChat article shares from expiring index-navigation links.

Temporary URLs can be retained as discovery evidence, but must not be
published as durable original-article links. No URL is rewritten or guessed.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlsplit

_SHORT_CODE = re.compile(r"/s/[A-Za-z0-9_-]+")
_LONG_IDENTITY = {"__biz", "mid", "idx"}
_TEMPORARY_PARAMETERS = {"signature", "timestamp"}


def classify_wechat_article_url(value: str) -> str:
    """Return durable, temporary, unverified or other.

    Durable describes URL structure only, not the current availability of
    an article or verification of its publisher.
    """
    try:
        parts = urlsplit(str(value or "").strip())
        hostname = (parts.hostname or "").casefold()
        if hostname != "mp.weixin.qq.com" or not (
            parts.path == "/s" or parts.path.startswith("/s/")
        ):
            return "other"
        if parts.scheme.casefold() != "https" or parts.username or parts.password:
            return "unverified"
        if parts.port not in (None, 443) or parts.fragment:
            return "unverified"
        pairs = parse_qsl(parts.query, keep_blank_values=True)
    except ValueError:
        return "unverified"

    names = [key.casefold() for key, _ in pairs]
    if _TEMPORARY_PARAMETERS.intersection(names) or {"src", "ver", "new"}.issubset(names):
        return "temporary"
    if _SHORT_CODE.fullmatch(parts.path):
        return "durable"
    if parts.path != "/s":
        return "unverified"

    params: dict[str, list[str]] = {}
    for key, item in pairs:
        params.setdefault(key, []).append(item)
    if not all(len(params.get(key, [])) == 1 and params[key][0] for key in _LONG_IDENTITY):
        return "unverified"
    if not params["mid"][0].isdigit() or not params["idx"][0].isdigit():
        return "unverified"
    if "sn" in params and (len(params["sn"]) != 1 or not params["sn"][0]):
        return "unverified"
    return "durable"


def is_durable_wechat_article_url(value: str) -> bool:
    return classify_wechat_article_url(value) == "durable"


def is_non_durable_wechat_article_url(value: str) -> bool:
    return classify_wechat_article_url(value) in {"temporary", "unverified"}



def historical_signed_wechat_key(article: object) -> tuple[str, str, str] | None:
    """Identify a pre-existing WeChat signed article without trusting new input.

    A key is only grandfathered when matched against the *persisted old
    snapshot*. Never treat this predicate as permission to publish an incoming
    signed URL; only historic records can be retained for manual repair.
    """
    if not isinstance(article, dict):
        return None
    source = article.get("source")
    if not isinstance(source, dict) or source.get("platform") != "微信":
        return None
    if article.get("wechatContentMode") == "index-only":
        return None
    article_id = str(article.get("id") or "").strip()
    source_id = str(article.get("sourceId") or "").strip()
    title = str(article.get("title") or "").strip()
    url = str(source.get("url") or "").strip()
    if not (article_id and source_id and title and url):
        return None
    if classify_wechat_article_url(url) != "temporary":
        return None
    return article_id, source_id, url
