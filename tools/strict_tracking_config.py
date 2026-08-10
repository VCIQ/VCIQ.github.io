"""Strict validation for browser-managed tracking configuration.

This module is intentionally independent from the crawler adapters so direct
JSON edits cannot bypass the same input rules enforced by the website admin.
"""

from __future__ import annotations

import copy
import re
import unicodedata
from typing import Any

GENERIC_PERSON_LABELS = {
    "人物", "专家", "研究员", "科学家", "创始人", "创业者", "投资人",
    "ceo", "cto", "founder", "researcher", "scientist",
}
GENERIC_TRACKING_KEYWORDS = {
    "ai", "ml", "人工智能", "技术", "科技", "公司", "企业", "行业", "产业",
    "研究", "论文", "新闻", "资讯", "产品", "项目", "模型", "系统", "平台",
    "创新", "投资", "融资", "上市", "发布", "突破", "发展", "市场", "应用",
    "机器人", "半导体", "新能源", "生物科技", "量子计算", "商业航天", "web3",
    "新材料", "智能制造", "tech", "technology", "company", "industry", "research",
    "paper", "news", "product", "project", "model", "system", "platform", "innovation",
    "investment", "funding", "launch", "update",
}
SEPARATOR_PATTERN = r"[\s|｜·•:：,，;；/\\\-—–()（）\[\]【】]+"
HANDLE_TAIL_PATTERN = re.compile(
    r"^([A-Za-z0-9_]{1,15})(?:[\s|｜,，;；)）\]】]*)$"
)


def _clean(value: Any, limit: int = 100) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip()[:limit]


def _trim_separators(value: str) -> str:
    value = re.sub(rf"^{SEPARATOR_PATTERN}", "", value)
    value = re.sub(rf"{SEPARATOR_PATTERN}$", "", value)
    return _clean(value, 80)


def parse_person_label(raw: Any) -> dict[str, Any] | None:
    value = _clean(raw).replace("＠", "@")
    if not value:
        return None
    if re.match(r"^https?://", value, flags=re.IGNORECASE):
        return None
    if re.search(r"(?:x|twitter)\.com/", value, flags=re.IGNORECASE):
        return None

    at_count = value.count("@")
    if at_count > 1:
        return None
    if at_count == 1:
        before, after = value.split("@", 1)
        match = HANDLE_TAIL_PATTERN.fullmatch(after)
        if not match:
            return None
        handle = match.group(1)
        display_name = _trim_separators(before)
        if display_name and not re.search(r"[A-Za-z0-9\u3400-\u9fff]", display_name):
            return None
        normalized = f"{display_name} @{handle}" if display_name else f"@{handle}"
        return {
            "normalized": normalized,
            "displayName": display_name,
            "handle": handle,
            "searchTerms": _unique([display_name, handle, f"@{handle}"], 3),
        }

    display_name = _trim_separators(value)
    if (
        len(display_name) < 2
        or not re.search(r"[A-Za-z0-9\u3400-\u9fff]", display_name)
        or display_name.casefold() in GENERIC_PERSON_LABELS
    ):
        return None
    return {
        "normalized": display_name,
        "displayName": display_name,
        "handle": "",
        "searchTerms": [display_name],
    }


def parse_tracking_keyword(raw: Any) -> str | None:
    value = _clean(raw, 80).strip('"\'“”‘’`')
    if not value or len(value) > 40:
        return None
    if re.match(r"^https?://", value, flags=re.IGNORECASE):
        return None
    if re.search(r"\b(?:www\.)?[^\s]+\.(?:com|cn|org|net)\b", value, flags=re.IGNORECASE):
        return None
    if "@" in value:
        return None
    if re.match(r"^site\s*:", value, flags=re.IGNORECASE):
        return None
    if re.search(r"(^|\s)(?:AND|OR|NOT)(\s|$)", value, flags=re.IGNORECASE):
        return None
    if not re.search(r"[A-Za-z0-9\u3400-\u9fff]", value):
        return None
    if value.casefold() in GENERIC_TRACKING_KEYWORDS:
        return None

    cjk_count = len(re.findall(r"[\u3400-\u9fff]", value))
    alphanumeric_count = len(re.findall(r"[A-Za-z0-9]", value))
    if cjk_count == 1 and alphanumeric_count == 0:
        return None
    symbolic_language = bool(re.fullmatch(r"(?i)c(?:\+\+|#)?|r", value))
    if cjk_count == 0 and alphanumeric_count < 2 and not symbolic_language:
        return None
    return value


def _unique(values: list[Any], limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = _clean(raw, 120)
        key = value.casefold()
        if not value or key in seen:
            continue
        result.append(value)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def sanitize_tracking_config(config: dict[str, Any]) -> dict[str, Any]:
    sanitized = copy.deepcopy(config)
    tracks = sanitized.get("tracks", [])
    if not isinstance(tracks, list):
        sanitized["tracks"] = []
        return sanitized

    for track in tracks:
        if not isinstance(track, dict):
            continue

        people: list[str] = []
        seen_people: set[str] = set()
        for raw in track.get("people", []) if isinstance(track.get("people"), list) else []:
            parsed = parse_person_label(raw)
            if not parsed:
                continue
            normalized = str(parsed["normalized"])
            key = normalized.casefold()
            if key in seen_people:
                continue
            people.append(normalized)
            seen_people.add(key)
            if len(people) >= 40:
                break
        track["people"] = people

        keywords: list[str] = []
        seen_keywords: set[str] = set()
        for raw in track.get("keywords", []) if isinstance(track.get("keywords"), list) else []:
            normalized = parse_tracking_keyword(raw)
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen_keywords:
                continue
            keywords.append(normalized)
            seen_keywords.add(key)
            if len(keywords) >= 80:
                break
        track["keywords"] = keywords

    return sanitized
