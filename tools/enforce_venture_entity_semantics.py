#!/usr/bin/env python3
"""Apply entity-level semantic checks to venture profile facts.

The crawler and existing finalizer remove structural noise. This terminal pass
checks a different failure class: whether a fact actually belongs to the entity
whose page renders it. It rejects third-party financing mentions, year-only
products, unrelated technology descriptions, generic team biographies and
investor-relations page chrome. The transformation is deterministic and
idempotent so it can be used as the last publication gate.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlsplit

try:
    from .sanitize_venture_narratives import sanitize_narrative
    from .venture_profile_extraction import (
        clean_text,
        evidence_score,
        parse_catalog,
    )
except ImportError:
    from sanitize_venture_narratives import sanitize_narrative
    from venture_profile_extraction import clean_text, evidence_score, parse_catalog


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"
SNAPSHOT_PATH = ROOT / "public" / "data" / "venture_profiles.json"

PAGE_CHROME_RE = re.compile(
    r"\b(?:toll[- ]?free|investor relations|transfer agent|media kit|"
    r"cookie settings|all rights reserved|contact us|careers)\b|"
    r"(?:投资者关系|联系方式|联系我们|媒体资料|版权所有|备案号|加入我们)",
    re.IGNORECASE,
)
YEAR_ONLY_RE = re.compile(r"^(?:19|20)\d{2}$")
NUMERIC_ONLY_RE = re.compile(r"^[\d.,%+-]+$")
FINANCING_ACTION_RE = re.compile(
    r"\b(?:rais(?:e|ed|es|ing)(?!\s+(?:full[- ]year\s+)?guidance\b)|"
    r"funding round|financing round|"
    r"series\s+[a-z0-9]+\s+(?:funding|financing|round)|"
    r"first close.{0,80}(?:funding|financing)|"
    r"complet(?:e|ed|es|ing).{0,80}(?:funding|financing)|"
    r"seed round|pre-seed|secured .{0,40} funding|"
    r"closes? .{0,40} round|investment in|invests? in|valuation)\b|"
    r"(?:完成|获得|宣布|获).{0,30}(?:融资|投资)|"
    r"(?:融资|募资|领投|跟投|战略投资|估值)",
    re.IGNORECASE,
)
CAPITAL_ACTION_RE = re.compile(
    r"\b(?:ipo|initial public offering|went public|listed on|listing on|"
    r"acquired by|acquisition of|acquisition by|merger|delisted)\b|"
    r"(?:完成上市|正式上市|申请上市|挂牌|并购|收购|完成退出|退市|公开市场)",
    re.IGNORECASE,
)
FIRST_PERSON_FINANCING_RE = re.compile(
    r"\b(?:we|our company)\s+(?:raised|raises|secured|closed)\b|"
    r"(?:本公司|公司).{0,16}(?:完成|获得|宣布).{0,20}(?:融资|投资)",
    re.IGNORECASE,
)
RELATIONAL_MENTION_RE = re.compile(
    r"\b(?:researchers? from|investors? including|including|from|backed by|"
    r"advisers? from|employees? from)\b",
    re.IGNORECASE,
)
THIRD_PARTY_ROUNDUP_RE = re.compile(
    r"\b(?:weekly roundup|week in review|funding roundup|deal roundup)\b|"
    r"(?:创投周报|投融资周报|融资周报|一周融资|本周融资)",
    re.IGNORECASE,
)
TRANSACTION_DETAIL_RE = re.compile(
    r"(?:[$€£¥]\s?\d|\d+(?:\.\d+)?\s?(?:million|billion|亿元|亿美元|万元)|"
    r"\bseries\s+[a-z0-9]+\b|(?:天使|种子|pre[- ]?[a-z]|[a-z][0-9]?)轮|"
    r"first close|valuation|估值)",
    re.IGNORECASE,
)
TRANSPARENT_TECH_PLACEHOLDER_RE = re.compile(
    r"尚未识别到可独立核对的技术说明|具体技术参数以原始来源为准",
    re.IGNORECASE,
)
CLAUSE_SPLIT_RE = re.compile(r"[。！？!?；;\n]+|(?<=\.)\s+(?=[A-Z\u3400-\u9fff])")
PRODUCT_EDITORIAL_RE = re.compile(
    r"\b(?:press release|latest news|newsroom|things to know|crew undocks|"
    r"journey home|announces?|launches?|introduces?|partnership|collaboration|"
    r"read more|learn more|start chat|free chat|try now|new paper|explores?|"
    r"nominates?|applauded|positive topline|developed using|for the treatment|"
    r"enabling rapid|development with|raises?|raised|funding round|"
    r"financing round|contributed|arrives?|signs?|named|publishes?|delivers?|"
    r"updates?|development|virtual tour|bedroom tidy|demo(?:nstration)?)\b|"
    r"(?:新闻|资讯|发布|推出|宣布|携手|深化|合作|签约|亮相|荣获|入选|大会|峰会|"
    r"访谈|观点|生态合作|开始对话|免费对话|立即体验|体验全新|融资|募资|领投|跟投|"
    r"交付速度|再提升)",
    re.IGNORECASE,
)
PRODUCT_URL_RE = re.compile(
    r"(?:https?://|^https?:$|^www\.)|\b(?:qnimgs?|imgs?|images?|cdn)\b",
    re.IGNORECASE,
)
PRODUCT_FILE_RE = re.compile(
    r"\.(?:png|jpe?g|webp|svg|gif|pdf)(?:[?#].*)?$",
    re.IGNORECASE,
)
PRODUCT_SENTENCE_RE = re.compile(
    r"^(?:the first\b|new paper\b|development with\b)|"
    r"\b(?:nominates?|applauded|positive topline|for the treatment|"
    r"developed using|enabling rapid)\b",
    re.IGNORECASE,
)
PRODUCT_EXACT_NOISE = {
    "api", "apis", "model", "models", "platform", "platforms",
    "service", "services", "software", "hardware", "system", "systems",
    "模型", "平台", "服务", "软件", "硬件", "系统",
    "cost-effective drug discovery",
    "drug discovery",
    "nach01",
}
PRODUCT_DATE_LABEL_RE = re.compile(
    r"^(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\s+\d{1,2}(?:,?\s+20\d{2})?$",
    re.IGNORECASE,
)
PRODUCT_NAV_PREFIX_RE = re.compile(
    r"^(?:view|explore|discover|read|learn|watch|see|find|download|get started)\b",
    re.IGNORECASE,
)
PRODUCT_INTERNAL_SENTENCE_BREAK_RE = re.compile(r"[。！？!?；;]\s*\S")
PRODUCT_FRAGMENT_RE = re.compile(r"^\d{2,}\s+[A-Za-z]", re.IGNORECASE)
PRODUCT_GENERIC_RE = re.compile(
    r"^(?:b2b marketing|b2c marketing|marketing|工艺革新|技术创新|"
    r"产品|平台|服务|业务|更多|qnimgs|images?|assets?|static|uploads?)$",
    re.IGNORECASE,
)
NARRATIVE_EDITORIAL_RE = re.compile(
    r"(?:网友|直呼|狂塞|昨日|过去\d+天|一口气|热议|小编|据悉|报道称|"
    r"本文|作者|赌.{0,8}级|别再|它讲的是)|"
    r"\b(?:click here|we asked|viral|what you need to know)\b",
    re.IGNORECASE,
)
PERSON_CJK_RE = re.compile(r"^[\u3400-\u9fff·]{2,8}$")
PERSON_LATIN_TOKEN_RE = re.compile(r"^[A-Z][A-Za-z'’.-]*$")
PERSON_PARTICLES = {"de", "del", "da", "di", "van", "von", "la", "le"}
PERSON_NOISE_TOKENS = {
    "spotlight", "hear", "read", "view", "more", "team", "leadership",
    "newsroom", "profile", "people", "about", "featured", "general",
    "partner", "managing", "principal", "director", "founder", "cofounder",
    "chief", "officer", "president", "executive",
    "the", "next", "black", "history", "awards", "solutions", "platform",
    "overview", "providers", "program", "programs", "events", "resources",
    "discover", "explore", "learn", "browse", "build", "create", "support",
    "developer", "developers", "app", "apps", "application", "applications",
    "documentation", "docs", "community", "customers", "services", "technology",
    "experience", "stories", "story", "launch", "research", "hub", "contact",
    "login", "portfolio", "jobs", "careers", "insights", "news", "updates",
    "for", "with", "and", "our", "your", "all", "using", "how", "why", "what",
}
PERSON_ORGANIZATION_NAMES = {
    "moses singer",
    "sun microsystems",
}
PERSON_ORG_SUFFIXES = (
    "团队", "部门", "研究院", "实验室", "资本", "基金", "公司", "集团",
    "委员会", "中心", "办公室", "业务部", "事业部",
)


def _compact(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9\u3400-\u9fff]+",
        "",
        clean_text(value, 1200).casefold(),
    )


def _domain(value: Any) -> str:
    host = (urlsplit(clean_text(value, 1000)).hostname or "").casefold()
    host = host.removeprefix("www.")
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if parts[-2] in {"com", "co", "org", "net"} and parts[-1] in {
        "cn",
        "uk",
        "au",
        "jp",
    }:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _aliases(values: Iterable[Any]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = clean_text(raw, 160)
        key = item.casefold()
        if len(_compact(item)) < 2 or key in seen:
            continue
        result.append(item)
        seen.add(key)
    return tuple(result)


def _contains_any(value: Any, terms: Sequence[str]) -> bool:
    lowered = clean_text(value, 4000).casefold()
    return any(term.casefold() in lowered for term in terms if len(_compact(term)) >= 2)


def _trim_page_chrome(value: Any) -> str:
    text = clean_text(value, 5000)
    match = PAGE_CHROME_RE.search(text)
    if match:
        text = text[: match.start()].rstrip(" ,，:：;；|-。")
    return clean_text(text, 5000)


def _relevant_clauses(
    value: Any,
    aliases: Sequence[str],
    products: Sequence[str],
    *,
    limit: int,
) -> str:
    text = _trim_page_chrome(value)
    if not text:
        return ""
    terms = tuple([*aliases, *products])
    clauses: list[str] = []
    for raw in CLAUSE_SPLIT_RE.split(text):
        clause = clean_text(raw, 900).strip(" .。|｜\\-")
        if (
            len(clause) < 18
            or PAGE_CHROME_RE.search(clause)
            or NARRATIVE_EDITORIAL_RE.search(clause)
        ):
            continue
        if terms and not _contains_any(clause, terms):
            continue
        clauses.append(clause)
        if len(clauses) >= 4:
            break
    if not clauses:
        return ""
    cjk = sum(len(re.findall(r"[\u3400-\u9fff]", item)) for item in clauses)
    joined_length = sum(len(item) for item in clauses)
    if cjk / max(1, joined_length) >= 0.18:
        return sanitize_narrative(
            "。".join(item.rstrip("。") for item in clauses) + "。", limit=limit
        )
    return sanitize_narrative(
        ". ".join(item.rstrip(".") for item in clauses) + ".", limit=limit
    )


def _sanitize_background(value: Any) -> str:
    return sanitize_narrative(_trim_page_chrome(value), limit=900)


def _valid_product(value: Any, aliases: Sequence[str] = ()) -> bool:
    item = clean_text(value, 200).strip()
    compact = _compact(item)
    if (
        not item
        or len(item) > 100
        or YEAR_ONLY_RE.fullmatch(item)
        or NUMERIC_ONLY_RE.fullmatch(item)
        or PRODUCT_EDITORIAL_RE.search(item)
        or PRODUCT_URL_RE.search(item)
        or PRODUCT_FILE_RE.search(item)
        or PRODUCT_SENTENCE_RE.search(item)
        or PRODUCT_DATE_LABEL_RE.fullmatch(item)
        or PRODUCT_NAV_PREFIX_RE.search(item)
        or PRODUCT_INTERNAL_SENTENCE_BREAK_RE.search(item)
        or PRODUCT_FRAGMENT_RE.search(item)
        or PRODUCT_GENERIC_RE.fullmatch(item)
        or item.casefold().strip(" .") in PRODUCT_EXACT_NOISE
        or len(compact) < 2
    ):
        return False
    alias_compacts = {_compact(alias) for alias in aliases if _compact(alias)}
    return compact not in alias_compacts

def _valid_person_name(value: Any) -> bool:
    name = clean_text(value, 120).strip(" ,，:：;；-|｜")
    if (
        not name
        or name.casefold().strip(" .") in PERSON_ORGANIZATION_NAMES
        or any(name.endswith(suffix) for suffix in PERSON_ORG_SUFFIXES)
    ):
        return False
    if PERSON_CJK_RE.fullmatch(name):
        return True
    tokens = [token for token in name.split() if token]
    if not 2 <= len(tokens) <= 6:
        return False
    lowered = {token.casefold().strip(".,") for token in tokens}
    if lowered & PERSON_NOISE_TOKENS:
        return False
    if any("." in token and len(token.strip(".")) > 1 for token in tokens):
        return False
    if not PERSON_LATIN_TOKEN_RE.fullmatch(tokens[0]) or not PERSON_LATIN_TOKEN_RE.fullmatch(tokens[-1]):
        return False
    return all(
        PERSON_LATIN_TOKEN_RE.fullmatch(token) or token.casefold() in PERSON_PARTICLES
        for token in tokens[1:-1]
    )


def _subject_evidence(
    row: dict[str, Any],
    aliases: Sequence[str],
    official_domain: str,
    action_re: re.Pattern[str],
) -> bool:
    title = clean_text(row.get("title"), 500)
    summary = clean_text(row.get("summary"), 1200)
    evidence = f"{title} {summary}".strip()
    action = action_re.search(evidence)
    if not evidence or action is None:
        return False

    lowered = evidence.casefold()
    source_is_official = bool(
        official_domain and _domain(row.get("sourceUrl")) == official_domain
    )
    title_lowered = title.casefold()
    title_has_alias = any(
        len(_compact(alias)) >= 2 and alias.casefold() in title_lowered
        for alias in aliases
    )
    title_has_action = action_re.search(title) is not None

    # Third-party media rows must identify both the entity and event in the title,
    # avoid roundup headlines, and provide a concrete transaction detail or a
    # materially richer summary. Keyword-only weekly digests are not facts.
    if not source_is_official:
        if not (title_has_alias and title_has_action):
            return False
        if THIRD_PARTY_ROUNDUP_RE.search(title):
            return False
        investors = row.get("investors", []) if isinstance(row.get("investors"), list) else []
        has_detail = bool(
            clean_text(row.get("amount"), 80)
            or clean_text(row.get("round"), 80)
            or investors
            or TRANSACTION_DETAIL_RE.search(evidence)
        )
        title_key = _compact(title)
        summary_key = _compact(summary)
        has_distinct_summary = bool(
            summary_key
            and summary_key != title_key
            and len(summary_key) >= len(title_key) + 12
        )
        if not has_detail and not has_distinct_summary:
            return False

    alias_positions = [
        lowered.find(alias.casefold())
        for alias in aliases
        if len(_compact(alias)) >= 2 and alias.casefold() in lowered
    ]
    if not alias_positions:
        return bool(source_is_official and FIRST_PERSON_FINANCING_RE.search(evidence))

    alias_position = min(alias_positions)
    if alias_position <= action.start() + 8:
        return True

    prefix = lowered[max(0, alias_position - 45) : alias_position]
    if RELATIONAL_MENTION_RE.search(prefix):
        return False

    for alias in aliases:
        escaped = re.escape(alias.casefold())
        if re.search(
            rf"(?:investment|funding|financing).{{0,32}}(?:in|for|of)\s+{escaped}",
            lowered,
        ):
            return True
        if re.search(rf"(?:对|向){escaped}.{{0,18}}(?:投资|融资)", lowered):
            return True

    # An official news index is not enough by itself. Without direct subject
    # evidence, only an explicit first-person disclosure is accepted.
    return bool(source_is_official and FIRST_PERSON_FINANCING_RE.search(evidence))

def _sanitize_events(
    values: Any,
    aliases: Sequence[str],
    official_domain: str,
    action_re: re.Pattern[str],
) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, dict):
            continue
        row = copy.deepcopy(raw)
        if not _subject_evidence(row, aliases, official_domain, action_re):
            continue
        key = _compact(f"{row.get('date', '')}|{row.get('title', '')}|{row.get('summary', '')}")
        if not key or key in seen:
            continue
        result.append(row)
        seen.add(key)
        if len(result) >= 20:
            break
    return result


def _sanitize_team(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result: list[dict[str, Any]] = []
    for raw in values:
        if not isinstance(raw, dict):
            continue
        row = copy.deepcopy(raw)
        name = clean_text(row.get("name"), 120)
        if not _valid_person_name(name):
            continue
        summary = clean_text(row.get("summary"), 420)
        background = clean_text(row.get("background"), 420)
        previous = clean_text(row.get("previousExperience"), 420)
        if summary and not _contains_any(summary, (name,)):
            row["summary"] = ""
        if background and not _contains_any(background, (name,)):
            row["background"] = ""
        if previous and not _contains_any(previous, (name,)):
            row["previousExperience"] = ""
        result.append(row)
    return result


def _sanitize_technology_products(
    values: Any,
    products: Sequence[str],
    aliases: Sequence[str],
) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    allowed = {_compact(item) for item in products}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, dict):
            continue
        row = copy.deepcopy(raw)
        name = clean_text(row.get("name"), 160)
        key = _compact(name)
        if not _valid_product(name) or key not in allowed or key in seen:
            continue
        description = clean_text(row.get("description"), 600)
        direct_terms = (name, *aliases)
        if not description or not _contains_any(description, direct_terms):
            description = (
                f"公开资料将{name}列为该公司的核心产品或技术平台，"
                "具体技术参数以原始来源为准。"
            )
            row["sourceUrl"] = ""
        row["description"] = description
        highlights = row.get("technicalHighlights", [])
        row["technicalHighlights"] = [
            clean_text(item, 220)
            for item in highlights
            if clean_text(item, 220)
            and _contains_any(item, direct_terms)
            and not TRANSPARENT_TECH_PLACEHOLDER_RE.search(clean_text(item, 220))
        ][:6] if isinstance(highlights, list) else []
        result.append(row)
        seen.add(key)
        if len(result) >= 12:
            break
    return result


def _capital_summary(events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    latest = sorted(
        events,
        key=lambda row: clean_text(row.get("date"), 20),
        reverse=True,
    )[0] if events else {}
    amounts = list(
        dict.fromkeys(
            clean_text(row.get("amount"), 80)
            for row in events
            if clean_text(row.get("amount"), 80)
        )
    )[:12]
    rounds = list(
        dict.fromkeys(
            clean_text(row.get("round"), 80)
            for row in events
            if clean_text(row.get("round"), 80)
        )
    )[:12]
    investors = list(
        dict.fromkeys(
            clean_text(item, 120)
            for row in events
            for item in (
                row.get("investors", [])
                if isinstance(row.get("investors"), list)
                else []
            )
            if clean_text(item, 120)
        )
    )[:20]
    if events:
        summary = (
            f"共识别到{len(events)}条可追溯融资记录；"
            f"最新记录为{clean_text(latest.get('date'), 20) or '日期未披露'}的"
            f"{clean_text(latest.get('title'), 180)}。"
        )
    else:
        summary = "当前公开来源未提供可核对的融资轮次、金额和投资方记录。"
    return {
        "eventCount": len(events),
        "disclosedAmounts": amounts,
        "rounds": rounds,
        "majorInvestors": investors,
        "latestDate": clean_text(latest.get("date"), 20),
        "latestRound": clean_text(latest.get("round"), 80),
        "summary": summary,
    }

def _contains_product_noise(value: Any) -> bool:
    text = clean_text(value, 1600)
    if not text:
        return False
    for raw in re.split(r"[、，,;/。]", text):
        item = clean_text(raw, 300).strip(" .。:：")
        if not item:
            continue
        if (
            PRODUCT_EDITORIAL_RE.search(item)
            or PRODUCT_URL_RE.search(item)
            or PRODUCT_FILE_RE.search(item)
            or PRODUCT_SENTENCE_RE.search(item)
            or PRODUCT_DATE_LABEL_RE.fullmatch(item)
            or PRODUCT_NAV_PREFIX_RE.search(item)
            or PRODUCT_FRAGMENT_RE.search(item)
            or PRODUCT_GENERIC_RE.fullmatch(item)
            or item.casefold().strip(" .") in PRODUCT_EXACT_NOISE
        ):
            return True
    return False


def _exit_performance(
    events: Sequence[dict[str, Any]], *, listed: bool = False
) -> dict[str, str]:
    latest = sorted(
        events,
        key=lambda row: clean_text(row.get("date"), 20),
        reverse=True,
    )[0] if events else {}
    if latest:
        title = clean_text(latest.get("title"), 180)
        date = clean_text(latest.get("date"), 20)
        event_type = clean_text(latest.get("type"), 80)
        is_listing = listed or any(
            term in f"{event_type} {title}".casefold()
            for term in ("ipo", "listed", "listing", "上市", "挂牌")
        )
        return {
            "status": "已上市" if is_listing else "已发生并购或退出事件",
            "latestDate": date,
            "latestEvent": title,
            "summary": (
                f"最新可核对资本市场记录为{date or '日期未披露'}的"
                f"{title or '资本市场事件'}。"
            ),
            "sourceUrl": clean_text(latest.get("sourceUrl"), 1000),
        }
    if listed:
        return {
            "status": "已上市",
            "latestDate": "",
            "latestEvent": "",
            "summary": "目录状态显示该公司已上市；当前快照未保留可核对的上市事件明细。",
            "sourceUrl": "",
        }
    return {
        "status": "暂无公开退出信息",
        "latestDate": "",
        "latestEvent": "",
        "summary": "当前未发现上市、并购退出或明确退出安排的可核对公开证据。",
        "sourceUrl": "",
    }


def _enforce_snapshot_once(
    payload: dict[str, Any], catalog_text: str
) -> tuple[dict[str, Any], dict[str, int]]:
    company_specs, institution_specs = parse_catalog(catalog_text)
    company_by_slug = {item.slug: item for item in company_specs}
    institution_by_slug = {item.slug: item for item in institution_specs}
    cleaned = copy.deepcopy(payload)
    diagnostics = {
        "changedCompanies": 0,
        "changedInstitutions": 0,
        "removedProducts": 0,
        "removedFinancing": 0,
        "removedCapitalMarkets": 0,
        "removedTeamMembers": 0,
        "clearedTeamSummaries": 0,
        "replacedTechnologyDescriptions": 0,
    }

    companies = cleaned.get("companies", {})
    if not isinstance(companies, dict):
        companies = {}
        cleaned["companies"] = companies
    for slug, profile in companies.items():
        if not isinstance(profile, dict):
            continue
        before = copy.deepcopy(profile)
        spec = company_by_slug.get(slug)
        aliases = _aliases(
            (
                profile.get("name", ""),
                slug,
                *(spec.aliases if spec else ()),
            )
        )
        official_domain = _domain(spec.source_url) if spec else ""
        original_products = profile.get("products", [])
        original_product_items = [
            clean_text(item, 180)
            for item in original_products
            if clean_text(item, 180)
        ] if isinstance(original_products, list) else []
        products = [
            item
            for item in original_product_items
            if _valid_product(item, aliases)
        ]
        products = list(dict.fromkeys(products))[:16]
        removed_products = [
            item for item in original_product_items if item not in products
        ]
        diagnostics["removedProducts"] += max(
            0,
            len(original_product_items) - len(products),
        )
        profile["products"] = products

        background = _sanitize_background(profile.get("background", ""))
        if not background and spec:
            background = (
                sanitize_narrative(spec.summary, limit=900)
                or clean_text(spec.summary, 900)
            )
        profile["background"] = background
        raw_technology = clean_text(profile.get("technology", ""), 1400)
        technology = _relevant_clauses(
            raw_technology, aliases, products, limit=900
        )
        removed_in_technology = any(
            _contains_any(raw_technology, (item,))
            for item in removed_products
        )
        rebuild_technology = bool(
            products
            and (
                removed_in_technology
                or _contains_product_noise(raw_technology)
                or not technology
            )
        )
        if rebuild_technology:
            technology = f"核心技术与产品包括{'、'.join(products[:8])}。"
        profile["technology"] = technology
        raw_research_technology = clean_text(
            profile.get("researchTechnology", ""), 1400
        )
        research_technology = _relevant_clauses(
            raw_research_technology, aliases, products, limit=900
        )
        removed_in_research = any(
            _contains_any(raw_research_technology, (item,))
            for item in removed_products
        )
        profile["researchTechnology"] = (
            technology
            if removed_in_research or _contains_product_noise(raw_research_technology)
            else (research_technology or technology)
        )

        project = profile.get("projectBackground")
        if isinstance(project, dict):
            project["summary"] = background
            project["problemSolved"] = _relevant_clauses(
                project.get("problemSolved", ""), aliases, products, limit=520
            )
            project["marketOpportunity"] = _relevant_clauses(
                project.get("marketOpportunity", ""), aliases, products, limit=520
            )

        team_before = copy.deepcopy(profile.get("team", []))
        profile["team"] = _sanitize_team(profile.get("team", []))
        diagnostics["removedTeamMembers"] += max(
            0,
            (len(team_before) if isinstance(team_before, list) else 0)
            - len(profile["team"]),
        )
        for old, new in zip(team_before, profile["team"]):
            if isinstance(old, dict) and isinstance(new, dict):
                diagnostics["clearedTeamSummaries"] += sum(
                    1
                    for key in ("summary", "background", "previousExperience")
                    if old.get(key) and not new.get(key)
                )

        technology_before = copy.deepcopy(profile.get("technologyProducts", []))
        profile["technologyProducts"] = _sanitize_technology_products(
            profile.get("technologyProducts", []), products, aliases
        )
        for old, new in zip(technology_before, profile["technologyProducts"]):
            if isinstance(old, dict) and isinstance(new, dict) and old.get("description") != new.get("description"):
                diagnostics["replacedTechnologyDescriptions"] += 1

        financing_before = profile.get("financing", [])
        capital_before = profile.get("capitalMarkets", [])
        profile["financing"] = _sanitize_events(
            financing_before, aliases, official_domain, FINANCING_ACTION_RE
        )
        profile["capitalMarkets"] = _sanitize_events(
            capital_before, aliases, official_domain, CAPITAL_ACTION_RE
        )
        diagnostics["removedFinancing"] += max(
            0,
            (len(financing_before) if isinstance(financing_before, list) else 0)
            - len(profile["financing"]),
        )
        diagnostics["removedCapitalMarkets"] += max(
            0,
            (len(capital_before) if isinstance(capital_before, list) else 0)
            - len(profile["capitalMarkets"]),
        )
        profile["capitalSummary"] = _capital_summary(profile["financing"])
        profile["exitPerformance"] = _exit_performance(
            profile["capitalMarkets"],
            listed=bool(spec and spec.status == "已上市"),
        )
        profile["evidenceScore"] = evidence_score(profile, "company")
        if profile != before:
            diagnostics["changedCompanies"] += 1

    institutions = cleaned.get("institutions", {})
    if not isinstance(institutions, dict):
        institutions = {}
        cleaned["institutions"] = institutions
    for slug, profile in institutions.items():
        if not isinstance(profile, dict):
            continue
        before = copy.deepcopy(profile)
        spec = institution_by_slug.get(slug)
        aliases = _aliases(
            (profile.get("name", ""), slug, *(spec.aliases if spec else ()))
        )
        profile["overview"] = _sanitize_background(profile.get("overview", ""))
        profile["strategy"] = _relevant_clauses(
            profile.get("strategy", ""), aliases, (), limit=900
        )
        institution_team = profile.get("team", [])
        profile["team"] = _sanitize_team(institution_team)
        diagnostics["removedTeamMembers"] += max(
            0,
            (len(institution_team) if isinstance(institution_team, list) else 0)
            - len(profile["team"]),
        )
        profile["evidenceScore"] = evidence_score(profile, "institution")
        if profile != before:
            diagnostics["changedInstitutions"] += 1

    quality = cleaned.setdefault("qualityGate", {})
    checks = quality.setdefault("checks", {})
    checks["entitySemanticConsistency"] = {
        "actual": 0,
        "required": 0,
        "passed": True,
    }
    quality["passed"] = all(
        bool(check.get("passed"))
        for check in checks.values()
        if isinstance(check, dict) and "passed" in check
    )
    return cleaned, diagnostics


def enforce_snapshot(
    payload: dict[str, Any], catalog_text: str
) -> tuple[dict[str, Any], dict[str, int]]:
    """Return the terminal semantic fixed point in one public invocation.

    Individual field transforms are deterministic and information-reducing, but
    some derived fields depend on values normalized earlier in the same pass.
    Iterating the private single pass prevents callers from having to invoke the
    publication gate repeatedly and makes ``--check`` a true terminal check.
    """
    current = copy.deepcopy(payload)
    aggregate: dict[str, int] = {}
    for pass_index in range(1, 6):
        next_payload, diagnostics = _enforce_snapshot_once(current, catalog_text)
        for key, value in diagnostics.items():
            if isinstance(value, int):
                aggregate[key] = aggregate.get(key, 0) + value
        aggregate["internalPasses"] = pass_index
        if next_payload == current:
            return next_payload, aggregate
        current = next_payload
    raise RuntimeError("entity-semantic enforcement did not converge within five passes")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    cleaned, diagnostics = enforce_snapshot(
        payload, args.catalog.read_text(encoding="utf-8")
    )
    rendered = json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n"
    current = args.snapshot.read_text(encoding="utf-8")
    print(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))
    if args.check:
        if rendered != current:
            print("Venture profile snapshot requires entity-semantic enforcement.")
            return 1
        print("Venture profile snapshot passed entity-semantic checks.")
        return 0
    if rendered == current:
        print("No entity-semantic venture profile changes.")
        return 0
    args.snapshot.write_text(rendered, encoding="utf-8")
    print(f"Updated {args.snapshot.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
