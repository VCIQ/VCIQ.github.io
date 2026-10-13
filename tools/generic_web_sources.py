#!/usr/bin/env python3
"""Language-aware, multi-strategy crawler for user-added public websites."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Any, Iterable, Sequence
from urllib.parse import quote_plus, urljoin, urlsplit

try:
    from .article_body_summary import article_body_summary
except ImportError:
    from article_body_summary import article_body_summary

LANGUAGES = {"zh-Hans", "zh-Hant", "en", "multi"}
PUBLIC_SUFFIXES = {
    "com.cn",
    "com.hk",
    "com.tw",
    "co.uk",
    "co.jp",
    "com.au",
    "com.sg",
}
SOCIAL_ROOTS = {
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "bilibili.com": "bilibili",
    "x.com": "x",
    "twitter.com": "x",
}
BAD_PATHS = (
    "/login",
    "/signin",
    "/signup",
    "/account",
    "/settings",
    "/privacy",
    "/terms",
    "/about",
    "/contact",
    "/help",
    "/search",
    "/alerts",
    "/preferences",
    "/playlist",
)
ARTICLE_PATHS = (
    "/news/",
    "/article/",
    "/story/",
    "/post/",
    "/blog/",
    "/press/",
    "/release/",
    "/finance/",
    "/tech/",
    "/business/",
    "/watch",
    "/shorts/",
    "/video/",
    "/live/",
)
EVENT_TERMS = {
    "zh-Hans": (
        "融资",
        "投资",
        "上市",
        "发布",
        "突破",
        "研究",
        "财报",
        "公告",
        "监管",
        "并购",
        "合作",
    ),
    "zh-Hant": (
        "融資",
        "投資",
        "上市",
        "發布",
        "突破",
        "研究",
        "財報",
        "公告",
        "監管",
        "併購",
        "合作",
    ),
    "en": (
        "funding",
        "investment",
        "IPO",
        "launch",
        "breakthrough",
        "research",
        "earnings",
        "filing",
        "regulation",
        "acquisition",
        "partnership",
    ),
    "multi": (
        "融资",
        "融資",
        "funding",
        "发布",
        "發布",
        "launch",
        "研究",
        "research",
        "财报",
        "財報",
        "earnings",
    ),
}

# Deterministic domain glossary. Unknown proper nouns/acronyms are retained.
GLOSSARY: dict[str, dict[str, tuple[str, ...]]] = {
    "ai / agi": {
        "en": ("artificial intelligence", "AI", "AGI"),
        "zh-Hant": ("人工智慧", "通用人工智慧", "AI", "AGI"),
    },
    "人工智能": {"en": ("artificial intelligence", "AI"), "zh-Hant": ("人工智慧", "AI")},
    "基础模型": {"en": ("foundation model",), "zh-Hant": ("基礎模型",)},
    "大模型": {"en": ("large language model", "foundation model"), "zh-Hant": ("大型模型",)},
    "推理模型": {"en": ("reasoning model",), "zh-Hant": ("推理模型",)},
    "多模态": {"en": ("multimodal",), "zh-Hant": ("多模態",)},
    "具身智能": {"en": ("embodied AI",), "zh-Hant": ("具身智慧",)},
    "人形机器人": {"en": ("humanoid robot",), "zh-Hant": ("人形機器人",)},
    "自动驾驶": {"en": ("autonomous driving", "self-driving"), "zh-Hant": ("自動駕駛",)},
    "机器人量产": {"en": ("robot mass production",), "zh-Hant": ("機器人量產",)},
    "机器人": {"en": ("robotics", "robot"), "zh-Hant": ("機器人",)},
    "半导体": {"en": ("semiconductor",), "zh-Hant": ("半導體",)},
    "ai 芯片": {"en": ("AI chip", "AI accelerator"), "zh-Hant": ("AI 晶片",)},
    "推理芯片": {"en": ("inference chip",), "zh-Hant": ("推理晶片",)},
    "先进封装": {"en": ("advanced packaging",), "zh-Hant": ("先進封裝",)},
    "国产算力": {"en": ("domestic AI compute",), "zh-Hant": ("國產算力",)},
    "新能源": {"en": ("clean energy", "new energy"), "zh-Hant": ("新能源",)},
    "长时储能": {"en": ("long-duration energy storage",), "zh-Hant": ("長時儲能",)},
    "固态电池": {"en": ("solid-state battery",), "zh-Hant": ("固態電池",)},
    "聚变能源": {"en": ("fusion energy",), "zh-Hant": ("核融合能源",)},
    "动力电池": {"en": ("EV battery",), "zh-Hant": ("動力電池",)},
    "储能系统": {"en": ("energy storage system",), "zh-Hant": ("儲能系統",)},
    "生物科技": {"en": ("biotechnology", "biotech"), "zh-Hant": ("生物科技",)},
    "ai 制药": {"en": ("AI drug discovery",), "zh-Hant": ("AI 製藥",)},
    "基因组学": {"en": ("genomics",), "zh-Hant": ("基因組學",)},
    "计算生物学": {"en": ("computational biology",), "zh-Hant": ("計算生物學",)},
    "药物发现": {"en": ("drug discovery",), "zh-Hant": ("藥物發現",)},
    "自动化实验": {"en": ("laboratory automation",), "zh-Hant": ("自動化實驗",)},
    "量子计算": {"en": ("quantum computing",), "zh-Hant": ("量子計算",)},
    "量子纠错": {"en": ("quantum error correction",), "zh-Hant": ("量子糾錯",)},
    "逻辑量子比特": {"en": ("logical qubit",), "zh-Hant": ("邏輯量子位元",)},
    "离子阱": {"en": ("trapped ion", "ion trap"), "zh-Hant": ("離子阱",)},
    "超导量子": {"en": ("superconducting qubit",), "zh-Hant": ("超導量子",)},
    "光子量子": {"en": ("photonic quantum",), "zh-Hant": ("光子量子",)},
    "商业航天": {"en": ("commercial space",), "zh-Hant": ("商業航太",)},
    "可复用火箭": {"en": ("reusable rocket",), "zh-Hant": ("可重複使用火箭",)},
    "卫星互联网": {"en": ("satellite internet",), "zh-Hant": ("衛星網際網路",)},
    "商业发射": {"en": ("commercial launch",), "zh-Hant": ("商業發射",)},
    "在轨服务": {"en": ("in-orbit servicing",), "zh-Hant": ("在軌服務",)},
    "商业空间站": {"en": ("commercial space station",), "zh-Hant": ("商業太空站",)},
    "稳定币": {"en": ("stablecoin",), "zh-Hant": ("穩定幣",)},
    "区块链基础设施": {"en": ("blockchain infrastructure",), "zh-Hant": ("區塊鏈基礎設施",)},
    "数字资产": {"en": ("digital assets",), "zh-Hant": ("數位資產",)},
    "链上支付": {"en": ("on-chain payments",), "zh-Hant": ("鏈上支付",)},
    "新材料": {"en": ("advanced materials",), "zh-Hant": ("新材料",)},
    "半导体材料": {"en": ("semiconductor materials",), "zh-Hant": ("半導體材料",)},
    "复合材料": {"en": ("composite materials",), "zh-Hant": ("複合材料",)},
    "电池材料": {"en": ("battery materials",), "zh-Hant": ("電池材料",)},
    "高性能材料": {"en": ("high-performance materials",), "zh-Hant": ("高性能材料",)},
    "材料量产": {"en": ("materials mass production",), "zh-Hant": ("材料量產",)},
    "散热": {"en": ("thermal management",), "zh-Hant": ("散熱",)},
    "智能制造": {"en": ("smart manufacturing",), "zh-Hant": ("智慧製造",)},
    "工业软件": {"en": ("industrial software",), "zh-Hant": ("工業軟體",)},
    "数字工厂": {"en": ("digital factory",), "zh-Hant": ("數位工廠",)},
    "工业自动化": {"en": ("industrial automation",), "zh-Hant": ("工業自動化",)},
    "自主系统": {"en": ("autonomous systems",), "zh-Hant": ("自主系統",)},
    "智能装备": {"en": ("smart equipment",), "zh-Hant": ("智慧裝備",)},
    "可控核聚变": {"en": ("controlled nuclear fusion", "fusion energy"), "zh-Hant": ("可控核融合",)},
    "融资": {"en": ("funding", "financing"), "zh-Hant": ("融資",)},
    "投资": {"en": ("investment",), "zh-Hant": ("投資",)},
    "上市": {"en": ("IPO", "listing"), "zh-Hant": ("上市",)},
    "发布": {"en": ("launch", "release"), "zh-Hant": ("發布",)},
    "突破": {"en": ("breakthrough",), "zh-Hant": ("突破",)},
    "研究": {"en": ("research",), "zh-Hant": ("研究",)},
    "财报": {"en": ("earnings", "financial results"), "zh-Hant": ("財報",)},
    "公告": {"en": ("announcement", "filing"), "zh-Hant": ("公告",)},
    "监管": {"en": ("regulation", "regulatory"), "zh-Hant": ("監管",)},
    "并购": {"en": ("acquisition", "merger"), "zh-Hant": ("併購",)},
    "合作": {"en": ("partnership", "collaboration"), "zh-Hant": ("合作",)},
}
S2T = str.maketrans(
    "础态储长导动驶机产国计药组学验错逻辑离复发卫务间稳币块链设数资电热业软厂统装备变财监管购网际华创术进规",
    "礎態儲長導動駛機產國計藥組學驗錯邏輯離複發衛務間穩幣塊鏈設數資電熱業軟廠統裝備變財監管購網際華創術進規",
)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.links: list[tuple[str, str]] = []
        self.feeds: list[str] = []
        self.paragraphs: list[str] = []
        self._href = ""
        self._anchor: list[str] = []
        self._p_depth = 0
        self._p: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        tag = tag.casefold()
        if tag == "meta":
            key = (values.get("property") or values.get("name") or "").casefold()
            if key and values.get("content"):
                self.meta[key] = values["content"].strip()
        elif tag == "link":
            if (
                "alternate" in values.get("rel", "").casefold()
                and any(
                    token in values.get("type", "").casefold()
                    for token in ("rss", "atom", "xml")
                )
                and values.get("href")
            ):
                self.feeds.append(values["href"])
        elif tag == "a" and values.get("href"):
            self._href, self._anchor = values["href"], []
        elif tag == "p":
            self._p_depth += 1
            if self._p_depth == 1:
                self._p = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._anchor.append(data)
        if self._p_depth:
            self._p.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == "a" and self._href:
            self.links.append((self._href, clean(" ".join(self._anchor), 240)))
            self._href, self._anchor = "", []
        elif tag == "p" and self._p_depth:
            self._p_depth -= 1
            if not self._p_depth:
                value = clean(" ".join(self._p), 800)
                if len(value) >= 40:
                    self.paragraphs.append(value)
                self._p = []


def clean(value: Any, limit: int = 240) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()[:limit]


def unique(values: Iterable[Any], limit: int = 120) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = clean(raw, 120)
        key = value.casefold()
        if value and key not in seen:
            result.append(value)
            seen.add(key)
            if len(result) >= limit:
                break
    return result


def registrable_domain(host: str) -> str:
    labels = host.casefold().split(":", 1)[0].strip(".").split(".")
    if len(labels) <= 2:
        return ".".join(labels)
    return (
        ".".join(labels[-3:])
        if ".".join(labels[-2:]) in PUBLIC_SUFFIXES
        else ".".join(labels[-2:])
    )


def source_kind(url: str) -> str:
    root = registrable_domain(
        (urlsplit(url).hostname or "").removeprefix("www.")
    )
    return SOCIAL_ROOTS.get(root, "website")


def detect_language(url: str, body: str = "", override: str = "") -> str:
    if override in LANGUAGES:
        return override
    host = (urlsplit(url).hostname or "").casefold()
    if (
        host.endswith(".tw")
        or host.startswith(("tw.", "hk."))
        or ".com.tw" in host
        or ".com.hk" in host
    ):
        return "zh-Hant"
    if (
        host.endswith(".cn")
        or host.startswith("cn.")
        or any(
            value in host
            for value in ("eastmoney", "bilibili", "weixin", "zhihu")
        )
    ):
        return "zh-Hans"
    match = re.search(
        r"<html\b[^>]*\blang=[\"']?([^\"'\s>]+)", body, re.IGNORECASE
    )
    lang = (match.group(1) if match else "").casefold()
    if any(value in lang for value in ("zh-tw", "zh-hk", "zh-hant")):
        return "zh-Hant"
    if any(value in lang for value in ("zh-cn", "zh-sg", "zh-hans")):
        return "zh-Hans"
    if lang.startswith("en"):
        return "en"
    sample = clean(re.sub(r"<[^>]+>", " ", body), 12000)
    traditional = sum(
        sample.count(value) for value in "體臺灣發佈資訊產業機器網際融資監管財報"
    )
    simplified = sum(
        sample.count(value) for value in "体台湾发布资讯产业机器网络融资监管财报"
    )
    if traditional >= 3 and traditional > simplified:
        return "zh-Hant"
    if simplified >= 3 and simplified > traditional:
        return "zh-Hans"
    return "en"


def localize_keywords(terms: Sequence[str], language: str) -> list[str]:
    expanded: list[str] = []
    for raw in terms:
        term = clean(raw, 100)
        if not term:
            continue
        expanded.append(term)
        if language == "zh-Hant":
            expanded.append(term.translate(S2T))
            expanded.extend(GLOSSARY.get(term.casefold(), {}).get("zh-Hant", ()))
        elif language == "en":
            expanded.extend(GLOSSARY.get(term.casefold(), {}).get("en", ()))
        elif language == "multi":
            expanded.append(term.translate(S2T))
            expanded.extend(GLOSSARY.get(term.casefold(), {}).get("zh-Hant", ()))
            expanded.extend(GLOSSARY.get(term.casefold(), {}).get("en", ()))
    return unique(expanded, 120)


def _same_site(candidate: str, source: str) -> bool:
    return registrable_domain(
        urlsplit(candidate).hostname or ""
    ) == registrable_domain(urlsplit(source).hostname or "")


def discover_candidates(
    source_url: str, body: str, keywords: Sequence[str], limit: int = 28
) -> list[str]:
    parser = PageParser()
    parser.feed(body)
    kind = source_kind(source_url)
    scored: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for order, (href, label) in enumerate(parser.links):
        url = urljoin(source_url, html.unescape(href)).split("#", 1)[0].rstrip("/")
        path = urlsplit(url).path.casefold()
        if (
            not url.startswith(("http://", "https://"))
            or not _same_site(url, source_url)
            or url in seen
        ):
            continue
        if any(value in path for value in BAD_PATHS):
            continue
        if kind == "youtube" and not any(
            value in path for value in ("/watch", "/shorts/", "/live/")
        ):
            continue
        if kind == "bilibili" and "/video/" not in path:
            continue
        combined = f"{label} {path}".casefold()
        score = 6 if any(value in path for value in ARTICLE_PATHS) else 0
        score += 3 if re.search(r"/20\d{2}(?:/|-)\d{1,2}", path) else 0
        score += 2 if re.search(r"\d{6,}", path) else 0
        score += 2 if 12 <= len(label) <= 220 else 0
        score += 7 * sum(
            1 for term in keywords[:30] if term.casefold() in combined
        )
        if score >= 4:
            scored.append((score, -order, url))
            seen.add(url)
    scored.sort(reverse=True)
    return [url for _, _, url in scored[:limit]]


def discover_feeds(source_url: str, body: str) -> list[str]:
    parser = PageParser()
    parser.feed(body)
    urls = [urljoin(source_url, href) for href in parser.feeds]
    if source_kind(source_url) == "youtube":
        match = re.search(
            r'"channelId"\s*:\s*"(UC[A-Za-z0-9_-]{20,})"', body
        )
        if match:
            urls.append(
                "https://www.youtube.com/feeds/videos.xml?channel_id="
                + match.group(1)
            )
    return unique(urls, 4)


def platform_name(spec: dict[str, Any]) -> str:
    name = clean(spec.get("name"), 80)
    if re.match(r"^https?://", name, re.IGNORECASE):
        name = ""
    host = (
        urlsplit(str(spec.get("sourceUrl") or spec.get("url") or "")).hostname
        or ""
    )
    return name or host.removeprefix("www.") or "用户网站"


def parse_article(
    spec: dict[str, Any],
    url: str,
    body: str,
    crawler: Any,
    keywords: Sequence[str],
) -> dict[str, Any] | None:
    page = PageParser()
    parser = crawler.ArticleHTMLParser()
    page.feed(body)
    parser.feed(body)
    title = crawler.clean_title(
        page.meta.get("og:title")
        or page.meta.get("twitter:title")
        or parser.text("h1")
        or parser.text("title")
    )
    summary = article_body_summary(body, 700)
    published = crawler.normalize_date(crawler._published_value(parser, body))
    if (
        not title
        or not published
        or not crawler._matches_keywords(
            title,
            summary,
            keywords,
            title_only=bool(spec.get("strictTitleKeywords")),
        )
    ):
        return None
    return crawler._external_article(
        spec,
        title=title,
        summary=summary,
        url=crawler.normalize_url(url),
        published_at=published,
        source_name=platform_name(spec),
        source_level=spec.get("sourceLevel", "媒体报道"),
        platform=platform_name(spec),
        company=spec.get("company") or None,
        company_slug=spec.get("companySlug") or None,
    )


def search_feed_url(
    source_url: str, keywords: Sequence[str], language: str
) -> str:
    root = registrable_domain(urlsplit(source_url).hostname or "")
    kind = source_kind(source_url)
    site = (
        "site:youtube.com/watch"
        if kind == "youtube"
        else "site:bilibili.com/video"
        if kind == "bilibili"
        else f"site:{root}"
    )
    terms = unique(
        [*keywords[:14], *EVENT_TERMS.get(language, EVENT_TERMS["multi"])],
        24,
    )
    query = " OR ".join(
        f'"{term.replace(chr(34), "")}"' for term in terms
    )
    if (urlsplit(source_url).hostname or "").casefold() == "news.google.com":
        params = {
            "zh-Hant": "hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
            "zh-Hans": "hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
            "en": "hl=en-US&gl=US&ceid=US:en",
        }.get(language, "hl=en-US&gl=US&ceid=US:en")
        return (
            f"https://news.google.com/rss/search?q={quote_plus(query)}&{params}"
        )
    return (
        "https://www.bing.com/search?format=rss&q="
        + quote_plus(f"{site} ({query})")
    )


def _dedupe(
    items: Sequence[dict[str, Any]], crawler: Any
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        source = (
            item.get("source")
            if isinstance(item.get("source"), dict)
            else {}
        )
        url = crawler.normalize_url(str(source.get("url") or ""))
        if url and url not in seen:
            result.append(item)
            seen.add(url)
    return result


def _crawl_x(
    spec: dict[str, Any], source_url: str, user_agent: str, crawler: Any
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    handle = urlsplit(source_url).path.strip("/").split("/", 1)[0]
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
        return [], crawler._status(
            spec["id"],
            platform_name(spec),
            "error",
            0,
            0,
            failed=1,
            platform="X",
            error="X URL must contain a public profile handle",
        )
    profile = {
        **spec,
        "handle": handle,
        "name": platform_name(spec),
        "kind": (
            "person"
            if spec.get("sourceCategory") == "person"
            else "organization"
        ),
        "url": (
            "https://syndication.twitter.com/srv/timeline-profile/screen-name/"
            + quote_plus(handle)
        ),
    }
    try:
        items = crawler.parse_x_timeline(
            crawler.fetch_text(profile["url"], user_agent), profile
        )
        return items, crawler._status(
            spec["id"],
            platform_name(spec),
            "ok" if items else "empty",
            len(items),
            len(items),
            platform="X",
        )
    except Exception as exc:
        return [], crawler._status(
            spec["id"],
            platform_name(spec),
            "error",
            0,
            0,
            failed=1,
            platform="X",
            error=f"{type(exc).__name__}: {exc}",
        )


def crawl_generic_source(
    spec: dict[str, Any], user_agent: str, crawler: Any
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_url = str(spec.get("sourceUrl") or spec.get("url") or "").strip()
    if not source_url.startswith(("http://", "https://")):
        raise ValueError("generic website source requires an http(s) URL")
    if source_kind(source_url) == "x":
        return _crawl_x(spec, source_url, user_agent, crawler)
    if (
        (urlsplit(source_url).hostname or "").casefold().endswith("google.com")
        and urlsplit(source_url).path.rstrip("/") == "/alerts"
    ):
        return [], crawler._status(
            spec["id"],
            platform_name(spec),
            "error",
            0,
            0,
            failed=1,
            platform=platform_name(spec),
            error=(
                "Google Alerts settings page is not a public content feed; "
                "use a public RSS URL"
            ),
        )

    max_items = int(spec.get("maxItems", 10))
    errors: list[str] = []
    scanned = 0
    body = ""
    try:
        body = crawler.fetch_text(source_url, user_agent)
        scanned += 1
    except Exception as exc:
        errors.append(f"index {type(exc).__name__}: {exc}")
    language = detect_language(
        source_url, body, str(spec.get("sourceLanguage") or "")
    )
    keywords = localize_keywords(spec.get("keywords", []), language)
    runtime_spec = {
        **spec,
        "keywords": keywords,
        "sourceUrl": source_url,
        "platform": platform_name(spec),
    }
    items: list[dict[str, Any]] = []

    if body:
        for feed in discover_feeds(source_url, body):
            try:
                feed_spec = {
                    **runtime_spec,
                    "url": feed,
                    "allowedHosts": [
                        registrable_domain(urlsplit(source_url).hostname or "")
                    ],
                }
                items.extend(
                    crawler.parse_feed_items(
                        crawler.fetch_text(feed, user_agent, attempts=1),
                        feed_spec,
                    )
                )
                scanned += 1
            except Exception as exc:
                errors.append(f"feed {type(exc).__name__}: {exc}")
        for candidate in discover_candidates(source_url, body, keywords):
            if len(items) >= max_items:
                break
            try:
                article = parse_article(
                    runtime_spec,
                    candidate,
                    crawler.fetch_text(candidate, user_agent, attempts=1),
                    crawler,
                    keywords,
                )
                scanned += 1
                if article:
                    items.append(article)
            except Exception as exc:
                errors.append(f"article {type(exc).__name__}: {exc}")

    items = _dedupe(items, crawler)
    if len(items) < max_items:
        try:
            fallback = search_feed_url(source_url, keywords, language)
            fallback_spec = {
                **runtime_spec,
                "url": fallback,
                "allowedHosts": [
                    registrable_domain(urlsplit(source_url).hostname or "")
                ],
                "strictTitleKeywords": False,
            }
            items.extend(
                crawler.parse_feed_items(
                    crawler.fetch_text(fallback, user_agent), fallback_spec
                )
            )
            scanned += 1
        except Exception as exc:
            errors.append(f"search {type(exc).__name__}: {exc}")

    items = _dedupe(items, crawler)[:max_items]
    status = (
        "ok"
        if items and not errors
        else "partial"
        if items
        else "error"
        if errors
        else "empty"
    )
    return items, crawler._status(
        spec["id"],
        platform_name(spec),
        status,
        scanned,
        len(items),
        failed=len(errors),
        platform=platform_name(spec),
        error="; ".join(errors[:3]) if errors and not items else None,
    )
