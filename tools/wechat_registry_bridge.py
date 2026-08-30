"""Runtime bridge between media identities and publication endpoints.

Public aggregation pages remain discovery-only. A verified publisher may opt
in its own website or official cross-platform profile as acceptance evidence.
Those records retain their actual provenance and are not called WeChat originals.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlsplit

try:
    from . import wechat_source_registry
except ImportError:
    import wechat_source_registry

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_INDEX_PATH = ROOT / "config" / "wechat_public_indexes.json"
_INDEX_CACHE: dict[str, str] = {}
_WECHAT: Any | None = None
_GENERIC_ANCHOR_TEXT = {
    "",
    "打开原文",
    "查看详情",
    "详情",
    "阅读原文",
    "获取内容",
    "image",
}


def _clean(value: Any, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _unique(values: Iterable[str], limit: int = 100) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clean(value, 1000)
        key = item.casefold()
        if not item or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _record_diagnostic(spec: dict[str, Any], key: str, value: str) -> None:
    values = spec.setdefault(key, [])
    item = _clean(value, 100)
    if item and item not in values and len(values) < 8:
        values.append(item)


def _fetch_failure_kind(exc: Exception) -> str:
    message = str(exc).casefold()
    if "verification or block page" in message:
        return "wechat-block-page"
    if "not a recognizable wechat article" in message:
        return "wechat-not-article-page"
    if "redirected outside" in message:
        return "wechat-external-redirect"
    if "exceeded size limit" in message:
        return "wechat-response-too-large"
    return type(exc).__name__


def _runtime_diagnostics(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "publicIndexOriginalFetchFailureKinds": list(
            spec.get("_publicIndexOriginalFetchFailureKinds", [])
        ),
        "publicIndexArticleRejectKinds": list(
            spec.get("_publicIndexArticleRejectKinds", [])
        ),
        "publicIndexObservedAccounts": list(
            spec.get("_publicIndexObservedAccounts", [])
        ),
        "publicIndexSogouAccounts": list(
            spec.get("_publicIndexTitleCandidateAccounts", [])
        ),
        "publicIndexTitleAccountMismatches": int(
            spec.get("_publicIndexTitleAccountMismatches", 0) or 0
        ),
    }


def _load_public_indexes(path: Path = PUBLIC_INDEX_PATH) -> dict[str, list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or int(payload.get("schemaVersion", 0)) != 1:
        return {}
    accounts = payload.get("accounts", {})
    if not isinstance(accounts, dict):
        return {}
    return {
        str(account_id): _unique(
            str(url)
            for url in urls
            if isinstance(urls, list)
            and str(url).startswith(("https://", "http://"))
        )
        for account_id, urls in accounts.items()
        if isinstance(urls, list)
    }


class PublicIndexParser(HTMLParser):
    """Collect direct WeChat links and resolvable article-detail links."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.text_parts: list[str] = []
        self.links: list[dict[str, Any]] = []
        self.item_ranges: list[tuple[int, int]] = []
        self.title_hints: list[dict[str, Any]] = []
        self.page_title_parts: list[str] = []
        self._href = ""
        self._anchor_parts: list[str] = []
        self._anchor_position = 0
        self._item_depth = 0
        self._item_start = 0
        self._title_span_depth = 0
        self._title_parts: list[str] = []
        self._title_position = 0
        self._page_title_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag_key = tag.casefold()
        values = {key.casefold(): value or "" for key, value in attrs}
        classes = set(values.get("class", "").casefold().split())
        if tag_key == "title":
            self._page_title_depth += 1
        if tag_key == "div":
            if self._item_depth:
                self._item_depth += 1
            elif {"cell", "item"}.issubset(classes):
                self._item_depth = 1
                self._item_start = len(self.text_parts)
        if tag_key == "span":
            if self._title_span_depth:
                self._title_span_depth += 1
            elif "item_title" in classes:
                self._title_span_depth = 1
                self._title_parts = []
                self._title_position = len(self.text_parts)
        if tag_key != "a":
            return
        self._href = urljoin(self.base_url, values.get("href", ""))
        self._anchor_parts = []
        self._anchor_position = len(self.text_parts)

    def handle_data(self, data: str) -> None:
        value = _clean(data, 600)
        if not value:
            return
        self.text_parts.append(value)
        if self._href:
            self._anchor_parts.append(value)
        if self._title_span_depth:
            self._title_parts.append(value)
        if self._page_title_depth:
            self.page_title_parts.append(value)

    def handle_endtag(self, tag: str) -> None:
        tag_key = tag.casefold()
        if tag_key == "title" and self._page_title_depth:
            self._page_title_depth -= 1
        if tag_key == "a" and self._href:
            self.links.append(
                {
                    "url": self._href,
                    "title": _clean(" ".join(self._anchor_parts), 260),
                    "position": self._anchor_position,
                }
            )
            self._href = ""
            self._anchor_parts = []
        if tag_key == "span" and self._title_span_depth:
            self._title_span_depth -= 1
            if not self._title_span_depth:
                self.title_hints.append(
                    {
                        "title": _clean(" ".join(self._title_parts), 260),
                        "position": self._title_position,
                    }
                )
                self._title_parts = []
        if tag_key == "div" and self._item_depth:
            self._item_depth -= 1
            if not self._item_depth:
                self.item_ranges.append(
                    (self._item_start, len(self.text_parts))
                )


