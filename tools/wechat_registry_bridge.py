"""Runtime bridge between the WeChat parser and the account registry.

Public aggregation pages are used only as link-discovery fallbacks. An item is
accepted only after the original ``mp.weixin.qq.com`` page is fetched, the
configured public-account name is verified, and the existing entity relevance
rules pass.
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
        self._href = ""
        self._anchor_parts: list[str] = []
        self._anchor_position = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.casefold() != "a":
            return
        values = {key.casefold(): value or "" for key, value in attrs}
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

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or not self._href:
            return
        self.links.append(
            {
                "url": self._href,
                "title": _clean(" ".join(self._anchor_parts), 260),
                "position": self._anchor_position,
            }
        )
        self._href = ""
        self._anchor_parts = []


def _context(
    parser: PublicIndexParser,
    position: int,
    next_position: int | None = None,
) -> str:
    start = max(0, position)
    natural_end = min(len(parser.text_parts), position + 10)
    end = min(natural_end, next_position) if next_position is not None else natural_end
    return _clean(" ".join(parser.text_parts[start:end]), 1200)


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
    if not is_sohu_profile:
        return False
    page_text = _clean(" ".join(parser.text_parts), 5000)
    return wechat_source_registry.account_matches(spec, page_text)


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
    return result


def _fallback_index_rows(
    spec: dict[str, Any], user_agent: str, crawler: Any
) -> tuple[list[dict[str, str]], int]:
    rows: list[dict[str, str]] = []
    failures = 0
    diagnostics = {
        "publicIndexPagesFetched": 0,
        "publicIndexPagesFailed": 0,
        "publicIndexRowsDiscovered": 0,
        "publicIndexDetailResolved": 0,
        "publicIndexDetailUnresolved": 0,
        "publicIndexTitleResolved": 0,
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
        for row in discovered:
            resolved = _resolve_detail_row(row, spec, user_agent, crawler)
            if row.get("kind") == "detail":
                if resolved:
                    diagnostics["publicIndexDetailResolved"] += 1
                    if any(item.get("titleLookupQuery") for item in resolved):
                        diagnostics["publicIndexTitleResolved"] += 1
                else:
                    diagnostics["publicIndexDetailUnresolved"] += 1
                    failures += 1
            rows.extend(resolved)
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
                parser = wechat.WeChatPageParser()
                parser.feed(body or "")
                observed_account = parser.account or wechat._js_value(
                    body or "",
                    ("nickname", "profile_nickname", "account_name"),
                )
                if not wechat_source_registry.account_matches(
                    spec, observed_account
                ):
                    return None

                # Discovery-page dates are never acceptance evidence for a
                # configured account.  The original mp.weixin page must expose
                # its own date, which the wrapped parser then normalizes.
                kwargs.pop("fallback_date", None)

            article = original_parse(spec, url, body, crawler, **kwargs)
            if article and spec.get("expectedAccounts") and not _article_date_is_recent(
                article.get("publishedAt"),
                spec,
                crawler,
            ):
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
        max_items = int(spec.get("maxItems", 6))
        for row in rows[: max_items * 5]:
            try:
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
            except Exception:  # noqa: BLE001 - aggregated below.
                failures += 1
                continue
            if article:
                accepted.append(article)
            if len(accepted) >= max_items:
                break

        if not accepted:
            result = crawler._status(
                spec["id"],
                spec["name"],
                "error",
                len(rows),
                0,
                failed=max(1, failures),
                platform="微信",
                error=(
                    "No verified public WeChat articles discovered from Bing or "
                    "configured public indexes; previous snapshot retained"
                ),
            )
            result.update(diagnostics)
            return [], result
        result = crawler._status(
            spec["id"],
            spec["name"],
            "partial" if failures else "ok",
            len(rows),
            len(accepted),
            failed=failures,
            platform="微信",
        )
        result.update(diagnostics)
        return accepted, result

    setattr(crawl_wechat_source, "_wechat_public_index_fallback", True)
    wechat.crawl_wechat_source = crawl_wechat_source
