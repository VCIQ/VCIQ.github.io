#!/usr/bin/env python3
"""Structured official-source adapters for ByteDance, Doubao Seed and Volcengine.

The three official indexes are JavaScript applications. Their public payloads are
still available without authentication: ByteDance exposes ``/api/articles`` and
the Doubao Seed / Volcengine pages embed ``window._ROUTER_DATA``. Parsing those
first-party payloads avoids search-engine wrappers and preserves original links.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any, Callable, Sequence
from urllib.parse import quote


BYTEDANCE_SLUG = "bytedance"
DOUBAO_SLUG = "doubao"
VOLCENGINE_SLUG = "volcengine"
SUPPORTED_SLUGS = {BYTEDANCE_SLUG, DOUBAO_SLUG, VOLCENGINE_SLUG}

BYTEDANCE_ARTICLES_URL = (
    "https://www.bytedance.com/api/articles?language=1&limit=18&offset=0"
)
DOUBAO_SEED_BLOG_URL = "https://seed.bytedance.com/zh/blog"
VOLCENGINE_NEWS_URL = "https://www.volcengine.com/news"


def extract_router_data(body: str) -> dict[str, Any]:
    """Decode the JSON object assigned to ``window._ROUTER_DATA``."""

    marker = "window._ROUTER_DATA"
    start = body.find(marker)
    if start < 0:
        raise ValueError("official page did not expose window._ROUTER_DATA")
    assignment = body.find("=", start + len(marker))
    if assignment < 0:
        raise ValueError("official page ROUTER_DATA assignment is malformed")
    payload = body[assignment + 1 :].lstrip()
    value, _ = json.JSONDecoder().raw_decode(payload)
    if not isinstance(value, dict):
        raise ValueError("official page ROUTER_DATA is not an object")
    return value


def _clean(official: Any, value: Any, limit: int) -> str:
    return official.clean_text(str(value or ""))[:limit]


def _published_at(official: Any, value: Any) -> str | None:
    return official.normalize_date(value)


def _inside_age_window(published_at: str, max_age_days: int) -> bool:
    try:
        published = date.fromisoformat(published_at)
    except ValueError:
        return False
    return published >= datetime.now(UTC).date() - timedelta(days=max_age_days)


def _build_article(
    official: Any,
    spec: Any,
    *,
    title: Any,
    summary: Any,
    published: Any,
    url: str,
    platform: str,
    forced_type: str | None = None,
) -> dict[str, Any] | None:
    clean_title = _clean(official, title, 220)
    clean_summary = _clean(official, summary, 500)
    published_at = _published_at(official, published)
    if not clean_title or len(clean_title) < 6 or not published_at:
        return None
    if not _inside_age_window(published_at, int(spec.max_age_days)):
        return None
    if not clean_summary:
        clean_summary = f"{spec.name} 发布“{clean_title}”；完整内容见官方原文。"
    event_type, importance = official.infer_event_type(
        clean_title,
        clean_summary,
        forced_type=forced_type,
    )
    canonical_url = official.normalize_url(url)
    return {
        "id": official.article_id(spec.source_id, canonical_url),
        "sourceId": spec.source_id,
        "title": clean_title,
        "summary": clean_summary,
        "type": event_type,
        "region": spec.region,
        "sector": spec.sector,
        "company": spec.name,
        "companySlug": spec.slug,
        "publishedAt": published_at,
        "importance": max(importance, 80),
        "source": official._source(
            spec.name,
            canonical_url,
            "官方披露",
            platform,
        ),
    }


def _deduplicate_and_limit(
    articles: Sequence[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    by_url: dict[str, dict[str, Any]] = {}
    for article in articles:
        source = article.get("source") if isinstance(article.get("source"), dict) else {}
        key = str(source.get("url", "")) or str(article.get("id", ""))
        if key:
            by_url[key] = article
    return sorted(
        by_url.values(),
        key=lambda item: (
            str(item.get("publishedAt", "")),
            int(item.get("importance", 0) or 0),
            str(item.get("id", "")),
        ),
        reverse=True,
    )[: max(1, limit)]


def parse_bytedance_payload(
    body: str, spec: Any, official: Any
) -> list[dict[str, Any]]:
    payload = json.loads(body)
    container = payload.get("data") if isinstance(payload, dict) else None
    records = container.get("data", []) if isinstance(container, dict) else []
    articles: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        identity = _clean(official, record.get("theme") or record.get("_id"), 160)
        if not identity:
            continue
        article = _build_article(
            official,
            spec,
            title=record.get("title"),
            summary=record.get("abstract"),
            published=record.get("published"),
            url=f"https://www.bytedance.com/zh/news/{quote(identity, safe='-._~')}",
            platform="字节跳动官网",
        )
        if article:
            articles.append(article)
    return _deduplicate_and_limit(articles, spec.max_items)


def _seed_forced_type(record: dict[str, Any]) -> str | None:
    metadata = record.get("ArticleMeta")
    metadata = metadata if isinstance(metadata, dict) else {}
    areas = metadata.get("ResearchArea")
    areas = areas if isinstance(areas, list) else []
    labels = " ".join(
        str(area.get("ResearchAreaNameZh", ""))
        for area in areas
        if isinstance(area, dict)
    )
    if "研究" in labels:
        return "技术突破"
    if "模型发布" in labels:
        return "产品发布"
    return None


def parse_doubao_seed_page(
    body: str, spec: Any, official: Any
) -> list[dict[str, Any]]:
    router_data = extract_router_data(body)
    loader_data = router_data.get("loaderData")
    loader_data = loader_data if isinstance(loader_data, dict) else {}
    page = loader_data.get("(locale$)/blog/page")
    page = page if isinstance(page, dict) else {}
    records = page.get("article_list")
    records = records if isinstance(records, list) else []
    articles: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        metadata = record.get("ArticleMeta")
        metadata = metadata if isinstance(metadata, dict) else {}
        content = record.get("ArticleSubContentZh")
        if not isinstance(content, dict) or not content.get("Title"):
            content = record.get("ArticleSubContentEn")
        content = content if isinstance(content, dict) else {}
        title_key = _clean(official, content.get("TitleKey"), 320)
        if not title_key:
            continue
        article = _build_article(
            official,
            spec,
            title=content.get("Title"),
            summary=content.get("Abstract"),
            published=metadata.get("PublishDate"),
            url=(
                "https://seed.bytedance.com/zh/blog/"
                f"{quote(title_key, safe='-._~')}"
            ),
            platform="豆包 Seed",
            forced_type=_seed_forced_type(record),
        )
        if article:
            articles.append(article)
    return _deduplicate_and_limit(articles, spec.max_items)


def _volcengine_page(body: str) -> dict[str, Any]:
    router_data = extract_router_data(body)
    loader_data = router_data.get("loaderData")
    loader_data = loader_data if isinstance(loader_data, dict) else {}
    page = loader_data.get("__ssr_without_user/news/page")
    return page if isinstance(page, dict) else {}


def parse_volcengine_page(
    body: str, spec: Any, official: Any
) -> list[dict[str, Any]]:
    page = _volcengine_page(body)
    articles: list[dict[str, Any]] = []

    banners = page.get("banner")
    banners = banners if isinstance(banners, list) else []
    for record in banners:
        if not isinstance(record, dict):
            continue
        link = _clean(official, record.get("link"), 500)
        if not link.startswith("https://www.volcengine.com/news/detail/"):
            continue
        summary = " · ".join(
            value
            for value in (
                _clean(official, record.get("category"), 80),
                _clean(official, record.get("tag"), 80),
            )
            if value
        )
        article = _build_article(
            official,
            spec,
            title=record.get("title"),
            summary=summary,
            published=record.get("date"),
            url=link,
            platform="火山引擎发布中心",
        )
        if article:
            articles.append(article)

    online = page.get("listOnlineArticle")
    online = online if isinstance(online, dict) else {}
    records = online.get("List")
    records = records if isinstance(records, list) else []
    for record in records:
        if not isinstance(record, dict):
            continue
        document_id = record.get("DocumentID")
        if not isinstance(document_id, int) and not str(document_id or "").isdigit():
            continue
        summary = _clean(official, record.get("Summary"), 500)
        if not summary:
            summary = " · ".join(
                value
                for value in (
                    _clean(official, record.get("TagName"), 80),
                    _clean(official, record.get("CategoryCodeName"), 80),
                )
                if value
            )
        article = _build_article(
            official,
            spec,
            title=record.get("VersionTitle") or record.get("Title"),
            summary=summary,
            published=record.get("CreatedTime") or record.get("UpdatedTime"),
            url=f"https://www.volcengine.com/news/detail/{document_id}",
            platform="火山引擎发布中心",
        )
        if article:
            articles.append(article)

    return _deduplicate_and_limit(articles, spec.max_items)


def _structured_record_count(slug: str, body: str) -> int:
    """Count article records evaluated inside one structured transport payload."""

    if slug == BYTEDANCE_SLUG:
        payload = json.loads(body)
        container = payload.get("data") if isinstance(payload, dict) else None
        records = container.get("data", []) if isinstance(container, dict) else []
        return sum(1 for record in records if isinstance(record, dict))
    if slug == DOUBAO_SLUG:
        router_data = extract_router_data(body)
        loader_data = router_data.get("loaderData")
        loader_data = loader_data if isinstance(loader_data, dict) else {}
        page = loader_data.get("(locale$)/blog/page")
        page = page if isinstance(page, dict) else {}
        records = page.get("article_list")
        records = records if isinstance(records, list) else []
        return sum(1 for record in records if isinstance(record, dict))
    if slug == VOLCENGINE_SLUG:
        page = _volcengine_page(body)
        banners = page.get("banner")
        banners = banners if isinstance(banners, list) else []
        online = page.get("listOnlineArticle")
        online = online if isinstance(online, dict) else {}
        records = online.get("List")
        records = records if isinstance(records, list) else []
        return sum(1 for record in (*banners, *records) if isinstance(record, dict))
    return 0


def _status(
    spec: Any,
    *,
    accepted: int,
    scanned: int,
    failed: int,
    platform: str,
    transport_requests: int = 1,
    error: str = "",
) -> dict[str, Any]:
    state = "ok" if accepted and not failed else "partial" if accepted else "empty"
    # `scanned` and `accepted` are both record-level counters. The structured
    # adapters fetch one transport payload that can contain many article records;
    # keep that HTTP/request count separate so unlike units cannot be compared.
    scanned_records = max(int(scanned), int(accepted))
    result: dict[str, Any] = {
        "id": spec.source_id,
        "name": f"{spec.name} 官方动态",
        "company": spec.name,
        "companySlug": spec.slug,
        "coverage": "attempted",
        "status": state,
        "configuredIndexes": 1,
        "discovered": accepted,
        "scanned": scanned_records,
        "accepted": accepted,
        "failed": failed,
        "transportRequests": max(0, int(transport_requests)),
        "platform": platform,
    }
    if error:
        result["error"] = error[:240]
    return result


def crawl_structured_company(
    spec: Any, user_agent: str, official: Any
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    route: tuple[str, Callable[[str, Any, Any], list[dict[str, Any]]], str]
    if spec.slug == BYTEDANCE_SLUG:
        route = (BYTEDANCE_ARTICLES_URL, parse_bytedance_payload, "字节跳动官网")
    elif spec.slug == DOUBAO_SLUG:
        route = (DOUBAO_SEED_BLOG_URL, parse_doubao_seed_page, "豆包 Seed")
    elif spec.slug == VOLCENGINE_SLUG:
        route = (VOLCENGINE_NEWS_URL, parse_volcengine_page, "火山引擎发布中心")
    else:
        raise ValueError(f"unsupported structured company: {spec.slug}")

    url, parser, platform = route
    try:
        body = official.fetch_text(
            url,
            user_agent,
            timeout=spec.request_timeout,
            attempts=2,
        )
        articles = parser(body, spec, official)
        return articles, _status(
            spec,
            accepted=len(articles),
            scanned=_structured_record_count(spec.slug, body),
            failed=0,
            platform=platform,
            transport_requests=1,
            error="" if articles else "official structured payload returned no eligible articles",
        )
    except Exception as exc:
        return [], _status(
            spec,
            accepted=0,
            scanned=0,
            failed=1,
            platform=platform,
            transport_requests=1,
            error=f"{type(exc).__name__}: {exc}",
        )


def install(official: Any) -> None:
    """Route the three JavaScript official sites through structured parsers."""

    original = official.crawl_company
    if getattr(original, "_bytedance_structured_sources", False):
        return

    def crawl_company(spec: Any, user_agent: str):
        if spec.slug in SUPPORTED_SLUGS:
            return crawl_structured_company(spec, user_agent, official)
        return original(spec, user_agent)

    setattr(crawl_company, "_bytedance_structured_sources", True)
    official.crawl_company = crawl_company
