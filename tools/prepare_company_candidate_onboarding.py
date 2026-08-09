#!/usr/bin/env python3
"""Prepare safe automatic onboarding requests for accepted company candidates.

This is the bridge between entity acceptance and formal company publication. It
never treats a model as an authority for identity or source discovery.

Automatic onboarding requires all of the following:

* the candidate already has a versioned ``accepted`` decision;
* the candidate is not obviously an investment institution/person-like object;
* an official homepage comes from an existing official-source record or an exact
  public Wikidata identity match;
* the fetched official page names the candidate and supports its tracked sector;
* summary/product text is synthesized only from the verified official page, and
  the model returns verbatim support snippets that are found on that page;
* the existing onboarding quality gate remains the final publication authority.

If any condition is uncertain, the candidate stays accepted and is reported as an
exception. No homepage, identity or factual profile field is invented by the LLM.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import unicodedata
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

try:
    from . import onboard_company_candidates as onboarding
    from .research_agent import call_siliconflow
except ImportError:  # pragma: no cover - direct execution
    import onboard_company_candidates as onboarding  # type: ignore
    from research_agent import call_siliconflow  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_PATH = ROOT / "config" / "company_candidate_review_queue.json"
DECISIONS_PATH = ROOT / "config" / "company_candidate_decisions.json"
OFFICIAL_SOURCES_PATH = ROOT / "config" / "official_company_sources.json"
REGISTRY_PATH = onboarding.REGISTRY_PATH
CAPTURES_PATH = ROOT / "config" / "tracking_capture_inbox.json"

DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V4-Flash"
USER_AGENT = "VCIQ-Auto-Company-Onboarding/1.0 (+https://github.com/VCIQ/VCIQ.github.io)"
REQUEST_TIMEOUT = 14
MAX_PAGE_BYTES = 2_000_000
MAX_MODEL_TEXT = 14_000
MAX_AUTO_REQUESTS = 6

INSTITUTION_SECTORS = {
    "风险投资",
    "投资机构",
    "私募股权",
    "基金",
    "venture capital",
    "private equity",
}
INSTITUTION_NAME_RE = re.compile(
    r"(?:\b(?:growth\s+capital|venture\s+capital|ventures?|investment\s+partners?|"
    r"investment\s+management|asset\s+management|fund)\b|资本|创投|基金|投资管理)$",
    re.IGNORECASE,
)

SECTOR_TERMS: dict[str, tuple[str, ...]] = {
    "AI / AGI": (
        "artificial intelligence",
        "ai infrastructure",
        "ai computing",
        "ai chip",
        "ai accelerator",
        "machine learning",
        "人工智能",
        "智能算力",
        "大模型",
    ),
    "机器人": ("robotics", "robot", "humanoid", "机器人", "具身智能"),
    "半导体": ("semiconductor", "chip", "silicon", "processor", "半导体", "芯片"),
    "新能源": ("energy", "battery", "solar", "storage", "新能源", "电池", "储能"),
    "生物科技": ("biotech", "biotechnology", "drug discovery", "genomics", "生物", "制药"),
    "量子计算": ("quantum", "量子"),
    "商业航天": ("space", "satellite", "launch", "rocket", "航天", "卫星", "火箭"),
    "Web3": ("blockchain", "crypto", "stablecoin", "web3", "区块链", "数字资产"),
    "新材料": ("materials", "material", "新材料", "材料"),
    "智能制造": ("manufacturing", "industrial", "automation", "制造", "工业"),
    "可控核聚变": ("fusion", "tokamak", "聚变", "托卡马克"),
    "新消费": ("commerce", "consumer", "retail", "消费", "零售", "电商"),
    "智能交通": ("mobility", "transport", "autonomous driving", "交通", "自动驾驶"),
}

COUNTRY_LABELS = {
    "united states of america": "美国",
    "united states": "美国",
    "china": "中国",
    "people's republic of china": "中国",
    "canada": "加拿大",
    "united kingdom": "英国",
    "germany": "德国",
    "france": "法国",
    "australia": "澳大利亚",
    "singapore": "新加坡",
    "japan": "日本",
    "south korea": "韩国",
    "republic of korea": "韩国",
    "switzerland": "瑞士",
    "israel": "以色列",
    "india": "印度",
    "brazil": "巴西",
    "taiwan": "台湾",
}


def clean(value: Any, limit: int = 2_000) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def identity_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", clean(value, 240).casefold())


def safe_http_url(value: Any) -> str:
    url = clean(value, 2_000)
    try:
        parsed = urlsplit(url)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    return url


def unique(values: list[Any], limit: int = 30) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = clean(raw, 500)
        key = value.casefold()
        if not value or key in seen:
            continue
        result.append(value)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0).isoformat()


def _claim_value(row: Any) -> Any:
    if not isinstance(row, dict):
        return None
    return row.get("mainsnak", {}).get("datavalue", {}).get("value")


def _claim_strings(claims: Mapping[str, Any], prop: str) -> list[str]:
    rows = claims.get(prop, [])
    if not isinstance(rows, list):
        return []
    return [value for row in rows if isinstance((value := _claim_value(row)), str) and value]


def _claim_entity_ids(claims: Mapping[str, Any], prop: str) -> list[str]:
    rows = claims.get(prop, [])
    if not isinstance(rows, list):
        return []
    result: list[str] = []
    for row in rows:
        value = _claim_value(row)
        if not isinstance(value, dict):
            continue
        entity_id = clean(value.get("id"), 40)
        if entity_id:
            result.append(entity_id)
    return result


def _claim_year(claims: Mapping[str, Any]) -> str:
    rows = claims.get("P571", [])
    if not isinstance(rows, list):
        return ""
    for row in rows:
        value = _claim_value(row)
        if not isinstance(value, dict):
            continue
        timestamp = clean(value.get("time"), 80)
        match = re.match(r"^[+-](\d{4})-", timestamp)
        if match:
            return match.group(1)
    return ""


def _label(entity: Mapping[str, Any], language: str) -> str:
    labels = entity.get("labels", {})
    if not isinstance(labels, dict):
        return ""
    row = labels.get(language)
    return clean(row.get("value"), 240) if isinstance(row, dict) else ""


def _aliases(entity: Mapping[str, Any], language: str) -> list[str]:
    aliases = entity.get("aliases", {})
    rows = aliases.get(language, []) if isinstance(aliases, dict) else []
    if not isinstance(rows, list):
        return []
    return [
        clean(row.get("value"), 240)
        for row in rows
        if isinstance(row, dict) and clean(row.get("value"), 240)
    ]


def _description(entity: Mapping[str, Any], language: str) -> str:
    descriptions = entity.get("descriptions", {})
    row = descriptions.get(language) if isinstance(descriptions, dict) else None
    return clean(row.get("value"), 500) if isinstance(row, dict) else ""


def _http_json(url: str, *, timeout: int = REQUEST_TIMEOUT) -> Any:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _wikidata_api(
    params: Mapping[str, Any], *, fetch_json: Callable[[str], Any] = _http_json
) -> Any:
    url = "https://www.wikidata.org/w/api.php?" + urlencode(params)
    return fetch_json(url)


def resolve_wikidata_company(
    name: str,
    *,
    fetch_json: Callable[[str], Any] = _http_json,
) -> tuple[dict[str, Any] | None, str]:
    """Resolve one exact Wikidata identity and its official website.

    Fuzzy search alone is never accepted. A returned item must contain an exact
    normalized label/alias match for the candidate name and exactly one official
    website host. Human (Q5) identities are rejected explicitly.
    """

    query = clean(name, 160)
    if not query:
        return None, "empty candidate name"
    try:
        search = _wikidata_api(
            {
                "action": "wbsearchentities",
                "search": query,
                "language": "en",
                "uselang": "en",
                "type": "item",
                "format": "json",
                "limit": 6,
            },
            fetch_json=fetch_json,
        )
    except Exception as exc:
        return None, f"wikidata search {type(exc).__name__}"
    rows = search.get("search", []) if isinstance(search, dict) else []
    ids = [
        clean(row.get("id"), 30)
        for row in rows
        if isinstance(row, dict) and clean(row.get("id"), 30)
    ]
    if not ids:
        return None, "wikidata returned no candidate"
    try:
        payload = _wikidata_api(
            {
                "action": "wbgetentities",
                "ids": "|".join(ids),
                "props": "labels|aliases|descriptions|claims",
                "languages": "zh|en",
                "format": "json",
            },
            fetch_json=fetch_json,
        )
    except Exception as exc:
        return None, f"wikidata entity fetch {type(exc).__name__}"
    entities = payload.get("entities", {}) if isinstance(payload, dict) else {}
    wanted = identity_key(query)
    exact: list[tuple[str, dict[str, Any]]] = []
    if isinstance(entities, dict):
        for entity_id, raw in entities.items():
            if not isinstance(raw, dict):
                continue
            names = [
                _label(raw, "zh"),
                _label(raw, "en"),
                *_aliases(raw, "zh"),
                *_aliases(raw, "en"),
            ]
            if any(identity_key(value) == wanted for value in names if value):
                exact.append((str(entity_id), raw))
    if len(exact) != 1:
        return None, "wikidata identity is ambiguous" if exact else "wikidata has no exact identity"

    entity_id, entity = exact[0]
    claims = entity.get("claims", {}) if isinstance(entity.get("claims"), dict) else {}
    if "Q5" in _claim_entity_ids(claims, "P31"):
        return None, "wikidata exact identity is a person"
    homepages = unique(
        [safe_http_url(value) for value in _claim_strings(claims, "P856") if safe_http_url(value)],
        5,
    )
    hosts = {
        urlsplit(url).hostname.casefold()
        for url in homepages
        if urlsplit(url).hostname
    }
    if not homepages:
        return None, "wikidata exact identity has no official website"
    if len(hosts) != 1:
        return None, "wikidata exact identity has multiple official website hosts"

    related_ids = unique(
        [*_claim_entity_ids(claims, "P17"), *_claim_entity_ids(claims, "P159")],
        12,
    )
    related: dict[str, Any] = {}
    if related_ids:
        try:
            related_payload = _wikidata_api(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(related_ids),
                    "props": "labels",
                    "languages": "zh|en",
                    "format": "json",
                },
                fetch_json=fetch_json,
            )
            raw_related = (
                related_payload.get("entities", {})
                if isinstance(related_payload, dict)
                else {}
            )
            related = raw_related if isinstance(raw_related, dict) else {}
        except Exception:
            related = {}

    country_ids = _claim_entity_ids(claims, "P17")
    region = ""
    if country_ids:
        row = related.get(country_ids[0], {}) if isinstance(related, dict) else {}
        if isinstance(row, dict):
            english_country = _label(row, "en")
            region = _label(row, "zh") or COUNTRY_LABELS.get(
                english_country.casefold(), english_country
            )
    headquarters_ids = _claim_entity_ids(claims, "P159")
    headquarters = ""
    if headquarters_ids:
        row = related.get(headquarters_ids[0], {}) if isinstance(related, dict) else {}
        if isinstance(row, dict):
            headquarters = _label(row, "zh") or _label(row, "en")

    canonical = _label(entity, "zh") or _label(entity, "en") or query
    english = _label(entity, "en")
    return (
        {
            "source": "wikidata",
            "sourceId": entity_id,
            "canonicalName": canonical,
            "englishName": english,
            "homepage": homepages[0],
            "region": region,
            "founded": _claim_year(claims),
            "headquarters": headquarters,
            "aliases": unique([*_aliases(entity, "zh"), *_aliases(entity, "en")], 20),
            "description": _description(entity, "zh") or _description(entity, "en"),
        },
        "",
    )


class OfficialPageParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.text_parts: list[str] = []
        self.links: list[str] = []
        self._title_depth = 0
        self._text_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        tag = tag.casefold()
        if tag == "title":
            self._title_depth += 1
        if tag in {"h1", "h2", "h3", "p", "li"}:
            self._text_depth += 1
        if tag == "meta":
            key = (values.get("property") or values.get("name") or "").casefold()
            content = clean(values.get("content"), 1_500)
            if key and content:
                self.meta[key] = content
        if tag == "a" and values.get("href"):
            url = safe_http_url(urljoin(self.base_url, values["href"]))
            if url:
                self.links.append(url)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
        if tag in {"h1", "h2", "h3", "p", "li"} and self._text_depth:
            self._text_depth -= 1

    def handle_data(self, data: str) -> None:
        value = clean(data, 2_000)
        if not value:
            return
        if self._title_depth:
            self.title_parts.append(value)
        if self._text_depth:
            self.text_parts.append(value)


def fetch_official_page(url: str, *, timeout: int = REQUEST_TIMEOUT) -> dict[str, Any]:
    homepage = safe_http_url(url)
    if not homepage:
        raise ValueError("invalid official homepage")
    request = Request(
        homepage,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.6",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(MAX_PAGE_BYTES + 1)
        if len(raw) > MAX_PAGE_BYTES:
            raise ValueError("official homepage response too large")
        final_url = safe_http_url(response.geturl()) or homepage
        content_type = response.headers.get("Content-Type", "")
    match = re.search(r"charset=([A-Za-z0-9._-]+)", content_type, re.IGNORECASE)
    encodings = [match.group(1)] if match else []
    encodings.extend(["utf-8", "gb18030", "big5", "latin-1"])
    body = ""
    for encoding in encodings:
        try:
            body = raw.decode(encoding)
            break
        except (LookupError, UnicodeDecodeError):
            continue
    if not body:
        body = raw.decode("utf-8", errors="replace")
    parser = OfficialPageParser(final_url)
    parser.feed(body)
    title = clean(" ".join(parser.title_parts), 500)
    description = clean(
        parser.meta.get("description")
        or parser.meta.get("og:description")
        or parser.meta.get("twitter:description"),
        1_500,
    )
    site_name = clean(parser.meta.get("og:site_name"), 300)
    text = clean(" ".join([site_name, title, description, *parser.text_parts]), 50_000)
    final_host = urlsplit(final_url).hostname or ""
    news_urls: list[str] = []
    for link in parser.links:
        host = urlsplit(link).hostname or ""
        path = urlsplit(link).path.casefold()
        if host.casefold() != final_host.casefold():
            continue
        if any(
            token in path
            for token in ("/news", "/blog", "/press", "/updates", "/insights")
        ):
            news_urls.append(link)
    return {
        "url": final_url,
        "title": title,
        "description": description,
        "siteName": site_name,
        "text": text,
        "newsUrls": unique(news_urls, 5),
    }


def _term_present(text: str, term: str) -> bool:
    haystack = unicodedata.normalize("NFKC", text).casefold()
    needle = unicodedata.normalize("NFKC", term).casefold()
    if re.fullmatch(r"[a-z0-9]{1,4}", needle):
        return bool(
            re.search(
                rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack
            )
        )
    return needle in haystack


def page_supports_identity(page: Mapping[str, Any], names: list[str]) -> bool:
    text = clean(page.get("text"), 50_000)
    if not text:
        return False
    page_key = identity_key(text)
    for name in names:
        key = identity_key(name)
        if len(key) >= 4 and key in page_key:
            return True
    return False


def page_supports_sector(page: Mapping[str, Any], sector: str) -> bool:
    terms = SECTOR_TERMS.get(clean(sector, 120))
    if not terms:
        return True
    text = clean(page.get("text"), 50_000)
    return any(_term_present(text, term) for term in terms)


def candidate_is_institution_like(candidate: Mapping[str, Any]) -> bool:
    sector = clean(candidate.get("sector"), 120).casefold()
    if sector in {value.casefold() for value in INSTITUTION_SECTORS}:
        return True
    name = clean(candidate.get("name"), 240)
    return bool(INSTITUTION_NAME_RE.search(name))


def _official_source_match(
    payload: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any] | None:
    key = identity_key(candidate.get("decisionKey") or candidate.get("name"))
    matches: list[dict[str, Any]] = []
    rows = payload.get("companies", [])
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        aliases = row.get("aliases") if isinstance(row.get("aliases"), list) else []
        names = [row.get("name"), *aliases]
        if any(identity_key(value) == key for value in names if clean(value, 240)):
            homepage = safe_http_url(row.get("homepage"))
            if homepage:
                news = row.get("newsUrls") if isinstance(row.get("newsUrls"), list) else []
                matches.append(
                    {
                        "source": "official-source-registry",
                        "sourceId": clean(row.get("slug"), 120),
                        "canonicalName": clean(row.get("name"), 240)
                        or clean(candidate.get("name"), 240),
                        "englishName": "",
                        "homepage": homepage,
                        "region": clean(row.get("region"), 80),
                        "founded": "",
                        "headquarters": "",
                        "aliases": unique(list(aliases), 20),
                        "description": "",
                        "newsUrls": unique(list(news), 8),
                    }
                )
    return matches[0] if len(matches) == 1 else None


def _registry_match(payload: Mapping[str, Any], candidate: Mapping[str, Any]) -> str:
    key = identity_key(candidate.get("decisionKey") or candidate.get("name"))
    matches: list[str] = []
    rows = payload.get("companies", [])
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        aliases = row.get("aliases") if isinstance(row.get("aliases"), list) else []
        names = [row.get("name"), row.get("englishName"), *aliases]
        if any(identity_key(value) == key for value in names if clean(value, 240)):
            slug = clean(row.get("slug"), 120)
            if slug:
                matches.append(slug)
    return matches[0] if len(set(matches)) == 1 else ""


def _registry_slug_exists(payload: Mapping[str, Any], slug: str) -> bool:
    rows = payload.get("companies", [])
    if not isinstance(rows, list):
        return False
    return any(
        isinstance(row, dict) and clean(row.get("slug"), 120) == slug for row in rows
    )


def _capture_context(
    candidate: Mapping[str, Any], captures_payload: Mapping[str, Any]
) -> list[dict[str, str]]:
    raw_rows = captures_payload.get("records", [])
    rows = raw_rows if isinstance(raw_rows, list) else []
    by_id = {
        clean(row.get("id"), 200): row
        for row in rows
        if isinstance(row, dict) and clean(row.get("id"), 200)
    }
    result: list[dict[str, str]] = []
    ids = candidate.get("captureIds", [])
    for raw_id in ids if isinstance(ids, list) else []:
        row = by_id.get(clean(raw_id, 200))
        if not row:
            continue
        source = row.get("source") if isinstance(row.get("source"), dict) else {}
        result.append(
            {
                "title": clean(source.get("title"), 500),
                "summary": clean(source.get("summary"), 1_500),
                "url": safe_http_url(source.get("url")),
                "eventType": clean(source.get("eventType"), 80),
            }
        )
    return result[:5]


def _normalized_excerpt(value: Any) -> str:
    return clean(value, 50_000).casefold()


def _supported_quotes(quotes: Any, page_text: str) -> list[str]:
    if not isinstance(quotes, list):
        return []
    haystack = _normalized_excerpt(page_text)
    result: list[str] = []
    for raw in quotes[:6]:
        quote = clean(raw, 600)
        normalized = _normalized_excerpt(quote)
        if len(normalized) >= 8 and normalized in haystack:
            result.append(quote)
    return result


def synthesize_official_profile(
    *,
    candidate: Mapping[str, Any],
    metadata: Mapping[str, Any],
    page: Mapping[str, Any],
    capture_context: list[dict[str, str]],
) -> tuple[dict[str, Any] | None, str]:
    api_key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
    if not api_key:
        return None, "SiliconFlow API key unavailable"
    prompt = {
        "instruction": (
            "仅根据 officialPage 中的官方网页文本生成公司简介与核心产品描述。"
            "不得使用模型记忆补充事实，不得把 captureContext 当作公司事实来源；"
            "captureContext 只用于判断该官网是否与候选语境一致。"
            "summary/product 必须各给至少一个来自 officialPage.text 的逐字 support quote。"
            "如果官网与候选不是同一实体，sameEntity=false。输出合法 JSON。"
        ),
        "outputShape": {
            "sameEntity": True,
            "identityConfidence": 0.0,
            "identityReason": "string",
            "summary": "string, 简体中文, 20-500 chars",
            "product": "string, 简体中文, 6-400 chars",
            "summaryEvidence": ["verbatim quote from officialPage.text"],
            "productEvidence": ["verbatim quote from officialPage.text"],
        },
        "candidate": {
            "name": clean(candidate.get("name"), 240),
            "aliases": unique(
                list(candidate.get("aliases") or [])
                if isinstance(candidate.get("aliases"), list)
                else [],
                20,
            ),
            "sector": clean(candidate.get("sector"), 120),
            "eventTypes": unique(
                list(candidate.get("eventTypes") or [])
                if isinstance(candidate.get("eventTypes"), list)
                else [],
                12,
            ),
        },
        "resolvedPublicIdentity": {
            "canonicalName": clean(metadata.get("canonicalName"), 240),
            "englishName": clean(metadata.get("englishName"), 240),
            "description": clean(metadata.get("description"), 500),
            "homepage": safe_http_url(metadata.get("homepage")),
        },
        "captureContext": capture_context,
        "officialPage": {
            "url": safe_http_url(page.get("url")),
            "title": clean(page.get("title"), 500),
            "description": clean(page.get("description"), 1_500),
            "text": clean(page.get("text"), MAX_MODEL_TEXT),
        },
    }
    try:
        raw = call_siliconflow(
            api_key=api_key,
            base_url=os.environ.get("SILICONFLOW_BASE_URL", DEFAULT_BASE_URL).strip()
            or DEFAULT_BASE_URL,
            model=os.environ.get("SILICONFLOW_MODEL", DEFAULT_MODEL).strip()
            or DEFAULT_MODEL,
            reasoning_effort=os.environ.get(
                "AUTO_COMPANY_PROFILE_REASONING_EFFORT", "medium"
            ).strip()
            or "medium",
            prompt=json.dumps(prompt, ensure_ascii=False, separators=(",", ":")),
            timeout=float(
                os.environ.get("AUTO_COMPANY_PROFILE_API_TIMEOUT", "120") or 120
            ),
            retries=max(
                0,
                min(
                    2,
                    int(
                        os.environ.get("AUTO_COMPANY_PROFILE_API_RETRIES", "1") or 1
                    ),
                ),
            ),
        )
    except Exception as exc:
        return None, f"model {type(exc).__name__}"
    if not isinstance(raw, dict) or raw.get("sameEntity") is not True:
        return None, "model did not confirm same entity"
    try:
        confidence = float(raw.get("identityConfidence", 0) or 0)
    except (TypeError, ValueError):
        confidence = 0
    if confidence < 0.85:
        return None, "model identity confidence below 0.85"
    summary = clean(raw.get("summary"), 500)
    product = clean(raw.get("product"), 400)
    if len(summary) < 20 or len(product) < 6:
        return None, "model profile text is incomplete"
    page_text = clean(page.get("text"), 50_000)
    summary_quotes = _supported_quotes(raw.get("summaryEvidence"), page_text)
    product_quotes = _supported_quotes(raw.get("productEvidence"), page_text)
    if not summary_quotes or not product_quotes:
        return None, "model support quotes are absent from official page"
    return {
        "summary": summary,
        "product": product,
        "identityConfidence": confidence,
        "summaryEvidence": summary_quotes,
        "productEvidence": product_quotes,
    }, ""


def _slug_from_identity(name: str, homepage: str) -> str:
    ascii_name = (
        unicodedata.normalize("NFKD", clean(name, 200))
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.casefold()).strip("-")
    if slug and len(slug) >= 2:
        return slug[:80]
    host = (urlsplit(homepage).hostname or "").casefold().removeprefix("www.")
    parts = host.split(".")
    label = parts[-2] if len(parts) >= 2 else parts[0] if parts else ""
    label = re.sub(r"[^a-z0-9]+", "-", label).strip("-")
    if label:
        return label[:80]
    return "company-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]


def _profile_from_verified_sources(
    candidate: Mapping[str, Any],
    metadata: Mapping[str, Any],
    page: Mapping[str, Any],
    synthesis: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_region = clean(candidate.get("region"), 80)
    region = clean(metadata.get("region"), 80) or (
        candidate_region if candidate_region != "全球" else ""
    )
    sector = clean(candidate.get("sector"), 120)
    homepage = safe_http_url(page.get("url")) or safe_http_url(
        metadata.get("homepage")
    )
    canonical = clean(metadata.get("canonicalName"), 240) or clean(
        candidate.get("name"), 240
    )
    metadata_news = (
        metadata.get("newsUrls") if isinstance(metadata.get("newsUrls"), list) else []
    )
    page_news = page.get("newsUrls") if isinstance(page.get("newsUrls"), list) else []
    candidate_aliases = (
        candidate.get("aliases") if isinstance(candidate.get("aliases"), list) else []
    )
    metadata_aliases = (
        metadata.get("aliases") if isinstance(metadata.get("aliases"), list) else []
    )
    news_urls = unique([*metadata_news, *page_news, homepage], 8)
    return onboarding.normalize_profile(
        {
            "slug": _slug_from_identity(
                clean(metadata.get("englishName"), 240) or canonical, homepage
            ),
            "name": canonical,
            "englishName": clean(metadata.get("englishName"), 240),
            "region": region,
            "sector": sector if sector != "待分类" else "",
            "stage": "未披露",
            "status": "运营中",
            "founded": clean(metadata.get("founded"), 40),
            "headquarters": clean(metadata.get("headquarters"), 160),
            "summary": clean(synthesis.get("summary"), 1_200),
            "product": clean(synthesis.get("product"), 1_200),
            "homepage": homepage,
            "newsUrls": news_urls,
            "aliases": unique(
                [*candidate_aliases, *metadata_aliases, clean(candidate.get("name"), 240)],
                30,
            ),
            "confidence": max(
                0.85,
                min(
                    0.99,
                    float(synthesis.get("identityConfidence", 0.9) or 0.9),
                ),
            ),
        }
    )


def prepare_automatic_onboarding(
    candidates_payload: Mapping[str, Any],
    decisions_payload: Mapping[str, Any],
    official_sources_payload: Mapping[str, Any],
    registry_payload: Mapping[str, Any],
    captures_payload: Mapping[str, Any],
    *,
    resolver: Callable[[str], tuple[dict[str, Any] | None, str]] = resolve_wikidata_company,
    page_fetcher: Callable[[str], dict[str, Any]] = fetch_official_page,
    synthesizer: Callable[..., tuple[dict[str, Any] | None, str]] = synthesize_official_profile,
    now: datetime | None = None,
    limit: int = MAX_AUTO_REQUESTS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    decisions = onboarding.normalize_decisions(copy.deepcopy(decisions_payload))
    candidates = onboarding.candidate_index(dict(candidates_payload))
    timestamp = now_iso(now)
    requested: list[str] = []
    merged: list[str] = []
    holds: list[dict[str, str]] = []
    processed = 0

    for key, decision in decisions["decisions"].items():
        if processed >= max(1, limit):
            break
        if decision.get("status") != "accepted":
            continue
        onboarding_state = (
            decision.get("onboarding")
            if isinstance(decision.get("onboarding"), dict)
            else {}
        )
        if onboarding_state.get("status") in {
            "requested",
            "published",
            "failed",
            "merged",
        }:
            continue
        candidate = candidates.get(key)
        if not candidate:
            holds.append(
                {"candidateKey": key, "reason": "candidate absent from current snapshot"}
            )
            continue
        processed += 1

        if candidate_is_institution_like(candidate):
            holds.append(
                {
                    "candidateKey": key,
                    "reason": "candidate appears to be an investment institution, not a company profile",
                }
            )
            continue

        existing_slug = _registry_match(registry_payload, candidate)
        if existing_slug:
            decision["status"] = "merged"
            decision["mergedSlug"] = existing_slug
            decision["note"] = clean(
                f"{decision.get('note', '')} 自动建档发现该候选已精确命中正式公司实体 {existing_slug}，合并别名。",
                500,
            )
            merged.append(key)
            continue

        metadata = _official_source_match(official_sources_payload, candidate)
        reason = ""
        if metadata is None:
            metadata, reason = resolver(clean(candidate.get("name"), 240))
        if metadata is None:
            holds.append(
                {
                    "candidateKey": key,
                    "reason": reason or "no verified official homepage",
                }
            )
            continue
        homepage = safe_http_url(metadata.get("homepage"))
        if not homepage:
            holds.append(
                {
                    "candidateKey": key,
                    "reason": "verified identity has no valid homepage",
                }
            )
            continue
        try:
            page = page_fetcher(homepage)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            holds.append(
                {
                    "candidateKey": key,
                    "reason": f"official homepage fetch {type(exc).__name__}",
                }
            )
            continue
        candidate_aliases = (
            candidate.get("aliases") if isinstance(candidate.get("aliases"), list) else []
        )
        metadata_aliases = (
            metadata.get("aliases") if isinstance(metadata.get("aliases"), list) else []
        )
        names = unique(
            [
                candidate.get("name"),
                *candidate_aliases,
                metadata.get("canonicalName"),
                metadata.get("englishName"),
                *metadata_aliases,
            ],
            30,
        )
        if not page_supports_identity(page, names):
            holds.append(
                {
                    "candidateKey": key,
                    "reason": "official homepage does not name the resolved candidate",
                }
            )
            continue
        if not page_supports_sector(page, clean(candidate.get("sector"), 120)):
            holds.append(
                {
                    "candidateKey": key,
                    "reason": "official homepage does not support the candidate sector",
                }
            )
            continue

        synthesis, synthesis_reason = synthesizer(
            candidate=candidate,
            metadata=metadata,
            page=page,
            capture_context=_capture_context(candidate, captures_payload),
        )
        if synthesis is None:
            holds.append(
                {
                    "candidateKey": key,
                    "reason": synthesis_reason or "official profile synthesis failed",
                }
            )
            continue
        profile = _profile_from_verified_sources(candidate, metadata, page, synthesis)
        if _registry_slug_exists(registry_payload, profile["slug"]):
            holds.append(
                {
                    "candidateKey": key,
                    "reason": f"generated slug {profile['slug']} already belongs to another company",
                }
            )
            continue
        errors = onboarding.validate_profile(profile, candidate)
        if errors:
            holds.append(
                {"candidateKey": key, "reason": "; ".join(errors[:4])}
            )
            continue
        decision["onboarding"] = {
            "status": "requested",
            "mode": "create",
            "profile": profile,
            "evidenceFingerprint": onboarding.evidence_fingerprint(candidate),
            "requestedAt": timestamp,
            "requestedBy": "VCIQ/auto-profile",
            "publishedAt": "",
            "publishedSlug": "",
            "error": "",
        }
        requested.append(key)

    report = {
        "processedCount": processed,
        "requestedCount": len(requested),
        "requestedKeys": sorted(requested),
        "mergedCount": len(merged),
        "mergedKeys": sorted(merged),
        "holdCount": len(holds),
        "holds": sorted(holds, key=lambda row: row["candidateKey"]),
    }
    return decisions, report


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES_PATH)
    parser.add_argument("--decisions", type=Path, default=DECISIONS_PATH)
    parser.add_argument("--official-sources", type=Path, default=OFFICIAL_SOURCES_PATH)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--captures", type=Path, default=CAPTURES_PATH)
    parser.add_argument("--limit", type=int, default=MAX_AUTO_REQUESTS)
    args = parser.parse_args()

    current = onboarding.load_json(
        args.decisions, {"schemaVersion": 1, "decisions": {}}
    )
    next_decisions, report = prepare_automatic_onboarding(
        onboarding.load_json(args.candidates, {"candidates": []}),
        current,
        onboarding.load_json(args.official_sources, {"companies": []}),
        onboarding.load_json(args.registry, {"companies": []}),
        onboarding.load_json(args.captures, {"records": []}),
        limit=max(1, args.limit),
    )
    changed = onboarding.normalize_decisions(current) != next_decisions
    if changed:
        write_json(args.decisions, next_decisions)
    print(json.dumps({"changed": changed, **report}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
