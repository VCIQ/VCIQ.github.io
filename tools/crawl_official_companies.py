#!/usr/bin/env python3
"""Crawl official news for every company in the public company catalog.

The main crawler intentionally keeps source-specific adapters small. This module
adds a registry-driven layer for the complete 58-company catalog without
hard-coding each company in ``crawl_articles.py``. It prefers direct official
news, newsroom, blog and investor-relations pages, discovers RSS/Atom feeds and
article links on those pages, and uses a domain-restricted public search index
only to discover official URLs when a site exposes no usable index.

All accepted records are bound to the registry's exact ``companySlug``. This
prevents a company mentioned incidentally in an article summary from becoming
the article's primary company.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import quote_plus, urljoin, urlsplit
from urllib.request import Request, urlopen

try:  # Imported by tests as tools.crawl_official_companies.
    from .crawl_articles import (
        DEFAULT_USER_AGENT,
        OUTPUT_PATH,
        ROOT,
        ArticleHTMLParser,
        _published_value,
        _source,
        article_id,
        clean_text,
        clean_title,
        evaluate_quality,
        fetch_text,
        infer_event_type,
        load_config,
        load_existing_payload,
        merge_articles,
        merge_source_status,
        normalize_date,
        normalize_url,
        strip_html,
        write_if_changed,
    )
except ImportError:  # Executed directly with ``python tools/...``.
    from crawl_articles import (
        DEFAULT_USER_AGENT,
        OUTPUT_PATH,
        ROOT,
        ArticleHTMLParser,
        _published_value,
        _source,
        article_id,
        clean_text,
        clean_title,
        evaluate_quality,
        fetch_text,
        infer_event_type,
        load_config,
        load_existing_payload,
        merge_articles,
        merge_source_status,
        normalize_date,
        normalize_url,
        strip_html,
        write_if_changed,
    )


REGISTRY_PATH = ROOT / "config" / "official_company_sources.json"
CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"
COMPANY_REGISTRY_PATH = ROOT / "config" / "company_registry.json"
LISTED_INNOVATION_PATH = ROOT / "config" / "listed_innovation_companies.json"
LISTED_SOURCE_HEALTH_PATH = ROOT / "public" / "data" / "listed_innovation_source_health.json"
NEWS_PATH_HINTS = (
    "/news",
    "/newsroom",
    "/press",
    "/media",
    "/blog",
    "/updates",
    "/articles",
    "/insights",
    "/stories",
    "/resources",
    "/announcements",
    "/news-releases",
    "/press-releases",
)
NEWS_TEXT_HINTS = (
    "news",
    "newsroom",
    "press",
    "media",
    "blog",
    "update",
    "announcement",
    "release",
    "insight",
    "article",
    "新闻",
    "动态",
    "资讯",
    "公告",
    "媒体",
    "博客",
)
SKIP_PATH_HINTS = (
    "/about",
    "/company",
    "/careers",
    "/jobs",
    "/contact",
    "/privacy",
    "/terms",
    "/legal",
    "/products",
    "/solutions",
    "/events",
    "/tag/",
    "/category/",
    "/author/",
)
GENERIC_TITLES = {
    "news",
    "news center",
    "newsroom",
    "latest news and events.",
    "press",
    "press releases",
    "press updates",
    "blog",
    "updates",
    "articles",
    "insights",
    "media",
    "media center",
    "新闻",
    "新闻中心",
    "企业新闻",
    "公司动态",
    "资讯中心",
}
GENERIC_INDEX_SEGMENTS = {
    "articles",
    "blog",
    "insights",
    "media",
    "news",
    "newsroom",
    "press",
    "press-archives",
    "press-releases",
    "updates",
}
EPOCH_PLACEHOLDER_DATES = {"1969-12-31", "1970-01-01"}


@dataclass(frozen=True)
class CompanySpec:
    slug: str
    name: str
    region: str
    sector: str
    homepage: str
    news_urls: tuple[str, ...]
    sitemap_urls: tuple[str, ...]
    aliases: tuple[str, ...]
    entity_aliases: tuple[str, ...]
    article_url_patterns: tuple[str, ...]
    require_entity_match: bool
    max_items: int
    max_candidate_links: int
    max_age_days: int
    request_timeout: int
    title_suffixes: tuple[str, ...] = ()

    @property
    def source_id(self) -> str:
        return f"official-{self.slug}"

    @property
    def allowed_hosts(self) -> tuple[str, ...]:
        hosts: list[str] = []
        for raw_url in (self.homepage, *self.news_urls, *self.sitemap_urls):
            host = (urlsplit(raw_url).hostname or "").lower()
            if host.startswith("www."):
                host = host[4:]
            if host and host not in hosts:
                hosts.append(host)
        return tuple(hosts)


class OfficialIndexParser(HTMLParser):
    """Collect anchors and feed links without retaining page text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self.feeds: list[str] = []
        self._href: str | None = None
        self._anchor_text: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        lowered = tag.lower()
        if lowered == "a" and values.get("href"):
            self._href = values["href"]
            self._anchor_text = []
        elif lowered == "link" and values.get("href"):
            relation = values.get("rel", "").lower()
            media_type = values.get("type", "").lower()
            if "alternate" in relation and media_type in {
                "application/rss+xml",
                "application/atom+xml",
                "application/feed+json",
            }:
                self.feeds.append(values["href"])

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._anchor_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, clean_text(" ".join(self._anchor_text))))
            self._href = None
            self._anchor_text = []


class FeedLinkParser:
    """Extract destination URLs from RSS/Atom search output."""

    @staticmethod
    def links(body: str) -> list[str]:
        root = ET.fromstring(body)
        links: list[str] = []
        for node in root.iter():
            local = node.tag.rsplit("}", 1)[-1].lower()
            if local not in {"item", "entry"}:
                continue
            candidate = ""
            for child in node.iter():
                if child.tag.rsplit("}", 1)[-1].lower() != "link":
                    continue
                candidate = clean_text(child.attrib.get("href", "")) or clean_text(
                    child.text or ""
                )
                if candidate:
                    break
            if candidate and candidate not in links:
                links.append(candidate)
        return links


