"""Recognize current public Sogou result redirects to original WeChat articles.

The base parser handles the historical ``url +=`` script. Current public result
pages can expose the same destination through escaped article HTML, location
assignments, JSON fields, or a meta refresh. This compatibility layer only accepts
original ``mp.weixin.qq.com/s`` URLs and never attempts to bypass CAPTCHA pages.

We deliberately avoid ``html.unescape`` on whole URLs. Python's permissive HTML
entity decoder interprets the prefix of ``&timestamp`` as the legacy ``&times``
entity, corrupting signed WeChat URLs into ``×tamp``. Only explicit URL-safe HTML
entities are decoded here. Some current Sogou jump pages already expose that
legacy-entity artifact in the returned markup, so the narrowly scoped WeChat URL
repair converts only ``×tamp=`` / ``&times;tamp=`` back to ``&timestamp=``.
"""

from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import urljoin, urlsplit

try:
    from . import wechat_url_compat
except ImportError:
    import wechat_url_compat

_DIRECT_PATTERN = re.compile(
    r"https?://mp\.weixin\.qq\.com/s(?:\?|/)[^'\"<>\s]+",
    flags=re.IGNORECASE,
)
_LEGACY_CHUNK_PATTERN = re.compile(
    r"(?:var\s+)?(?:url|jump_url)\s*\+=\s*['\"]",
    flags=re.IGNORECASE,
)
_PATTERNS = (
    re.compile(
        r"(?:window\.|top\.)?location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:window\.|top\.)?location\.(?:replace|assign)\(\s*['\"]([^'\"]+)['\"]",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"<meta[^>]+http-equiv=['\"]?refresh['\"]?[^>]+content=['\"][^'\"]*url\s*=\s*([^'\";>]+)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"['\"](?:url|jump_url|redirect_url|target_url)['\"]\s*:\s*['\"]([^'\"]+)['\"]",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"href\s*=\s*['\"]([^'\"]*mp\.weixin\.qq\.com/s(?:\?|/)[^'\"]*)['\"]",
        flags=re.IGNORECASE,
    ),
)

def _repair_wechat_timestamp_artifact(value: str) -> str:
    return wechat_url_compat.decode_public_url(value)


def _decode(value: str) -> str:
    return wechat_url_compat.decode_public_url(value).strip().strip("'\"")


def _is_original(url: str) -> bool:
    parts = urlsplit(str(url or ""))
    path = parts.path.rstrip("/")
    return (
        parts.scheme.casefold() == "https"
        and (parts.hostname or "").casefold() == "mp.weixin.qq.com"
        and (path == "/s" or path.startswith("/s/"))
    )


def _candidates(body: str) -> Iterable[str]:
    decoded_body = _decode(body)
    for match in _DIRECT_PATTERN.finditer(decoded_body):
        yield match.group(0)
    for pattern in _PATTERNS:
        for match in pattern.finditer(decoded_body):
            yield match.group(1)


def resolve_current_redirect(body: str, base_url: str = "") -> str:
    for raw in _candidates(body or ""):
        candidate = _repair_wechat_timestamp_artifact(_decode(raw))
        if candidate.startswith("//"):
            candidate = f"https:{candidate}"
        elif candidate.startswith("/") and base_url:
            candidate = urljoin(base_url, candidate)
        if _is_original(candidate):
            return candidate
    return ""


def install(index: Any) -> None:
    """Extend the narrow script resolver while preserving all existing guards."""

    original = index.resolve_script_url
    if getattr(original, "_current_sogou_redirects", False):
        return

    def normalize_candidate(value: str) -> str:
        candidate = _repair_wechat_timestamp_artifact(value)
        if not candidate or not _is_original(candidate):
            return ""
        normalizer = getattr(index, "_normalized_url", None)
        return normalizer(candidate) if callable(normalizer) else candidate

    def resolve_script_url(body: str) -> str:
        # The historical resolver is authoritative for its native ``url +=``
        # chunks. A generic direct-URL regex would otherwise accept only the
        # first (valid-looking but incomplete) chunk.
        if _LEGACY_CHUNK_PATTERN.search(body or ""):
            return normalize_candidate(original(body))

        current = resolve_current_redirect(body)
        if current:
            return normalize_candidate(current)
        return normalize_candidate(original(body))

    setattr(resolve_script_url, "_current_sogou_redirects", True)
    index.resolve_script_url = resolve_script_url