def _context(
    parser: PublicIndexParser,
    position: int,
    next_position: int | None = None,
) -> str:
    start = max(0, position)
    natural_end = min(len(parser.text_parts), position + 10)
    end = min(natural_end, next_position) if next_position is not None else natural_end
    return _clean(" ".join(parser.text_parts[start:end]), 1200)


def _item_end(parser: PublicIndexParser, position: int) -> int | None:
    for start, end in parser.item_ranges:
        if start <= position < end:
            return end
    return None


def _fallback_title(
    parser: PublicIndexParser, position: int, anchor_title: str
) -> str:
    title = _clean(anchor_title, 240)
    if _usable_title(title):
        return title
    for item in reversed(parser.text_parts[max(0, position - 5) : position]):
        candidate = _clean(item, 240)
        if _usable_title(candidate):
            return candidate
    return ""


def _usable_title(value: Any) -> bool:
    title = _clean(value, 240)
    return (
        title.casefold() not in _GENERIC_ANCHOR_TEXT
        and len(title) >= 6
        and re.search(r"[A-Za-z\u3400-\u9fff]", title) is not None
    )


def _date_from_context(context: str, crawler: Any) -> str | None:
    match = re.search(r"20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}", context)
    return crawler.normalize_date(match.group(0)) if match else None


def _article_date_is_recent(
    value: Any,
    spec: dict[str, Any],
    crawler: Any,
) -> bool:
    """Require a parseable original-page date inside the source window."""

    normalized = crawler.normalize_date(value)
    if not normalized:
        return False
    try:
        published = datetime.fromisoformat(normalized).date()
    except ValueError:
        return False
    max_age_days = max(1, int(spec.get("maxArticleAgeDays", 45) or 45))
    return published >= datetime.now(UTC).date() - timedelta(days=max_age_days)


def _is_wechat_article_url(url: str) -> bool:
    parts = urlsplit(url)
    return (
        parts.scheme.casefold() == "https"
        and (parts.hostname or "").casefold() == "mp.weixin.qq.com"
        and (
            parts.path.rstrip("/") == "/s"
            or parts.path.rstrip("/").startswith("/s/")
        )
    )