def _load_company_registry_json(
    path: Path = COMPANY_REGISTRY_PATH,
) -> dict[str, dict[str, str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read company registry JSON: {path}") from exc
    rows = payload.get("companies", [])
    if not isinstance(rows, list):
        raise ValueError("company registry JSON must contain a companies array")
    companies: dict[str, dict[str, str]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        slug = clean_text(str(raw.get("slug", "")))
        name = clean_text(str(raw.get("name", "")))
        region = clean_text(str(raw.get("region", "")))
        sector = clean_text(str(raw.get("sector", "")))
        if not slug or not name or not region or not sector:
            continue
        if slug in companies:
            raise ValueError(f"company registry JSON contains duplicate slug: {slug}")
        companies[slug] = {
            "name": name,
            "region": region,
            "sector": sector,
        }
    if not companies:
        raise ValueError("company registry JSON parser returned no companies")
    return companies


def _load_catalog_companies(
    path: Path = CATALOG_PATH,
    company_registry_path: Path = COMPANY_REGISTRY_PATH,
) -> dict[str, dict[str, str]]:
    """Read the canonical company registry without a second slug list.

    Legacy fixtures and older branches may still expose a TypeScript company array.
    Production now exports companies from ``config/company_registry.json``; when the
    array is absent, the crawler reads that versioned registry directly.
    """

    body = path.read_text(encoding="utf-8")
    section = re.search(
        r"export\s+const\s+companies\s*:\s*Company\[\]\s*=\s*\[(.*?)\n\];",
        body,
        flags=re.DOTALL,
    )
    if section:
        pattern = re.compile(
            r'\{\s*slug:"([^"]+)",\s*name:"([^"]+)",'
            r'(?:\s*englishName:"[^"]+",)?\s*region:"([^"]+)",\s*sector:"([^"]+)"'
        )
        companies = {
            match.group(1): {
                "name": match.group(2),
                "region": match.group(3),
                "sector": match.group(4),
            }
            for match in pattern.finditer(section.group(1))
        }
        if companies:
            return companies
        raise ValueError("company catalog parser returned no companies")
    return _load_company_registry_json(company_registry_path)


def load_registry(
    path: Path = REGISTRY_PATH,
    catalog_path: Path = CATALOG_PATH,
    company_registry_path: Path = COMPANY_REGISTRY_PATH,
) -> list[CompanySpec]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    defaults = payload.get("defaults", {})
    raw_companies = payload.get("companies", [])
    if not isinstance(raw_companies, list):
        raise ValueError("official company registry must contain a companies array")
    specs: list[CompanySpec] = []
    for raw in raw_companies:
        spec = CompanySpec(
            slug=clean_text(str(raw.get("slug", ""))),
            name=clean_text(str(raw.get("name", ""))),
            region=clean_text(str(raw.get("region", ""))),
            sector=clean_text(str(raw.get("sector", ""))),
            homepage=normalize_url(str(raw.get("homepage", ""))),
            news_urls=tuple(
                normalize_url(str(url)) for url in raw.get("newsUrls", []) if url
            ),
            sitemap_urls=tuple(
                normalize_url(str(url)) for url in raw.get("sitemapUrls", []) if url
            ),
            aliases=tuple(
                clean_text(str(alias)) for alias in raw.get("aliases", []) if alias
            ),
            entity_aliases=tuple(
                clean_text(str(alias))
                for alias in raw.get(
                    "entityAliases",
                    [raw.get("name", ""), *raw.get("aliases", [])],
                )
                if alias
            ),
            article_url_patterns=tuple(
                clean_text(str(pattern))
                for pattern in raw.get("articleUrlPatterns", [])
                if pattern
            ),
            require_entity_match=bool(raw.get("requireEntityMatch", False)),
            max_items=int(raw.get("maxItems", defaults.get("maxItems", 4))),
            max_candidate_links=int(
                raw.get(
                    "maxCandidateLinks", defaults.get("maxCandidateLinks", 10)
                )
            ),
            max_age_days=int(raw.get("maxAgeDays", defaults.get("maxAgeDays", 730))),
            request_timeout=int(
                raw.get("requestTimeout", defaults.get("requestTimeout", 10))
            ),
            title_suffixes=tuple(str(value) for value in raw.get("titleSuffixes", []) if value),
        )
        missing = [
            field
            for field, value in (
                ("slug", spec.slug),
                ("name", spec.name),
                ("region", spec.region),
                ("sector", spec.sector),
                ("homepage", spec.homepage),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"registry entry missing {','.join(missing)}: {raw}")
        if not spec.allowed_hosts:
            raise ValueError(f"registry entry has no valid official host: {spec.slug}")
        for pattern in spec.article_url_patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(
                    f"invalid articleUrlPatterns value for {spec.slug}: {pattern}"
                ) from exc
        specs.append(spec)
    slugs = [spec.slug for spec in specs]
    if len(slugs) != len(set(slugs)):
        raise ValueError("official company registry contains duplicate slugs")
    # The catalog/registry slug-set comparison below is the canonical coverage
    # gate. A second hard-coded count becomes stale whenever a company is added.
    catalog = _load_catalog_companies(catalog_path, company_registry_path)
    registry_by_slug = {spec.slug: spec for spec in specs}
    missing = sorted(set(catalog) - set(registry_by_slug))
    extra = sorted(set(registry_by_slug) - set(catalog))
    if missing or extra:
        raise ValueError(
            "official company registry does not match company catalog: "
            f"missing={missing}, extra={extra}"
        )
    mismatches = [
        spec.slug
        for spec in specs
        if any(
            (
                spec.name != catalog[spec.slug]["name"],
                spec.region != catalog[spec.slug]["region"],
                spec.sector != catalog[spec.slug]["sector"],
            )
        )
    ]
    if mismatches:
        raise ValueError(
            "official company registry metadata differs from company catalog: "
            + ", ".join(sorted(mismatches))
        )
    return specs


def _host_allowed(url: str, allowed_hosts: Sequence[str]) -> bool:
    parts = urlsplit(url)
    if parts.scheme not in {"https", "http"} or parts.username or parts.password:
        return False
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts)


def _path_date(url: str) -> str | None:
    path = urlsplit(url).path
    for pattern in (
        r"/(20\d{2})/(\d{1,2})/(\d{1,2})(?:/|$)",
        r"/(20\d{2})-(\d{1,2})-(\d{1,2})(?:/|$)",
    ):
        match = re.search(pattern, path)
        if not match:
            continue
        try:
            return date(*map(int, match.groups())).isoformat()
        except ValueError:
            pass
    return None


def _candidate_score(
    url: str, anchor_text: str, article_url_patterns: Sequence[str] = ()
) -> int:
    parts = urlsplit(url)
    path = parts.path.casefold()
    text = anchor_text.casefold()
    if parts.scheme not in {"http", "https"} or parts.username or parts.password:
        return -100
    if not path or path == "/" or re.search(r"\.(?:pdf|mp4|mp3|zip|jpg|jpeg|png|svg|webp)$", path):
        return -100
    explicit_detail = any(
        pattern.startswith("^https://") and pattern.endswith("$")
        and re.fullmatch(pattern, url, flags=re.IGNORECASE)
        for pattern in article_url_patterns
    )
    # Only reviewed exact article paths may override /about; never attachments.
    if any(hint in path and not (explicit_detail and hint == "/about") for hint in SKIP_PATH_HINTS):
        return -100
    score = 0
    if any(
        re.search(pattern, url, flags=re.IGNORECASE)
        for pattern in article_url_patterns
    ):
        score += 10
    if any(hint in path for hint in NEWS_PATH_HINTS):
        score += 5
    if any(hint in text for hint in NEWS_TEXT_HINTS):
        score += 3
    if re.search(r"/20\d{2}(?:/|-)", path):
        score += 3
    if len([part for part in path.split("/") if part]) >= 2:
        score += 1
    if parts.query:
        score -= 1
    return score


def discover_candidate_urls(
    index_url: str,
    body: str,
    allowed_hosts: Sequence[str],
    limit: int,
    article_url_patterns: Sequence[str] = (),
) -> tuple[list[str], list[str]]:
    parser = OfficialIndexParser()
    parser.feed(body)
    scored: dict[str, int] = {}
    for href, text in parser.anchors:
        absolute = normalize_url(urljoin(index_url, href))
        if absolute == normalize_url(index_url) or not _host_allowed(
            absolute, allowed_hosts
        ):
            continue
        score = _candidate_score(absolute, text, article_url_patterns)
        if score >= 4:
            scored[absolute] = max(score, scored.get(absolute, -100))
    # Python's sort is stable, so equal-score links retain the newsroom's own
    # order. Most official indexes place their newest articles first; sorting
    # equal scores by URL previously selected arbitrary slugs instead.
    candidates = sorted(
        scored,
        key=lambda candidate: scored[candidate],
        reverse=True,
    )[:limit]
    feeds = []
    for href in parser.feeds:
        absolute = normalize_url(urljoin(index_url, href))
        if _host_allowed(absolute, allowed_hosts) and absolute not in feeds:
            feeds.append(absolute)
    return candidates, feeds


def _publication_title_key(value: str) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]", "", clean_title(value).casefold())


def _index_publication_evidence(
    index_url: str, body: str, spec: CompanySpec,
) -> dict[str, list[dict[str, str]]]:
    """Bind publication dates to one exact linked record and its detail title.

    Never use feed updated, copyright or collection timestamps. Conflicting
    publication dates stay conflicting rather than selecting the newest date.
    """
    result: dict[str, list[dict[str, str]]] = {}

    def add(href: str, title: str, raw_date: str, method: str) -> None:
        url = normalize_url(urljoin(index_url, href))
        published = normalize_date(raw_date)
        if (
            not published or len(_publication_title_key(title)) < 8
            or not _host_allowed(url, spec.allowed_hosts)
            or _candidate_score(url, title, spec.article_url_patterns) < 4
            or (url not in result and len(result) >= spec.max_candidate_links)
        ):
            return
        result.setdefault(url, []).append({
            "title": clean_title(title), "publishedAt": published,
            "sourceUrl": normalize_url(index_url), "method": method,
        })

    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        root = None
    if root is not None and root.tag.rsplit("}", 1)[-1].lower() in {"rss", "feed", "rdf"}:
        for node in list(root.iter())[:2000]:
            if node.tag.rsplit("}", 1)[-1].lower() not in {"item", "entry"}:
                continue
            fields: dict[str, str] = {}
            for child in node:
                key = child.tag.rsplit("}", 1)[-1].lower()
                if key == "link":
                    if child.attrib.get("rel", "alternate") == "alternate":
                        fields.setdefault("link", child.attrib.get("href", "") or clean_text(child.text or ""))
                elif key in {"title", "pubdate", "published"}:
                    fields[key] = clean_text("".join(child.itertext()))
            if fields.get("link"):
                add(fields["link"], fields.get("title", ""),
                    fields.get("pubdate", "") or fields.get("published", ""), "official-feed")
        return result

    parser = OfficialIndexParser()
    parser.feed(body)
    for href, text in parser.anchors[:2000]:
        dates = list(re.finditer(r"(?<!\d)20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}(?!\d)", text))
        if len(dates) != 1:
            continue
        match = dates[0]
        before, after = text[:match.start()].strip(), text[match.end():].strip()
        title = before if before else after
        add(href, title, match.group(0), "official-index-link")
    return result


def _matched_publication_evidence(
    title: str, rows: Sequence[dict[str, str]],
) -> dict[str, str] | None:
    matching = [row for row in rows if _publication_title_key(row["title"]) == _publication_title_key(title)]
    dates = {row["publishedAt"] for row in matching}
    return matching[0] if len(dates) == 1 else None


def _classify_explicit_publication_date(value: Any) -> tuple[str, str | None]:
    """Ignore obvious non-publication placeholders but fail closed otherwise."""
    raw = clean_text(str(value or ""))
    if not raw:
        return "ignore", None
    if re.fullmatch(r"20\d{2}", raw):
        return "ignore", None
    normalized = normalize_date(raw)
    if normalized in EPOCH_PLACEHOLDER_DATES:
        return "epoch-placeholder", normalized
    if normalized is None:
        return "invalid", None
    return "valid", normalized


def _contains_entity_alias(text: str, alias: str) -> bool:
    folded_text = text.casefold()
    folded_alias = clean_text(alias).casefold()
    if not folded_alias:
        return False
    if re.fullmatch(r"[a-z0-9][a-z0-9 .&+_-]*", folded_alias):
        return bool(
            re.search(
                rf"(?<![a-z0-9]){re.escape(folded_alias)}(?![a-z0-9])",
                folded_text,
            )
        )
    return folded_alias in folded_text


def _is_index_page(spec: CompanySpec, url: str, title: str) -> bool:
    normalized = normalize_url(url)
    configured_indexes = {
        normalize_url(index_url)
        for index_url in (spec.homepage, *spec.news_urls)
    }
    if normalized in configured_indexes:
        return True
    segments = [
        segment.casefold()
        for segment in urlsplit(normalized).path.split("/")
        if segment
    ]
    if segments and segments[-1] in GENERIC_INDEX_SEGMENTS:
        return True
    if len(segments) <= 2 and segments[-2:] == ["blog", "product"]:
        return True
    folded_title = clean_text(title).casefold()
    if folded_title in GENERIC_TITLES:
        return True
    entity_names = (spec.name, *spec.aliases)
    return any(
        folded_title == clean_text(entity_name).casefold()
        for entity_name in entity_names
        if entity_name
    )


class _SmicPublicationDateParser(HTMLParser):
    """Read only the reviewed SMIC detail field, not dates in article prose.

    The observed markup is div.date.clearfix > div > p. In particular, a
    fiscal period in div.content, a visit count or a footer year is not a
    publication date. Callers restrict this adapter to exact SMIC news URLs.
    """

    _VOID_TAGS = frozenset({
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    })

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[str] = []
        self._stack: list[tuple[str, set[str]]] = []
        self._capture_depth: int | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        classes = set((dict(attrs).get("class") or "").split())
        if (
            tag == "p" and self._capture_depth is None
            and len(self._stack) >= 2
            and self._stack[-1][0] == "div"
            and self._stack[-2][0] == "div"
            and {"date", "clearfix"} <= self._stack[-2][1]
            and not any(t in {"footer", "nav", "aside"} for t, _ in self._stack)
        ):
            self._capture_depth = len(self._stack) + 1
            self._parts = []
        if tag not in self._VOID_TAGS:
            self._stack.append((tag, classes))

    def handle_endtag(self, tag) -> None:
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] != tag:
                continue
            if self._capture_depth is not None and index < self._capture_depth:
                # Publish only a complete paragraph; malformed fields fail
                # closed instead of borrowing dates from adjacent content.
                self.values.append(
                    clean_text(" ".join(self._parts)) if tag == "p" else ""
                )
                self._capture_depth = None
                self._parts = []
            del self._stack[index:]
            break

    def handle_data(self, data) -> None:
        if self._capture_depth is not None:
            self._parts.append(data)


def _smic_publication_dates(spec: CompanySpec, url: str, body: str) -> list[str]:
    if spec.slug != "smic" or not re.fullmatch(
        r"https://www\.smics\.com/site/news_read/\d+", normalize_url(url)
    ):
        return []
    parser = _SmicPublicationDateParser()
    parser.feed(body)
    return parser.values


def _article_from_page(
    spec: CompanySpec, url: str, body: str,
    rejection_counts: dict[str, int] | None = None,
    index_evidence: Sequence[dict[str, str]] = (),
) -> dict[str, Any] | None:
    def reject(reason: str) -> None:
        if rejection_counts is not None:
            rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
        return None

    parser = ArticleHTMLParser()
    parser.feed(body)
    requested_url = normalize_url(url)
    canonical_url = normalize_url(parser.meta.get("og:url", "") or requested_url)
    configured_indexes = {
        normalize_url(index_url)
        for index_url in (spec.homepage, *spec.news_urls)
    }
    # Some corporate CMS templates put the homepage in og:url on every page.
    # Keep the requested article URL when that metadata collapses to an index.
    if canonical_url in configured_indexes and requested_url not in configured_indexes:
        canonical_url = requested_url
    if not _host_allowed(canonical_url, spec.allowed_hosts):
        return reject("canonical-host-mismatch")
    title = ""
    for raw_title in (
        parser.meta.get("og:title", ""),
        parser.text("title"),
        *parser.texts("h1"),
    ):
        candidate_title = clean_title(raw_title)
        for suffix in spec.title_suffixes:
            if candidate_title.endswith(suffix):
                candidate_title = candidate_title[:-len(suffix)].strip()
        for suffix in (spec.name, *spec.aliases):
            candidate_title = re.sub(
                rf"\s*(?:\||—|–|-)\s*{re.escape(suffix)}\s*$",
                "",
                candidate_title,
                flags=re.IGNORECASE,
            )
        candidate_title = clean_text(candidate_title)
        # Reviewed CMS boilerplate can be repeated on every detail URL. A dated
        # page with a corporate slogan/media-library heading is not a news item;
        # continue to its actual H1 rather than publishing the boilerplate.
        if re.search(r"Inspiring AGI to Benefit Humanity|智绘全球|晶泰\s*媒体资料库", candidate_title, re.IGNORECASE):
            continue
        if (
            len(candidate_title) >= 8
            and not _is_index_page(spec, canonical_url, candidate_title)
        ):
            title = candidate_title
            break
    if not title:
        return reject("index-or-missing-title")
    summary = strip_html(
        parser.meta.get("description", "")
        or parser.meta.get("og:description", "")
        or parser.meta.get("twitter:description", "")
    )
    if spec.require_entity_match and not any(
        _contains_entity_alias(f"{title} {summary}", alias)
        for alias in spec.entity_aliases
    ):
        return reject("entity-not-in-title-or-summary")
    reviewed_dates = _smic_publication_dates(spec, requested_url, body)
    if reviewed_dates and canonical_url != requested_url:
        return reject("canonical-detail-mismatch")
    if any(not re.fullmatch(r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}", value)
           for value in reviewed_dates):
        return reject("conflicting-or-invalid-detail-publication-date")
    # An invalid/future explicit detail date cannot be replaced by an older
    # feed/index date. Disagreeing explicit publication metadata also fails shut.
    explicit_dates = [value for value in (
        parser.meta.get("article:published_time"), parser.meta.get("date"),
        parser.meta.get("datepublished"), parser.meta.get("publishdate"),
        *parser.time_values, *parser.date_values, *reviewed_dates,
    ) if value]
    for field in ("datePublished", "dateCreated", "publishDate"):
        explicit_dates.extend(re.findall(
            rf'"{field}"\s*:\s*"([^"]+)"', body, flags=re.IGNORECASE,
        ))
    classified_explicit = [
        _classify_explicit_publication_date(value) for value in explicit_dates
    ]
    if any(state == "invalid" for state, _ in classified_explicit):
        return reject("conflicting-or-invalid-detail-publication-date")
    normalized_explicit = {
        normalized
        for state, normalized in classified_explicit
        if state == "valid" and normalized
    }
    if (
        any(state == "epoch-placeholder" for state, _ in classified_explicit)
        and not normalized_explicit
    ):
        return reject("conflicting-or-invalid-detail-publication-date")
    if len(normalized_explicit) > 1:
        return reject("conflicting-or-invalid-detail-publication-date")
    path_date = _path_date(canonical_url)
    if path_date and not normalize_date(path_date):
        return reject("conflicting-or-invalid-detail-publication-date")
    # A reviewed on-page publication field is stronger than dates mentioned
    # in quarterly results or other prose. It still participated in all the
    # real-date conflict checks above, so this never overrides a conflict.
    published_at = (
        normalize_date(reviewed_dates[0]) if reviewed_dates else
        normalize_date(_published_value(parser, body)) or normalize_date(path_date)
    )
    publication_evidence = ({
        "title": title,
        "publishedAt": published_at,
        "sourceUrl": requested_url,
        "method": "official-detail-field",
        "field": "div.date.clearfix > div > p",
    } if reviewed_dates else None)
    if not published_at:
        publication_evidence = _matched_publication_evidence(title, index_evidence)
        if publication_evidence:
            published_at = publication_evidence["publishedAt"]
    if not published_at:
        return reject("missing-or-invalid-publication-date")
    published_date = date.fromisoformat(published_at)
    if published_date < datetime.now(UTC).date() - timedelta(days=spec.max_age_days):
        return reject("outside-age-window")
    if not summary:
        summary = f"{spec.name} 发布“{title}”；完整事实、数据与附件见官方原文。"
    event_type, importance = infer_event_type(title, summary)
    return {
        "id": article_id(spec.source_id, canonical_url),
        "sourceId": spec.source_id,
        "title": title[:220],
        "summary": summary[:500].rstrip(),
        "type": event_type,
        "region": spec.region if spec.region in {"中国", "美国", "全球"} else "全球",
        "sector": spec.sector,
        "company": spec.name,
        "companySlug": spec.slug,
        "publishedAt": published_at,
        **({"publicationDateEvidence": publication_evidence} if publication_evidence else {}),
        "importance": max(importance, 80),
        "source": _source(spec.name, canonical_url, "官方披露", "官方网站"),
    }


def _unitree_article_from_payload(
    spec: CompanySpec,
    url: str,
    payload: dict[str, Any],
    rejection_counts: dict[str, int] | None = None,
) -> dict[str, Any] | None:
    def reject(reason: str) -> None:
        if rejection_counts is not None:
            rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
        return None

    normalized_url = normalize_url(url)
    match = re.fullmatch(
        r"https://(?:www\.)?unitree\.com/(?:cn/)?news/(\d+)", normalized_url
    )
    if spec.slug != "unitree" or not match:
        return reject("unitree-api-url-mismatch")
    if payload.get("code") != 100:
        return reject("unitree-api-status")
    data = payload.get("data") if isinstance(payload, dict) else None
    article = data.get("article") if isinstance(data, dict) else None
    if not isinstance(article, dict) or str(data.get("id", "")) != match.group(1):
        return reject("unitree-api-id-mismatch")
    title = clean_title(str(article.get("title", "")))
    summary = strip_html(
        str(article.get("description", "") or article.get("content", ""))
    )
    if len(title) < 8:
        return reject("index-or-missing-title")
    if spec.require_entity_match and not any(
        _contains_entity_alias(f"{title} {summary}", alias)
        for alias in spec.entity_aliases
    ):
        return reject("entity-not-in-title-or-summary")
    published_at = normalize_date(article.get("publishTime"))
    if not published_at:
        return reject("missing-or-invalid-publication-date")
    if date.fromisoformat(published_at) < datetime.now(UTC).date() - timedelta(days=spec.max_age_days):
        return reject("outside-age-window")
    if not summary:
        summary = f"{spec.name} 发布“{title}”；完整事实、数据与附件见官方原文。"
    event_type, importance = infer_event_type(title, summary)
    api_url = f"https://api.unitree.com/website/news/info?id={match.group(1)}"
    return {
        "id": article_id(spec.source_id, normalized_url),
        "sourceId": spec.source_id,
        "title": title[:220],
        "summary": summary[:500].rstrip(),
        "type": event_type,
        "region": spec.region if spec.region in {"中国", "美国", "全球"} else "全球",
        "sector": spec.sector,
        "company": spec.name,
        "companySlug": spec.slug,
        "publishedAt": published_at,
        "publicationDateEvidence": {
            "title": title,
            "publishedAt": published_at,
            "sourceUrl": api_url,
            "method": "official-api",
        },
        "importance": max(importance, 80),
        "source": _source(spec.name, normalized_url, "官方披露", "官方网站"),
    }


def _fetch_unitree_article(
    spec: CompanySpec,
    url: str,
    user_agent: str,
    rejection_counts: dict[str, int] | None = None,
) -> dict[str, Any] | None:
    normalized_url = normalize_url(url)
    match = re.fullmatch(
        r"https://(?:www\.)?unitree\.com/(?:cn/)?news/(\d+)", normalized_url
    )
    if spec.slug != "unitree" or not match:
        return None
    api_url = f"https://api.unitree.com/website/news/info?id={match.group(1)}"
    request = Request(
        api_url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Origin": "https://www.unitree.com",
            "Referer": "https://www.unitree.com/",
        },
    )
    with urlopen(request, timeout=spec.request_timeout) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    return _unitree_article_from_payload(spec, normalized_url, payload, rejection_counts)


