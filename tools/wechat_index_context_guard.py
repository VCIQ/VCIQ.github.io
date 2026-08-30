"""Prevent adjacent public-index entries from sharing account context."""

from __future__ import annotations

from typing import Any

try:
    from . import wechat_source_registry
except ImportError:
    import wechat_source_registry


def _bounded_context(parser: Any, position: int, next_position: int | None) -> str:
    start = max(0, position)
    natural_end = min(len(parser.text_parts), position + 14)
    end = min(natural_end, next_position) if next_position is not None else natural_end
    return parser_module._clean(" ".join(parser.text_parts[start:end]), 1200)


def _bounded_title(
    parser: Any,
    position: int,
    next_position: int | None,
    anchor_titles: list[str],
) -> str:
    for raw_title in anchor_titles:
        title = parser_module._clean(raw_title, 240)
        if (
            title.casefold() not in parser_module._GENERIC_ANCHOR_TEXT
            and len(title) >= 6
        ):
            return title
    natural_end = min(len(parser.text_parts), position + 10)
    end = min(natural_end, next_position) if next_position is not None else natural_end
    for item in parser.text_parts[position:end]:
        candidate = parser_module._clean(item, 240)
        if (
            candidate.casefold() not in parser_module._GENERIC_ANCHOR_TEXT
            and len(candidate) >= 6
        ):
            return candidate
    return ""


def _article_link_groups(parser: Any, crawler: Any) -> list[dict[str, Any]]:
    """Group repeated title/original links belonging to one article card."""

    candidates: list[dict[str, Any]] = []
    for link in parser.links:
        url = crawler.normalize_url(str(link.get("url", "")))
        if not (
            parser_module._is_wechat_article_url(url)
            or parser_module._is_resolvable_detail_url(url)
        ):
            continue
        candidates.append(
            {
                "url": url,
                "position": int(link.get("position", 0)),
                "title": str(link.get("title", "")),
            }
        )

    groups: list[dict[str, Any]] = []
    for candidate in candidates:
        if groups and groups[-1]["url"] == candidate["url"]:
            groups[-1]["titles"].append(candidate["title"])
            groups[-1]["lastPosition"] = candidate["position"]
            continue
        groups.append(
            {
                "url": candidate["url"],
                "position": candidate["position"],
                "lastPosition": candidate["position"],
                "titles": [candidate["title"]],
            }
        )
    return groups


def extract_index_rows(
    body: str,
    index_url: str,
    spec: dict[str, Any],
    crawler: Any,
    *,
    require_account_context: bool = True,
) -> list[dict[str, str]]:
    parser = parser_module.PublicIndexParser(index_url)
    parser.feed(body or "")
    profile_account_match = parser_module._profile_page_matches_account(
        parser,
        index_url,
        spec,
    )
    groups = _article_link_groups(parser, crawler)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for index, group in enumerate(groups):
        url = str(group["url"])
        if not parser_module._detail_belongs_to_index(index_url, url):
            continue
        position = int(group["position"])
        next_position = (
            int(groups[index + 1]["position"])
            if index + 1 < len(groups)
            else None
        )
        context = _bounded_context(parser, position, next_position)
        if (
            require_account_context
            and not profile_account_match
            and not wechat_source_registry.account_matches(spec, context)
        ):
            continue
        title = _bounded_title(
            parser,
            position,
            next_position,
            list(group["titles"]),
        )
        if not title or url in seen or parser_module._WECHAT is None:
            continue
        companies, people, keywords = parser_module._WECHAT._relevance_entities(
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
                "date": parser_module._date_from_context(context, crawler) or "",
                "kind": (
                    "wechat"
                    if parser_module._is_wechat_article_url(url)
                    else "detail"
                ),
            }
        )
        seen.add(url)
    return rows


parser_module: Any = None


def install(bridge: Any) -> None:
    """Replace the index-row parser with a card-bounded implementation."""

    global parser_module
    parser_module = bridge
    bridge._extract_index_rows = extract_index_rows
