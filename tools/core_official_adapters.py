"""Install dedicated first-party newsroom adapters for core research companies.

The generic official-company crawler remains the broad fallback. This module
adds a small high-priority set to the crawler's native ``NewsSource`` path so
core companies receive predictable link scopes, date parsing and bounded direct
requests before the generic discovery layer runs.

A few first-party sites need a slightly different treatment:

* Google DeepMind moved its canonical news index from ``/discover/blog/`` to
  ``/blog/``.
* SpaceX now exposes stable, dated releases through its investor-relations
  newsroom rather than the JavaScript-heavy ``www.spacex.com/updates`` page.
* Unitree's news detail pages currently render almost no server-side article
  metadata, while the first-party news index itself exposes the canonical URL,
  title and publication date. For Unitree only, the index row is therefore the
  authoritative publication record and the adapter does not depend on the empty
  detail-page HTML.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit


CORE_OFFICIAL_SOURCES = (
    {
        "id": "google-deepmind",
        "name": "Google DeepMind",
        "index_url": "https://deepmind.google/blog/",
        "company": "Google DeepMind",
        "company_slug": "google",
        "region": "美国",
        "sector": "AI / AGI",
        "path_prefixes": ("/blog/",),
    },
    {
        "id": "bytedance",
        "name": "字节跳动",
        "index_url": "https://www.bytedance.com/zh/news",
        "company": "字节跳动",
        "company_slug": "bytedance",
        "region": "中国",
        "sector": "AI / AGI",
        "path_prefixes": ("/zh/news/",),
    },
    {
        "id": "doubao",
        "name": "豆包 Seed",
        "index_url": "https://seed.bytedance.com/zh/blog",
        "company": "豆包",
        "company_slug": "doubao",
        "region": "中国",
        "sector": "AI / AGI",
        "path_prefixes": ("/zh/blog/",),
    },
    {
        "id": "volcengine",
        "name": "火山引擎",
        "index_url": "https://www.volcengine.com/news",
        "company": "火山引擎",
        "company_slug": "volcengine",
        "region": "中国",
        "sector": "AI / AGI",
        "path_prefixes": ("/news/detail/",),
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "index_url": "https://api-docs.deepseek.com/news/",
        "company": "DeepSeek",
        "company_slug": "deepseek",
        "region": "中国",
        "sector": "AI / AGI",
        "path_prefixes": ("/news/",),
    },
    {
        "id": "minimax",
        "name": "MiniMax",
        "index_url": "https://www.minimaxi.com/news",
        "company": "MiniMax",
        "company_slug": "minimax",
        "region": "中国",
        "sector": "AI / AGI",
        "path_prefixes": ("/news/",),
    },
    {
        "id": "zhipu-ai",
        "name": "智谱AI",
        "index_url": "https://www.zhipuai.cn/zh/news",
        "company": "智谱AI",
        "company_slug": "zhipu-ai",
        "region": "中国",
        "sector": "AI / AGI",
        "path_prefixes": ("/zh/news/",),
    },
    {
        "id": "unitree",
        "name": "宇树科技",
        "index_url": "https://www.unitree.com/news/",
        "company": "宇树科技",
        "company_slug": "unitree",
        "region": "中国",
        "sector": "机器人",
        "path_prefixes": ("/news/",),
    },
    {
        "id": "spacex",
        "name": "SpaceX",
        "index_url": "https://ir.spacex.com/updates/",
        "company": "SpaceX",
        "company_slug": "spacex",
        "region": "美国",
        "sector": "商业航天",
        "path_prefixes": (
            "/updates/releases-details/",
            "/updates/releases/details/",
        ),
    },
    {
        "id": "cerebras",
        "name": "Cerebras Systems",
        "index_url": "https://www.cerebras.ai/blog",
        "company": "Cerebras Systems",
        "company_slug": "cerebras",
        "region": "美国",
        "sector": "半导体",
        "path_prefixes": ("/blog/",),
    },
    {
        "id": "scale-ai",
        "name": "Scale AI",
        "index_url": "https://scale.com/blog",
        "company": "Scale AI",
        "company_slug": "scale-ai",
        "region": "美国",
        "sector": "AI / AGI",
        "path_prefixes": ("/blog/",),
    },
)


_UNITREE_ROW_RE = re.compile(
    r"^(?P<title>.+?)(?P<date>\d{4}-\d{2}-\d{2})\s*"
    r"(?:Media Coverage|媒体报道)?\s*$",
    flags=re.IGNORECASE,
)
_UNITREE_ARTICLE_PATH_RE = re.compile(r"^/news/\d+/?$")


class _AnchorTextParser(HTMLParser):
    """Collect anchor destinations together with their visible text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() != "a":
            return
        values = {key.lower(): value or "" for key, value in attrs}
        href = values.get("href", "").strip()
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._href is None:
            return
        self.anchors.append((self._href, " ".join(self._text)))
        self._href = None
        self._text = []


