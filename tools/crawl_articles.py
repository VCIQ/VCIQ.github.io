"""Build the public intelligence snapshot from traceable public sources.

The job intentionally uses only Python's standard library so it can run in
GitHub Actions without a paid API, database, server, or package-install step.
It stores metadata and short factual summaries, never full copyrighted text.

Output:
    public/data/articles.json

Source families:
    * official company newsrooms and investor-relations pages
    * SEC EDGAR submissions and Company Facts
    * configured RSS/Atom feeds and Sina's public finance roll
    * X's public profile syndication pages
    * OpenAlex and arXiv
    * public search indexes with strict destination-host allowlists
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from .article_observation import (
        apply_incoming_observations,
        prepare_existing_articles,
        validate_observation_metadata,
    )
    from .article_publication_gate import financing_event_supported
except ImportError:
    from article_observation import (
        apply_incoming_observations,
        prepare_existing_articles,
        validate_observation_metadata,
    )
    from article_publication_gate import financing_event_supported
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote_plus, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "public" / "data" / "articles.json"
LEGACY_PATH = ROOT / "data" / "public" / "dashboard.json"
CONFIG_PATH = ROOT / "config" / "intelligence_sources.json"
MAX_ARTICLES = 1200
MAX_NEWS_PER_SOURCE = 10
MAX_FILINGS_PER_COMPANY = 6
REQUEST_TIMEOUT = 18
REQUEST_ATTEMPTS = 3
PUBLICATION_TIMEZONE = ZoneInfo("Asia/Taipei")
TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "source",
    "spm",
}
DEFAULT_USER_AGENT = (
    "LizeRoadOne/3.0 contact=VCIQ@users.noreply.github.com "
    "(+https://github.com/VCIQ/VCIQ.github.io)"
)
VALID_EVENT_TYPES = {
    "融资",
    "产业投资",
    "产品发布",
    "技术突破",
    "商业进展",
    "公司动态",
    "并购",
    "财报",
    "政策",
    "监管文件",
    "IPO",
    "论文",
    "人物观点",
}
VALID_REGIONS = {"中国", "美国", "全球"}
VALID_SOURCE_LEVELS = {
    "官方披露",
    "原始材料",
    "监管文件",
    "媒体报道",
    "数据库记录",
    "待交叉验证",
}


@dataclass(frozen=True)
class NewsSource:
    id: str
    name: str
    index_url: str
    company: str
    company_slug: str
    region: str
    sector: str
    path_prefixes: tuple[str, ...]


NEWS_SOURCES = (
    NewsSource(
        "openai",
        "OpenAI",
        "https://openai.com/news/",
        "OpenAI",
        "openai",
        "美国",
        "AI / AGI",
        ("/index/",),
    ),
    NewsSource(
        "anthropic",
        "Anthropic",
        "https://www.anthropic.com/news",
        "Anthropic",
        "anthropic",
        "美国",
        "AI / AGI",
        ("/news/",),
    ),
    NewsSource(
        "figure",
        "Figure AI",
        "https://www.figure.ai/news",
        "Figure AI",
        "figure-ai",
        "美国",
        "机器人",
        ("/news/",),
    ),
    NewsSource(
        "xai",
        "xAI",
        "https://x.ai/news",
        "xAI",
        "xai",
        "美国",
        "AI / AGI",
        ("/news/",),
    ),
    NewsSource(
        "pony-ai",
        "Pony.ai Investor Relations",
        "https://ir.pony.ai/news-events/press-releases",
        "小马智行",
        "pony-ai",
        "中国",
        "机器人",
        ("/news-releases/news-release-details/",),
    ),
    NewsSource(
        "weride",
        "WeRide Investor Relations",
        "https://ir.weride.ai/news-events/news-releases/",
        "文远知行",
        "weride",
        "中国",
        "机器人",
        ("/news-releases/news-release-details/",),
    ),
    NewsSource(
        "rocket-lab",
        "Rocket Lab Investor Relations",
        "https://investors.rocketlabcorp.com/news",
        "Rocket Lab",
        "rocket-lab",
        "美国",
        "商业航天",
        ("/news-releases/news-release-details/",),
    ),
    NewsSource(
        "ionq",
        "IonQ",
        "https://ionq.com/news",
        "IonQ",
        "ionq",
        "美国",
        "量子计算",
        ("/news/",),
    ),
    NewsSource(
        "catl",
        "CATL",
        "https://www.catl.com/en/news/",
        "宁德时代",
        "catl",
        "中国",
        "新能源",
        ("/en/news/",),
    ),
)


# CIKs are resolved from SEC's current ticker directory rather than hard-coded.
SEC_TRACKED = {
    "PONY": ("小马智行", "pony-ai", "机器人", "中国"),
    "WRD": ("文远知行", "weride", "机器人", "中国"),
    "RGTI": ("Rigetti Computing", "rigetti", "量子计算", "美国"),
    "IONQ": ("IonQ", "ionq", "量子计算", "美国"),
    "RKLB": ("Rocket Lab", "rocket-lab", "商业航天", "美国"),
    "TEM": ("Tempus AI", "tempus-ai", "生物科技", "美国"),
    "RXRX": ("Recursion Pharmaceuticals", "recursion", "生物科技", "美国"),
    "MBLY": ("Mobileye", "mobileye", "半导体", "美国"),
    "AUR": ("Aurora Innovation", "aurora", "机器人", "美国"),
    "JOBY": ("Joby Aviation", "joby", "商业航天", "美国"),
}
SUPPORTED_FORMS = {"10-K", "10-Q", "20-F", "6-K", "8-K", "S-1", "F-1", "424B4"}
FINANCIAL_CONCEPTS = (
    (
        "revenue",
        "营业收入",
        ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
    ),
    ("netIncome", "净利润", ("NetIncomeLoss", "ProfitLoss")),
    ("researchAndDevelopment", "研发投入", ("ResearchAndDevelopmentExpense",)),
    (
        "operatingCashFlow",
        "经营现金流",
        ("NetCashProvidedByUsedInOperatingActivities",),
    ),
)
COMPANY_ALIASES = (
    (("openai", "chatgpt"), ("OpenAI", "openai", "美国")),
    (("anthropic", "claude"), ("Anthropic", "anthropic", "美国")),
    (("deepseek", "深度求索"), ("DeepSeek", "deepseek", "中国")),
    (("kimi", "moonshot", "月之暗面"), ("月之暗面", "moonshot-ai", "中国")),
    (("qwen", "通义千问", "阿里云"), ("阿里云 / Qwen", None, "中国")),
    (("元宝", "hunyuan", "混元"), ("腾讯 / 元宝", None, "中国")),
    (("智谱", "zhipu", "glm"), ("智谱AI", "zhipu-ai", "中国")),
    (("字节", "bytedance", "豆包", "doubao"), ("字节跳动", None, "中国")),
    (("小马智行", "pony.ai", "pony ai"), ("小马智行", "pony-ai", "中国")),
    (("文远知行", "weride"), ("文远知行", "weride", "中国")),
    (("figure ai",), ("Figure AI", "figure-ai", "美国")),
    (("rocket lab",), ("Rocket Lab", "rocket-lab", "美国")),
    (("ionq",), ("IonQ", "ionq", "美国")),
    (("宁德时代", "catl"), ("宁德时代", "catl", "中国")),
)


class ArticleHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.links: list[str] = []
        self.time_values: list[str] = []
        self._capture: str | None = None
        self._current: list[str] = []
        self._texts: dict[str, list[str]] = {
            "h1": [],
            "h2": [],
            "h3": [],
            "time": [],
            "title": [],
        }

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            content = values.get("content", "").strip()
            if key and content:
                self.meta[key] = content
        elif tag == "a" and values.get("href"):
            self.links.append(values["href"])
        elif tag == "time":
            if values.get("datetime"):
                self.time_values.append(values["datetime"])
            self._capture = tag
            self._current = []
        elif tag in self._texts:
            self._capture = tag
            self._current = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == self._capture:
            text = clean_text(" ".join(self._current))
            if text:
                self._texts[self._capture].append(text)
            self._capture = None
            self._current = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._current.append(data)

    def text(self, tag: str) -> str:
        values = self._texts.get(tag, [])
        return values[0] if values else ""

    def texts(self, tag: str) -> tuple[str, ...]:
        return tuple(self._texts.get(tag, []))


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def strip_html(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value or "")
    return clean_text(re.sub(r"(?s)<[^>]+>", " ", value))


def clean_title(value: str) -> str:
    title = strip_html(value)
    title = re.sub(
        r"\s*(?:\||—|-)\s*(?:OpenAI|Anthropic|Figure(?: AI)?|"
        r"Rocket Lab|PR Newswire|VentureBeat|TechCrunch)\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    )
    return clean_text(title)


def normalize_url(url: str) -> str:
    parts = urlsplit(clean_text(url))
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in TRACKING_PARAMETERS
        )
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def article_id(prefix: str, url: str) -> str:
    digest = hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def fetch_text(
    url: str,
    user_agent: str,
    timeout: int = REQUEST_TIMEOUT,
    attempts: int = REQUEST_ATTEMPTS,
) -> str:
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = Request(
            url,
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/json,application/xml,text/xml;q=0.9,*/*;q=0.8",
                "Accept-Encoding": "identity",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode(
                    response.headers.get_content_charset() or "utf-8",
                    errors="replace",
                )
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.5 * (2**attempt))
    assert last_error is not None
    raise last_error


def normalize_date(value: str | int | float | None) -> str | None:
    if value is None or value == "":
        return None
    latest_allowed = datetime.now(PUBLICATION_TIMEZONE).date()
    if isinstance(value, (int, float)) or str(value).isdigit():
        try:
            number = float(value)
            if number > 10_000_000_000:
                number /= 1000
            parsed = datetime.fromtimestamp(number, tz=UTC).date()
            if parsed <= latest_allowed:
                return parsed.isoformat()
            return None
        except (OSError, OverflowError, ValueError):
            return None
    text = clean_text(str(value))
    iso_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if iso_match:
        try:
            parsed = date.fromisoformat(iso_match.group(0))
            if parsed > latest_allowed:
                return None
            return parsed.isoformat()
        except ValueError:
            pass
    localized = re.search(
        r"(?<!\d)(\d{4})\s*(?:年|[/.])\s*(\d{1,2})"
        r"\s*(?:月|[/.])\s*(\d{1,2})\s*日?",
        text,
    )
    if localized:
        try:
            parsed = date(*(int(part) for part in localized.groups()))
            if parsed > latest_allowed:
                return None
            return parsed.isoformat()
        except ValueError:
            pass
    try:
        parsed_dt = parsedate_to_datetime(text)
        if parsed_dt:
            parsed_date = parsed_dt.date()
            if parsed_date <= latest_allowed:
                return parsed_date.isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    named = re.search(
        r"(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+(\d{1,2}),?\s+(\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if named:
        try:
            parsed = datetime.strptime(" ".join(named.groups()), "%B %d %Y").date()
            if parsed <= latest_allowed:
                return parsed.isoformat()
            return None
        except ValueError:
            return None
    return None


def infer_event_type(
    title: str, summary: str = "", *, forced_type: str | None = None
) -> tuple[str, int]:
    if forced_type in VALID_EVENT_TYPES and (
        forced_type != "融资"
        or financing_event_supported(title, summary)
    ):
        return forced_type, 84 if forced_type == "论文" else 81
    text = title.casefold()
    if financing_event_supported(title, summary):
        return "融资", 91
    rules = (
        (
            (
                "series a",
                "series b",
                "series c",
                "series d",
                "series e",
                "series f",
                "seed round",
                "funding round",
                "raises funding",
                "raised funding",
                "raises $",
                "raised $",
                "融资",
                "领投",
            ),
            "融资",
            91,
        ),
        (("acquisition", "acquires", "acquire ", "merger", "并购", "收购"), "并购", 89),
        (
            (
                "initial public offering",
                "files for ipo",
                "ipo filing",
                "招股书",
                "首次公开募股",
                "申请上市",
            ),
            "IPO",
            90,
        ),
        (("financial results", "earnings", "annual report", "财报", "业绩"), "财报", 84),
        (
            (
                "partnership",
                "agreement",
                "deploys",
                "deployment",
                "customer",
                "expands",
                "expansion",
                "commercial service",
                "selected by",
                "selects ",
                "contract",
                "合作",
                "携手",
                "签署",
                "落地",
                "扩展",
                "扩张",
                "商业化",
                "获选",
                "中标",
            ),
            "商业进展",
            84,
        ),
        (
            (
                "launch ",
                "launches",
                "launching",
                "introducing",
                "introduces",
                "unveils",
                "new product",
                "now available",
                "发布",
                "推出",
                "上线",
            ),
            "产品发布",
            82,
        ),
        (
            (
                "regulation",
                "regulatory",
                "policy",
                "government rule",
                "executive order",
                "监管",
                "政策",
                "法规",
                "条例",
                "办法",
            ),
            "政策",
            86,
        ),
        (
            (
                "investment in",
                "invests in",
                "new fund",
                "infrastructure investment",
                "capital expenditure",
                "产业投资",
                "投资",
                "设立基金",
                "战略投资",
            ),
            "产业投资",
            84,
        ),
        (
            (
                "research",
                "breakthrough",
                "benchmark",
                "state of the art",
                " award",
                "奖",
                "技术突破",
                "研究成果",
            ),
            "技术突破",
            85,
        ),
    )
    for keywords, event_type, importance in rules:
        if not any(keyword in text for keyword in keywords):
            continue
        if event_type == "融资" and not financing_event_supported(title, summary):
            continue
        return event_type, importance
    return "公司动态", 76


def _company_alias_in_title(alias: str, folded_title: str) -> bool:
    normalized = clean_text(alias).casefold()
    if not normalized:
        return False
    if re.fullmatch(r"[a-z0-9 .-]+", normalized):
        return bool(
            re.search(
                rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])",
                folded_title,
            )
        )
    return normalized in folded_title


def infer_company(
    title: str, summary: str, fallback: str = "科技产业"
) -> tuple[str, str | None, str | None]:
    """Attribute a media item only when its title identifies one company.

    Feed summaries often mention competitors or add generic context. Using that
    text for ownership caused Claude stories to be assigned to OpenAI and
    unrelated stories to inherit whichever alias appeared first. The summary
    argument remains for call-site compatibility but is intentionally excluded
    from entity attribution.
    """

    del summary
    folded_title = clean_text(title).casefold()
    matches = {
        result
        for aliases, result in COMPANY_ALIASES
        if any(_company_alias_in_title(alias, folded_title) for alias in aliases)
    }
    if len(matches) == 1:
        return next(iter(matches))
    return fallback, None, None


def infer_region(title: str, summary: str, fallback: str = "全球") -> str:
    _, _, company_region = infer_company(title, summary)
    if company_region:
        return company_region
    text = f"{title} {summary}".casefold()
    china = ("中国", "北京", "上海", "深圳", "杭州", "hong kong", "china", "chinese")
    usa = ("美国", "u.s.", "united states", "silicon valley", "washington", "california")
    if any(value in text for value in china):
        return "中国"
    if any(value in text for value in usa):
        return "美国"
    return fallback if fallback in VALID_REGIONS else "全球"


def infer_sector(title: str, summary: str, fallback: str = "AI / AGI") -> str:
    text = f"{title} {summary}".casefold()
    rules = (
        (("robot", "robotaxi", "autonomous driving", "机器人", "自动驾驶"), "机器人"),
        (("chip", "semiconductor", "gpu", "芯片", "半导体"), "半导体"),
        (("battery", "energy", "fusion", "电池", "新能源", "储能"), "新能源"),
        (("biotech", "drug", "genomic", "生物", "药物", "基因"), "生物科技"),
        (("quantum", "量子"), "量子计算"),
        (("space", "rocket", "satellite", "航天", "火箭", "卫星"), "商业航天"),
        (("manufacturing", "industrial", "制造", "工业"), "智能制造"),
        (("material", "材料"), "新材料"),
        # Label must equal the enabled track name; "Web3 / 区块链" entries were
        # filtered out by the exact sector match on the technology channel.
        (("blockchain", "crypto", "web3", "区块链"), "Web3"),
        (("ai", "model", "agent", "人工智能", "大模型", "智能体"), "AI / AGI"),
    )
    for keywords, sector in rules:
        if any(keyword in text for keyword in keywords):
            return sector
    return fallback


def _published_value(parser: ArticleHTMLParser, body: str) -> str | None:
    candidates = (
        parser.meta.get("article:published_time"),
        parser.meta.get("date"),
        parser.meta.get("datepublished"),
        parser.meta.get("publishdate"),
        parser.time_values[0] if parser.time_values else None,
        parser.text("time"),
        parser.text("h3"),
    )
    for candidate in candidates:
        if normalize_date(candidate):
            return candidate
    for pattern in (
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'"dateCreated"\s*:\s*"([^"]+)"',
        r'"publishDate"\s*:\s*"([^"]+)"',
    ):
        for match in re.finditer(pattern, body, flags=re.IGNORECASE):
            if normalize_date(match.group(1)):
                return match.group(1)
    # IR templates sometimes omit publication metadata while including both a
    # future event date in the headline and the actual release date elsewhere.
    # Prefer the latest valid ISO date that is not materially in the future.
    valid_iso_dates = [
        normalized
        for raw in re.findall(r"\d{4}-\d{2}-\d{2}", body)
        if (normalized := normalize_date(raw))
    ]
    if valid_iso_dates:
        return max(valid_iso_dates)
    localized_dates = [
        normalized
        for match in re.finditer(
            r"(?<!\d)\d{4}\s*(?:年|[/.])\s*\d{1,2}"
            r"\s*(?:月|[/.])\s*\d{1,2}\s*日?",
            strip_html(body),
        )
        if (normalized := normalize_date(match.group(0)))
    ]
    if localized_dates:
        return localized_dates[0]
    named_dates = re.findall(
        r"(?:January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+\d{1,2},?\s+\d{4}",
        strip_html(body),
        flags=re.IGNORECASE,
    )
    valid_named_dates = [
        normalized
        for raw in named_dates
        if (normalized := normalize_date(raw))
    ]
    return max(valid_named_dates) if valid_named_dates else None


def _source(
    name: str, url: str, level: str, platform: str
) -> dict[str, str]:
    return {
        "name": clean_text(name),
        "url": normalize_url(url),
        "level": level if level in VALID_SOURCE_LEVELS else "待交叉验证",
        "platform": clean_text(platform),
    }


def parse_news_article(
    source: NewsSource, url: str, body: str
) -> dict[str, Any] | None:
    parser = ArticleHTMLParser()
    parser.feed(body)
    canonical_url = normalize_url(parser.meta.get("og:url", "") or url)
    if canonical_url == normalize_url(source.index_url):
        return None
    candidates = (
        parser.meta.get("og:title", ""),
        parser.text("h1"),
        parser.text("title"),
    )
    raw_title = next((value for value in candidates if clean_title(value)), "")
    title_suffix_date = re.search(r"\|\s*(\d{4}-\d{2}-\d{2})\s*$", raw_title)
    title = clean_title(raw_title)
    title = re.sub(r"\s*\|\s*\d{4}-\d{2}-\d{2}\s*$", "", title)
    for suffix in (source.name, source.company, "WeRide Inc.", "PONY AI Inc."):
        title = re.sub(
            rf"\s*\|\s*{re.escape(suffix)}\s*$",
            "",
            title,
            flags=re.IGNORECASE,
        )
        title = re.sub(
            rf"^{re.escape(suffix)}\s*\|\s*",
            "",
            title,
            flags=re.IGNORECASE,
        )
    title = re.sub(
        r"\s*\|\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s*"
        r"\d{2}/\d{2}/\d{4}\s*-\s*\d{2}:\d{2}\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    )
    title = clean_text(title)
    if (
        not title
        or len(title) < 8
        or title.casefold() in {"news", "newsroom", "updates", source.name.casefold()}
        or "newsroom | product" in title.casefold()
    ):
        return None
    published_at = normalize_date(
        title_suffix_date.group(1) if title_suffix_date else None
    ) or normalize_date(_published_value(parser, body))
    if not published_at:
        return None
    summary = strip_html(
        parser.meta.get("description", "")
        or parser.meta.get("og:description", "")
        or parser.meta.get("twitter:description", "")
    )
    if not summary:
        summary = f"{source.name} 发布“{title}”；完整事实与数据见原文。"
    summary = summary[:500].rstrip()
    event_type, importance = infer_event_type(title, summary)
    return {
        "id": article_id(source.id, canonical_url),
        "sourceId": source.id,
        "title": title[:220],
        "summary": summary,
        "type": event_type,
        "region": source.region,
        "sector": source.sector,
        "company": source.company,
        "companySlug": source.company_slug,
        "publishedAt": published_at,
        "importance": importance,
        "source": _source(source.name, canonical_url, "官方披露", "官方网站"),
    }


def discover_news_urls(source: NewsSource, body: str) -> list[str]:
    parser = ArticleHTMLParser()
    parser.feed(body)
    index_url = normalize_url(source.index_url)
    index_host = urlsplit(index_url).netloc
    discovered: list[str] = []
    for href in parser.links:
        absolute = normalize_url(urljoin(source.index_url, href))
        parts = urlsplit(absolute)
        if parts.netloc != index_host or absolute == index_url:
            continue
        if not any(parts.path.startswith(prefix) for prefix in source.path_prefixes):
            continue
        if absolute not in discovered:
            discovered.append(absolute)
    return discovered[:MAX_NEWS_PER_SOURCE]


def _status(
    source_id: str,
    name: str,
    status: str,
    scanned: int,
    accepted: int,
    *,
    failed: int = 0,
    platform: str = "",
    error: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": source_id,
        "name": name,
        "status": status,
        "scanned": scanned,
        "accepted": accepted,
        "failed": failed,
    }
    if platform:
        result["platform"] = platform
    if error:
        result["error"] = clean_text(error)[:240]
    return result


def crawl_news_source(
    source: NewsSource, user_agent: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.monotonic()
    index_body = fetch_text(source.index_url, user_agent)
    urls = discover_news_urls(source, index_body)
    articles: list[dict[str, Any]] = []
    failures = 0
    for url in urls:
        try:
            parsed = parse_news_article(source, url, fetch_text(url, user_agent))
            if parsed:
                articles.append(parsed)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            failures += 1
    if not articles:
        raise RuntimeError(f"no dated articles parsed from {len(urls)} discovered links")
    elapsed = time.monotonic() - started
    print(
        f"source={source.id} accepted={len(articles)} scanned={len(urls)} "
        f"seconds={elapsed:.2f}",
        file=sys.stderr,
    )
    return articles, _status(
        source.id,
        source.name,
        "ok" if failures == 0 else "partial",
        len(urls),
        len(articles),
        failed=failures,
        platform="官方网站",
    )


def crawl_company_news(
    user_agent: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    articles: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=min(6, len(NEWS_SOURCES))) as executor:
        future_map = {
            executor.submit(crawl_news_source, source, user_agent): source
            for source in NEWS_SOURCES
        }
        for future in as_completed(future_map):
            source = future_map[future]
            try:
                incoming, status = future.result()
                articles.extend(incoming)
                statuses.append(status)
            except Exception as exc:
                message = f"{source.id}: {type(exc).__name__}: {exc}"
                errors.append(message)
                statuses.append(
                    _status(
                        source.id,
                        source.name,
                        "error",
                        0,
                        0,
                        failed=1,
                        platform="官方网站",
                        error=str(exc),
                    )
                )
                print(f"Company source warning: {message}", file=sys.stderr)
    return articles, sorted(statuses, key=lambda item: item["id"]), errors


def sec_article(
    *,
    cik: str,
    company: str,
    company_slug: str,
    sector: str,
    form: str,
    filing_date: str,
    accession_number: str,
    primary_document: str,
    region: str = "美国",
) -> dict[str, Any]:
    accession_path = accession_number.replace("-", "")
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession_path}/{primary_document}"
    )
    importance = {
        "S-1": 94,
        "F-1": 94,
        "424B4": 92,
        "10-K": 87,
        "20-F": 87,
        "10-Q": 82,
        "6-K": 79,
        "8-K": 80,
    }.get(form, 74)
    event_type = (
        "IPO"
        if form in {"S-1", "F-1", "424B4"}
        else "财报"
        if form in {"10-K", "10-Q", "20-F"}
        else "监管文件"
    )
    label = {
        "10-K": "年度报告",
        "20-F": "年度报告",
        "10-Q": "季度报告",
        "6-K": "境外发行人报告",
        "8-K": "重大事项报告",
        "S-1": "上市注册文件",
        "F-1": "境外发行人上市注册文件",
        "424B4": "最终招股文件",
    }.get(form, "监管文件")
    return {
        "id": article_id("sec", url),
        "sourceId": "sec",
        "title": f"{company} 提交 {form}（{label}）",
        "summary": (
            f"SEC EDGAR 于 {filing_date} 收录 {company} 的 {form} 文件。"
            "原始文件包含本次披露的完整正文、附件和财务口径。"
        ),
        "type": event_type,
        "region": region,
        "sector": sector,
        "company": company,
        "companySlug": company_slug,
        "publishedAt": filing_date,
        "importance": importance,
        "source": _source("SEC EDGAR", url, "监管文件", "SEC"),
    }


def _resolve_sec_companies(
    user_agent: str,
) -> dict[str, tuple[str, str, str, str, str]]:
    body = fetch_text("https://www.sec.gov/files/company_tickers.json", user_agent)
    ticker_rows = json.loads(body)
    by_ticker = {
        row["ticker"].upper(): str(row["cik_str"]).zfill(10)
        for row in ticker_rows.values()
    }
    resolved: dict[str, tuple[str, str, str, str, str]] = {}
    for ticker, (company, slug, sector, region) in SEC_TRACKED.items():
        cik = by_ticker.get(ticker)
        if cik:
            resolved[ticker] = (cik, company, slug, sector, region)
    return resolved


def _filing_arrays(recent: dict[str, Any]) -> Iterable[dict[str, str]]:
    for index, form in enumerate(recent.get("form", [])):
        if form not in SUPPORTED_FORMS:
            continue
        try:
            filing_date = normalize_date(recent["filingDate"][index])
            if not filing_date:
                continue
            yield {
                "form": form,
                "filingDate": filing_date,
                "accessionNumber": recent["accessionNumber"][index],
                "primaryDocument": recent["primaryDocument"][index],
            }
        except (IndexError, KeyError):
            continue


def _latest_metric(
    company_facts: dict[str, Any],
    metric_id: str,
    label: str,
    concepts: tuple[str, ...],
) -> dict[str, Any] | None:
    namespace = company_facts.get("facts", {}).get("us-gaap", {})
    candidates: list[dict[str, Any]] = []
    for concept in concepts:
        units = namespace.get(concept, {}).get("units", {})
        for unit in ("USD", "USD/shares"):
            for fact in units.get(unit, []):
                if fact.get("form") not in {"10-K", "10-Q", "20-F", "6-K"}:
                    continue
                if not all(key in fact for key in ("val", "filed", "end")):
                    continue
                candidates.append(
                    {
                        "id": metric_id,
                        "label": label,
                        "value": fact["val"],
                        "unit": unit,
                        "periodEnd": fact["end"],
                        "filedAt": fact["filed"],
                        "form": fact.get("form"),
                        "fiscalYear": fact.get("fy"),
                        "fiscalPeriod": fact.get("fp"),
                        "accessionNumber": fact.get("accn"),
                        "concept": concept,
                    }
                )
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            item.get("filedAt", ""),
            item.get("periodEnd", ""),
            str(item.get("accessionNumber", "")),
        ),
    )


def _company_financials(
    *,
    cik: str,
    ticker: str,
    company: str,
    company_slug: str,
    body: str,
) -> dict[str, Any]:
    company_facts = json.loads(body)
    metrics = [
        metric
        for metric_id, label, concepts in FINANCIAL_CONCEPTS
        if (metric := _latest_metric(company_facts, metric_id, label, concepts))
    ]
    return {
        "company": company,
        "companySlug": company_slug,
        "ticker": ticker,
        "cik": cik,
        "entityName": company_facts.get("entityName") or company,
        "metrics": metrics,
        "source": _source(
            "SEC Company Facts",
            f"https://www.sec.gov/edgar/browse/?CIK={int(cik)}",
            "监管文件",
            "SEC",
        ),
    }


def crawl_sec(
    user_agent: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    company_facts: dict[str, Any] = {}
    resolved = _resolve_sec_companies(user_agent)
    failures = 0
    for ticker, (cik, company, company_slug, sector, region) in resolved.items():
        try:
            submissions = json.loads(
                fetch_text(f"https://data.sec.gov/submissions/CIK{cik}.json", user_agent)
            ).get("filings", {}).get("recent", {})
            filings = list(_filing_arrays(submissions))[:MAX_FILINGS_PER_COMPANY]
            for filing in filings:
                articles.append(
                    sec_article(
                        cik=cik,
                        company=company,
                        company_slug=company_slug,
                        sector=sector,
                        region=region,
                        form=filing["form"],
                        filing_date=filing["filingDate"],
                        accession_number=filing["accessionNumber"],
                        primary_document=filing["primaryDocument"],
                    )
                )
            company_facts[company_slug] = _company_financials(
                cik=cik,
                ticker=ticker,
                company=company,
                company_slug=company_slug,
                body=fetch_text(
                    f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                    user_agent,
                ),
            )
        except Exception as exc:
            failures += 1
            print(f"SEC warning: {ticker} ({type(exc).__name__}: {exc})", file=sys.stderr)
    if not articles:
        raise RuntimeError("SEC returned no supported filings")
    return (
        articles,
        company_facts,
        _status(
            "sec",
            "SEC EDGAR",
            "ok" if failures == 0 else "partial",
            len(resolved),
            len(articles),
            failed=failures,
            platform="SEC",
        ),
    )


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing source configuration: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("source configuration must be a JSON object")
    return payload


def _xml_local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _xml_text(node: ET.Element, names: Sequence[str]) -> str:
    wanted = {name.lower() for name in names}
    for child in node.iter():
        if _xml_local(child.tag) in wanted:
            text = clean_text(" ".join(child.itertext()))
            if text:
                return text
    return ""


def _xml_link(node: ET.Element) -> str:
    for child in node.iter():
        if _xml_local(child.tag) != "link":
            continue
        href = clean_text(child.attrib.get("href", ""))
        relation = child.attrib.get("rel", "alternate")
        if href and relation in {"alternate", ""}:
            return href
        text = clean_text(child.text or "")
        if text:
            return text
    return ""


def _matches_keywords(
    title: str,
    summary: str,
    keywords: Sequence[str],
    *,
    title_only: bool = False,
) -> bool:
    if not keywords:
        return True
    haystack = title if title_only else f"{title} {summary}"
    folded = haystack.casefold()
    return any(_keyword_in_text(keyword, folded) for keyword in keywords)


def _keyword_in_text(keyword: str, folded_haystack: str) -> bool:
    normalized = keyword.casefold().strip()
    if not normalized:
        return False
    if re.fullmatch(r"[a-z0-9 ]+", normalized):
        return bool(
            re.search(
                rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])",
                folded_haystack,
            )
        )
    return normalized in folded_haystack


def _matches_required_keywords(
    title: str,
    summary: str,
    required_keywords: Sequence[str],
    *,
    title_only: bool = False,
) -> bool:
    if not required_keywords:
        return True
    folded = (title if title_only else f"{title} {summary}").casefold()
    return any(_keyword_in_text(keyword, folded) for keyword in required_keywords)


def _external_article(
    spec: dict[str, Any],
    *,
    title: str,
    summary: str,
    url: str,
    published_at: str,
    forced_type: str | None = None,
    source_name: str | None = None,
    source_level: str | None = None,
    platform: str | None = None,
    company: str | None = None,
    company_slug: str | None = None,
    person_slug: str | None = None,
    authors: list[str] | None = None,
) -> dict[str, Any]:
    inferred_company, inferred_slug, inferred_company_region = infer_company(title, summary)
    region = spec.get("region") or inferred_company_region or infer_region(title, summary)
    sector = infer_sector(title, summary, spec.get("sector", "AI / AGI"))
    event_type, importance = infer_event_type(
        title, summary, forced_type=forced_type or spec.get("eventType")
    )
    result: dict[str, Any] = {
        "id": article_id(spec["id"], url),
        "sourceId": spec["id"],
        "title": clean_title(title)[:220],
        "summary": strip_html(summary)[:500].rstrip()
        or f"{source_name or spec['name']} 发布相关公开信息，完整内容见原文。",
        "type": event_type,
        "region": region if region in VALID_REGIONS else "全球",
        "sector": sector,
        "company": company or inferred_company,
        "publishedAt": published_at,
        "importance": int(spec.get("importance", importance)),
        "source": _source(
            source_name or spec["name"],
            url,
            source_level or spec.get("sourceLevel", "媒体报道"),
            platform or spec.get("platform", spec["name"]),
        ),
    }
    slug = company_slug or inferred_slug
    if slug:
        result["companySlug"] = slug
    if person_slug:
        result["personSlug"] = person_slug
    if authors:
        result["authors"] = authors[:12]
    return result


def parse_feed_items(body: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
    root = ET.fromstring(body)
    entries = [
        node
        for node in root.iter()
        if _xml_local(node.tag) in {"item", "entry"}
    ]
    accepted: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in entries:
        title = clean_title(_xml_text(node, ("title",)))
        summary = strip_html(_xml_text(node, ("description", "summary", "content")))
        url = _xml_link(node)
        published_at = normalize_date(
            _xml_text(node, ("pubdate", "published", "updated", "date"))
        )
        if not title or not url or not published_at:
            continue
        normalized = normalize_url(url)
        if normalized in seen:
            continue
        allowed_hosts = tuple(spec.get("allowedHosts", []))
        hostname = (urlsplit(normalized).hostname or "").lower()
        if allowed_hosts and not any(
            hostname == host or hostname.endswith(f".{host}") for host in allowed_hosts
        ):
            continue
        if not _matches_keywords(
            title,
            summary,
            spec.get("keywords", []),
            title_only=bool(spec.get("strictTitleKeywords")),
        ):
            continue
        if not _matches_required_keywords(
            title,
            summary,
            spec.get("requiredKeywords", []),
            title_only=bool(spec.get("strictRequiredTitleKeywords")),
        ):
            continue
        accepted.append(
            _external_article(
                spec,
                title=title,
                summary=summary,
                url=normalized,
                published_at=published_at,
                forced_type=spec.get("eventType"),
            )
        )
        seen.add(normalized)
        if len(accepted) >= int(spec.get("maxItems", 12)):
            break
    return accepted


def parse_sina_items(body: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
    payload = json.loads(body)
    rows = payload.get("result", {}).get("data", payload.get("data", []))
    if isinstance(rows, dict):
        rows = rows.get("data", rows.get("list", []))
    accepted: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        title = clean_title(str(row.get("title") or ""))
        summary = strip_html(str(row.get("intro") or row.get("summary") or ""))
        url = str(row.get("url") or row.get("wapurl") or "")
        published_at = normalize_date(
            row.get("createtime") or row.get("ctime") or row.get("time")
        )
        if not title or not url or not published_at:
            continue
        if not _matches_keywords(
            title,
            summary,
            spec.get("keywords", []),
            title_only=True,
        ):
            continue
        if not _matches_required_keywords(
            title,
            summary,
            spec.get("requiredKeywords", []),
            title_only=bool(spec.get("strictRequiredTitleKeywords")),
        ):
            continue
        accepted.append(
            _external_article(
                spec,
                title=title,
                summary=summary,
                url=url,
                published_at=published_at,
                source_name=spec.get("name", "新浪财经"),
                source_level=spec.get("sourceLevel", "媒体报道"),
                platform=spec.get("platform", "新浪"),
            )
        )
        if len(accepted) >= int(spec.get("maxItems", 15)):
            break
    return accepted


def _crawl_config_source(
    spec: dict[str, Any], user_agent: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.monotonic()
    body = fetch_text(spec["url"], user_agent)
    if spec.get("adapter") == "sina_json":
        articles = parse_sina_items(body, spec)
    else:
        articles = parse_feed_items(body, spec)
    elapsed = time.monotonic() - started
    print(
        f"source={spec['id']} accepted={len(articles)} seconds={elapsed:.2f}",
        file=sys.stderr,
    )
    status_value = "ok" if articles else "empty"
    return articles, _status(
        spec["id"],
        spec["name"],
        status_value,
        len(articles),
        len(articles),
        platform=spec.get("platform", spec["name"]),
    )


def _crawl_config_group(
    specs: Sequence[dict[str, Any]], user_agent: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    articles: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    errors: list[str] = []
    if not specs:
        return articles, statuses, errors
    with ThreadPoolExecutor(max_workers=min(6, len(specs))) as executor:
        future_map = {
            executor.submit(_crawl_config_source, spec, user_agent): spec
            for spec in specs
            if spec.get("enabled", True)
        }
        for future in as_completed(future_map):
            spec = future_map[future]
            try:
                incoming, status = future.result()
                articles.extend(incoming)
                statuses.append(status)
            except Exception as exc:
                message = f"{spec['id']}: {type(exc).__name__}: {exc}"
                errors.append(message)
                statuses.append(
                    _status(
                        spec["id"],
                        spec["name"],
                        "error",
                        0,
                        0,
                        failed=1,
                        platform=spec.get("platform", spec["name"]),
                        error=str(exc),
                    )
                )
                print(f"Source warning: {message}", file=sys.stderr)
    return articles, sorted(statuses, key=lambda item: item["id"]), errors


def parse_x_timeline(body: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    seen: set[str] = set()
    next_data = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if next_data:
        try:
            payload = json.loads(html.unescape(next_data.group(1)))
            entries = (
                payload.get("props", {})
                .get("pageProps", {})
                .get("timeline", {})
                .get("entries", [])
            )
            for entry in entries:
                tweet = entry.get("content", {}).get("tweet", {})
                tweet_id = str(
                    tweet.get("id_str")
                    or tweet.get("conversation_id_str")
                    or ""
                )
                text_value = clean_text(
                    str(tweet.get("full_text") or tweet.get("text") or "")
                )
                visible_text = re.sub(r"https?://\S+", "", text_value).strip()
                published_at = normalize_date(tweet.get("created_at"))
                if (
                    not tweet_id
                    or len(visible_text) < 20
                    or not published_at
                ):
                    continue
                url = normalize_url(
                    f"https://x.com/{spec.get('handle', spec['id'])}/status/{tweet_id}"
                )
                forced_type = "人物观点" if spec.get("kind") == "person" else None
                accepted.append(
                    _external_article(
                        spec,
                        title=f"{spec['name']}：{text_value[:150]}",
                        summary=text_value,
                        url=url,
                        published_at=published_at,
                        forced_type=forced_type,
                        source_name=f"{spec['name']} on X",
                        source_level="原始材料",
                        platform="X",
                        company=spec.get("company") or spec["name"],
                        company_slug=spec.get("companySlug"),
                        person_slug=spec.get("personSlug"),
                    )
                )
                seen.add(url)
                if len(accepted) >= int(spec.get("maxItems", 6)):
                    return accepted
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass
    status_pattern = re.compile(
        r'href=["\'](https?://(?:x|twitter)\.com/[^"\']+/status/\d+[^"\']*)["\']',
        flags=re.IGNORECASE,
    )
    for match in status_pattern.finditer(body):
        url = normalize_url(html.unescape(match.group(1)))
        if url in seen:
            continue
        window = body[max(0, match.start() - 4500) : min(len(body), match.end() + 4500)]
        text_matches = re.findall(
            r'<p[^>]*class=["\'][^"\']*timeline-Tweet-text[^"\']*["\'][^>]*>(.*?)</p>',
            window,
            flags=re.IGNORECASE | re.DOTALL,
        )
        time_matches = re.findall(
            r'<time[^>]*datetime=["\']([^"\']+)["\']', window, flags=re.IGNORECASE
        )
        text_value = strip_html(text_matches[-1] if text_matches else "")
        visible_text = re.sub(r"https?://\S+", "", text_value).strip()
        published_at = next(
            (value for raw in reversed(time_matches) if (value := normalize_date(raw))),
            None,
        )
        if len(visible_text) < 20 or not published_at:
            continue
        name = spec["name"]
        title = f"{name}：{text_value[:150]}"
        forced_type = "人物观点" if spec.get("kind") == "person" else None
        accepted.append(
            _external_article(
                spec,
                title=title,
                summary=text_value,
                url=url,
                published_at=published_at,
                forced_type=forced_type,
                source_name=f"{name} on X",
                source_level="原始材料",
                platform="X",
                company=spec.get("company") or name,
                company_slug=spec.get("companySlug"),
                person_slug=spec.get("personSlug"),
            )
        )
        seen.add(url)
        if len(accepted) >= int(spec.get("maxItems", 6)):
            break
    return accepted


def crawl_x_profile(
    spec: dict[str, Any], user_agent: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    profile_url = spec.get("url") or (
        "https://syndication.twitter.com/srv/timeline-profile/screen-name/"
        f"{quote_plus(spec['handle'])}"
    )
    body = fetch_text(profile_url, user_agent)
    articles = parse_x_timeline(body, spec)
    return articles, _status(
        spec["id"],
        spec["name"],
        "ok" if articles else "empty",
        len(articles),
        len(articles),
        platform="X",
    )


def crawl_x(
    specs: Sequence[dict[str, Any]], user_agent: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    articles: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=min(5, len(specs))) as executor:
        future_map = {
            executor.submit(crawl_x_profile, spec, user_agent): spec
            for spec in specs
            if spec.get("enabled", True)
        }
        for future in as_completed(future_map):
            spec = future_map[future]
            try:
                incoming, status = future.result()
                articles.extend(incoming)
                statuses.append(status)
            except Exception as exc:
                message = f"{spec['id']}: {type(exc).__name__}: {exc}"
                errors.append(message)
                statuses.append(
                    _status(
                        spec["id"],
                        spec["name"],
                        "error",
                        0,
                        0,
                        failed=1,
                        platform="X",
                        error=str(exc),
                    )
                )
                print(f"X source warning: {message}", file=sys.stderr)
    return articles, sorted(statuses, key=lambda item: item["id"]), errors


def parse_openalex(body: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
    payload = json.loads(body)
    accepted: list[dict[str, Any]] = []
    for work in payload.get("results", []):
        title = clean_title(str(work.get("title") or work.get("display_name") or ""))
        published_at = normalize_date(work.get("publication_date"))
        location = work.get("primary_location") or {}
        url = (
            location.get("landing_page_url")
            or work.get("doi")
            or work.get("id")
            or ""
        )
        if not title or not published_at or not url:
            continue
        if not _matches_keywords(
            title,
            "",
            spec.get("keywords", []),
            title_only=True,
        ):
            continue
        authors = [
            item.get("author", {}).get("display_name", "")
            for item in work.get("authorships", [])
            if item.get("author", {}).get("display_name")
        ]
        venue = (location.get("source") or {}).get("display_name") or "OpenAlex"
        summary = (
            f"OpenAlex 收录的人工智能研究成果；作者："
            f"{'、'.join(authors[:5]) or '详见记录'}；发表载体：{venue}。"
        )
        accepted.append(
            _external_article(
                spec,
                title=title,
                summary=summary,
                url=url,
                published_at=published_at,
                forced_type="论文",
                source_name=f"OpenAlex · {venue}",
                source_level="数据库记录",
                platform="OpenAlex",
                company="AI 研究",
                authors=authors,
            )
        )
        if len(accepted) >= int(spec.get("maxItems", 12)):
            break
    return accepted


def crawl_paper_source(
    spec: dict[str, Any], user_agent: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_url = spec["url"].replace(
        "{today}", datetime.now(UTC).date().isoformat()
    )
    body = fetch_text(source_url, user_agent)
    if spec.get("adapter") == "openalex":
        articles = parse_openalex(body, spec)
    else:
        feed_spec = {
            **spec,
            "eventType": "论文",
            "sourceLevel": spec.get("sourceLevel", "原始材料"),
        }
        articles = parse_feed_items(body, feed_spec)
    return articles, _status(
        spec["id"],
        spec["name"],
        "ok" if articles else "empty",
        len(articles),
        len(articles),
        platform=spec.get("platform", spec["name"]),
    )


def crawl_papers(
    specs: Sequence[dict[str, Any]], user_agent: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    articles: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    errors: list[str] = []
    for spec in specs:
        if not spec.get("enabled", True):
            statuses.append(
                _status(
                    spec["id"],
                    spec["name"],
                    "disabled",
                    0,
                    0,
                    platform=spec.get("platform", spec["name"]),
                )
            )
            continue
        try:
            incoming, status = crawl_paper_source(spec, user_agent)
            articles.extend(incoming)
            statuses.append(status)
        except Exception as exc:
            message = f"{spec['id']}: {type(exc).__name__}: {exc}"
            errors.append(message)
            statuses.append(
                _status(
                    spec["id"],
                    spec["name"],
                    "error",
                    0,
                    0,
                    failed=1,
                    platform=spec.get("platform", spec["name"]),
                    error=str(exc),
                )
            )
            print(f"Paper source warning: {message}", file=sys.stderr)
    return articles, sorted(statuses, key=lambda item: item["id"]), errors


def load_existing_payload(
    output_path: Path = OUTPUT_PATH, legacy_path: Path = LEGACY_PATH
) -> dict[str, Any]:
    if output_path.exists():
        return json.loads(output_path.read_text(encoding="utf-8"))
    if legacy_path.exists():
        legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
        return {
            "schemaVersion": 3,
            "generatedAt": legacy.get("updated_at"),
            "articleCount": len(legacy.get("events", [])),
            "articles": legacy.get("events", []),
            "companyFacts": {},
            "sourceStatus": [],
            "qualityGate": {},
        }
    return {
        "schemaVersion": 3,
        "generatedAt": None,
        "articleCount": 0,
        "articles": [],
        "companyFacts": {},
        "sourceStatus": [],
        "qualityGate": {},
    }


def _title_fingerprint(article: dict[str, Any]) -> str:
    title = re.sub(r"[^\w\u4e00-\u9fff]+", "", article.get("title", "").casefold())
    return "|".join(
        (
            article.get("companySlug") or article.get("company", ""),
            article.get("publishedAt", ""),
            title,
        )
    )


def merge_articles(
    existing: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for article in existing:
        source_url = article.get("source", {}).get("url")
        if source_url:
            merged[normalize_url(source_url)] = article
    for article in incoming:
        source_url = article["source"]["url"]
        key = normalize_url(source_url)
        if key in merged:
            previous = merged[key]
            curated = bool(previous.get("curated"))
            merged[key] = {
                **previous,
                **article,
                "id": previous.get("id", article["id"]),
                "title": (
                    previous.get("title") if curated else article.get("title")
                )
                or previous.get("title")
                or article["title"],
                "summary": (
                    previous.get("summary") if curated else article.get("summary")
                )
                or previous.get("summary")
                or article["summary"],
                "importance": max(
                    int(previous.get("importance", 0)),
                    int(article.get("importance", 0)),
                ),
            }
        else:
            merged[key] = article
    deduplicated: dict[str, dict[str, Any]] = {}
    for article in sorted(
        merged.values(),
        key=lambda item: (
            item.get("publishedAt", ""),
            int(item.get("importance", 0)),
            item.get("id", ""),
        ),
        reverse=True,
    ):
        fingerprint = _title_fingerprint(article)
        if fingerprint not in deduplicated:
            deduplicated[fingerprint] = article
    return list(deduplicated.values())[:MAX_ARTICLES]


def repair_media_company_attribution(
    articles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Repair generated media ownership and stale financing labels.

    This function runs over the merged existing+incoming snapshot, so rule
    fixes can migrate previously published non-primary media rows on the next
    crawler run rather than protecting stale classifications behind URL
    deduplication.  Curated and primary rows retain their authored labels.
    """

    repaired: list[dict[str, Any]] = []
    for article in articles:
        source = article.get("source", {})
        source_role = str(
            source.get("sourceRole") or article.get("sourceRole") or ""
        ).casefold()
        is_primary = source_role == "primary" or str(
            source.get("evidenceGrade") or ""
        ).upper() in {"A", "B"}
        if article.get("curated") or source.get("level") != "媒体报道":
            repaired.append(article)
            continue
        company, company_slug, _ = infer_company(
            str(article.get("title", "")),
            "",
        )
        next_article = dict(article)
        next_article["company"] = company
        if company_slug:
            next_article["companySlug"] = company_slug
        else:
            next_article.pop("companySlug", None)
        if (
            not is_primary
            and article.get("type") == "融资"
            and not financing_event_supported(
                article.get("title"), article.get("summary")
            )
        ):
            event_type, importance = infer_event_type(
                str(article.get("title", "")),
                str(article.get("summary", "")),
            )
            next_article["type"] = event_type
            next_article["importance"] = importance
        repaired.append(next_article)
    return repaired