def _candidate_urls_from_feed(
    feed_url: str,
    body: str,
    allowed_hosts: Sequence[str],
    limit: int,
) -> list[str]:
    candidates: list[str] = []
    try:
        for url in FeedLinkParser.links(body):
            absolute = normalize_url(urljoin(feed_url, url))
            if _host_allowed(absolute, allowed_hosts) and absolute not in candidates:
                candidates.append(absolute)
            if len(candidates) >= limit:
                break
    except ET.ParseError:
        return []
    return candidates


def _default_sitemap_urls(spec: CompanySpec) -> list[str]:
    if spec.sitemap_urls:
        return list(spec.sitemap_urls)
    parts = urlsplit(spec.homepage)
    return [f"{parts.scheme}://{parts.netloc}/sitemap.xml"]


def _sitemap_locations(body: str) -> list[str]:
    root = ET.fromstring(body)
    return [
        clean_text(node.text or "")
        for node in root.iter()
        if node.tag.rsplit("}", 1)[-1].lower() == "loc"
        and clean_text(node.text or "")
    ]


def _discover_sitemap_urls(
    spec: CompanySpec, user_agent: str
) -> tuple[list[str], int, int]:
    queue = _default_sitemap_urls(spec)
    visited: set[str] = set()
    scored: dict[str, int] = {}
    scanned = 0
    failures = 0
    while queue and scanned < 4:
        sitemap_url = normalize_url(queue.pop(0))
        if sitemap_url in visited or not _host_allowed(
            sitemap_url, spec.allowed_hosts
        ):
            continue
        visited.add(sitemap_url)
        try:
            body = fetch_text(
                sitemap_url,
                user_agent,
                timeout=min(spec.request_timeout, 8),
                attempts=1,
            )
            scanned += 1
            for location in _sitemap_locations(body):
                normalized = normalize_url(location)
                if not _host_allowed(normalized, spec.allowed_hosts):
                    continue
                if urlsplit(normalized).path.casefold().endswith(".xml"):
                    if normalized not in visited and normalized not in queue:
                        queue.append(normalized)
                    continue
                score = _candidate_score(
                    normalized, "", spec.article_url_patterns
                )
                if score >= 4:
                    scored[normalized] = max(score, scored.get(normalized, -100))
        except (ET.ParseError, OSError, TimeoutError, ValueError):
            failures += 1
        except Exception:
            failures += 1
    discovered = sorted(
        scored,
        key=lambda candidate: scored[candidate],
        reverse=True,
    )[: spec.max_candidate_links]
    return discovered, scanned, failures