def _parse_unitree_listing_entries(
    body: str,
    index_url: str = "https://www.unitree.com/news/",
) -> list[dict[str, str]]:
    """Extract Unitree article URL/title/date from the server-rendered news index."""

    parser = _AnchorTextParser()
    parser.feed(body)
    index_host = (urlsplit(index_url).hostname or "").casefold()
    entries: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for href, raw_text in parser.anchors:
        absolute = urljoin(index_url, href)
        parts = urlsplit(absolute)
        if (parts.hostname or "").casefold() != index_host:
            continue
        if not _UNITREE_ARTICLE_PATH_RE.fullmatch(parts.path):
            continue
        text = re.sub(r"\s+", " ", raw_text).strip()
        match = _UNITREE_ROW_RE.fullmatch(text)
        if not match:
            continue
        title = match.group("title").strip(" -|—")
        published_at = match.group("date")
        if len(title) < 8:
            continue
        canonical = absolute.split("#", 1)[0]
        if canonical in seen_urls:
            continue
        seen_urls.add(canonical)
        entries.append(
            {
                "url": canonical,
                "title": title,
                "publishedAt": published_at,
            }
        )

    entries.sort(
        key=lambda item: (item["publishedAt"], item["url"]),
        reverse=True,
    )
    return entries


def _install_unitree_listing_adapter(crawler: Any) -> None:
    original = crawler.crawl_news_source
    if getattr(original, "_unitree_listing_adapter", False):
        return

    def crawl_news_source(source: Any, user_agent: str):
        if source.id != "unitree":
            return original(source, user_agent)

        body = crawler.fetch_text(source.index_url, user_agent)
        entries = _parse_unitree_listing_entries(body, source.index_url)
        limit = max(1, int(getattr(crawler, "MAX_NEWS_PER_SOURCE", 10)))
        articles: list[dict[str, Any]] = []
        for entry in entries[:limit]:
            published_at = crawler.normalize_date(entry["publishedAt"])
            if not published_at:
                continue
            url = crawler.normalize_url(entry["url"])
            title = crawler.clean_text(entry["title"])
            summary = f"{source.name} 发布“{title}”；完整事实与数据见官方原文。"
            event_type, importance = crawler.infer_event_type(title, summary)
            articles.append(
                {
                    "id": crawler.article_id(source.id, url),
                    "sourceId": source.id,
                    "title": title[:220],
                    "summary": summary[:500],
                    "type": event_type,
                    "region": source.region,
                    "sector": source.sector,
                    "company": source.company,
                    "companySlug": source.company_slug,
                    "publishedAt": published_at,
                    "importance": importance,
                    "source": crawler._source(
                        source.name,
                        url,
                        "官方披露",
                        "官方网站",
                    ),
                }
            )

        if not articles:
            raise RuntimeError(
                "no dated articles parsed from Unitree first-party news index"
            )
        return articles, crawler._status(
            source.id,
            source.name,
            "ok",
            len(entries),
            len(articles),
            platform="官方网站",
        )

    setattr(crawl_news_source, "_unitree_listing_adapter", True)
    crawler.crawl_news_source = crawl_news_source


def install(crawler: Any) -> None:
    existing = tuple(crawler.NEWS_SOURCES)
    existing_ids = {source.id for source in existing}
    additions = []
    for raw in CORE_OFFICIAL_SOURCES:
        if raw["id"] in existing_ids:
            continue
        additions.append(
            crawler.NewsSource(
                raw["id"],
                raw["name"],
                raw["index_url"],
                raw["company"],
                raw["company_slug"],
                raw["region"],
                raw["sector"],
                tuple(raw["path_prefixes"]),
            )
        )
        existing_ids.add(raw["id"])
    if additions:
        crawler.NEWS_SOURCES = (*existing, *additions)
    _install_unitree_listing_adapter(crawler)
