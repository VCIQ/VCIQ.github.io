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
from urllib.parse import unquote, urljoin, urlsplit

_DIRECT_PATTERN = re.compile(
    r"https?://mp\.weixin\.qq\.com/s(?:\?|/)[^'\"<>\s]+",
    flags=re.IGNORECASE,
)
_LEGACY_CHUNK_PATTERN = re.compile(
    r"(?:var\s+)?(?:url|jump_url)\s*\+=\s*['\"]",
    flags=re.IGNORECASE,
)
_TIMESTAMP_ARTIFACT_PATTERN = re.compile(
    r"(?:&times;tamp|×tamp|%c3%97tamp|%26times%3btamp)(?:=|%3d)",
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

_EXPLICIT_HTML_ENTITIES = {
    "&amp;": "&",
    "&#38;": "&",
    "&#x26;": "&",
    "&#X26;": "&",
    "&quot;": '"',
    "&#34;": '"',
    "&#x22;": '"',
    "&#X22;": '"',
    "&apos;": "'",
    "&#39;": "'",
    "&#x27;": "'",
    "&#X27;": "'",
}


def _explicit_html_unescape(value: str) -> str:
    text = str(value or "")
    for old, new in _EXPLICIT_HTML_ENTITIES.items():
        text = text.replace(old, new)
    return text


def _repair_wechat_timestamp_artifact(value: str) -> str:
    text = str(value or "")
    # Apply only to the distinctive query-parameter artifact observed on Sogou
    # redirect pages. The final host/path check still gates acceptance.
    return _TIMESTAMP_ARTIFACT_PATTERN.sub("&timestamp=", text)


def _decode(value: str) -> str:
    text = _explicit_html_unescape(value)
    replacements = {
        "\\/": "/",
        "\\x26": "&",
        "\\u0026": "&",
        "\\u003d": "=",
        "\\u003D": "=",
        "\\u002f": "/",
        "\\u002F": "/",
        "\\u003a": ":",
        "\\u003A": ":",
        "\\u0025": "%",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    for _ in range(2):
        decoded = unquote(text)
        if decoded == text:
            break
        text = decoded
    return _repair_wechat_timestamp_artifact(text).strip().strip("'\"")


def _is_original(url: str) -> bool:
    parts = urlsplit(str(url or ""))
    path = parts.path.rstrip("/")
    return (
        (parts.hostname or "").casefold() == "mp.weixin.qq.com"
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
            return candidate
        normalizer = getattr(index, "_normalized_url", None)
        return normalizer(candidate) if callable(normalizer) else candidate

    def resolve_script_url(body: str) -> str:
        # The historical resolver is authoritative for its native ``url +=``
        # chunks. A generic direct-URL regex would otherwise accept only the
        # first (valid-looking but incomplete) chunk.
        if _LEGACY_CHUNK_PATTERN.search(body or ""):
            legacy = normalize_candidate(original(body))
            if legacy:
                return legacy

        current = resolve_current_redirect(body)
        if current:
            return normalize_candidate(current)
        return normalize_candidate(original(body))

    setattr(resolve_script_url, "_current_sogou_redirects", True)
    index.resolve_script_url = resolve_script_url
