"""Python adapter for the public person's shared identity contract.

Policy and parsing patterns live in lib/person-identity-policy.json. The public
TypeScript adapter and this adapter are compared on fixtures and production rows
by tests/person-identity-parity.test.ts. Validation mirrors the public order:
normalize bilingual/handle labels, then validate the display and English names.
No network, model call, Node runtime, or persisted allowlist is needed by Python.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Mapping

POLICY_PATH = Path(__file__).resolve().parents[1] / "lib" / "person-identity-policy.json"
POLICY = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
if POLICY.get("schemaVersion") != 1:
    raise ValueError("Unsupported person identity policy version")

# ECMAScript whitespace differs from Python's Unicode \s (notably U+0085,
# U+001C..U+001F and U+FEFF). Expand only whitespace; keep \b/\w ASCII, as in
# the public regex. NFKC is applied only in validation, NOT label parsing.
_JS_SPACE = r"[\u0009-\u000d\u0020\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]"
PATTERNS = {
    key: re.compile(value.replace(r"\s", _JS_SPACE), re.ASCII)
    for key, value in POLICY["patterns"].items()
}


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _clean(value: Any, *, normalize: bool = False) -> str:
    text = _text(value)
    if normalize:
        text = unicodedata.normalize(POLICY["normalizationForm"], text)
    return PATTERNS["whitespace"].sub(" ", text).strip(" ")


def _fold(value: str) -> str:
    # /[a-z]/iu matches Kelvin K and long s, but NOT dotted/dotless I.
    # Python re.I would add the latter, and full casefold expands sharp s.
    # The policy's case-insensitive classes contain ASCII letters only.
    return value.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ\u017f\u212a", "abcdefghijklmnopqrstuvwxyzsk"))


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le", errors="surrogatepass")) // 2


def _has_cjk(value: str) -> bool:
    return bool(PATTERNS["cjk"].search(value))


def _has_latin(value: str) -> bool:
    return bool(PATTERNS["latin"].search(value))


def parse_person_identity_label(value: Any) -> dict[str, str]:
    label = _clean(value)
    handle = ""
    match = PATTERNS["handle"].search(label)
    if match:
        label, handle = _clean(match[1]), _clean(match[2])
    match = PATTERNS["bilingualLabel"].search(label)
    if match:
        left, right = _clean(match[1]), _clean(match[2])
        if left and right:
            if _has_cjk(left) and _has_latin(right) and not _has_cjk(right):
                return {"name": left, "englishName": right, "handle": handle}
            if _has_latin(left) and not _has_cjk(left) and _has_cjk(right):
                return {"name": right, "englishName": left, "handle": handle}
    return {
        "name": label,
        "englishName": label if _has_latin(label) and not _has_cjk(label) else "",
        "handle": handle,
    }


def normalized_person_identity(candidate: Mapping[str, Any]) -> dict[str, str]:
    """Return only validation fields; do not rewrite task text or stored identity."""
    primary = parse_person_identity_label(candidate.get("name"))
    english = parse_person_identity_label(candidate.get("englishName"))
    name = primary["name"] or english["name"] or _clean(candidate.get("name"))
    english_name = (
        primary["englishName"]
        or english["englishName"]
        or (english["name"] if _has_latin(english["name"]) and not _has_cjk(english["name"]) else "")
        or (name if _has_latin(name) and not _has_cjk(name) else "")
        or _clean(candidate.get("englishName"))
        or name
    )
    return {"name": name, "englishName": english_name}


def validate_person_identity(candidate: Mapping[str, Any]) -> dict[str, Any]:
    name = _clean(candidate.get("name"), normalize=True)
    english = _clean(candidate.get("englishName"), normalize=True)
    reason = ""
    if not name:
        reason = "missing-name"
    elif _utf16_length(name) > POLICY["maxNameUtf16Units"] or _utf16_length(english) > POLICY["maxEnglishNameUtf16Units"]:
        reason = "name-too-long"
    elif not PATTERNS["personCharacters"].search(_fold(name)):
        reason = "name-has-no-person-characters"
    elif PATTERNS["nonPersonTerms"].search(name):
        reason = "non-person-entity-term"
    elif PATTERNS["titleBleed"].search(_fold(name)) or PATTERNS["titleBleed"].search(_fold(english)):
        reason = "title-or-organization-bleed"
    elif PATTERNS["sentencePunctuation"].search(name):
        reason = "sentence-like-name"
    elif len(PATTERNS["latinWords"].findall(_fold(name))) > POLICY["maxLatinWords"]:
        reason = "too-many-name-tokens"
    return {"valid": False, "reason": reason} if reason else {"valid": True}


def validate_generated_person_identity(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return validate_person_identity(normalized_person_identity(candidate))
