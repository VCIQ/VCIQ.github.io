"""Decode public WeChat URLs without permissive whole-URL HTML unescaping.

Python's ``html.unescape`` accepts legacy entities without a semicolon, so a
valid ``&timestamp=`` query can be interpreted as ``&times`` + ``tamp``.  URL
boundaries must decode only explicit entities and repair the already-observed
artifact narrowly; ordinary text decoding remains unchanged elsewhere.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote

_EXPLICIT_ENTITY_PATTERN = re.compile(
    r"&(?:amp|quot|apos|#0*(?:38|34|39)|#x0*(?:26|22|27));",
    flags=re.IGNORECASE,
)
_ENCODED_SCHEME_PATTERN = re.compile(r"^https?%3a%2f%2f", flags=re.IGNORECASE)
_TIMESTAMP_ENTITY_PATTERN = re.compile(
    r"&times;tamp=(?=\d{8,13}(?:&|#|$))",
    flags=re.IGNORECASE,
)
_TIMESTAMP_SRC_ARTIFACT_PATTERN = re.compile(
    r"([?&]src=\d+)(?:×tamp|%c3%97tamp|%26times%3btamp)(?:=|%3d)"
    r"(?=\d{8,13}(?:&|%26|#|$))",
    flags=re.IGNORECASE,
)


def _decode_explicit_entity(match: re.Match[str]) -> str:
    token = match.group(0)[1:-1]
    lowered = token.casefold()
    if lowered == "amp":
        return "&"
    if lowered == "quot":
        return '"'
    if lowered == "apos":
        return "'"
    base = 16 if lowered.startswith("#x") else 10
    digits = lowered[2:] if base == 16 else lowered[1:]
    return chr(int(digits, base))


def _repair_timestamp_artifact(value: str) -> str:
    text = _TIMESTAMP_ENTITY_PATTERN.sub("&timestamp=", value)
    return _TIMESTAMP_SRC_ARTIFACT_PATTERN.sub(r"\1&timestamp=", text)


def decode_public_url(value: Any) -> str:
    """Decode explicit HTML/JavaScript URL escapes and preserve signed queries."""

    text = _EXPLICIT_ENTITY_PATTERN.sub(
        _decode_explicit_entity,
        str(value or ""),
    )
    text = (
        text.replace("\\/", "/")
        .replace("\\x26", "&")
        .replace("\\u0026", "&")
        .replace("\\u003d", "=")
        .replace("\\u003D", "=")
        .replace("\\u002f", "/")
        .replace("\\u002F", "/")
        .replace("\\u003a", ":")
        .replace("\\u003A", ":")
        .replace("\\u0025", "%")
    )
    # Decode percent escapes only when the entire URL scheme is encoded. Once
    # a literal scheme exists, percent escapes belong to query values and must
    # remain structural data rather than becoming '&' or '#'.
    stripped = text.strip()
    for _ in range(2):
        if not _ENCODED_SCHEME_PATTERN.match(stripped):
            break
        stripped = unquote(stripped)
    if stripped != text.strip():
        leading = text[: len(text) - len(text.lstrip())]
        trailing = text[len(text.rstrip()):]
        text = f"{leading}{stripped}{trailing}"
    return _repair_timestamp_artifact(text)
