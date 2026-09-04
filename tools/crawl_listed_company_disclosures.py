#!/usr/bin/env python3
"""Refresh verified A-share and Hong Kong listed-company disclosures.

Official exchange or designated disclosure pages are queried first. Every
published event must point to SSE, SZSE, CNINFO or HKEXnews. Eastmoney's public
announcement database is a fallback only when no official document is found.
The snapshot stores metadata and short snippets, not full announcement text.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TRACKING_PATH = ROOT / "config" / "user_tracking.json"
CONFIG_PATH = ROOT / "config" / "listed_company_disclosure_sources.json"
OUTPUT_PATH = ROOT / "public" / "data" / "listed_company_disclosures.json"
USER_AGENT = (
    "VCIQResearchBot/1.0 contact=VCIQ@users.noreply.github.com "
    "(+https://github.com/VCIQ/VCIQ.github.io)"
)
SUPPORTED_MARKETS = {"A股", "港股"}
CAPITAL_TERMS_ZH = (
    "招股说明书",
    "招股章程",
    "上市公告",
    "年度报告",
    "半年度报告",
    "季度报告",
    "业绩预告",
    "业绩快报",
    "配售",
    "定向增发",
    "非公开发行",
    "发行股份",
    "可转换债券",
    "公司债券",
    "募集资金",
    "重大资产重组",
    "收购",
    "并购",
    "出售资产",
    "股权激励",
    "股份回购",
    "回购股份",
    "重大合同",
    "重大事项",
    "关联交易",
)
CAPITAL_TERMS_EN = (
    "prospectus",
    "listing document",
    "global offering",
    "annual report",
    "interim report",
    "quarterly results",
    "profit warning",
    "placing",
    "issue of shares",
    "issue of securities",
    "convertible bond",
    "notes issue",
    "acquisition",
    "disposal",
    "major transaction",
    "share scheme",
    "share option",
    "restricted share units",
    "repurchase",
    "business update",
    "inside information",
)
ROUTINE_NOISE = (
    "monthly return",
    "next day disclosure return",
    "notice of board meeting",
    "poll results",
    "list of directors",
    "terms of reference",
    "月报表",
    "翌日披露报表",
    "董事名单",
    "董事会会议日期",
    "股东大会通知",
    "股东大会决议",
)


@dataclass(frozen=True)
class Listing:
    catalog_slug: str
    name: str
    market: str
    ticker: str
    sector: str
    listing_role: str = "primary"

    @property
    def identity(self) -> str:
        return f"{self.catalog_slug}:{self.market}:{self.ticker}"

    @property
    def source_id(self) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", self.catalog_slug.casefold()).strip("-")
        market = "a" if self.market == "A股" else "hk"
        return f"exchange-disclosure-{slug}-{market}-{self.ticker.casefold()}"

    @property
    def exchange(self) -> str:
        if self.market == "港股":
            return "香港交易所"
        return "上海证券交易所" if a_share_exchange(self.ticker) == "sse" else "深圳证券交易所"


@dataclass(frozen=True)
class Candidate:
    title: str
    url: str
    summary: str
    published_at: str
    provider: str


class TableRowParser(HTMLParser):
    """Capture links and visible text grouped by table rows or list blocks."""

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.rows: list[tuple[str, list[tuple[str, str]]]] = []
        self._depth = 0
        self._text: list[str] = []
        self._links: list[tuple[str, str]] = []
        self._href = ""
        self._anchor: list[str] = []
        self.all_links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        lowered = tag.casefold()
        if lowered in {"tr", "li", "article"}:
            if self._depth == 0:
                self._text = []
                self._links = []
            self._depth += 1
        if lowered == "a" and values.get("href"):
            self._href = urljoin(self.base_url, values["href"])
            self._anchor = []

    def handle_data(self, data: str) -> None:
        value = clean_text(data, 1000)
        if value:
            if self._depth:
                self._text.append(value)
            if self._href:
                self._anchor.append(value)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered == "a" and self._href:
            title = clean_text(" ".join(self._anchor), 600)
            pair = (self._href, title)
            self.all_links.append(pair)
            if self._depth:
                self._links.append(pair)
            self._href = ""
            self._anchor = []
        if lowered in {"tr", "li", "article"} and self._depth:
            self._depth -= 1
            if self._depth == 0 and (self._text or self._links):
                self.rows.append((clean_text(" ".join(self._text), 4000), list(self._links)))
                self._text = []
                self._links = []


def clean_text(value: Any, limit: int = 1000) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" |_-—")
    return text[:limit]


def normalized_host(url: str) -> str:
    return (urlsplit(str(url or "")).hostname or "").casefold().removeprefix("www.")


def a_share_exchange(ticker: str) -> str:
    return "sse" if str(ticker).startswith(("5", "6", "9")) else "szse"


def normalize_ticker(market: str, value: Any) -> str:
    raw = re.sub(r"\s+", "", str(value or "")).upper()
    if market == "A股":
        digits = re.sub(r"\D", "", raw)
        return digits if re.fullmatch(r"\d{6}", digits) else ""
    if market == "港股":
        digits = re.sub(r"\D", "", raw)
        return digits.zfill(5) if 1 <= len(digits) <= 5 else ""
    return ""


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if int(payload.get("schemaVersion", 0)) != 1:
        raise ValueError("unsupported listed disclosure config schema")
    if not isinstance(payload.get("settings"), dict):
        raise ValueError("listed disclosure config requires settings")
    return payload


def load_listings(
    tracking_path: Path = TRACKING_PATH,
    config_path: Path = CONFIG_PATH,
) -> list[Listing]:
    tracking = json.loads(tracking_path.read_text(encoding="utf-8"))
    config = load_config(config_path)
    raw_rows = [
        row
        for row in tracking.get("listedCompanies", [])
        if isinstance(row, dict)
        and row.get("enabled", True) is not False
        and row.get("market") in SUPPORTED_MARKETS
    ]
    raw_rows.extend(
        row
        for row in config.get("extraListings", [])
        if isinstance(row, dict)
        and row.get("enabled", True) is not False
        and row.get("market") in SUPPORTED_MARKETS
    )
    listings: list[Listing] = []
    seen: set[str] = set()
    for row in raw_rows:
        market = clean_text(row.get("market"), 20)
        ticker = normalize_ticker(market, row.get("ticker"))
        listing = Listing(
            catalog_slug=clean_text(row.get("catalogSlug"), 80),
            name=clean_text(row.get("name"), 120),
            market=market,
            ticker=ticker,
            sector=clean_text(row.get("sector"), 60),
            listing_role=clean_text(row.get("listingRole", "primary"), 20) or "primary",
        )
        if not all((listing.catalog_slug, listing.name, listing.ticker, listing.sector)):
            raise ValueError(f"incomplete listed-company disclosure row: {row}")
        if listing.identity in seen:
            continue
        seen.add(listing.identity)
        listings.append(listing)
    return listings


def bing_rss(query: str) -> str:
    return "https://www.bing.com/news/search?q=" + quote_plus(query) + "&format=rss"


def official_query(listing: Listing) -> str:
    terms = " OR ".join(f'"{term}"' for term in (*CAPITAL_TERMS_ZH, *CAPITAL_TERMS_EN))
    identity = f'("{listing.ticker}" OR "{listing.name}")'
    if listing.market == "港股":
        sites = "site:hkexnews.hk/listedco/listconews/sehk"
    elif a_share_exchange(listing.ticker) == "sse":
        sites = "(site:cninfo.com.cn OR site:sse.com.cn/disclosure)"
    else:
        sites = "(site:cninfo.com.cn OR site:szse.cn/disclosure)"
    return f"{sites} {identity} ({terms})"


def fallback_query(listing: Listing) -> str:
    terms = " OR ".join(f'"{term}"' for term in CAPITAL_TERMS_ZH[:18])
    return f'site:data.eastmoney.com/notices ("{listing.ticker}" OR "{listing.name}") ({terms})'


def direct_index_url(listing: Listing, config: dict[str, Any]) -> str:
    if listing.market == "港股":
        stock_id = str(config.get("hkexStockIds", {}).get(listing.catalog_slug, ""))
        if not stock_id:
            return ""
        return (
            "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=EN&market=SEHK"
            f"&stockId={stock_id}&category=0"
        )
    return "https://www.cninfo.com.cn/new/fulltextSearch?keyWord=" + quote_plus(listing.ticker)


def fetch_text(url: str, timeout: int, attempts: int) -> str:
    last_error: Exception | None = None
    for attempt in range(max(1, min(attempts, 3))):
        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
                "Accept-Encoding": "identity",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read(4_000_000).decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.1 * (attempt + 1))
    raise RuntimeError(f"fetch failed for {url}: {last_error}")


def normalize_date(value: str) -> str:
    raw = clean_text(value, 160)
    if not raw:
        return ""
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", raw)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
        except ValueError:
            return ""
    compact = re.search(r"/(20\d{2})/(\d{2})(\d{2})/", raw)
    if compact:
        try:
            return date(int(compact.group(1)), int(compact.group(2)), int(compact.group(3))).isoformat()
        except ValueError:
            return ""
    return ""


def parse_rss(body: str, provider: str) -> list[Candidate]:
    root = ET.fromstring(body)
    rows: list[Candidate] = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1].casefold() not in {"item", "entry"}:
            continue
        values: dict[str, str] = {}
        for child in node.iter():
            key = child.tag.rsplit("}", 1)[-1].casefold()
            value = (
                clean_text(child.attrib.get("href", ""), 1200)
                if key == "link"
                else clean_text(child.text, 2000)
            )
            if not value and key == "link":
                value = clean_text(child.text, 1200)
            if value and key not in values:
                values[key] = value
        title = clean_text(values.get("title"), 600)
        url = clean_text(values.get("link"), 1200)
        summary = clean_text(values.get("description") or values.get("summary"), 1200)
        published = normalize_date(
            values.get("pubdate") or values.get("published") or values.get("updated") or summary
        )
        if title and url:
            rows.append(Candidate(title, url, summary, published, provider))
    return rows


def parse_direct_page(body: str, base_url: str, provider: str) -> list[Candidate]:
    parser = TableRowParser(base_url)
    parser.feed(body)
    candidates: list[Candidate] = []
    seen: set[str] = set()
    for row_text, links in parser.rows:
        published = normalize_date(row_text)
        for url, anchor_text in links:
            if url in seen:
                continue
            title = clean_text(anchor_text or row_text, 600)
            if not title:
                continue
            candidates.append(Candidate(title, url, row_text, published or normalize_date(url), provider))
            seen.add(url)
    for url, anchor_text in parser.all_links:
        if url in seen or not anchor_text:
            continue
        candidates.append(
            Candidate(anchor_text, url, anchor_text, normalize_date(url), provider)
        )
        seen.add(url)
    return candidates


def source_name(url: str) -> tuple[str, str]:
    host = normalized_host(url)
    if host == "cninfo.com.cn" or host.endswith(".cninfo.com.cn"):
        return "巨潮资讯", "监管文件"
    if host == "sse.com.cn" or host.endswith(".sse.com.cn"):
        return "上海证券交易所", "监管文件"
    if host == "szse.cn" or host.endswith(".szse.cn"):
        return "深圳证券交易所", "监管文件"
    if host == "hkexnews.hk" or host.endswith(".hkexnews.hk"):
        return "香港交易所披露易", "监管文件"
    if host == "eastmoney.com" or host.endswith(".eastmoney.com"):
        return "东方财富公告", "数据库记录"
    return "", ""


def allowed_url(listing: Listing, url: str, *, fallback: bool = False) -> bool:
    host = normalized_host(url)
    path = urlsplit(url).path.casefold()
    if fallback:
        return (host == "eastmoney.com" or host.endswith(".eastmoney.com")) and "/notices" in path
    if listing.market == "港股":
        return (host == "hkexnews.hk" or host.endswith(".hkexnews.hk")) and "/listedco/" in path
    if host == "cninfo.com.cn" or host.endswith(".cninfo.com.cn"):
        return "/disclosure/" in path or "/finalpage/" in path or "/new/disclosure/" in path
    if a_share_exchange(listing.ticker) == "sse":
        return (host == "sse.com.cn" or host.endswith(".sse.com.cn")) and "/disclosure" in path
    return (host == "szse.cn" or host.endswith(".szse.cn")) and "/disclosure" in path


def relevant_candidate(listing: Listing, candidate: Candidate) -> bool:
    text = clean_text(f"{candidate.title} {candidate.summary} {candidate.url}", 6000).casefold()
    variants = {
        listing.ticker.casefold(),
        listing.ticker.lstrip("0").casefold(),
        listing.name.casefold(),
        listing.name.replace("机器人", "").casefold(),
        listing.name.replace("科技", "").casefold(),
    }
    return any(term and term in text for term in variants)


def classify_document(title: str, summary: str = "") -> str:
    text = clean_text(f"{title} {summary}", 4000).casefold()
    if any(term in text for term in ROUTINE_NOISE):
        return ""
    groups = (
        ("招股与上市", ("招股说明书", "招股章程", "上市公告", "prospectus", "listing document", "global offering")),
        ("定期报告与业绩", ("年度报告", "半年度报告", "季度报告", "业绩预告", "业绩快报", "annual report", "annual results", "interim report", "quarterly results", "profit warning")),
        ("证券发行与融资", ("配售", "定向增发", "非公开发行", "发行股份", "可转换债券", "公司债券", "募集资金", "placing", "issue of shares", "issue of securities", "convertible bond", "notes issue")),
        ("并购与资产交易", ("重大资产重组", "收购", "并购", "出售资产", "acquisition", "disposal", "major transaction")),
        ("股权激励", ("股权激励", "员工持股", "share scheme", "share option", "restricted share units")),
        ("股份回购", ("股份回购", "回购股份", "share buyback", "repurchase")),
        ("重大经营与风险", ("重大合同", "重大事项", "关联交易", "交易进展", "business update", "trading update", "inside information")),
    )
    for label, terms in groups:
        if any(term in text for term in terms):
            return label
    return ""


def event_id(listing: Listing, url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:18]
    return f"disclosure-{listing.catalog_slug}-{digest}"


def to_event(listing: Listing, candidate: Candidate, *, fallback: bool) -> dict[str, Any] | None:
    if not candidate.published_at:
        return None
    document_type = classify_document(candidate.title, candidate.summary)
    if not document_type:
        return None
    source, level = source_name(candidate.url)
    if not source:
        return None
    return {
        "id": event_id(listing, candidate.url),
        "companySlug": listing.catalog_slug,
        "companyName": listing.name,
        "market": listing.market,
        "ticker": listing.ticker,
        "exchange": listing.exchange,
        "listingRole": listing.listing_role,
        "publishedAt": candidate.published_at,
        "documentType": document_type,
        "title": clean_text(candidate.title, 600),
        "summary": clean_text(candidate.summary or f"{source}公开披露：{candidate.title}", 420),
        "source": {"name": source, "url": candidate.url, "level": level},
        "discoveredVia": candidate.provider,
        "fallback": fallback,
    }


def discover(
    listing: Listing,
    settings: dict[str, Any],
    config: dict[str, Any],
    *,
    fallback: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    timeout = int(settings.get("requestTimeout", 18))
    attempts = int(settings.get("requestAttempts", 2))
    candidates: list[Candidate] = []
    errors: list[str] = []
    if not fallback:
        direct_url = direct_index_url(listing, config)
        if direct_url:
            try:
                body = fetch_text(direct_url, timeout, attempts)
                candidates.extend(parse_direct_page(body, direct_url, "official-direct-index"))
            except Exception as exc:  # noqa: BLE001 - continue with official domain search.
                errors.append(f"direct:{type(exc).__name__}:{exc}")
    query = fallback_query(listing) if fallback else official_query(listing)
    provider = "eastmoney-domain-search" if fallback else "official-domain-search"
    try:
        candidates.extend(parse_rss(fetch_text(bing_rss(query), timeout, attempts), provider))
    except Exception as exc:  # noqa: BLE001 - direct results may still be usable.
        errors.append(f"search:{type(exc).__name__}:{exc}")

    cutoff = date.today() - timedelta(days=int(settings.get("maxAgeDays", 1095)))
    accepted: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        if not allowed_url(listing, candidate.url, fallback=fallback):
            continue
        if not relevant_candidate(listing, candidate):
            continue
        event = to_event(listing, candidate, fallback=fallback)
        if not event:
            continue
        try:
            if date.fromisoformat(event["publishedAt"]) < cutoff:
                continue
        except ValueError:
            continue
        accepted[event["source"]["url"]] = event
    limit = max(1, min(int(settings.get("maxItemsPerListing", 18)), 30))
    rows = sorted(
        accepted.values(),
        key=lambda event: (event["publishedAt"], event["id"]),
        reverse=True,
    )[:limit]
    return rows, {
        "id": listing.source_id,
        "companySlug": listing.catalog_slug,
        "name": listing.name,
        "market": listing.market,
        "ticker": listing.ticker,
        "exchange": listing.exchange,
        "provider": "eastmoney" if fallback else "official",
        "status": "ok" if rows else "error",
        "scanned": len(candidates),
        "qualified": len(accepted),
        "accepted": len(rows),
        "fallback": fallback,
        "errors": errors,
    }


def load_previous(path: Path = OUTPUT_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"schemaVersion": 1, "companies": {}, "sourceStatus": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schemaVersion": 1, "companies": {}, "sourceStatus": []}
    return payload if isinstance(payload, dict) else {"schemaVersion": 1, "companies": {}, "sourceStatus": []}


def build_snapshot(
    listings: Iterable[Listing] | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = load_config()
    settings = config["settings"]
    rows = list(listings or load_listings())
    previous = previous or load_previous()
    previous_companies = previous.get("companies", {}) if isinstance(previous.get("companies"), dict) else {}
    events_by_company: dict[str, dict[str, dict[str, Any]]] = {}
    listing_rows_by_company: dict[str, list[dict[str, Any]]] = {}
    statuses: list[dict[str, Any]] = []

    for listing in rows:
        try:
            events, status = discover(listing, settings, config, fallback=False)
        except Exception as exc:  # noqa: BLE001
            events = []
            status = {
                "id": listing.source_id,
                "companySlug": listing.catalog_slug,
                "name": listing.name,
                "market": listing.market,
                "ticker": listing.ticker,
                "exchange": listing.exchange,
                "provider": "official",
                "status": "error",
                "scanned": 0,
                "qualified": 0,
                "accepted": 0,
                "fallback": False,
                "errors": [f"{type(exc).__name__}:{exc}"],
            }
        if not events and bool(settings.get("fallbackEnabled", True)):
            try:
                fallback_events, fallback_status = discover(
                    listing, settings, config, fallback=True
                )
                if fallback_events:
                    events = fallback_events
                    status["status"] = "partial"
                    status["fallbackUsed"] = True
                    status["accepted"] = len(events)
                status["fallbackScanned"] = fallback_status.get("scanned", 0)
                status["fallbackQualified"] = fallback_status.get("qualified", 0)
                status["fallbackAccepted"] = fallback_status.get("accepted", 0)
                status["fallbackErrors"] = fallback_status.get("errors", [])
            except Exception as exc:  # noqa: BLE001
                status["fallbackErrors"] = [f"{type(exc).__name__}:{exc}"]

        company_events = events_by_company.setdefault(listing.catalog_slug, {})
        for event in events:
            company_events[event["source"]["url"]] = event
        listing_rows_by_company.setdefault(listing.catalog_slug, []).append(
            {
                "market": listing.market,
                "ticker": listing.ticker,
                "exchange": listing.exchange,
                "listingRole": listing.listing_role,
            }
        )
        statuses.append(status)

    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    companies: dict[str, Any] = {}
    for slug in sorted({listing.catalog_slug for listing in rows}):
        current = list(events_by_company.get(slug, {}).values())
        previous_company = previous_companies.get(slug, {}) if isinstance(previous_companies.get(slug), dict) else {}
        previous_events = [event for event in previous_company.get("events", []) if isinstance(event, dict)]
        by_url = {
            str(event.get("source", {}).get("url", "")): event
            for event in previous_events
            if str(event.get("source", {}).get("url", ""))
        }
        for event in current:
            by_url[event["source"]["url"]] = event
        max_items = max(1, min(int(settings.get("maxItemsPerListing", 18)) * 2, 48))
        merged = sorted(
            by_url.values(),
            key=lambda event: (str(event.get("publishedAt", "")), str(event.get("id", ""))),
            reverse=True,
        )[:max_items]
        name = next((listing.name for listing in rows if listing.catalog_slug == slug), slug)
        companies[slug] = {
            "slug": slug,
            "name": name,
            "updatedAt": generated_at,
            "status": "ok" if current else ("retained" if merged else "partial"),
            "listings": listing_rows_by_company.get(slug, []),
            "events": merged,
            "officialEventCount": sum(not bool(event.get("fallback")) for event in merged),
            "fallbackEventCount": sum(bool(event.get("fallback")) for event in merged),
        }
    return {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "companyCount": len(companies),
        "eventCount": sum(len(company["events"]) for company in companies.values()),
        "companies": companies,
        "sourceStatus": statuses,
    }


def validate_snapshot(
    payload: dict[str, Any],
    listings: Iterable[Listing] | None = None,
) -> list[str]:
    errors: list[str] = []
    rows = list(listings or load_listings())
    expected_status = {listing.source_id for listing in rows}
    statuses = {
        str(status.get("id")): status
        for status in payload.get("sourceStatus", [])
        if isinstance(status, dict)
    }
    missing = sorted(expected_status - set(statuses))
    if missing:
        errors.append("missing disclosure source statuses: " + ", ".join(missing[:10]))
    companies = payload.get("companies")
    if not isinstance(companies, dict):
        return [*errors, "companies must be an object"]
    listings_by_slug: dict[str, list[Listing]] = {}
    for listing in rows:
        listings_by_slug.setdefault(listing.catalog_slug, []).append(listing)
    for slug, company in companies.items():
        if not isinstance(company, dict):
            errors.append(f"invalid disclosure company: {slug}")
            continue
        valid_listings = listings_by_slug.get(slug, [])
        for event in company.get("events", []):
            if not isinstance(event, dict):
                errors.append(f"invalid event row: {slug}")
                continue
            source = event.get("source") if isinstance(event.get("source"), dict) else {}
            url = str(source.get("url", ""))
            fallback = bool(event.get("fallback"))
            if not any(allowed_url(listing, url, fallback=fallback) for listing in valid_listings):
                errors.append(f"disclosure URL outside allowlist: {url}")
            if not classify_document(str(event.get("title", "")), str(event.get("summary", ""))):
                errors.append(f"unclassified disclosure event: {event.get('id', 'unknown')}")
            if not normalize_date(str(event.get("publishedAt", ""))):
                errors.append(f"invalid disclosure date: {event.get('id', 'unknown')}")
    expected_count = sum(
        len(company.get("events", []))
        for company in companies.values()
        if isinstance(company, dict)
    )
    if int(payload.get("eventCount", -1)) != expected_count:
        errors.append("eventCount does not match disclosure events")
    return errors


def write_snapshot(payload: dict[str, Any], path: Path = OUTPUT_PATH) -> bool:
    previous = load_previous(path)
    comparable_previous = json.loads(json.dumps(previous, ensure_ascii=False))
    comparable_next = json.loads(json.dumps(payload, ensure_ascii=False))
    comparable_previous.pop("generatedAt", None)
    comparable_next.pop("generatedAt", None)
    for comparable in (comparable_previous, comparable_next):
        companies = comparable.get("companies", {})
        if isinstance(companies, dict):
            for company in companies.values():
                if isinstance(company, dict):
                    company.pop("updatedAt", None)
    if comparable_previous == comparable_next and path.exists():
        print("No listed-company disclosure changes.")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "companies": payload.get("companyCount", 0),
                "events": payload.get("eventCount", 0),
                "officialEvents": sum(
                    int(company.get("officialEventCount", 0) or 0)
                    for company in payload.get("companies", {}).values()
                    if isinstance(company, dict)
                ),
                "fallbackEvents": sum(
                    int(company.get("fallbackEventCount", 0) or 0)
                    for company in payload.get("companies", {}).values()
                    if isinstance(company, dict)
                ),
            },
            ensure_ascii=False,
        )
    )
    return True


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--require-events", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        payload = load_previous()
        errors = validate_snapshot(payload)
        if args.require_events and int(payload.get("eventCount", 0) or 0) <= 0:
            errors.append("no listed-company disclosure events were published")
        if errors:
            raise SystemExit("; ".join(errors))
        print(json.dumps({"passed": True, "eventCount": payload.get("eventCount", 0)}, ensure_ascii=False))
        return 0
    payload = build_snapshot()
    errors = validate_snapshot(payload)
    if errors:
        raise SystemExit("; ".join(errors))
    write_snapshot(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