def replace_source_batches(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    successful_ids = {
        status["id"]
        for status in statuses
        if status.get("status") == "disabled"
        or (
            status.get("status") in {"ok", "partial"}
            and status.get("accepted", 0) > 0
        )
    }
    preserved = [
        article
        for article in existing
        if article.get("curated")
        or not article.get("sourceId")
        or article.get("sourceId") not in successful_ids
    ]
    return merge_articles(preserved, incoming)


def merge_source_status(
    existing: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    statuses = {item["id"]: item for item in existing if item.get("id")}
    statuses.update({item["id"]: item for item in incoming if item.get("id")})
    return [statuses[key] for key in sorted(statuses)]


def validate_article(article: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("id", "title", "summary", "type", "region", "sector", "company", "publishedAt"):
        if not article.get(field):
            errors.append(f"missing:{field}")
    if article.get("type") not in VALID_EVENT_TYPES:
        errors.append("invalid:type")
    if article.get("region") not in VALID_REGIONS:
        errors.append("invalid:region")
    if normalize_date(article.get("publishedAt")) != article.get("publishedAt"):
        errors.append("invalid:date")
    source = article.get("source", {})
    url = source.get("url", "")
    if urlsplit(url).scheme not in {"http", "https"} or not urlsplit(url).netloc:
        errors.append("invalid:url")
    if source.get("level") not in VALID_SOURCE_LEVELS:
        errors.append("invalid:source-level")
    if not (0 <= int(article.get("importance", -1)) <= 100):
        errors.append("invalid:importance")
    errors.extend(validate_observation_metadata(article))
    return errors


def evaluate_quality(
    articles: list[dict[str, Any]],
    source_status: list[dict[str, Any]],
    settings: dict[str, Any],
) -> dict[str, Any]:
    invalid = [
        {"id": article.get("id", "unknown"), "errors": validate_article(article)}
        for article in articles
        if validate_article(article)
    ]
    urls = [normalize_url(item.get("source", {}).get("url", "")) for item in articles]
    platforms = {
        item.get("source", {}).get("platform")
        for item in articles
        if item.get("source", {}).get("platform")
    }
    levels = {item.get("source", {}).get("level") for item in articles}
    regions = {item.get("region") for item in articles}
    event_types = {item.get("type") for item in articles}
    healthy_sources = sum(
        1
        for item in source_status
        if item.get("status") in {"ok", "partial"} and item.get("accepted", 0) > 0
    )
    counts = Counter(
        item.get("sourceId") or item.get("source", {}).get("name", "unknown")
        for item in articles
    )
    max_share = (max(counts.values()) / len(articles)) if articles and counts else 1.0
    checks = {
        "minimumArticles": {
            "actual": len(articles),
            "required": int(settings.get("minimumArticles", 30)),
            "passed": len(articles) >= int(settings.get("minimumArticles", 30)),
        },
        "minimumHealthySources": {
            "actual": healthy_sources,
            "required": int(settings.get("minimumHealthySources", 4)),
            "passed": healthy_sources >= int(settings.get("minimumHealthySources", 4)),
        },
        "minimumRegions": {
            "actual": len(regions),
            "required": int(settings.get("minimumRegions", 2)),
            "passed": len(regions) >= int(settings.get("minimumRegions", 2)),
        },
        "minimumSourceLevels": {
            "actual": len(levels),
            "required": int(settings.get("minimumSourceLevels", 2)),
            "passed": len(levels) >= int(settings.get("minimumSourceLevels", 2)),
        },
        "minimumPlatforms": {
            "actual": len(platforms),
            "required": int(settings.get("minimumPlatforms", 3)),
            "passed": len(platforms) >= int(settings.get("minimumPlatforms", 3)),
        },
        "minimumEventTypes": {
            "actual": len(event_types),
            "required": int(settings.get("minimumEventTypes", 5)),
            "passed": len(event_types) >= int(settings.get("minimumEventTypes", 5)),
        },
        "minimumChinaArticles": {
            "actual": sum(item.get("region") == "中国" for item in articles),
            "required": int(settings.get("minimumChinaArticles", 5)),
            "passed": sum(item.get("region") == "中国" for item in articles)
            >= int(settings.get("minimumChinaArticles", 5)),
        },
        "minimumUsArticles": {
            "actual": sum(item.get("region") == "美国" for item in articles),
            "required": int(settings.get("minimumUsArticles", 10)),
            "passed": sum(item.get("region") == "美国" for item in articles)
            >= int(settings.get("minimumUsArticles", 10)),
        },
        "maximumSingleSourceShare": {
            "actual": round(max_share, 4),
            "required": float(settings.get("maximumSingleSourceShare", 0.6)),
            "passed": max_share <= float(settings.get("maximumSingleSourceShare", 0.6)),
        },
        "invalidArticles": {
            "actual": len(invalid),
            "required": 0,
            "passed": not invalid,
        },
        "uniqueUrls": {
            "actual": len(set(urls)),
            "required": len(urls),
            "passed": len(set(urls)) == len(urls),
        },
    }
    return {
        "passed": all(check["passed"] for check in checks.values()),
        "checks": checks,
        "invalidArticles": invalid[:20],
    }


def write_if_changed(
    articles: list[dict[str, Any]],
    previous_payload: dict[str, Any],
    output_path: Path = OUTPUT_PATH,
    *,
    company_facts: dict[str, Any] | None = None,
    source_status: list[dict[str, Any]] | None = None,
    quality_gate: dict[str, Any] | None = None,
) -> bool:
    next_company_facts = (
        company_facts if company_facts is not None else previous_payload.get("companyFacts", {})
    )
    next_source_status = (
        source_status if source_status is not None else previous_payload.get("sourceStatus", [])
    )
    next_quality_gate = (
        quality_gate if quality_gate is not None else previous_payload.get("qualityGate", {})
    )
    unchanged = (
        articles == previous_payload.get("articles", [])
        and next_company_facts == previous_payload.get("companyFacts", {})
        and next_source_status == previous_payload.get("sourceStatus", [])
        and next_quality_gate == previous_payload.get("qualityGate", {})
        and output_path.exists()
        and previous_payload.get("schemaVersion") == 3
    )
    if unchanged:
        print(f"No snapshot changes ({len(articles)} articles).")
        return False
    preserved_metadata = {
        key: previous_payload[key]
        for key in (
            "refreshAudit",
            "trackingConfigHash",
            "trackingEnrichedAt",
            "trackCoverage",
        )
        if key in previous_payload
    }
    payload = {
        **preserved_metadata,
        "schemaVersion": 3,
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "articleCount": len(articles),
        "articles": articles,
        "companyFacts": next_company_facts,
        "sourceStatus": next_source_status,
        "qualityGate": next_quality_gate,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Updated {output_path.relative_to(ROOT)} "
        f"({len(articles)} articles, {len(next_company_facts)} financial profiles)."
    )
    return True


def _selected_groups(source: str) -> tuple[str, ...]:
    if source == "all":
        return ("company", "feeds", "x", "papers", "discovery", "sec")
    if source == "news":
        return ("company", "feeds", "x", "discovery")
    return (source,)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        choices=("all", "news", "company", "feeds", "x", "papers", "discovery", "sec"),
        default="all",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Only normalize and validate the existing snapshot.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the current snapshot without fetching or writing.",
    )
    args = parser.parse_args()

    config = load_config()
    payload = load_existing_payload()
    observation_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    existing_articles = prepare_existing_articles(
        payload.get("articles", []), payload.get("generatedAt")
    )
    if args.validate_only:
        quality = evaluate_quality(
            payload.get("articles", []),
            payload.get("sourceStatus", []),
            config.get("qualityGate", {}),
        )
        print(json.dumps(quality, ensure_ascii=False))
        return 0 if quality["passed"] else 1

    incoming: list[dict[str, Any]] = []
    company_facts = dict(payload.get("companyFacts", {}))
    new_statuses: list[dict[str, Any]] = []
    errors: list[str] = []
    selected = _selected_groups(args.source)
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip() or DEFAULT_USER_AGENT

    if not args.offline:
        for group in selected:
            try:
                if group == "company":
                    items, statuses, group_errors = crawl_company_news(user_agent)
                elif group == "feeds":
                    items, statuses, group_errors = _crawl_config_group(
                        config.get("feeds", []), user_agent
                    )
                elif group == "x":
                    items, statuses, group_errors = crawl_x(
                        config.get("xProfiles", []), user_agent
                    )
                elif group == "papers":
                    items, statuses, group_errors = crawl_papers(
                        config.get("papers", []), user_agent
                    )
                elif group == "discovery":
                    items, statuses, group_errors = _crawl_config_group(
                        config.get("publicDiscovery", []), user_agent
                    )
                else:
                    sec_items, sec_facts, sec_status = crawl_sec(user_agent)
                    items, statuses, group_errors = sec_items, [sec_status], []
                    company_facts.update(sec_facts)
                incoming.extend(items)
                new_statuses.extend(statuses)
                errors.extend(group_errors)
            except Exception as exc:
                errors.append(f"{group}: {type(exc).__name__}: {exc}")

    if args.offline:
        merged = merge_articles([], existing_articles)
    else:
        incoming = apply_incoming_observations(
            existing_articles, incoming, observation_at
        )
        merged = replace_source_batches(
            existing_articles, incoming, new_statuses
        )
    merged = repair_media_company_attribution(merged)
    source_status = merge_source_status(
        payload.get("sourceStatus", []), new_statuses
    )
    quality = evaluate_quality(
        merged, source_status, config.get("qualityGate", {})
    )
    result = {
        "sources": list(selected),
        "incoming": len(incoming),
        "total": len(merged),
        "financialProfiles": len(company_facts),
        "healthySources": sum(
            item.get("status") in {"ok", "partial"} and item.get("accepted", 0) > 0
            for item in source_status
        ),
        "qualityPassed": quality["passed"],
        "errors": errors,
    }
    if not quality["passed"]:
        print("Quality gate failed; previous snapshot retained.", file=sys.stderr)
        print(json.dumps({"result": result, "qualityGate": quality}, ensure_ascii=False))
        return 1
    write_if_changed(
        merged,
        payload,
        company_facts=company_facts,
        source_status=source_status,
        quality_gate=quality,
    )
    print(json.dumps(result, ensure_ascii=False))
    if not args.offline and not incoming:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
