#!/usr/bin/env python3
"""Expand tracking entities from public web sources and sync the config.

For every enabled track the tool takes the existing seeds (track name,
keywords, people, sample companies), queries only public, no-login web
endpoints (Wikipedia, Wikidata, OpenAlex, Baidu/Google suggest), scores
closely-related candidate keywords, people, companies and official-site
sources, and writes accepted candidates straight into
``config/user_tracking.json`` — the same file the /tracking admin edits, so
the existing crawler pipeline picks them up on the next refresh.

Rules that keep the loop safe:

- a candidate is only accepted when it is validated with the same rules the
  /tracking admin UI enforces (mirrored from lib/user-tracking.ts);
- every automatic addition is remembered in
  ``config/tracking_auto_discovery.json``; when the site owner later deletes
  an auto-added entry (or it appears in ``ignoredRecommendations``), it
  becomes a tombstone and is never added again;
- a brand-new custom track with an empty keyword list is seeded first: its
  name alone is expanded on the web and the top keywords are imported
  directly into the keyword area;
- when the network is unreachable the tool changes nothing — it never
  fabricates entities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, quote_plus, urlparse
from urllib.request import Request, urlopen

try:
    from .tracking_manual_feedback import (
        load_manual_feedback,
        manual_held_source_hosts,
        manual_held_values,
        manual_source_affinity,
        normalize_identity as normalize_manual_identity,
    )
    from .tracking_source_governance import (
        canonical_source_host,
        looks_like_derived_source_name,
        strip_discovery_source_suffix,
    )
except ImportError:
    from tracking_manual_feedback import (
        load_manual_feedback,
        manual_held_source_hosts,
        manual_held_values,
        manual_source_affinity,
        normalize_identity as normalize_manual_identity,
    )
    from tracking_source_governance import (
        canonical_source_host,
        looks_like_derived_source_name,
        strip_discovery_source_suffix,
    )

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "user_tracking.json"
LEDGER_PATH = ROOT / "config" / "tracking_auto_discovery.json"
# The site's own crawled corpus is the primary supply of professional
# entities: whatever recurs in a track's accepted articles is, by
# construction, industry vocabulary rather than encyclopedia language.
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
MANUAL_CAPTURE_PATH = ROOT / "config" / "tracking_capture_inbox.json"
MANUAL_INTENTS_PATH = ROOT / "config" / "tracking_intents.json"
MANUAL_RUNTIME_PATH = CONFIG_PATH

USER_AGENT = (
    "VCIQResearch/1.0 (+https://github.com/VCIQ/VCIQ.github.io; "
    "public tracking entity discovery)"
)
REQUEST_TIMEOUT = 20
REQUEST_SLEEP = 0.35

MAX_KEYWORDS_PER_RUN = 5
MAX_SEED_KEYWORDS = 8
MAX_PEOPLE_PER_RUN = 2
MAX_COMPANIES_PER_RUN = 3
MAX_SOURCES_PER_RUN = 2
MAX_TRACK_KEYWORDS = 45
MAX_TRACK_PEOPLE = 25
MAX_TRACK_COMPANIES = 30
ACCEPT_THRESHOLD = 3.0
SEED_ACCEPT_THRESHOLD = 2.0
RELAXED_ACCEPT_THRESHOLD = 1.4

COMPANY_CLASSES = {
    "Q4830453",  # business
    "Q891723",  # public company
    "Q6881511",  # enterprise
    "Q783794",  # company
    "Q161726",  # multinational corporation
    "Q1058914",  # software company
    "Q18388277",  # technology company
    "Q207652",  # chemical company
    "Q43229",  # organization (weak, only with website)
}
HUMAN_CLASS = "Q5"
COUNTRY_REGIONS = {"Q148": "中国", "Q30": "美国"}

GENERIC_TRACKING_KEYWORDS = {
    "ai",
    "ml",
    "人工智能",
    "技术",
    "科技",
    "公司",
    "企业",
    "行业",
    "产业",
    "研究",
    "论文",
    "新闻",
    "资讯",
    "产品",
    "项目",
    "模型",
    "系统",
    "平台",
    "创新",
    "投资",
    "融资",
    "上市",
    "发布",
    "突破",
    "发展",
    "市场",
    "应用",
    "机器人",
    "半导体",
    "新能源",
    "生物科技",
    "量子计算",
    "商业航天",
    "web3",
    "新材料",
    "智能制造",
    "tech",
    "technology",
    "company",
    "industry",
    "research",
    "paper",
    "news",
    "product",
    "project",
    "model",
    "system",
    "platform",
    "innovation",
    "investment",
    "startup",
    "价格",
    "招聘",
    "股票",
    "概念股",
    "龙头股",
    "是什么",
    "什么意思",
    "怎么样",
    "官网",
    "下载",
    "培训",
    "招标",
    # Calendar words picked out of news titles are never tracking keywords.
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    # Title-case English filler that survives the capitalization filter.
    "the",
    "how",
    "why",
    "what",
    "when",
    "where",
    "who",
    "quarter",
    "build",
    "release",
    "earnings",
    "financial results",
    "earnings call",
    "first quarter",
    "second quarter",
    "third quarter",
    "fourth quarter",
}
GENERIC_SUFFIXES = ("是什么", "什么意思", "怎么样", "官网", "招聘", "股吧", "股票")

FetchJson = Callable[[str], Any]
FetchText = Callable[[str], str]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def normalize_term(value: str) -> str:
    cleaned = unicodedata.normalize("NFKC", str(value or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.casefold()


def clean_candidate(value: str) -> str:
    cleaned = unicodedata.normalize("NFKC", str(value or ""))
    cleaned = re.sub(r"[\"'“”‘’`]+", " ", cleaned)
    # Preserve a meaningful leading dot in technologies such as .NET while
    # still removing ordinary sentence-final periods from extracted titles.
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -·:：,，。;；")
    return cleaned.rstrip(".").strip()


def validate_keyword(value: str) -> str:
    """Mirror lib/user-tracking.ts validateTrackingKeyword; return normalized
    keyword or empty string when rejected."""

    raw = clean_candidate(value)[:80]
    if not raw or len(raw) > 40:
        return ""
    if re.search(r"^https?://", raw, re.IGNORECASE):
        return ""
    if re.search(r"\b(?:www\.)?[^\s]+\.(?:com|cn|org|net)\b", raw, re.IGNORECASE):
        return ""
    if "@" in raw:
        return ""
    if re.search(r"^site\s*:", raw, re.IGNORECASE):
        return ""
    if re.search(r"(^|\s)(?:AND|OR|NOT)(\s|$)", raw):
        return ""
    if not re.search(r"[A-Za-z0-9㐀-鿿]", raw):
        return ""
    if normalize_term(raw) in GENERIC_TRACKING_KEYWORDS:
        return ""
    if any(raw.endswith(suffix) for suffix in GENERIC_SUFFIXES):
        return ""
    cjk = len(re.findall(r"[㐀-鿿]", raw))
    alnum = len(re.findall(r"[A-Za-z0-9]", raw))
    symbolic_language = bool(re.fullmatch(r"(?i)c(?:\+\+|#)?|r", raw))
    if cjk == 1 and alnum == 0:
        return ""
    if cjk == 0 and alnum < 2 and not symbolic_language:
        return ""
    # Short title-cased fragments such as “Don” are typically clipped words
    # from headlines. Keep established all-caps technical acronyms such as RAG.
    if re.fullmatch(r"[A-Za-z]{1,3}", raw) and not raw.isupper():
        return ""
    return raw


PERSON_NAME_NOISE_RE = re.compile(
    r"(?:\b(?:company|business|corporate|global|development|sales|marketing|"
    r"supply\s+chain|manufacturing|technologies?|systems?|senior|vice|president|"
    r"officer|cfo|cto|ceo|team|leadership|management|press|news|post|co)\b|"
    r"关注|作为|参加|出席|共同|主题演讲|演讲|负责|表示|介绍|宣布|致辞|担任|"
    r"现任|曾任|来自|团队|公司|集团|部门|供应链|业务发展)",
    re.IGNORECASE,
)


def likely_person_name(value: str) -> bool:
    raw = clean_candidate(value)[:100]
    name = re.sub(r"\s+@(?:[A-Za-z0-9_]{1,15})$", "", raw).strip()
    if not name or re.search(r"https?://|@", name):
        return False
    if PERSON_NAME_NOISE_RE.search(name):
        return False
    if re.fullmatch(r"[㐀-鿿·•]{2,8}", name):
        return 2 <= len(name.replace("·", "").replace("•", "")) <= 5
    if re.search(r"[㐀-鿿]", name):
        return len(name) <= 40
    words = name.split()
    return 2 <= len(words) <= 5 and all(
        re.fullmatch(r"[A-Za-z][A-Za-z'.-]*", word) for word in words
    )


def validate_person(display_name: str, handle: str = "") -> str:
    name = clean_candidate(display_name)[:100]
    if not likely_person_name(name):
        return ""
    if handle and re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
        return f"{name} @{handle}"
    return name


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore")
    text = re.sub(r"[^a-z0-9]+", "-", normalized.decode("ascii").lower()).strip("-")
    if text:
        return text
    digest = hashlib.md5(value.encode("utf-8")).hexdigest()[:8]
    return f"item-{digest}"


@dataclass
class Candidate:
    value: str
    score: float = 0.0
    evidence: set[str] = field(default_factory=set)
    entity_id: str = ""
    website: str = ""
    region: str = "全球"
    handle: str = ""
    # Kind hint from the corpus (company/person); used when Wikidata does not
    # know the entity — common for young Chinese startups and investors.
    hint: str = ""


def evidence_is_professional(evidence: set[str] | list[str]) -> bool:
    values = set(evidence)
    return "news-confirmed" in values or any(
        value.startswith("corpus-") for value in values
    )


def candidate_has_professional_evidence(candidate: Candidate) -> bool:
    return evidence_is_professional(candidate.evidence)


GENERIC_ENTITY_NAMES = {
    "",
    "科技产业",
    "持续更新",
    "未识别",
    "未分类",
    "公司",
    "行业",
    "产业",
    "AI 研究",
    "研究机构",
    "媒体",
    "资本动态",
    "公司动态",
}
# Aggregators, indexes and login-walled platforms never become media sources.
DENY_SOURCE_HOSTS = {
    "news.google.com",
    "google.com",
    "bing.com",
    "cn.bing.com",
    "baidu.com",
    "weixin.qq.com",
    "mp.weixin.qq.com",
    "x.com",
    "twitter.com",
    "toutiao.com",
    "www.toutiao.com",
    "youtube.com",
    "sogou.com",
    "arxiv.org",
    "openalex.org",
    # Regulator and exchange disclosure channels have dedicated adapters and
    # must not be re-added as generic media sources.
    "sec.gov",
    "hkexnews.hk",
    "www1.hkexnews.hk",
    "cninfo.com.cn",
    "sse.com.cn",
    "szse.cn",
}

QUOTED_TITLE_TERM = re.compile(r"[《「【“\"]([^》」】”\"]{2,14})[》」】”\"]")
LATIN_TITLE_TERM = re.compile(
    r"[A-Za-z][A-Za-z0-9+&.\-]*(?:\s+[A-Z][A-Za-z0-9+&.\-]*){0,2}",
)
CJK_TITLE_RUN = re.compile(r"[㐀-鿿]{2,8}")


def extract_title_terms(title: str) -> set[str]:
    terms: set[str] = set()
    for match in QUOTED_TITLE_TERM.finditer(title):
        terms.add(match.group(1).strip())
    for match in LATIN_TITLE_TERM.finditer(title):
        value = match.group(0).strip(" .-")
        # Keep branded/technical tokens (HBM4, CoWoS, OpenAI); plain
        # lowercase English words are stopword-grade, and a lowercase first
        # token ("and Google") marks a mid-phrase fragment.
        if 2 <= len(value) <= 30 and not value.islower() and not value[0].islower():
            terms.add(value)
    for match in CJK_TITLE_RUN.finditer(title):
        terms.add(match.group(0))
    return {term for term in terms if term}


def source_host(url: str) -> str:
    return canonical_source_host(url)


def load_track_corpus() -> dict[str, dict[str, Any]]:
    payload = load_json(ARTICLES_PATH, None)
    articles = payload.get("articles") if isinstance(payload, dict) else None
    stats: dict[str, dict[str, Any]] = {}
    if not isinstance(articles, list):
        return stats
    for article in articles:
        if not isinstance(article, dict):
            continue
        slugs = article.get("trackSlugs")
        if not isinstance(slugs, list) or not slugs:
            continue
        title = str(article.get("title") or "")
        source = article.get("source") or {}
        source_name = str(source.get("name") or source.get("platform") or "")
        source_id = str(source.get("id") or source.get("sourceId") or "")
        derived_source = (
            source_id.startswith("source-auto-")
            or source_id.startswith("user-source-source-auto-")
            or looks_like_derived_source_name(source_name)
        )
        host = source_host(str(source.get("url") or ""))
        region = str(article.get("region") or "全球")
        companies = [str(article.get("company") or "")] + [
            str(value) for value in article.get("mentionedCompanies") or []
        ]
        people = [str(value) for value in article.get("mentionedPeople") or []]
        title_terms = extract_title_terms(title)
        for slug in slugs:
            row = stats.setdefault(
                str(slug),
                {
                    "companies": Counter(),
                    "people": Counter(),
                    "terms": Counter(),
                    "termSources": {},
                    "sources": {},
                },
            )
            for company in companies:
                cleaned = clean_candidate(company)
                if cleaned and cleaned not in GENERIC_ENTITY_NAMES:
                    row["companies"][cleaned] += 1
            for person in people:
                cleaned = clean_candidate(person)
                if cleaned and cleaned not in GENERIC_ENTITY_NAMES:
                    row["people"][cleaned] += 1
            for term in title_terms:
                row["terms"][term] += 1
                row["termSources"].setdefault(term, set()).add(source_name)
            if host and host not in DENY_SOURCE_HOSTS and not derived_source:
                srow = row["sources"].setdefault(
                    host,
                    {"count": 0, "names": Counter(), "regions": Counter()},
                )
                srow["count"] += 1
                if source_name:
                    srow["names"][source_name] += 1
                srow["regions"][region] += 1
    return stats


class PublicWebClient:
    """Thin wrapper over public keyless endpoints with a request budget."""

    def __init__(
        self,
        max_requests: int,
        fetch_text: FetchText | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.max_requests = max_requests
        self.used_requests = 0
        self.failed_requests = 0
        self._fetch_text = fetch_text or self._default_fetch_text
        self._sleep = sleep

    def _default_fetch_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")

    def text(self, url: str) -> str:
        if self.used_requests >= self.max_requests:
            raise BudgetExhausted()
        self.used_requests += 1
        try:
            body = self._fetch_text(url)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            self.failed_requests += 1
            return ""
        self._sleep(REQUEST_SLEEP)
        return body

    def json(self, url: str) -> Any:
        body = self.text(url)
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None


class BudgetExhausted(Exception):
    pass


def wikipedia_resolve(client: PublicWebClient, term: str, lang: str) -> str:
    data = client.json(
        f"https://{lang}.wikipedia.org/w/api.php?action=opensearch"
        f"&search={quote_plus(term)}&limit=1&namespace=0&format=json"
    )
    if isinstance(data, list) and len(data) >= 2 and data[1]:
        return str(data[1][0])
    return ""


def wikipedia_morelike(client: PublicWebClient, title: str, lang: str) -> list[str]:
    data = client.json(
        f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search"
        f"&srsearch=morelike:{quote(title)}&srlimit=10&format=json"
    )
    results = (
        data.get("query", {}).get("search", []) if isinstance(data, dict) else []
    )
    return [str(row.get("title", "")) for row in results if row.get("title")]


def baidu_suggest(client: PublicWebClient, term: str) -> list[str]:
    body = client.text(
        f"https://suggestion.baidu.com/su?wd={quote_plus(term)}&cb=window.baidu.sug"
    )
    match = re.search(r"s\s*:\s*\[(.*?)\]", body)
    if not match:
        return []
    return [
        value.strip().strip('"')
        for value in match.group(1).split('","')
        if value.strip().strip('"')
    ]


def google_suggest(client: PublicWebClient, term: str) -> list[str]:
    data = client.json(
        "https://suggestqueries.google.com/complete/search?client=firefox"
        f"&q={quote_plus(term)}"
    )
    if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
        return [str(value) for value in data[1]]
    return []


def openalex_related_concepts(client: PublicWebClient, term: str) -> list[str]:
    data = client.json(
        f"https://api.openalex.org/concepts?search={quote_plus(term)}&per-page=1"
    )
    results = data.get("results") if isinstance(data, dict) else None
    if not results:
        return []
    related = results[0].get("related_concepts") or []
    names: list[str] = []
    for row in related:
        if float(row.get("score") or 0) < 0.4:
            continue
        name = str(row.get("display_name") or "")
        if name:
            names.append(name)
    return names[:8]


def wikidata_lookup(client: PublicWebClient, term: str) -> dict[str, Any]:
    """Classify a candidate: kind (company/person/keyword) + enrichment."""

    for language in ("zh", "en"):
        search = client.json(
            "https://www.wikidata.org/w/api.php?action=wbsearchentities"
            f"&search={quote_plus(term)}&language={language}&format=json&limit=1"
        )
        rows = search.get("search") if isinstance(search, dict) else None
        if not rows:
            continue
        entity_id = str(rows[0].get("id") or "")
        if not entity_id:
            continue
        detail = client.json(
            "https://www.wikidata.org/w/api.php?action=wbgetentities"
            f"&ids={entity_id}&props=claims&format=json"
        )
        claims = (
            detail.get("entities", {}).get(entity_id, {}).get("claims", {})
            if isinstance(detail, dict)
            else {}
        )

        def claim_ids(prop: str) -> list[str]:
            values = []
            for row in claims.get(prop, []):
                value = (
                    row.get("mainsnak", {})
                    .get("datavalue", {})
                    .get("value", {})
                )
                if isinstance(value, dict) and value.get("id"):
                    values.append(str(value["id"]))
            return values

        def claim_strings(prop: str) -> list[str]:
            values = []
            for row in claims.get(prop, []):
                value = (
                    row.get("mainsnak", {})
                    .get("datavalue", {})
                    .get("value")
                )
                if isinstance(value, str):
                    values.append(value)
            return values

        instance_of = set(claim_ids("P31"))
        kind = "keyword"
        if HUMAN_CLASS in instance_of:
            kind = "person"
        elif instance_of & COMPANY_CLASSES:
            kind = "company"
        websites = claim_strings("P856")
        countries = claim_ids("P17")
        handles = claim_strings("P2002")
        region = "全球"
        for country in countries:
            if country in COUNTRY_REGIONS:
                region = COUNTRY_REGIONS[country]
                break
        return {
            "id": entity_id,
            "kind": kind,
            "website": websites[0] if websites else "",
            "region": region,
            "handle": handles[0] if handles else "",
        }
    return {}


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def empty_ledger() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "updatedAt": "",
        "tracks": {},
        "added": [],
        "removed": [],
    }


def ledger_key(track: str, kind: str, value: str) -> tuple[str, str, str]:
    return (track, kind, normalize_term(value))


def config_values(track: dict[str, Any], kind: str, config: dict[str, Any]) -> list[str]:
    if kind == "sources":
        return [
            str(source.get("url") or "")
            for source in config.get("sources", [])
            if source.get("sector") == track.get("name")
        ]
    return [str(value) for value in track.get(kind, [])]


def prune_low_quality_auto_entries(
    ledger: dict[str, Any], config: dict[str, Any]
) -> list[dict[str, str]]:
    """Remove prior automatic noise while preserving owner-entered values.

    Existing non-custom tracks only retain automatically discovered keywords
    confirmed by the accepted article corpus or current industry news. New
    custom tracks keep reference-web seed terms until they have a corpus.
    """

    tracks = {
        str(track.get("slug")): track
        for track in config.get("tracks", [])
        if isinstance(track, dict)
    }
    kept: list[dict[str, Any]] = []
    pruned: list[dict[str, str]] = []
    for row in ledger.get("added", []):
        if not isinstance(row, dict):
            continue
        track = tracks.get(str(row.get("track") or ""))
        kind = str(row.get("kind") or "")
        value = str(row.get("value") or "")
        evidence = {
            str(item) for item in row.get("evidence", []) if str(item)
        }
        invalid = False
        if track and kind == "people":
            invalid = not likely_person_name(value)
        elif track and kind == "keywords" and not track.get("custom"):
            invalid = bool(evidence) and not evidence_is_professional(evidence)
        if not invalid or not track or kind not in {
            "keywords", "people", "sampleCompanies"
        }:
            kept.append(row)
            continue
        values = track.get(kind)
        if isinstance(values, list):
            target = normalize_term(value)
            track[kind] = [
                item for item in values if normalize_term(str(item)) != target
            ]
        pruned.append(
            {"track": str(row.get("track") or ""), "kind": kind, "value": value}
        )
    ledger["added"] = kept
    return pruned


def sync_tombstones(ledger: dict[str, Any], config: dict[str, Any]) -> None:
    """Auto-added entries that the owner has deleted become tombstones."""

    tracks_by_slug = {track.get("slug"): track for track in config.get("tracks", [])}
    still_added: list[dict[str, Any]] = []
    removed = ledger.setdefault("removed", [])
    removed_keys = {
        ledger_key(row.get("track", ""), row.get("kind", ""), row.get("value", ""))
        for row in removed
    }
    for row in ledger.get("added", []):
        track = tracks_by_slug.get(row.get("track"))
        present = False
        if track:
            values = {
                normalize_term(value)
                for value in config_values(track, str(row.get("kind")), config)
            }
            present = normalize_term(str(row.get("value"))) in values
        if present:
            still_added.append(row)
            continue
        key = ledger_key(
            str(row.get("track")), str(row.get("kind")), str(row.get("value"))
        )
        if key not in removed_keys:
            removed.append(
                {
                    "track": row.get("track"),
                    "kind": row.get("kind"),
                    "value": row.get("value"),
                    "removedAt": now_iso(),
                }
            )
            removed_keys.add(key)
    ledger["added"] = still_added


def blocked_values(
    ledger: dict[str, Any],
    track: dict[str, Any],
    kind: str,
    manual_profile: dict[str, Any] | None = None,
) -> set[str]:
    slug = str(track.get("slug"))
    blocked = {
        normalize_term(str(row.get("value")))
        for row in ledger.get("removed", [])
        if row.get("track") == slug and row.get("kind") == kind
    }
    ignored = track.get("ignoredRecommendations") or {}
    ignored_kind = {
        "keywords": "keywords",
        "people": "people",
        "sampleCompanies": "companies",
        "sources": "sources",
    }[kind]
    for value in ignored.get(ignored_kind, []) or []:
        blocked.add(normalize_term(str(value)))
    # A queued/rejected manual identity is a human decision, regardless of
    # whether a later heuristic tries to classify the same spelling as a
    # keyword, person, company or source.
    blocked.update(manual_held_values(manual_profile or {}, slug))
    if kind == "sources":
        blocked.update(
            f"host:{host}"
            for host in manual_held_source_hosts(manual_profile or {}, slug)
        )
    return blocked


def value_is_blocked(blocked: set[str], value: str) -> bool:
    host = canonical_source_host(value) if "://" in value else ""
    return (
        normalize_term(value) in blocked
        or normalize_manual_identity(value) in blocked
        or bool(host and f"host:{host}" in blocked)
    )


def selected_manual_seed_rows(
    manual_profile: dict[str, Any] | None, slug: str
) -> list[dict[str, Any]]:
    profile_track = (
        (manual_profile or {}).get("tracks", {}).get(slug, {})
        if isinstance(manual_profile, dict)
        else {}
    )
    rows = profile_track.get("seedTerms", []) if isinstance(profile_track, dict) else []
    eligible = [
        row
        for row in rows
        if isinstance(row, dict)
        and clean_candidate(str(row.get("value") or ""))
        and (row.get("pinned") is True or float(row.get("score") or 0) >= 2.0)
    ]
    # Explicit v2 pins get the first two protected slots.  Noisy legacy browser
    # history may fill at most one remaining slot, never both.
    manual_rows = [row for row in eligible if row.get("pinned") is True][:2]
    legacy_rows = [
        row
        for row in eligible
        if row.get("pinned") is not True
        and normalize_term(str(row.get("value") or ""))
        not in {normalize_term(str(item.get("value") or "")) for item in manual_rows}
    ]
    if len(manual_rows) < 2:
        manual_rows.extend(legacy_rows[:1])
    return manual_rows[:2]


def track_seed_terms(
    track: dict[str, Any],
    seeding: bool,
    manual_profile: dict[str, Any] | None = None,
) -> list[str]:
    slug = str(track.get("slug") or "")
    track_name = str(track.get("name") or "")
    manual_rows = selected_manual_seed_rows(manual_profile, slug)
    manual_candidates: list[str] = []
    for row in manual_rows:
        value = str(row.get("value") or "")
        if row.get("kind") in {"people", "sampleCompanies"} and track_name:
            value = f"{value} {track_name}"
        manual_candidates.append(value)
    actor_candidates: list[str] = []
    if not seeding:
        for company in (track.get("sampleCompanies") or [])[:1]:
            actor_candidates.append(
                f"{company} {track_name}" if track_name else str(company)
            )
        for person in (track.get("people") or [])[:1]:
            person_name = re.sub(r"@\S+", "", str(person)).strip()
            actor_candidates.append(
                f"{person_name} {track_name}" if track_name else person_name
            )

    # Eight-query planner.  Reserve one company and one person exploration
    # query, keep track identity + at least three core technologies, then place
    # up to two manual signals.  If a pinned signal duplicates a compiled core
    # keyword, backfill from later core terms rather than wasting the slot.
    actor_unique: list[str] = []
    actor_seen: set[str] = set()
    for candidate in actor_candidates:
        cleaned = clean_candidate(candidate)
        key = normalize_term(cleaned)
        if cleaned and key not in actor_seen:
            actor_seen.add(key)
            actor_unique.append(cleaned)
    actor_unique = actor_unique[:2]
    non_actor_limit = max(0, 8 - len(actor_unique))
    core_candidates = [track_name]
    if not seeding:
        core_candidates.extend(str(value) for value in (track.get("keywords") or []))
    unique: list[str] = []
    seen: set[str] = set()

    def add(seed: str) -> None:
        cleaned = clean_candidate(seed)
        key = normalize_term(cleaned)
        if cleaned and key not in seen and len(unique) < non_actor_limit:
            seen.add(key)
            unique.append(cleaned)

    core_index = 0
    while core_index < len(core_candidates) and len(unique) < min(4, non_actor_limit):
        add(core_candidates[core_index])
        core_index += 1
    for seed in manual_candidates:
        add(seed)
    while core_index < len(core_candidates) and len(unique) < non_actor_limit:
        add(core_candidates[core_index])
        core_index += 1
    for seed in actor_unique:
        cleaned = clean_candidate(seed)
        key = normalize_term(cleaned)
        if cleaned and key not in seen:
            seen.add(key)
            unique.append(cleaned)
    # A pinned company/person is normally already present in the runtime actor
    # arrays, so its contextual manual and actor queries can be identical.  If
    # final cross-bucket deduplication frees a reserved actor slot, backfill it
    # from the remaining core technologies.
    while core_index < len(core_candidates) and len(unique) < 8:
        cleaned = clean_candidate(core_candidates[core_index])
        core_index += 1
        key = normalize_term(cleaned)
        if cleaned and key not in seen:
            seen.add(key)
            unique.append(cleaned)
    return unique[:8]


def has_cjk(value: str) -> bool:
    return bool(re.search(r"[㐀-鿿]", value))


def google_news_titles(
    client: PublicWebClient, query: str, chinese: bool
) -> list[str]:
    encoded = quote_plus(query)
    locale = (
        "hl=zh-CN&gl=CN&ceid=CN:zh-Hans" if chinese else "hl=en-US&gl=US&ceid=US:en"
    )
    body = client.text(
        f"https://news.google.com/rss/search?q={encoded}&{locale}",
    )
    titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", body)
    # First <title> is the channel's own name.
    return [decode_html(title) for title in titles[1:]][:20]


def decode_html(value: str) -> str:
    return (
        value.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )


def gather_candidates(
    client: PublicWebClient,
    track: dict[str, Any],
    seeds: list[str],
    corpus_row: dict[str, Any] | None,
    seeding: bool,
) -> dict[str, Candidate]:
    """Merge the corpus (primary), industry news, and reference-web signals.

    Professional-first ranking: entities recurring in the track's own
    accepted articles score highest, fresh news co-occurrence confirms them,
    and encyclopedia relations only supplement — the track NAME is never fed
    to Wikipedia in expand mode, which is what used to surface textbook
    physics terms instead of industry vocabulary.
    """

    pool: dict[str, Candidate] = {}
    track_name = clean_candidate(str(track.get("name") or ""))

    def bump(value: str, weight: float, evidence: str, hint: str = "") -> None:
        cleaned = clean_candidate(value)
        if not cleaned or len(cleaned) > 60:
            return
        key = normalize_term(cleaned)
        if not key or any(normalize_term(seed) == key for seed in seeds):
            return
        candidate = pool.setdefault(key, Candidate(value=cleaned))
        candidate.score += weight
        candidate.evidence.add(evidence)
        if hint and not candidate.hint:
            candidate.hint = hint

    if corpus_row:
        for company, count in corpus_row["companies"].most_common(15):
            if count >= 2:
                bump(
                    company,
                    1.8 + min(1.8, 0.6 * count),
                    "corpus-company",
                    hint="company",
                )
        for person, count in corpus_row["people"].most_common(10):
            if count >= 2:
                bump(person, 2.0 + min(1.6, 0.6 * count), "corpus-person", hint="person")
        for term, count in corpus_row["terms"].most_common(60):
            if count < 3 or len(corpus_row["termSources"].get(term, ())) < 2:
                continue
            # Pure-Latin fragments below three characters are almost always
            # broken tokens ("SK" from SK海力士), not standalone terms.
            if re.fullmatch(r"[A-Za-z]{1,2}", term):
                continue
            bump(term, 1.2 + min(1.8, 0.3 * count), "corpus-term")

    news_titles: list[str] = []
    news_seeds = [track_name, *seeds[:1]] if track_name else seeds[:2]
    for query in dict.fromkeys(filter(None, news_seeds)):
        try:
            news_titles += google_news_titles(client, query, has_cjk(query))
        except BudgetExhausted:
            break
    for title in news_titles:
        for term in extract_title_terms(title):
            bump(term, 0.6, "news-term")

    for seed in seeds:
        if not seeding and track_name and normalize_term(seed) == normalize_term(track_name):
            continue
        lang = "zh" if has_cjk(seed) else "en"
        try:
            title = wikipedia_resolve(client, seed, lang)
            if title:
                # Seeding a brand-new track has no corpus yet, so reference
                # relations stay a first-class signal there.
                for related in wikipedia_morelike(client, title, lang):
                    bump(related, 2.0 if seeding else 1.5, "wikipedia-morelike")
            if has_cjk(seed):
                for suggestion in baidu_suggest(client, seed):
                    bump(suggestion, 1.0, "baidu-suggest")
            else:
                for suggestion in google_suggest(client, seed):
                    bump(suggestion, 1.0, "google-suggest")
                for concept in openalex_related_concepts(client, seed):
                    bump(concept, 1.2, "openalex-related")
        except BudgetExhausted:
            break

    # Fresh-news co-occurrence confirms a candidate as active industry
    # vocabulary rather than reference-only language.
    if news_titles:
        lowered_titles = [title.lower() for title in news_titles]
        for candidate in pool.values():
            if "news-term" in candidate.evidence and len(candidate.evidence) == 1:
                continue
            needle = candidate.value.lower()
            if len(needle) >= 2 and any(needle in title for title in lowered_titles):
                candidate.score += 1.5
                candidate.evidence.add("news-confirmed")
    return pool


def expand_track(
    client: PublicWebClient,
    config: dict[str, Any],
    ledger: dict[str, Any],
    track: dict[str, Any],
    all_track_names: set[str],
    corpus_row: dict[str, Any] | None,
    dry_run: bool,
    manual_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    seeding = not (track.get("keywords") or [])
    seeds = track_seed_terms(track, seeding, manual_profile)
    summary = {
        "track": track.get("slug"),
        "mode": "seed" if seeding else "expand",
        "manualSeeds": [
            clean_candidate(str(row.get("value") or ""))
            for row in selected_manual_seed_rows(
                manual_profile, str(track.get("slug") or "")
            )
        ],
        "added": {"keywords": [], "people": [], "sampleCompanies": [], "sources": []},
    }
    if not seeds:
        return summary

    pool = gather_candidates(client, track, seeds, corpus_row, seeding)
    threshold = SEED_ACCEPT_THRESHOLD if seeding else ACCEPT_THRESHOLD
    ranked = sorted(
        (c for c in pool.values() if c.score >= threshold),
        key=lambda c: c.score,
        reverse=True,
    )

    existing = {
        kind: {
            normalize_term(value)
            for value in config_values(track, kind, config)
        }
        for kind in ("keywords", "people", "sampleCompanies", "sources")
    }
    existing_all = (
        existing["keywords"] | existing["people"] | existing["sampleCompanies"]
    )
    # Entities configured under ANY track stay where they are: articles that
    # span tracks (an AI-chip story naming OpenAI) must not leak one track's
    # companies into another track's keyword list.
    for other in config.get("tracks", []):
        for kind in ("keywords", "people", "sampleCompanies"):
            for value in other.get(kind) or []:
                cleaned = re.sub(r"@\S+", "", str(value)).strip()
                if cleaned:
                    existing_all.add(normalize_term(cleaned))
    for listed in config.get("listedCompanies", []):
        for field_name in ("name", "ticker"):
            cleaned = clean_candidate(str(listed.get(field_name) or ""))
            if cleaned:
                existing_all.add(normalize_term(cleaned))
    for source in config.get("sources", []):
        cleaned = clean_candidate(str(source.get("company") or ""))
        if cleaned:
            existing_all.add(normalize_term(cleaned))
    blocked = {
        kind: blocked_values(ledger, track, kind, manual_profile)
        for kind in ("keywords", "people", "sampleCompanies", "sources")
    }

    caps = {
        "keywords": MAX_SEED_KEYWORDS if seeding else MAX_KEYWORDS_PER_RUN,
        "people": 0 if seeding else MAX_PEOPLE_PER_RUN,
        "sampleCompanies": 0 if seeding else MAX_COMPANIES_PER_RUN,
        "sources": 0 if seeding else MAX_SOURCES_PER_RUN,
    }
    if len(track.get("keywords") or []) >= MAX_TRACK_KEYWORDS:
        caps["keywords"] = 0
    if len(track.get("people") or []) >= MAX_TRACK_PEOPLE:
        caps["people"] = 0
    if len(track.get("sampleCompanies") or []) >= MAX_TRACK_COMPANIES:
        caps["sampleCompanies"] = 0

    added = summary["added"]
    for candidate in ranked:
        if (
            len(added["keywords"]) >= caps["keywords"]
            and len(added["people"]) >= caps["people"]
            and len(added["sampleCompanies"]) >= caps["sampleCompanies"]
        ):
            break
        value_key = normalize_term(candidate.value)
        if value_key in existing_all or value_key in existing["sources"]:
            continue
        if normalize_term(candidate.value) in {
            normalize_term(name) for name in all_track_names
        }:
            continue

        info: dict[str, Any] = {}
        # Only spend classification requests on strong multi-source candidates.
        if not seeding and len(candidate.evidence) >= 1 and candidate.score >= threshold:
            try:
                info = wikidata_lookup(client, candidate.value)
            except BudgetExhausted:
                info = {}
        # Corpus hints break ties for entities Wikidata does not know yet
        # (young startups, Chinese investors): the crawler already labelled
        # them as company/person context in accepted articles.
        kind = str(info.get("kind") or candidate.hint or "keyword")

        if kind == "person" and caps["people"] > len(added["people"]):
            label = validate_person(candidate.value, str(info.get("handle") or ""))
            if not label or value_is_blocked(blocked["people"], label):
                continue
            if normalize_term(label) in existing["people"]:
                continue
            added["people"].append(label)
            existing["people"].add(normalize_term(label))
            existing_all.add(value_key)
            continue

        if kind == "company" and caps["sampleCompanies"] > len(added["sampleCompanies"]):
            company = clean_candidate(candidate.value)[:60]
            if not company or value_is_blocked(blocked["sampleCompanies"], company):
                continue
            added["sampleCompanies"].append(company)
            existing["sampleCompanies"].add(normalize_term(company))
            existing_all.add(value_key)
            website = str(info.get("website") or "")
            if (
                website.startswith("http")
                and caps["sources"] > len(added["sources"])
                and not value_is_blocked(blocked["sources"], website)
                and normalize_term(website) not in existing["sources"]
            ):
                added["sources"].append(
                    {
                        "id": f"source-auto-{slugify(company)}",
                        "name": f"{company} 官方网站",
                        "url": website,
                        "sourceType": "listing-search",
                        "sourceCategory": "company",
                        "region": str(info.get("region") or "全球"),
                        "sector": str(track.get("name") or "未分类"),
                        "company": company,
                        "ticker": "",
                        "keywords": [company],
                        "enabled": True,
                    }
                )
                existing["sources"].add(normalize_term(website))
            continue

        if caps["keywords"] > len(added["keywords"]):
            if not seeding and not candidate_has_professional_evidence(candidate):
                continue
            keyword = validate_keyword(candidate.value)
            if not keyword or value_is_blocked(blocked["keywords"], keyword):
                continue
            if normalize_term(keyword) in existing["keywords"]:
                continue
            added["keywords"].append(keyword)
            existing["keywords"].add(normalize_term(keyword))
            existing_all.add(value_key)

    # Tracks with diverse seeds (e.g. GPU / 先进封装 / LPU) rarely produce
    # cross-seed candidates, so nothing clears the strict threshold. Relax to
    # the seeding threshold for keywords only, capped small, so every track
    # with usable web results moves forward instead of staying frozen.
    if (
        not seeding
        and not any(added[kind] for kind in added)
        and caps["keywords"] > 0
    ):
        relaxed = sorted(
            (
                candidate
                for candidate in pool.values()
                if RELAXED_ACCEPT_THRESHOLD <= candidate.score < threshold
                and candidate_has_professional_evidence(candidate)
            ),
            key=lambda candidate: candidate.score,
            reverse=True,
        )
        for candidate in relaxed:
            if len(added["keywords"]) >= 3:
                break
            value_key = normalize_term(candidate.value)
            if value_key in existing_all or value_key in existing["sources"]:
                continue
            if value_key in {normalize_term(name) for name in all_track_names}:
                continue
            keyword = validate_keyword(candidate.value)
            if not keyword or value_is_blocked(blocked["keywords"], keyword):
                continue
            if normalize_term(keyword) in existing["keywords"]:
                continue
            added["keywords"].append(keyword)
            existing["keywords"].add(normalize_term(keyword))
            existing_all.add(value_key)
        if added["keywords"]:
            summary["relaxed"] = True

    # Promote repeatedly productive but unconfigured publishers into media
    # sources: domains that already delivered ≥2 accepted articles for this
    # track are proven professional outlets for it.
    if corpus_row and caps["sources"] > len(added["sources"]):
        existing_hosts = {
            source_host(str(source.get("url") or ""))
            for source in config.get("sources", [])
            if normalize_term(str(source.get("sector") or ""))
            == normalize_term(str(track.get("name") or ""))
        }
        existing_hosts.discard("")
        ranked_hosts = sorted(
            corpus_row["sources"].items(),
            key=lambda item: (
                float(item[1]["count"])
                + min(
                    5,
                    manual_source_affinity(
                        manual_profile or {}, str(track.get("slug") or ""), item[0]
                    ),
                )
                * 0.5,
                item[1]["count"],
            ),
            reverse=True,
        )
        for host, srow in ranked_hosts:
            if len(added["sources"]) >= caps["sources"]:
                break
            if srow["count"] < 2 or host in existing_hosts:
                continue
            url = f"https://{host}/"
            if (
                value_is_blocked(blocked["sources"], url)
                or normalize_term(url) in existing["sources"]
            ):
                continue
            top_names = srow["names"].most_common(1)
            name = strip_discovery_source_suffix(
                clean_candidate(top_names[0][0]) if top_names else host
            )
            region = (
                srow["regions"].most_common(1)[0][0]
                if srow["regions"]
                else "全球"
            )
            if region not in {"中国", "美国", "全球"}:
                region = "全球"
            added["sources"].append(
                {
                    "id": (
                        f"source-auto-media-{slugify(host)}-"
                        f"{slugify(str(track.get('slug') or track.get('name') or 'track'))}"
                    ),
                    "name": f"{name or host} · {track.get('name')}信源",
                    "url": url,
                    "sourceType": "listing-search",
                    "sourceCategory": "media",
                    "region": region,
                    "sector": str(track.get("name") or "未分类"),
                    "company": "",
                    "ticker": "",
                    "keywords": [str(track.get("name") or "")],
                    "enabled": True,
                }
            )
            existing["sources"].add(normalize_term(url))
            existing_hosts.add(host)

    summary["poolSize"] = len(pool)
    if dry_run:
        return summary

    stamp = now_iso()
    for kind in ("keywords", "people", "sampleCompanies"):
        for value in added[kind]:
            track.setdefault(kind, []).append(value)
            ledger["added"].append(
                {
                    "track": track.get("slug"),
                    "kind": kind,
                    "value": value,
                    "addedAt": stamp,
                    "evidence": sorted(
                        pool.get(normalize_term(value), Candidate(value)).evidence
                    ),
                }
            )
    existing_source_ids = {
        str(source.get("id")) for source in config.get("sources", [])
    }
    existing_source_urls = {
        normalize_term(str(source.get("url") or ""))
        for source in config.get("sources", [])
    }
    for source in added["sources"]:
        if source["id"] in existing_source_ids:
            source["id"] = f"{source['id']}-{len(existing_source_ids)}"
        if normalize_term(source["url"]) in existing_source_urls:
            continue
        config.setdefault("sources", []).append(source)
        existing_source_ids.add(source["id"])
        existing_source_urls.add(normalize_term(source["url"]))
        ledger["added"].append(
            {
                "track": track.get("slug"),
                "kind": "sources",
                "value": source["url"],
                "addedAt": stamp,
                "evidence": [
                    "corpus-proven-publisher"
                    if str(source.get("sourceCategory") or "") == "media"
                    else "wikidata-official-site"
                ],
            }
        )
    ledger.setdefault("tracks", {})[str(track.get("slug"))] = {
        "lastExpandedAt": stamp
    }
    return summary


def pick_tracks(
    config: dict[str, Any],
    ledger: dict[str, Any],
    only_track: str,
    seed_only: bool,
    max_tracks: int,
) -> list[dict[str, Any]]:
    enabled = [track for track in config.get("tracks", []) if track.get("enabled")]
    if only_track:
        return [track for track in enabled if track.get("slug") == only_track]
    seeding = [track for track in enabled if not (track.get("keywords") or [])]
    if seed_only:
        return seeding
    expandable = [track for track in enabled if track.get("keywords")]

    def last_expanded(track: dict[str, Any]) -> str:
        row = (ledger.get("tracks") or {}).get(str(track.get("slug"))) or {}
        return str(row.get("lastExpandedAt") or "")

    expandable.sort(key=last_expanded)
    remaining = max(0, max_tracks - len(seeding))
    return seeding + expandable[:remaining]


def run(argv: list[str] | None = None, fetch_text: FetchText | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--seed-new-only",
        action="store_true",
        help="only seed brand-new tracks that still have no keywords",
    )
    parser.add_argument("--only-track", default="")
    parser.add_argument("--max-tracks", type=int, default=4)
    parser.add_argument("--max-requests", type=int, default=150)
    args = parser.parse_args(argv)

    config = load_json(CONFIG_PATH, None)
    if not isinstance(config, dict) or not config.get("tracks"):
        print(json.dumps({"error": "config/user_tracking.json unreadable"}))
        return 1
    ledger = load_json(LEDGER_PATH, empty_ledger())
    if not isinstance(ledger, dict):
        ledger = empty_ledger()
    for key, fallback in empty_ledger().items():
        ledger.setdefault(key, fallback)

    sync_tombstones(ledger, config)
    pruned = prune_low_quality_auto_entries(ledger, config)

    tracks = pick_tracks(
        config, ledger, args.only_track, args.seed_new_only, args.max_tracks
    )
    all_track_names = {
        str(track.get("name") or "") for track in config.get("tracks", [])
    }

    client = PublicWebClient(args.max_requests, fetch_text=fetch_text)
    corpus = load_track_corpus()
    manual_profile = load_manual_feedback(
        capture_path=MANUAL_CAPTURE_PATH,
        intents_path=MANUAL_INTENTS_PATH,
        runtime_path=MANUAL_RUNTIME_PATH,
    )
    summaries = []
    for track in tracks:
        summaries.append(
            expand_track(
                client,
                config,
                ledger,
                track,
                all_track_names,
                corpus.get(str(track.get("slug"))),
                args.dry_run,
                manual_profile,
            )
        )

    if (
        client.used_requests > 0
        and client.failed_requests == client.used_requests
        and not pruned
    ):
        # Fully offline: honor the no-fabrication contract — even corpus-only
        # additions wait for a run that can cross-check the public web.
        print(
            json.dumps(
                {
                    "changed": False,
                    "offline": True,
                    "requestsUsed": client.used_requests,
                    "requestsFailed": client.failed_requests,
                    "tracks": [],
                    "pruned": [],
                    "manualFeedback": {
                        "rawHistoryRecords": manual_profile.get("rawHistoryRecords", 0),
                        "historyRecords": manual_profile.get("historyRecords", 0),
                        "ignoredHistoryRecords": manual_profile.get(
                            "ignoredHistoryRecords", 0
                        ),
                        "heldSignals": manual_profile.get("heldSignals", 0),
                    },
                },
                ensure_ascii=False,
            )
        )
        return 0

    changed = bool(pruned) or any(
        any(summary["added"][kind] for kind in summary["added"])
        for summary in summaries
    )
    tombstoned = bool(ledger.get("removed"))
    if not args.dry_run and (changed or tombstoned):
        ledger["updatedAt"] = now_iso()
        LEDGER_PATH.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if not args.dry_run and changed:
        CONFIG_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "changed": changed,
                "requestsUsed": client.used_requests,
                "requestsFailed": client.failed_requests,
                "tracks": summaries,
                "pruned": pruned,
                "manualFeedback": {
                    "rawHistoryRecords": manual_profile.get("rawHistoryRecords", 0),
                    "historyRecords": manual_profile.get("historyRecords", 0),
                    "ignoredHistoryRecords": manual_profile.get(
                        "ignoredHistoryRecords", 0
                    ),
                    "appliedSignals": manual_profile.get("appliedSignals", 0),
                    "heldSignals": manual_profile.get("heldSignals", 0),
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())