def _is_resolvable_detail_url(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").casefold().removeprefix("www.")
    return (
        host in {"jintiankansha.com", "jintiankansha.me"}
        and parts.path.startswith("/t/")
    ) or (
        host in {"m.sohu.com", "sohu.com"}
        and re.fullmatch(r"/a/\d+_\d+", parts.path.rstrip("/")) is not None
    ) or (
        host == "eet-china.com"
        and re.fullmatch(r"/mp/a\d+\.html", parts.path.rstrip("/")) is not None
    )


def _official_crosspost_host_allowed(spec: dict[str, Any], url: str) -> bool:
    host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
    allowed = {
        str(value).casefold().removeprefix("www.")
        for value in spec.get("officialCrosspostHosts", [])
        if str(value).strip()
    }
    return bool(host and host in allowed)


def _official_platform(url: str) -> str:
    host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
    return "搜狐号" if host in {"m.sohu.com", "sohu.com"} else "官方网站"


def _parse_official_crosspost(
    spec: dict[str, Any],
    row: dict[str, str],
    body: str,
    crawler: Any,
) -> dict[str, Any] | None:
    """Parse a whitelisted publisher-owned copy without calling it WeChat."""

    url = crawler.normalize_url(row.get("url", ""))
    if not url or not _official_crosspost_host_allowed(spec, url):
        return None
    parser = _WECHAT.WeChatPageParser()
    parser.feed(body or "")
    page_parser = PublicIndexParser(url)
    page_parser.feed(body or "")
    title = crawler.clean_title(
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title")
        or parser.title
        or " ".join(page_parser.page_title_parts)
        or row.get("title", "")
    )
    # Some first-party sites expose the date in the visible article header
    # rather than article:published_time. This remains acceptable only after
    # the article host passed the explicit publisher whitelist above.
    visible_text = _clean(" ".join(page_parser.text_parts), 20_000)
    published_at = _WECHAT._published_at(
        parser, body or "", crawler
    ) or _date_from_context(visible_text[:3000], crawler)
    content = parser.content or visible_text
    summary = _clean(
        parser.meta.get("description")
        or parser.meta.get("og:description")
        or parser.meta.get("twitter:description")
        or content[:650]
        or row.get("summary", ""),
        500,
    )
    if (
        not title
        or len(title) < 6
        or not summary
        or not _article_date_is_recent(published_at, spec, crawler)
    ):
        return None
    companies, people, keywords = _WECHAT._relevance_entities(
        title, summary, content, spec, crawler
    )
    if not (companies or people or keywords):
        return None
    publisher = str(spec.get("publisherEntity") or spec.get("name") or "")
    company, company_slug = _WECHAT._company_attribution(
        title, content, publisher, companies, crawler
    )
    platform = _official_platform(url)
    article = crawler._external_article(
        spec,
        title=title,
        summary=summary,
        url=url,
        published_at=published_at,
        source_name=publisher,
        source_level=spec.get("sourceLevel", "媒体报道"),
        platform=platform,
        company=company,
        company_slug=company_slug,
    )
    article["publisherEntity"] = publisher
    article["sourceKind"] = (
        "official-crosspost" if platform != "官方网站" else "official-website"
    )
    article["mentionedCompanies"] = companies
    article["mentionedPeople"] = people
    article["matchedTrackingTerms"] = keywords[:20]
    if isinstance(article.get("source"), dict):
        article["source"]["sourceKind"] = article["sourceKind"]
        article["source"]["publisherEntity"] = publisher
    return article


def _detail_belongs_to_index(index_url: str, detail_url: str) -> bool:
    """Exclude unrelated recommendation links on account profile pages."""

    index_parts = urlsplit(index_url)
    detail_parts = urlsplit(detail_url)
    index_host = (index_parts.hostname or "").casefold().removeprefix("www.")
    if index_host not in {"m.sohu.com", "sohu.com"}:
        return True
    profile = re.fullmatch(r"/media/(\d+)", index_parts.path.rstrip("/"))
    if not profile:
        # Author-id scoping belongs to an account profile page only. Once a
        # profile-owned article is being parsed as a nested detail page, its
        # original WeChat link must be allowed through to the final account
        # verification layer.
        return True
    article = re.fullmatch(r"/a/\d+_(\d+)", detail_parts.path.rstrip("/"))
    return bool(article and profile.group(1) == article.group(1))


def _profile_page_matches_account(
    parser: PublicIndexParser,
    index_url: str,
    spec: dict[str, Any],
) -> bool:
    """Verify an account-scoped profile before using its article titles."""

    parts = urlsplit(index_url)
    host = (parts.hostname or "").casefold().removeprefix("www.")
    is_sohu_profile = host in {"m.sohu.com", "sohu.com"} and re.fullmatch(
        r"/media/\d+", parts.path.rstrip("/")
    )
    is_qnmlgb_profile = (
        host == "qnmlgb.tech"
        and parts.path.rstrip("/").startswith("/authors/")
    )
    is_gsi24_profile = host == "gsi24.com" and parts.path.rstrip("/") == ""
    if not (is_sohu_profile or is_qnmlgb_profile or is_gsi24_profile):
        return False
    if wechat_source_registry.account_matches(
        spec,
        " ".join(parser.page_title_parts),
    ):
        return True
    # Match bounded visible nodes near the profile header independently. Passing
    # the whole document to account_matches() lets large leading scripts consume
    # its input limit before the author name is reached. Limiting the search to
    # early nodes also avoids treating a recommended article's publisher name as
    # proof that the profile itself belongs to the configured account.
    return any(
        wechat_source_registry.account_matches(spec, text)
        for text in parser.text_parts[:120]
    )


def _extract_index_rows(
    body: str,
    index_url: str,
    spec: dict[str, Any],
    crawler: Any,
    *,
    require_account_context: bool = True,
) -> list[dict[str, str]]:
    parser = PublicIndexParser(index_url)
    parser.feed(body or "")
    profile_account_match = _profile_page_matches_account(parser, index_url, spec)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    seen_titles: set[str] = set()
    for index, link in enumerate(parser.links):
        url = crawler.normalize_url(str(link.get("url", "")))
        if not (_is_wechat_article_url(url) or _is_resolvable_detail_url(url)):
            continue
        if not _detail_belongs_to_index(index_url, url):
            continue
        # Some profile pages render an empty image anchor immediately before a
        # text anchor for the same article. Let the explicit title anchor win;
        # otherwise fallback-title heuristics can mistake a page statistic for
        # the article title and then block the real anchor through deduplication.
        if not _usable_title(link.get("title")) and any(
            crawler.normalize_url(str(next_link.get("url", ""))) == url
            and _usable_title(next_link.get("title"))
            for next_link in parser.links[index + 1 :]
        ):
            continue
        position = int(link.get("position", 0))
        next_position = None
        for next_link in parser.links[index + 1 :]:
            next_url = crawler.normalize_url(str(next_link.get("url", "")))
            if next_url == url:
                continue
            if _is_wechat_article_url(next_url) or _is_resolvable_detail_url(
                next_url
            ):
                next_position = int(next_link.get("position", 0))
                break
        item_end = _item_end(parser, position)
        if item_end is not None:
            next_position = min(next_position, item_end) if next_position else item_end
        context = _context(parser, position, next_position)
        if (
            require_account_context
            and not profile_account_match
            and not wechat_source_registry.account_matches(spec, context)
        ):
            continue
        title = _fallback_title(
            parser, position, str(link.get("title", ""))
        )
        if not title or url in seen or _WECHAT is None:
            continue
        companies, people, keywords = _WECHAT._relevance_entities(
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
                "date": _date_from_context(context, crawler) or "",
                "kind": "wechat" if _is_wechat_article_url(url) else "detail",
            }
        )
        seen.add(url)
        seen_titles.add(_clean(title, 260).casefold())

    # Some Jintiankansha column pages expose recent article titles and account
    # context while withholding the detail URL.  Keep those titles as
    # discovery-only hints: the bounded Sogou fallback must still recover a
    # direct mp.weixin URL, and the original page remains the only acceptance
    # evidence.  Item boundaries prevent a following hidden title from making
    # an unrelated linked headline appear sector-relevant.
    index_parts = urlsplit(index_url)
    index_host = (index_parts.hostname or "").casefold().removeprefix("www.")
    title_only_index = (
        index_host in {"jintiankansha.com", "jintiankansha.me"}
        and index_parts.path.startswith("/column/")
    ) or (
        index_host == "qnmlgb.tech"
        and index_parts.path.startswith("/authors/")
    ) or (
        index_host == "gsi24.com"
        and index_parts.path.rstrip("/") == ""
    ) or (
        index_host == "zhidx.com"
        and index_parts.path.rstrip("/") == "/aichip001"
    )
    if title_only_index:
        title_hints = list(parser.title_hints)
        if index_host == "qnmlgb.tech" and profile_account_match:
            for position, text in enumerate(parser.text_parts):
                title = re.sub(
                    r"^\s*\^__\^\s*[•·]\s*\d{1,2}\s*/\s*\d{1,2}\s*",
                    "",
                    _clean(text, 320),
                )
                if title != _clean(text, 320):
                    title_hints.append({"title": title, "position": position})
        official_title_urls: dict[tuple[str, int], str] = {}
        if index_host in {"gsi24.com", "zhidx.com"}:
            for link in parser.links:
                link_parts = urlsplit(str(link.get("url", "")))
                is_article = (
                    index_host == "gsi24.com"
                    and re.fullmatch(r"/a/[^/]+", link_parts.path.rstrip("/"))
                    is not None
                ) or (
                    index_host == "zhidx.com"
                    and re.fullmatch(r"/p/\d+\.html", link_parts.path.rstrip("/"))
                    is not None
                )
                if is_article and _usable_title(link.get("title")):
                    hint_title = link.get("title")
                    hint_position = int(link.get("position", 0))
                    title_hints.append(
                        {
                            "title": hint_title,
                            "position": hint_position,
                        }
                    )
                    official_title_urls[
                        (_clean(hint_title, 260).casefold(), hint_position)
                    ] = crawler.normalize_url(str(link.get("url", "")))
        for hint in title_hints:
            title = _clean(hint.get("title"), 260)
            title_key = title.casefold()
            position = int(hint.get("position", 0))
            if not _usable_title(title) or title_key in seen_titles:
                continue
            context = _context(parser, position, _item_end(parser, position))
            if (
                require_account_context
                and not profile_account_match
                and index_host not in {"gsi24.com", "zhidx.com"}
                and not wechat_source_registry.account_matches(spec, context)
            ):
                continue
            companies, people, keywords = _WECHAT._relevance_entities(
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
                    "url": official_title_urls.get((title_key, position), index_url),
                    "title": title,
                    "summary": context,
                    "date": _date_from_context(context, crawler) or "",
                    "kind": (
                        "official"
                        if (title_key, position) in official_title_urls
                        else "title"
                    ),
                }
            )
            seen_titles.add(title_key)
    return rows


