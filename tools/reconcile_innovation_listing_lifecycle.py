#!/usr/bin/env python3
"""Promote primary-source listing events into the reviewed IPO lifecycle.

This reconciler is deliberately narrower than discovery:
- only already reviewed watchlist/lifecycle companies are eligible;
- an article must come from an official regulator/exchange source;
- company identity must match a reviewed company or explicit alias;
- route changes are accepted only when the official text names the board;
- source URLs are deduplicated;
- lifecycle transitions reject stale/regressive events.

New companies still go through the existing human-review candidate queue.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
WATCHLIST_PATH = ROOT / "config" / "innovation_listing_watchlist.json"
LIFECYCLE_PATH = ROOT / "config" / "innovation_listing_lifecycle.json"

OFFICIAL_SOURCE_LEVELS = {
    "监管文件",
    "交易所公告",
    "官方披露",
    "原始材料",
}
OFFICIAL_HOSTS = {
    "csrc.gov.cn",
    "sse.com.cn",
    "szse.cn",
    "hkexnews.hk",
}
PROJECT_SOURCE_PREFIX = "innovation-listing-primary-project-"

STATUS_RANK = {
    "exchange-review": 20,
    "registration-review": 30,
    "registered": 40,
    "issuing": 50,
    "listed": 60,
    "terminated": 90,
}
TERMINAL_RESTART_TARGETS = {
    "exchange-review",
    "registration-review",
    "registered",
    "issuing",
    "listed",
}
EVENT_PRIORITY = {
    "交易所受理": 10,
    "已问询": 20,
    "新一轮问询": 30,
    "问询回复": 40,
    "上市委审议": 50,
    "上市委审议通过": 60,
    "H股递表": 20,
    "港交所聆讯": 50,
    "提交注册": 70,
    "注册阶段": 72,
    "注册生效": 80,
    "发行/招股": 90,
    "已上市": 100,
    "撤回/终止": 110,
}


def clean(value: Any, limit: int = 2000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def normalize(value: Any) -> str:
    return unicodedata.normalize("NFKC", clean(value, 1000)).casefold()


def identity(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", normalize(value))


def unique(values: Iterable[str], limit: int = 80) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = clean(raw, 1800)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
        if len(result) >= limit:
            break
    return result


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def article_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        return [row for row in payload.get("articles", []) if isinstance(row, dict)]
    return []


def parse_date(value: Any) -> datetime | None:
    raw = clean(value, 80)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.fromisoformat(f"{raw[:10]}T00:00:00+00:00")
        except ValueError:
            return None
    return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(UTC)


def source(article: dict[str, Any]) -> dict[str, Any]:
    value = article.get("source")
    return value if isinstance(value, dict) else {}


def source_url(article: dict[str, Any]) -> str:
    return clean(source(article).get("url"), 1800)


def source_host(article: dict[str, Any]) -> str:
    host = (urlsplit(source_url(article)).hostname or "").casefold().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def official_host(host: str) -> bool:
    return any(host == root or host.endswith(f".{root}") for root in OFFICIAL_HOSTS)


def is_primary_article(article: dict[str, Any]) -> bool:
    source_id = clean(article.get("sourceId"), 240)
    level = clean(source(article).get("level"), 80)
    return (
        source_id.startswith(PROJECT_SOURCE_PREFIX)
        and level in OFFICIAL_SOURCE_LEVELS
        and official_host(source_host(article))
        and bool(source_url(article))
    )


def explicit_route(text: str) -> str:
    if "科创板" in text:
        return "STAR"
    if "创业板" in text:
        return "ChiNext"
    if any(term in text for term in ("港交所", "香港联交所", "H股", "港股")):
        return "HK"
    return ""


def classify_event(text: str) -> dict[str, str] | None:
    folded = normalize(text)

    def has(*terms: str) -> bool:
        return any(normalize(term) in folded for term in terms)

    if has("撤回", "终止审核", "终止上市审核", "终止"):
        return {"status": "terminated", "stage": "撤回/终止"}
    if has("上市交易", "正式挂牌", "挂牌上市"):
        return {"status": "listed", "stage": "已上市"}
    if has("全球发售", "开始招股", "启动招股", "招股书", "发行公告") and has(
        "H股", "港股", "全球发售", "上市"
    ):
        return {"status": "issuing", "stage": "发行/招股"}
    if has("注册生效", "同意注册", "注册批复"):
        return {"status": "registered", "stage": "注册生效"}
    if has("提交注册", "注册稿", "进入注册阶段"):
        return {"status": "registration-review", "stage": "提交注册"}
    if has("聆讯") and has("港交所", "香港联交所", "上市"):
        return {"status": "exchange-review", "stage": "港交所聆讯"}
    if has("上市委") and has("通过", "审议结果"):
        return {"status": "exchange-review", "stage": "上市委审议通过"}
    if has("上市委", "审议会议"):
        return {"status": "exchange-review", "stage": "上市委审议"}
    if has("问询回复", "审核问询回复", "回复审核问询", "回复问询"):
        return {"status": "exchange-review", "stage": "问询回复"}
    if re.search(r"第[二三四五六七八九十0-9]+轮.*问询", text):
        return {"status": "exchange-review", "stage": "新一轮问询"}
    if has("新一轮问询", "第二轮问询", "第三轮问询"):
        return {"status": "exchange-review", "stage": "新一轮问询"}
    if has("问询"):
        return {"status": "exchange-review", "stage": "已问询"}
    if has("已受理", "受理通知", "上市申请获受理", "申请获受理"):
        return {"status": "exchange-review", "stage": "交易所受理"}
    if has("递表", "递交上市申请", "递交h股", "上市申请") and has(
        "港交所", "香港联交所", "H股", "港股"
    ):
        return {"status": "exchange-review", "stage": "H股递表"}
    return None


def company_index(
    watchlist: dict[str, Any],
    lifecycle: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    alias_to_project: dict[str, dict[str, Any]] = {}
    lifecycle_by_company: dict[str, dict[str, Any]] = {}

    for project in lifecycle.get("projects", []):
        if not isinstance(project, dict):
            continue
        canonical_key = identity(project.get("company"))
        if canonical_key:
            lifecycle_by_company[canonical_key] = project
        values = [
            project.get("company"),
            *(project.get("aliases", []) if isinstance(project.get("aliases"), list) else []),
        ]
        for value in values:
            key = identity(value)
            if key:
                alias_to_project[key] = project

    for project in watchlist.get("projects", []):
        if not isinstance(project, dict):
            continue
        values = [
            project.get("company"),
            *(project.get("aliases", []) if isinstance(project.get("aliases"), list) else []),
        ]
        for value in values:
            key = identity(value)
            if key and key not in alias_to_project:
                alias_to_project[key] = project

    return alias_to_project, lifecycle_by_company


def match_project(
    article: dict[str, Any],
    alias_to_project: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    title = clean(article.get("title"), 600)
    summary = clean(article.get("summary"), 1200)
    article_company = clean(article.get("company"), 240)
    text_identity = identity(f"{title} {summary}")

    structured_key = identity(article_company)
    if structured_key and structured_key in alias_to_project:
        return alias_to_project[structured_key]

    candidates: list[tuple[int, dict[str, Any]]] = []
    for alias_key, project in alias_to_project.items():
        if len(alias_key) < 4:
            continue
        if alias_key in text_identity:
            candidates.append((len(alias_key), project))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def source_record(article: dict[str, Any]) -> dict[str, str]:
    src = source(article)
    return {
        "title": clean(article.get("title"), 600),
        "url": source_url(article),
        "kind": "exchange-official" if "交易所" in clean(src.get("level"), 80) else "regulatory-official",
        "level": "regulatory",
    }


def event_text(article: dict[str, Any]) -> str:
    return " ".join(
        [
            clean(article.get("title"), 700),
            clean(article.get("summary"), 1500),
        ]
    )


def event_date(article: dict[str, Any]) -> str:
    value = parse_date(article.get("publishedAt"))
    return value.date().isoformat() if value else ""


def transition_allowed(current: dict[str, Any], detected: dict[str, str], date: str) -> bool:
    current_status = clean(current.get("lifecycleStatus"), 80)
    next_status = detected["status"]
    current_date = clean(current.get("latestEventDate"), 20)

    if current_date and date and date < current_date:
        return False
    if current_status == "listed" and next_status != "listed":
        return False
    if current_status == "terminated" and next_status in TERMINAL_RESTART_TARGETS:
        return bool(date and (not current_date or date > current_date))

    current_rank = STATUS_RANK.get(current_status, 0)
    next_rank = STATUS_RANK.get(next_status, 0)
    if next_rank < current_rank:
        return False

    if current_date == date and next_rank == current_rank:
        return EVENT_PRIORITY.get(detected["stage"], 0) > EVENT_PRIORITY.get(
            clean(current.get("stage"), 80), 0
        )
    return not current_date or not date or date >= current_date


def lifecycle_id(project: dict[str, Any]) -> str:
    raw = identity(project.get("company"))
    broker = identity(project.get("broker"))
    return f"auto-{broker or 'broker'}-{raw[:32]}-lifecycle"


def promote_watchlist_project(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": lifecycle_id(project),
        "company": clean(project.get("company"), 240),
        "broker": clean(project.get("broker"), 160),
        "sector": clean(project.get("sector"), 160),
        "subsector": clean(project.get("subsector"), 240),
        "route": clean(project.get("route"), 80) or "A-share-TBD",
        "capitalMarketPath": clean(project.get("capitalMarketPath"), 80) or "A",
        "lifecycleStatus": "exchange-review",
        "stage": "交易所审核",
        "firstGuidanceDate": clean(project.get("firstGuidanceDate"), 20),
        "latestEventDate": clean(project.get("latestEventDate"), 20),
        "latestEvent": clean(project.get("latestEvent"), 600),
        "stockCode": "",
        "fifteenthTags": [
            clean(value, 120)
            for value in project.get("fifteenthTags", [])
            if clean(value, 120)
        ][:12],
        "sources": [],
        "aliases": [
            clean(value, 240)
            for value in project.get("aliases", [])
            if clean(value, 240)
        ][:12],
        "eventHistory": [],
    }


def reconcile(
    articles_payload: Any,
    watchlist_payload: dict[str, Any],
    lifecycle_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, int]]:
    result = deepcopy(lifecycle_payload)
    projects = result.setdefault("projects", [])
    alias_to_project, lifecycle_by_company = company_index(watchlist_payload, result)
    stats = {
        "eligiblePrimaryEvents": 0,
        "matchedEvents": 0,
        "updatedProjects": 0,
        "promotedProjects": 0,
        "dedupedEvents": 0,
        "ignoredTransitions": 0,
    }

    for article in sorted(
        article_rows(articles_payload),
        key=lambda row: clean(row.get("publishedAt"), 80),
    ):
        if not is_primary_article(article):
            continue
        detected = classify_event(event_text(article))
        if not detected:
            continue
        stats["eligiblePrimaryEvents"] += 1

        reviewed = match_project(article, alias_to_project)
        if not reviewed:
            continue
        stats["matchedEvents"] += 1

        canonical_key = identity(reviewed.get("company"))
        current = lifecycle_by_company.get(canonical_key)
        if current is None:
            if detected["status"] not in {
                "exchange-review",
                "registration-review",
                "registered",
                "issuing",
                "listed",
                "terminated",
            }:
                continue
            current = promote_watchlist_project(reviewed)
            projects.append(current)
            lifecycle_by_company[canonical_key] = current
            for value in [
                current.get("company"),
                *(current.get("aliases", []) if isinstance(current.get("aliases"), list) else []),
            ]:
                key = identity(value)
                if key:
                    alias_to_project[key] = current
            stats["promotedProjects"] += 1

        url = source_url(article)
        existing_urls = {
            clean(item.get("url"), 1800)
            for item in current.get("sources", [])
            if isinstance(item, dict)
        }
        if url in existing_urls:
            stats["dedupedEvents"] += 1
            continue

        date = event_date(article)
        if not transition_allowed(current, detected, date):
            stats["ignoredTransitions"] += 1
            continue

        text = event_text(article)
        route = explicit_route(text)
        if route:
            current["route"] = route
            if route == "HK":
                old_path = clean(current.get("capitalMarketPath"), 40)
                if old_path == "A":
                    current["capitalMarketPath"] = "A+H"
                elif not old_path:
                    current["capitalMarketPath"] = "H"

        current["lifecycleStatus"] = detected["status"]
        current["stage"] = detected["stage"]
        if date:
            current["latestEventDate"] = date
        current["latestEvent"] = clean(article.get("title"), 600)
        current.setdefault("sources", []).append(source_record(article))
        current["sources"] = current["sources"][-12:]

        history = current.setdefault("eventHistory", [])
        history.append(
            {
                "date": date,
                "stage": detected["stage"],
                "title": clean(article.get("title"), 600),
                "url": url,
            }
        )
        current["eventHistory"] = history[-24:]
        stats["updatedProjects"] += 1

    dates = [
        clean(project.get("latestEventDate"), 20)
        for project in projects
        if isinstance(project, dict) and clean(project.get("latestEventDate"), 20)
    ]
    if dates:
        result["asOf"] = max([clean(result.get("asOf"), 20), *dates])

    governance = result.setdefault("governance", {})
    governance["autoReconcileRule"] = (
        "已跟踪项目仅在监管/交易所官方来源、实体精确匹配且状态机允许时自动更新；"
        "板块只按官方原文明示更新；新公司仍进入人工候选队列。"
    )
    return result, stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--articles", type=Path, default=ARTICLES_PATH)
    parser.add_argument("--watchlist", type=Path, default=WATCHLIST_PATH)
    parser.add_argument("--lifecycle", type=Path, default=LIFECYCLE_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    articles = load_json(args.articles, {"articles": []})
    watchlist = load_json(args.watchlist, {"projects": []})
    lifecycle = load_json(args.lifecycle, {"schemaVersion": 1, "projects": []})
    if not isinstance(watchlist, dict) or not isinstance(lifecycle, dict):
        raise SystemExit("innovation listing watchlist/lifecycle must be JSON objects")

    reconciled, stats = reconcile(articles, watchlist, lifecycle)
    rendered = serialize(reconciled)
    current = args.lifecycle.read_text(encoding="utf-8") if args.lifecycle.exists() else ""

    if args.check:
        if current != rendered:
            print(json.dumps({"ok": False, **stats}, ensure_ascii=False))
            return 1
        print(json.dumps({"ok": True, **stats}, ensure_ascii=False))
        return 0

    changed = current != rendered
    if changed:
        args.lifecycle.write_text(rendered, encoding="utf-8")
    print(json.dumps({"changed": changed, **stats}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
