"""Strict first-party/certified cross-platform discovery for WeChat Source Entities.

This compatibility layer does not create new source entities and does not weaken
article acceptance. It only turns explicitly configured publisher-owned or
certified cross-platform index pages into candidate article URLs. Final
acceptance still runs through ``wechat_registry_bridge._parse_official_crosspost``
and therefore retains the existing host whitelist, recency and entity relevance
checks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "wechat_sources.json"


def _host(value: str) -> str:
    return (urlsplit(value).hostname or "").casefold().removeprefix("www.")


def _allowed_hosts(spec: dict[str, Any]) -> set[str]:
    return {
        str(value).casefold().removeprefix("www.")
        for value in spec.get("officialCrosspostHosts", [])
        if str(value).strip()
    }


def _platform_labels(path: Path = REGISTRY_PATH) -> dict[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    result: dict[str, str] = {}
    for raw in payload.get("accounts", []):
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue
        labels = raw.get("officialPlatformLabels", {})
        if not isinstance(labels, dict):
            continue
        for hostname, label in labels.items():
            key = str(hostname).casefold().removeprefix("www.").strip()
            value = str(label).strip()
            if key and value:
                result[key] = value[:80]
    return result


def source_kind_allowed(spec: dict[str, Any], source_kind: str) -> bool:
    configured = {
        str(value).strip()
        for value in spec.get("acceptedSourceKinds", [])
        if str(value).strip()
    }
    return not configured or source_kind in configured


def extract_official_index_rows(
    body: str,
    index_url: str,
    spec: dict[str, Any],
    crawler: Any,
    bridge: Any,
) -> list[dict[str, str]]:
    """Return relevant article links only from an explicitly whitelisted host."""

    allowed = _allowed_hosts(spec)
    index_host = _host(index_url)
    if not index_host or index_host not in allowed:
        return []

    parser = bridge.PublicIndexParser(index_url)
    parser.feed(body or "")
    normalized_index = crawler.normalize_url(index_url)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    limit = max(12, int(spec.get("maxItems", 6)) * 8)

    for link in parser.links:
        url = crawler.normalize_url(str(link.get("url", "")))
        parts = urlsplit(url)
        hostname = (parts.hostname or "").casefold().removeprefix("www.")
        if (
            not url
            or url == normalized_index
            or parts.scheme not in {"http", "https"}
            or hostname not in allowed
            or url in seen
            or (parts.path.rstrip("/") == "" and not parts.query)
        ):
            continue

        title = bridge._clean(link.get("title"), 260)
        if not bridge._usable_title(title):
            continue
        position = int(link.get("position", 0))
        context = bridge._context(parser, position, bridge._item_end(parser, position))
        companies, people, keywords = bridge._WECHAT._relevance_entities(
            title,
            context,
            "",
            spec,
            crawler,
        )
        if not (companies or people or keywords):
            continue

        rows.append(
            {
                "url": url,
                "title": title,
                "summary": context,
                "date": bridge._date_from_context(context, crawler) or "",
                "kind": "official",
            }
        )
        seen.add(url)
        if len(rows) >= limit:
            break
    return rows


def install(bridge: Any) -> None:
    """Install generic official-index discovery and source-kind enforcement."""

    original_extract = bridge._extract_index_rows
    if not getattr(original_extract, "_official_index_bridge", False):

        def extract_index_rows(
            body: str,
            index_url: str,
            spec: dict[str, Any],
            crawler: Any,
            *,
            require_account_context: bool = True,
        ) -> list[dict[str, str]]:
            rows = original_extract(
                body,
                index_url,
                spec,
                crawler,
                require_account_context=require_account_context,
            )
            official_rows = extract_official_index_rows(
                body, index_url, spec, crawler, bridge
            )
            seen = {crawler.normalize_url(row.get("url", "")) for row in rows}
            rows.extend(
                row
                for row in official_rows
                if crawler.normalize_url(row.get("url", "")) not in seen
            )
            return rows

        setattr(extract_index_rows, "_official_index_bridge", True)
        bridge._extract_index_rows = extract_index_rows

    labels = _platform_labels()
    original_platform = bridge._official_platform
    if not getattr(original_platform, "_official_index_bridge", False):

        def official_platform(url: str) -> str:
            hostname = _host(url)
            if hostname in labels:
                return labels[hostname]
            return original_platform(url)

        setattr(official_platform, "_official_index_bridge", True)
        bridge._official_platform = official_platform

    original_parse = bridge._parse_official_crosspost
    if not getattr(original_parse, "_official_index_bridge", False):

        def parse_official_crosspost(
            spec: dict[str, Any],
            row: dict[str, str],
            body: str,
            crawler: Any,
        ) -> dict[str, Any] | None:
            article = original_parse(spec, row, body, crawler)
            if article is None:
                return None
            source_kind = str(article.get("sourceKind", ""))
            return article if source_kind_allowed(spec, source_kind) else None

        setattr(parse_official_crosspost, "_official_index_bridge", True)
        bridge._parse_official_crosspost = parse_official_crosspost