def _fetch_cached(url: str, user_agent: str, crawler: Any) -> str:
    if url not in _INDEX_CACHE:
        _INDEX_CACHE[url] = crawler.fetch_text(url, user_agent)
    return _INDEX_CACHE[url]


def _resolve_detail_row(
    row: dict[str, str],
    spec: dict[str, Any],
    user_agent: str,
    crawler: Any,
) -> list[dict[str, str]]:
    if row.get("kind") != "detail":
        return [row]
    try:
        body = _fetch_cached(row["url"], user_agent, crawler)
    except Exception:  # noqa: BLE001 - the caller records aggregate failures.
        return []
    resolved = _extract_index_rows(
        body,
        row["url"],
        spec,
        crawler,
        require_account_context=False,
    )
    result: list[dict[str, str]] = []
    for item in resolved:
        if item.get("kind") != "wechat":
            continue
        result.append(
            {
                **item,
                "title": item.get("title") or row.get("title", ""),
                "summary": item.get("summary") or row.get("summary", ""),
                "date": item.get("date") or row.get("date", ""),
            }
        )
    if not result and _official_crosspost_host_allowed(spec, row["url"]):
        # The profile page already proved publisher ownership and scoped this
        # detail URL to the same account. Prefer an embedded WeChat original,
        # but retain the publisher-owned platform copy when that link is absent.
        result.append({**row, "kind": "official"})
    return result


