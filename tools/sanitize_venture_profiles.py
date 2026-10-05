#!/usr/bin/env python3
"""Conservatively remove semantic noise from generated venture profiles.

The crawler intentionally keeps broad discovery recall. This post-processing pass
applies stricter rules to fields rendered as structured facts, where false
positives are more damaging than missing entries. It is deterministic and can
also validate that a committed snapshot has already been sanitized.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from .venture_profile_extraction import (
        clean_text,
        evidence_score,
        normalize_url,
        parse_catalog,
        sanitize_product_items,
        sanitize_team_members,
    )
except ImportError:
    from venture_profile_extraction import (
        clean_text,
        evidence_score,
        normalize_url,
        parse_catalog,
        sanitize_product_items,
        sanitize_team_members,
    )


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"
SNAPSHOT_PATH = ROOT / "public" / "data" / "venture_profiles.json"

EDITORIAL_PRODUCT_TERMS = (
    "terms of service",
    "data processing agreement",
    "privacy policy",
    "cookie policy",
    "responsible scaling policy",
    "press release",
    "research fund",
    "white paper",
    "case study",
    "introducing ",
    "announcing ",
    "teachers",
    "students",
    "k-12",
    "careers",
    "jobs",
    "新闻",
    "资讯",
    "公告",
    "招聘",
    "隐私政策",
    "服务条款",
    "用户协议",
    "数据处理协议",
    "研究报告",
    "白皮书",
)

GENERIC_ENTITY_LABELS = {
    "portfolio",
    "companies",
    "investments",
    "projects",
    "news",
    "insights",
    "more",
    "投资组合",
    "被投企业",
    "投资项目",
    "项目",
    "新闻",
    "动态",
    "更多",
}

FINANCING_ACTION_RE = re.compile(
    r"\b(?:raised?|raises?|raising|funding round|financing round|"
    r"series\s+[a-z0-9]+|seed round|pre-seed|backed by|led by|"
    r"investment from|invested in|secured)\b|"
    r"(?:完成|获得|宣布|获).{0,28}(?:融资|投资)|"
    r"(?:融资|募资|领投|跟投|战略投资|估值)",
    re.IGNORECASE,
)

CAPITAL_ACTION_RE = re.compile(
    r"\b(?:ipo|listed|listing|went public|acquired|acquisition|merger|"
    r"nasdaq|nyse|hkex|stock exchange)\b|"
    r"(?:上市|挂牌|并购|收购|退市|交易所|公开市场)",
    re.IGNORECASE,
)

NON_TRANSACTION_ACQUISITION_RE = re.compile(
    r"\b(?:talent|customer|user|client)\s+acquisition\b|"
    r"\bacquisition\s+(?:marketing|costs?|channels?|strategy|team)\b|"
    r"(?:人才|客户|用户)(?:获取|招募|招聘)",
    re.IGNORECASE,
)

DATE_LIKE_RE = re.compile(
    r"(?:\b20\d{2}[-/.]\d{1,2}(?:[-/.]\d{1,2})?\b|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+20\d{2}\b)",
    re.IGNORECASE,
)

CONCRETE_PRODUCT_RE = re.compile(
    r"(?:\b[A-Z][A-Za-z0-9.+_-]*\d[A-Za-z0-9.+_-]*\b|"
    r"\b[A-Z]{2,}[A-Za-z0-9.+_-]*\b|"
    r"[\u3400-\u9fff]{2,}(?:机器人|模型|平台|系统|芯片|引擎|终端|助手|智能体|API))",
    re.IGNORECASE,
)


def _compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", clean_text(value, 500).casefold())


def _unique_strings(values: Iterable[Any], *, limit: int, item_limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = clean_text(raw, item_limit).strip(" >›→-|｜")
        key = _compact(item)
        if not item or not key or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _catalog_products(value: str) -> list[str]:
    parts = re.split(
        r"[、，,;/]|\s*与\s*|\s+and\s+",
        clean_text(value, 800),
        flags=re.IGNORECASE,
    )
    cleaned: list[str] = []
    pure_research = {
        "research", "ai research", "ai safety research", "safety research",
        "研究", "安全研究", "人工智能研究", "ai安全研究",
    }
    for raw in parts:
        item = clean_text(raw, 180).strip(" >›→-|｜。.!！")
        item = re.sub(
            r"(?:等)?(?:机器人|产品|解决方案)?系列$|(?:等产品|等解决方案)$",
            "",
            item,
            flags=re.IGNORECASE,
        ).strip(" >›→-|｜。.!！")
        if item and item.casefold() not in {value.casefold() for value in pure_research}:
            cleaned.append(item)
    return sanitize_product_items(cleaned)


def _editorial_product(value: str) -> bool:
    item = clean_text(value, 260)
    lowered = item.casefold()
    if any(term in lowered for term in EDITORIAL_PRODUCT_TERMS):
        return True
    if DATE_LIKE_RE.search(item):
        return True
    if len(item) > 140 and not CONCRETE_PRODUCT_RE.search(item):
        return True
    word_count = len(re.findall(r"[A-Za-z0-9]+|[\u3400-\u9fff]", item))
    if word_count > 22 and not CONCRETE_PRODUCT_RE.search(item):
        return True
    return False


def sanitize_products(values: Sequence[Any], catalog_product: str = "") -> list[str]:
    """Prefer curated catalog products and discard editorial/navigation labels."""

    curated = _catalog_products(catalog_product)
    discovered = sanitize_product_items(values)
    result: list[str] = []
    seen: set[str] = set()

    for item in [*curated, *discovered]:
        key = _compact(item)
        if not key or key in seen:
            continue
        if item not in curated and _editorial_product(item):
            continue
        if any(key in previous or previous in key for previous in seen if len(previous) >= 6):
            continue
        result.append(clean_text(item, 180))
        seen.add(key)
        if len(result) >= 10:
            break
    return result


def _clean_investors(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return _unique_strings(values, limit=16, item_limit=120)


def sanitize_capital_events(
    values: Sequence[Any], *, capital_market: bool = False
) -> list[dict[str, Any]]:
    """Keep only events containing explicit transaction or market-action evidence."""

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    action_re = CAPITAL_ACTION_RE if capital_market else FINANCING_ACTION_RE

    for raw in values if isinstance(values, list) else []:
        if not isinstance(raw, dict):
            continue
        title = clean_text(raw.get("title"), 220)
        summary = clean_text(raw.get("summary"), 520)
        amount = clean_text(raw.get("amount"), 80)
        round_name = clean_text(raw.get("round"), 80)
        source_url = normalize_url(raw.get("sourceUrl", ""))
        haystack = f"{title} {summary}"

        if not title and not summary:
            continue
        if not source_url:
            continue
        if capital_market:
            if not action_re.search(haystack):
                continue
            # "Acquisition" is also ordinary operating language (for example,
            # "talent acquisition"). Do not publish those phrases as M&A/exit
            # events unless another explicit capital-market action is present.
            without_non_transaction = NON_TRANSACTION_ACQUISITION_RE.sub("", haystack)
            if (
                NON_TRANSACTION_ACQUISITION_RE.search(haystack)
                and not action_re.search(without_non_transaction)
            ):
                continue
        elif not (amount or round_name or action_re.search(haystack)):
            continue

        date = clean_text(raw.get("date"), 24)
        event_type = clean_text(raw.get("type"), 60) or (
            "资本市场" if capital_market else "融资"
        )
        key = _compact(f"{date}|{event_type}|{title}|{summary}")
        if not key or key in seen:
            continue

        result.append(
            {
                "date": date,
                "type": event_type,
                "title": title or summary[:120],
                "summary": summary or title,
                "amount": amount,
                "round": round_name,
                "investors": _clean_investors(raw.get("investors")),
                "sourceUrl": source_url,
            }
        )
        seen.add(key)
        if len(result) >= 16:
            break
    return result


def sanitize_sources(values: Sequence[Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in values if isinstance(values, list) else []:
        if not isinstance(raw, dict):
            continue
        url = normalize_url(raw.get("url", ""))
        if not url or url in seen:
            continue
        result.append(
            {
                "name": clean_text(raw.get("name"), 120),
                "url": url,
                "level": clean_text(raw.get("level"), 30) or "待交叉验证",
                "section": clean_text(raw.get("section"), 60),
                "title": clean_text(raw.get("title"), 220),
                "publishedAt": clean_text(raw.get("publishedAt"), 24),
            }
        )
        seen.add(url)
        if len(result) >= 30:
            break
    return result


def _valid_case_name(value: Any) -> str:
    name = clean_text(value, 120).strip(" ,，:：;；-|｜")
    if not name or _compact(name) in {_compact(item) for item in GENERIC_ENTITY_LABELS}:
        return ""
    if len(name) < 2 or len(name) > 120 or re.search(r"https?://|@", name):
        return ""
    return name


def sanitize_portfolio(values: Sequence[Any], *, require_date: bool = False) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in values if isinstance(values, list) else []:
        if not isinstance(raw, dict):
            continue
        name = _valid_case_name(raw.get("name"))
        date = clean_text(raw.get("date"), 24)
        summary = clean_text(raw.get("summary"), 420)
        source_url = normalize_url(raw.get("sourceUrl", ""))
        company_slug = clean_text(raw.get("companySlug"), 100)
        if not name or len(summary) < 12 or (not source_url and not company_slug):
            continue
        if require_date and not date:
            continue
        key = _compact(f"{name}|{date}|{summary}")
        if not key or key in seen:
            continue
        result.append(
            {
                "name": name,
                "companySlug": company_slug,
                "date": date,
                "round": clean_text(raw.get("round"), 80),
                "summary": summary,
                "sourceUrl": source_url,
            }
        )
        seen.add(key)
        if len(result) >= 30:
            break
    return result


def sanitize_classic_cases(values: Sequence[Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in values if isinstance(values, list) else []:
        if not isinstance(raw, dict):
            continue
        name = _valid_case_name(raw.get("name"))
        analysis = clean_text(raw.get("analysis"), 620)
        source_url = normalize_url(raw.get("sourceUrl", ""))
        company_slug = clean_text(raw.get("companySlug"), 100)
        if not name or len(analysis) < 24 or (not source_url and not company_slug):
            continue
        key = _compact(f"{name}|{analysis}")
        if not key or key in seen:
            continue
        result.append(
            {
                "name": name,
                "companySlug": company_slug,
                "analysis": analysis,
                "sourceUrl": source_url,
            }
        )
        seen.add(key)
        if len(result) >= 10:
            break
    return result


def sanitize_company_profile(
    profile: dict[str, Any], *, aliases: Sequence[str], catalog_product: str
) -> dict[str, Any]:
    cleaned = copy.deepcopy(profile)
    cleaned["team"] = sanitize_team_members(cleaned.get("team", []), aliases)
    cleaned["products"] = sanitize_products(cleaned.get("products", []), catalog_product)
    cleaned["financing"] = sanitize_capital_events(
        cleaned.get("financing", []), capital_market=False
    )
    cleaned["capitalMarkets"] = sanitize_capital_events(
        cleaned.get("capitalMarkets", []), capital_market=True
    )
    cleaned["sources"] = sanitize_sources(cleaned.get("sources", []))
    cleaned["evidenceScore"] = evidence_score(cleaned, "company")
    return cleaned


def sanitize_institution_profile(
    profile: dict[str, Any], *, aliases: Sequence[str]
) -> dict[str, Any]:
    cleaned = copy.deepcopy(profile)
    cleaned["team"] = sanitize_team_members(cleaned.get("team", []), aliases)
    cleaned["recentInvestments"] = sanitize_portfolio(
        cleaned.get("recentInvestments", []), require_date=True
    )
    cleaned["portfolio"] = sanitize_portfolio(
        cleaned.get("portfolio", []), require_date=False
    )
    cleaned["classicCases"] = sanitize_classic_cases(cleaned.get("classicCases", []))
    cleaned["sources"] = sanitize_sources(cleaned.get("sources", []))
    cleaned["evidenceScore"] = evidence_score(cleaned, "institution")
    return cleaned


def sanitize_snapshot(
    payload: dict[str, Any], catalog_text: str
) -> tuple[dict[str, Any], dict[str, int]]:
    companies, institutions = parse_catalog(catalog_text)
    company_specs = {item.slug: item for item in companies}
    institution_specs = {item.slug: item for item in institutions}
    cleaned = copy.deepcopy(payload)
    diagnostics = {
        "changedCompanies": 0,
        "changedInstitutions": 0,
        "removedProducts": 0,
        "removedCapitalEvents": 0,
        "removedPortfolioItems": 0,
    }

    for slug, profile in list(cleaned.get("companies", {}).items()):
        if not isinstance(profile, dict):
            continue
        spec = company_specs.get(slug)
        aliases = (
            (spec.name, spec.english_name) if spec else (profile.get("name", ""),)
        )
        catalog_product = spec.product if spec else ""
        before_products = len(profile.get("products", []))
        before_events = len(profile.get("financing", [])) + len(
            profile.get("capitalMarkets", [])
        )
        next_profile = sanitize_company_profile(
            profile, aliases=aliases, catalog_product=catalog_product
        )
        diagnostics["removedProducts"] += max(
            0, before_products - len(next_profile.get("products", []))
        )
        diagnostics["removedCapitalEvents"] += max(
            0,
            before_events
            - len(next_profile.get("financing", []))
            - len(next_profile.get("capitalMarkets", [])),
        )
        if next_profile != profile:
            diagnostics["changedCompanies"] += 1
            cleaned["companies"][slug] = next_profile

    for slug, profile in list(cleaned.get("institutions", {}).items()):
        if not isinstance(profile, dict):
            continue
        spec = institution_specs.get(slug)
        aliases = (
            (spec.name, spec.english_name) if spec else (profile.get("name", ""),)
        )
        before_items = (
            len(profile.get("recentInvestments", []))
            + len(profile.get("portfolio", []))
            + len(profile.get("classicCases", []))
        )
        next_profile = sanitize_institution_profile(profile, aliases=aliases)
        after_items = (
            len(next_profile.get("recentInvestments", []))
            + len(next_profile.get("portfolio", []))
            + len(next_profile.get("classicCases", []))
        )
        diagnostics["removedPortfolioItems"] += max(0, before_items - after_items)
        if next_profile != profile:
            diagnostics["changedInstitutions"] += 1
            cleaned["institutions"][slug] = next_profile

    quality_gate = cleaned.setdefault("qualityGate", {})
    checks = quality_gate.setdefault("checks", {})
    checks["postprocessSemanticNoise"] = {
        "actual": 0,
        "required": 0,
        "passed": True,
    }
    quality_gate["passed"] = all(
        bool(check.get("passed"))
        for check in checks.values()
        if isinstance(check, dict) and "passed" in check
    )
    return cleaned, diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the snapshot still contains data changed by this sanitizer.",
    )
    args = parser.parse_args()

    payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    catalog_text = args.catalog.read_text(encoding="utf-8")
    cleaned, diagnostics = sanitize_snapshot(payload, catalog_text)
    changed = cleaned != payload

    print(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))
    if args.check:
        if changed:
            print("Venture profile snapshot requires semantic post-processing.")
            return 1
        print("Venture profile snapshot is post-processed.")
        return 0

    if changed:
        args.snapshot.write_text(
            json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Updated {args.snapshot.relative_to(ROOT)}.")
    else:
        print("No venture profile post-processing changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