def _search_official_urls(
    spec: CompanySpec, user_agent: str
) -> list[str]:
    discovered: list[str] = []
    for host in spec.allowed_hosts[:2]:
        query = (
            f'site:{host} "{spec.name}" '
            "(news OR newsroom OR blog OR update OR press OR 新闻 OR 动态 OR 公告)"
        )
        search_url = f"https://www.bing.com/search?format=rss&q={quote_plus(query)}"
        try:
            body = fetch_text(
                search_url,
                user_agent,
                timeout=min(spec.request_timeout, 8),
                attempts=1,
            )
            for url in FeedLinkParser.links(body):
                normalized = normalize_url(url)
                if (
                    _host_allowed(normalized, spec.allowed_hosts)
                    and normalized not in discovered
                    and _candidate_score(
                        normalized, "news", spec.article_url_patterns
                    )
                    >= 4
                ):
                    discovered.append(normalized)
                if len(discovered) >= spec.max_candidate_links:
                    return discovered
        except Exception:
            continue
    return discovered


def crawl_company(
    spec: CompanySpec, user_agent: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.monotonic()
    index_urls = list(spec.news_urls) or [spec.homepage]
    if spec.homepage not in index_urls:
        index_urls.append(spec.homepage)
    candidate_urls: list[str] = []
    feed_urls: list[str] = []
    failures = 0
    rejection_counts: dict[str, int] = {}
    failure_samples: list[dict[str, Any]] = []
    successful_indexes: list[str] = []
    index_evidence: dict[str, list[dict[str, str]]] = {}

    def remember_index(url: str, body: str) -> None:
        for candidate, rows in _index_publication_evidence(url, body, spec).items():
            index_evidence.setdefault(candidate, []).extend(rows)
            if candidate not in candidate_urls:
                candidate_urls.append(candidate)

    def record_failure(stage: str, url: str, exc: Exception) -> None:
        if len(failure_samples) >= 12:
            return
        parts = urlsplit(url)
        sample: dict[str, Any] = {
            "stage": stage,
            "url": f"{parts.scheme}://{parts.netloc}{parts.path}",
            "errorType": type(exc).__name__,
        }
        if isinstance(getattr(exc, "code", None), int):
            sample["httpStatus"] = exc.code
        failure_samples.append(sample)

    scanned_indexes = 0
    scanned_sitemaps = 0
    for index_url in index_urls:
        try:
            body = fetch_text(
                index_url,
                user_agent,
                timeout=spec.request_timeout,
                attempts=2,
            )
            scanned_indexes += 1
            successful_indexes.append(index_url)
            remember_index(index_url, body)
            # A configured RSS endpoint is itself a feed, not a webpage that
            # must first expose a rel=alternate link. Still fetch each detail.
            for candidate in _candidate_urls_from_feed(index_url, body, spec.allowed_hosts, spec.max_candidate_links):
                if _candidate_score(candidate, "news", spec.article_url_patterns) >= 4 and candidate not in candidate_urls:
                    candidate_urls.append(candidate)
            candidates, feeds = discover_candidate_urls(
                index_url,
                body,
                spec.allowed_hosts,
                spec.max_candidate_links,
                spec.article_url_patterns,
            )
            for candidate in candidates:
                if candidate not in candidate_urls:
                    candidate_urls.append(candidate)
            for feed in feeds:
                if feed not in feed_urls:
                    feed_urls.append(feed)
        except Exception as exc:
            failures += 1
            record_failure("index", index_url, exc)

    for feed_url in feed_urls[:3]:
        try:
            body = fetch_text(
                feed_url,
                user_agent,
                timeout=spec.request_timeout,
                attempts=2,
            )
            remember_index(feed_url, body)
            for candidate in _candidate_urls_from_feed(
                feed_url,
                body,
                spec.allowed_hosts,
                spec.max_candidate_links,
            ):
                if candidate not in candidate_urls:
                    candidate_urls.append(candidate)
        except Exception as exc:
            failures += 1
            record_failure("feed", feed_url, exc)

    articles: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    attempted_urls: set[str] = set()

    def parse_candidates(candidates: Sequence[str], budget: int) -> None:
        nonlocal failures
        for candidate in candidates:
            if (
                candidate in attempted_urls
                or len(attempted_urls) >= budget
                or len(articles) >= spec.max_items
            ):
                continue
            attempted_urls.add(candidate)
            try:
                article = _fetch_unitree_article(
                    spec, candidate, user_agent, rejection_counts
                )
                if article is None:
                    body = fetch_text(
                        candidate,
                        user_agent,
                        timeout=spec.request_timeout,
                        attempts=2,
                    )
                    article = _article_from_page(
                        spec,
                        candidate,
                        body,
                        rejection_counts,
                        index_evidence.get(candidate, ()),
                    )
                if article and article["source"]["url"] not in seen_urls:
                    articles.append(article)
                    seen_urls.add(article["source"]["url"])
            except Exception as exc:
                failures += 1
                record_failure("article", candidate, exc)

    parse_candidates(candidate_urls, spec.max_candidate_links)

    if len(articles) < spec.max_items:
        sitemap_candidates, scanned_sitemaps, sitemap_failures = (
            _discover_sitemap_urls(spec, user_agent)
        )
        failures += sitemap_failures
        for candidate in sitemap_candidates:
            if candidate not in candidate_urls:
                candidate_urls.append(candidate)
        search_candidates = _search_official_urls(spec, user_agent)
        for candidate in search_candidates:
            if candidate not in candidate_urls:
                candidate_urls.append(candidate)
        fallback_budget = spec.max_candidate_links + max(
            4, spec.max_candidate_links // 2
        )
        parse_candidates(candidate_urls, fallback_budget)

    articles.sort(
        key=lambda item: (
            item.get("publishedAt", ""),
            int(item.get("importance", 0)),
            item.get("id", ""),
        ),
        reverse=True,
    )
    articles = articles[: spec.max_items]
    status = "ok" if articles and failures == 0 else "partial" if articles else "empty"
    if not articles and failures and not scanned_indexes and not scanned_sitemaps:
        status = "error"
    elapsed = time.monotonic() - started
    print(
        f"official={spec.slug} status={status} accepted={len(articles)} "
        f"candidates={len(candidate_urls)} indexes={scanned_indexes} "
        f"sitemaps={scanned_sitemaps} "
        f"failures={failures} seconds={elapsed:.2f}",
        file=sys.stderr,
    )
    result: dict[str, Any] = {
        "id": spec.source_id,
        "name": f"{spec.name} 官方动态",
        "company": spec.name,
        "companySlug": spec.slug,
        "coverage": "attempted",
        "status": status,
        "configuredIndexes": len(index_urls),
        "discovered": len(candidate_urls),
        "scanned": len(attempted_urls) + scanned_indexes + scanned_sitemaps,
        "accepted": len(articles),
        "failed": failures,
        "platform": "官方网站",
        "successfulIndexes": successful_indexes,
        "rejectedByReason": rejection_counts,
        "failureSamples": failure_samples,
        "acceptedArticleUrls": [article["source"]["url"] for article in articles],
    }
    if not articles and failures:
        result["error"] = "official indexes returned no dated article pages"
    return articles, result


def crawl_all_companies(
    specs: Sequence[CompanySpec], user_agent: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    articles: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    if not specs:
        raise ValueError("official company registry is empty")
    with ThreadPoolExecutor(max_workers=min(8, len(specs))) as executor:
        future_map = {
            executor.submit(crawl_company, spec, user_agent): spec for spec in specs
        }
        for future in as_completed(future_map):
            spec = future_map[future]
            try:
                incoming, status = future.result()
                articles.extend(incoming)
                statuses.append(status)
            except Exception as exc:
                statuses.append(
                    {
                        "id": spec.source_id,
                        "name": f"{spec.name} 官方动态",
                        "company": spec.name,
                        "companySlug": spec.slug,
                        "coverage": "attempted",
                        "status": "error",
                        "scanned": 0,
                        "accepted": 0,
                        "failed": 1,
                        "platform": "官方网站",
                        "error": f"{type(exc).__name__}: {exc}"[:240],
                    }
                )
                print(
                    f"official={spec.slug} fatal={type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
    if len(statuses) != len(specs):
        raise RuntimeError(
            f"attempted {len(statuses)} of {len(specs)} official companies"
        )
    return articles, sorted(statuses, key=lambda item: item["id"])


def replace_official_source_batches(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Replace every completed official batch, including a verified empty one.

    Retaining an old batch after a clean empty scan kept previously accepted
    index pages alive indefinitely. Only a fatal per-company error preserves
    the prior batch; completed ok/partial/empty scans are authoritative.
    """

    replace_ids = {
        str(status.get("id", ""))
        for status in statuses
        if status.get("status") in {"ok", "partial"}
        or (
            status.get("status") == "empty"
            and int(status.get("failed", 0)) == 0
        )
    }
    preserved = [
        article
        for article in existing
        if article.get("curated")
        or str(article.get("sourceId", "")) not in replace_ids
    ]
    return merge_articles(preserved, incoming)


def listed_source_receipt(
    statuses: Sequence[dict[str, Any]], approved_slugs: set[str], *,
    generated_at: str, snapshot_published: bool,
) -> dict[str, Any]:
    """A collection receipt, not evidence that all official filings are covered."""
    observed = sorted(
        [row for row in statuses if row.get("companySlug") in approved_slugs],
        key=lambda row: str(row.get("companySlug", "")),
    )
    return {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "scope": "owner-approved-listed-p1",
        "receiptType": "targeted-collection-receipt",
        "approvedCompanyCount": len(approved_slugs),
        "attemptedCompanyCount": len(observed),
        "companiesWithNewArticles": sum(int(row.get("accepted", 0)) > 0 for row in observed),
        "snapshotPublished": snapshot_published,
        "note": "官方新闻采集实测；不等同于完整监管披露覆盖。空结果、失败和原始发布日期分别保留。",
        "sources": observed,
    }


def all_sources_failed(statuses: Sequence[dict[str, Any]]) -> bool:
    return bool(statuses) and all(
        row.get("status") == "error"
        or (int(row.get("accepted", 0)) == 0 and int(row.get("failed", 0)) > 0 and int(row.get("scanned", 0)) == 0)
        for row in statuses
    )


def main(argv: Sequence[str] = ()) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved-listed", action="store_true", help="Collect only the owner-approved P1 companies, without creating private follows.")
    args = parser.parse_args(argv)
    specs = load_registry()
    approved = json.loads(LISTED_INNOVATION_PATH.read_text(encoding="utf-8"))
    approved_slugs = {str(row["companySlug"]) for row in approved["companies"]}
    if args.approved_listed:
        specs = [spec for spec in specs if spec.slug in approved_slugs]
        if {spec.slug for spec in specs} != approved_slugs:
            raise ValueError("approved listed companies do not have complete official-source configuration")
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip() or DEFAULT_USER_AGENT
    payload = load_existing_payload()
    incoming, statuses = crawl_all_companies(specs, user_agent)
    completed_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    for status in statuses:
        status["lastAttemptAt"] = completed_at
    merged = replace_official_source_batches(
        payload.get("articles", []), incoming, statuses
    )
    source_status = merge_source_status(payload.get("sourceStatus", []), statuses)
    quality = evaluate_quality(merged, source_status, load_config().get("qualityGate", {}))
    receipt = listed_source_receipt(statuses, approved_slugs,
        generated_at=completed_at,
        snapshot_published=False)
    # Normal scheduled refreshes publish the existing sourceStatus ledger only.
    # A one-off receipt is emitted solely for an explicit targeted acceptance run.
    if args.approved_listed:
        LISTED_SOURCE_HEALTH_PATH.parent.mkdir(parents=True, exist_ok=True)
        LISTED_SOURCE_HEALTH_PATH.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if all_sources_failed(statuses):
        print("All official sources failed; retained the last-good article snapshot. See the failed collection receipt.", file=sys.stderr)
        return 1
    result = {
        "registeredCompanies": len(specs),
        "attemptedCompanies": len(statuses),
        "companiesWithArticles": sum(status.get("accepted", 0) > 0 for status in statuses),
        "companiesWithoutArticles": sum(
            status.get("accepted", 0) == 0 for status in statuses
        ),
        "incoming": len(incoming),
        "total": len(merged),
        "qualityPassed": quality["passed"],
    }
    if not quality["passed"]:
        print("Official-company quality gate failed; previous snapshot retained.", file=sys.stderr)
        print(json.dumps({"result": result, "qualityGate": quality}, ensure_ascii=False))
        return 1
    write_if_changed(
        merged,
        payload,
        company_facts=payload.get("companyFacts", {}),
        source_status=source_status,
        quality_gate=quality,
    )
    if args.approved_listed:
        receipt["snapshotPublished"] = True
        LISTED_SOURCE_HEALTH_PATH.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    existing_official = any(
        str(item.get("sourceId", "")).startswith("official-")
        for item in payload.get("articles", [])
    )
    if not incoming and not existing_official:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