def _fallback_index_rows(
    spec: dict[str, Any], user_agent: str, crawler: Any
) -> tuple[list[dict[str, str]], int]:
    rows: list[dict[str, str]] = []
    discovered_rows: list[dict[str, str]] = []
    failures = 0
    diagnostics = {
        "publicIndexPagesFetched": 0,
        "publicIndexPagesFailed": 0,
        "publicIndexRowsDiscovered": 0,
        "publicIndexDetailResolved": 0,
        "publicIndexDetailUnresolved": 0,
        "publicIndexTitleResolved": 0,
        "publicIndexTitleHintsDiscovered": 0,
        "publicIndexTitleHintsUnresolved": 0,
        "publicIndexDirectRows": 0,
    }
    for index_url in spec.get("publicIndexUrls", []):
        try:
            body = _fetch_cached(index_url, user_agent, crawler)
            discovered = _extract_index_rows(body, index_url, spec, crawler)
        except Exception:  # noqa: BLE001 - reported through the source status.
            failures += 1
            diagnostics["publicIndexPagesFailed"] += 1
            continue
        diagnostics["publicIndexPagesFetched"] += 1
        diagnostics["publicIndexRowsDiscovered"] += len(discovered)
        discovered_rows.extend(discovered)
        diagnostics["publicIndexTitleHintsDiscovered"] += sum(
            1 for row in discovered if row.get("kind") == "title"
        )

    for row_index, row in enumerate(discovered_rows):
        resolved = _resolve_detail_row(row, spec, user_agent, crawler)
        if row.get("kind") in {"detail", "title"}:
            if resolved:
                if row.get("kind") == "detail":
                    diagnostics["publicIndexDetailResolved"] += 1
                if any(item.get("titleLookupQuery") for item in resolved):
                    diagnostics["publicIndexTitleResolved"] += 1
            else:
                if row.get("kind") == "detail":
                    diagnostics["publicIndexDetailUnresolved"] += 1
                else:
                    diagnostics["publicIndexTitleHintsUnresolved"] += 1
                failures += 1
        rows.extend(resolved)
        if resolved:
            # Do not spend the second source-local query until the original
            # page behind this first candidate has passed account/date/entity
            # verification.  The crawl wrapper resumes these rows only after a
            # rejection, preserving both request budget and title diversity.
            spec["_publicIndexDeferredRows"] = discovered_rows[row_index + 1 :]
            break
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        url = crawler.normalize_url(row.get("url", ""))
        if not url or url in seen:
            continue
        deduped.append({**row, "url": url})
        seen.add(url)
    diagnostics["publicIndexDirectRows"] = len(deduped)
    spec["_publicIndexDiagnostics"] = diagnostics
    return deduped, failures


def install(wechat: Any) -> None:
    """Apply whitelist-first discovery, account verification, and fallbacks."""

    global _WECHAT
    _WECHAT = wechat
    index_map = _load_public_indexes()
    original_generate = wechat_source_registry.generated_wechat_sources

    def generated_wechat_sources(tracks: Any, tracking: Any) -> list[dict[str, Any]]:
        specs = original_generate(tracks, tracking)
        for spec in specs:
            account_id = str(spec.get("accountConfigId") or "")
            spec["publicIndexUrls"] = list(index_map.get(account_id, []))
        return specs

    setattr(generated_wechat_sources, "_wechat_registry_indexed", True)
    wechat.generated_wechat_sources = generated_wechat_sources

    original_parse = wechat.parse_wechat_article
    if not getattr(original_parse, "_wechat_registry_verified", False):

        def parse_wechat_article(
            spec: dict[str, Any],
            url: str,
            body: str,
            crawler: Any,
            **kwargs: Any,
        ) -> dict[str, Any] | None:
            if spec.get("expectedAccounts"):
                if any(
                    marker in (body or "")
                    for marker in getattr(wechat, "BLOCK_PAGE_MARKERS", ())
                ):
                    _record_diagnostic(
                        spec,
                        "_publicIndexArticleRejectKinds",
                        "original-block-page",
                    )
                    return None
                parser = wechat.WeChatPageParser()
                parser.feed(body or "")
                observed_account = parser.account or wechat._js_value(
                    body or "",
                    ("nickname", "profile_nickname", "account_name"),
                )
                _record_diagnostic(
                    spec,
                    "_publicIndexObservedAccounts",
                    str(observed_account or "(missing)"),
                )
                if not wechat_source_registry.account_matches(
                    spec, observed_account
                ):
                    _record_diagnostic(
                        spec,
                        "_publicIndexArticleRejectKinds",
                        (
                            "original-account-missing"
                            if not observed_account
                            else "original-account-mismatch"
                        ),
                    )
                    return None

                # Discovery-page dates are never acceptance evidence for a
                # configured account.  The original mp.weixin page must expose
                # its own date, which the wrapped parser then normalizes.
                kwargs.pop("fallback_date", None)

            article = original_parse(spec, url, body, crawler, **kwargs)
            if not article and spec.get("expectedAccounts"):
                _record_diagnostic(
                    spec,
                    "_publicIndexArticleRejectKinds",
                    "original-parser-rejected",
                )
            if article and spec.get("expectedAccounts") and not _article_date_is_recent(
                article.get("publishedAt"),
                spec,
                crawler,
            ):
                _record_diagnostic(
                    spec,
                    "_publicIndexArticleRejectKinds",
                    "original-date-missing-or-stale",
                )
                return None
            if article and isinstance(article.get("source"), dict):
                article["source"]["level"] = spec.get(
                    "sourceLevel", "媒体报道"
                )
                article["source"]["platform"] = "微信"
                if spec.get("accountConfigId"):
                    article["wechatAccountConfigId"] = spec["accountConfigId"]
            return article

        setattr(parse_wechat_article, "_wechat_registry_verified", True)
        wechat.parse_wechat_article = parse_wechat_article

    original_crawl = wechat.crawl_wechat_source
    if getattr(original_crawl, "_wechat_public_index_fallback", False):
        return

    def crawl_wechat_source(
        spec: dict[str, Any], user_agent: str, crawler: Any
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        try:
            articles, status = original_crawl(spec, user_agent, crawler)
        except Exception as exc:  # noqa: BLE001 - fallback may still recover.
            articles = []
            status = crawler._status(
                spec["id"],
                spec["name"],
                "error",
                0,
                0,
                failed=1,
                platform="微信",
                error=f"{type(exc).__name__}: {exc}",
            )
        if articles or not spec.get("publicIndexUrls"):
            return articles, status

        rows, index_failures = _fallback_index_rows(spec, user_agent, crawler)
        diagnostics = dict(spec.get("_publicIndexDiagnostics") or {})
        accepted: list[dict[str, Any]] = []
        failures = index_failures
        attempted_rows = 0
        max_items = int(spec.get("maxItems", 6))

        def verify_rows(candidate_rows: list[dict[str, str]]) -> None:
            nonlocal attempted_rows, failures
            for row in candidate_rows[: max_items * 5]:
                attempted_rows += 1
                try:
                    if row.get("kind") == "official":
                        body = _fetch_cached(row["url"], user_agent, crawler)
                        article = _parse_official_crosspost(spec, row, body, crawler)
                    else:
                        body = wechat.fetch_public_wechat_page(row["url"])
                        article = wechat.parse_wechat_article(
                            spec,
                            row["url"],
                            body,
                            crawler,
                            fallback_title=row.get("title", ""),
                            fallback_summary=row.get("summary", ""),
                            fallback_date=row.get("date") or None,
                        )
                except Exception as exc:  # noqa: BLE001 - aggregated below.
                    _record_diagnostic(
                        spec,
                        "_publicIndexOriginalFetchFailureKinds",
                        _fetch_failure_kind(exc),
                    )
                    failures += 1
                    continue
                if article:
                    accepted.append(article)
                if len(accepted) >= max_items:
                    break

        verify_rows(rows)
        if not accepted:
            for deferred in list(spec.pop("_publicIndexDeferredRows", [])):
                # A direct URL is a candidate, not proof. Re-open title lookup
                # only after the original page rejected the earlier candidate.
                spec.pop("_publicIndexTitleDirectResolved", None)
                resolved = _resolve_detail_row(
                    deferred,
                    spec,
                    user_agent,
                    crawler,
                )
                if not resolved:
                    if deferred.get("kind") == "detail":
                        diagnostics["publicIndexDetailUnresolved"] += 1
                    elif deferred.get("kind") == "title":
                        diagnostics["publicIndexTitleHintsUnresolved"] += 1
                    failures += 1
                    if int(spec.get("_publicIndexTitleSearchQueries", 0) or 0) >= 2:
                        break
                    continue
                if deferred.get("kind") == "detail":
                    diagnostics["publicIndexDetailResolved"] += 1
                if any(item.get("titleLookupQuery") for item in resolved):
                    diagnostics["publicIndexTitleResolved"] += 1
                verify_rows(resolved)
                if accepted:
                    break

        diagnostics["publicIndexDirectRows"] = attempted_rows

        if not accepted:
            result = crawler._status(
                spec["id"],
                spec["name"],
                "error",
                attempted_rows,
                0,
                failed=max(1, failures),
                platform="媒体官方端点",
                error=(
                    "No verified publisher article discovered from WeChat or "
                    "configured official endpoints; previous snapshot retained"
                ),
            )
            result.update(diagnostics)
            result.update(_runtime_diagnostics(spec))
            return [], result
        result = crawler._status(
            spec["id"],
            spec["name"],
            "partial" if failures else "ok",
            attempted_rows,
            len(accepted),
            failed=failures,
            platform=accepted[0].get("source", {}).get("platform", "媒体官方端点"),
        )
        result.update(diagnostics)
        result.update(_runtime_diagnostics(spec))
        return accepted, result

    setattr(crawl_wechat_source, "_wechat_public_index_fallback", True)
    wechat.crawl_wechat_source = crawl_wechat_source
