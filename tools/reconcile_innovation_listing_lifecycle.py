#!/usr/bin/env python3
"""Reconcile reviewed innovation-listing state from primary public evidence.

This writer is intentionally conservative:
- only official regulator / exchange / target-broker URLs are eligible;
- entity matching is exact/alias-based and must be unambiguous;
- board routes are only changed when the evidence text explicitly names them;
- older or regressive events do not overwrite a newer lifecycle state;
- primary-backed hard-tech candidates may be promoted automatically, while
  discovery-only candidates remain in the review queue.

The script updates the canonical watchlist/lifecycle JSON used by both the
innovation-capital research page and the build-derived homepage "科创" feed.
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
QUEUE_PATH = ROOT / "config" / "innovation_listing_candidate_review_queue.json"

PRIMARY_SOURCE_LEVELS = {
    "官方披露",
    "原始材料",
    "监管文件",
    "交易所公告",
    "券商官方",
}
OFFICIAL_HOSTS = (
    "eid.csrc.gov.cn",
    "csrc.gov.cn",
    "sse.com.cn",
    "szse.cn",
    "hkexnews.hk",
    "hkex.com.hk",
    "citics.com",
    "ecitic.com",
    "csc108.com",
    "cicc.com",
    "gtja.com",
    "haitong.com",
    "htsc.com",
    "htsc.com.cn",
    "gf.com.cn",
)
STAGE_RANK = {
    "辅导备案": 10,
    "辅导进展": 20,
    "辅导验收": 30,
    "交易所受理": 40,
    "H股递表": 42,
    "已问询": 50,
    "问询回复": 55,
    "新一轮问询": 56,
    "新一轮问询回复": 57,
    "港股聆讯": 60,
    "上市委审议": 60,
    "港股聆讯通过": 65,
    "上市委审议通过": 65,
    "提交注册": 70,
    "注册生效": 80,
    "发行": 90,
    "H股招股": 92,
    "已上市": 100,
    "终止审核": 110,
    "不予注册": 110,
}
ROUTE_CHANGE_TERMS = (
    "改道",
    "转向",
    "转板",
    "变更申报板块",
    "调整申报板块",
    "更换上市板块",
    "路线变更",
    "转科创板",
    "转创业板",
    "A+H",
    "H+A",
)

STATUS_RANK = {
    "counselling": 10,
    "exchange-review": 40,
    "registration-review": 70,
    "registered": 80,
    "issuing": 90,
    "listed": 100,
    "terminated": 110,
}


def clean(value: Any, limit: int = 2400) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def normalize(value: Any) -> str:
    return unicodedata.normalize("NFKC", clean(value, 1600)).casefold()


def identity(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", normalize(value))


def unique(values: Iterable[str], limit: int = 80) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = clean(value, 1600)
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return deepcopy(fallback)


def serialize(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


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


def date_text(value: Any) -> str:
    parsed = parse_date(value)
    return parsed.date().isoformat() if parsed else ""


def article_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("articles", [])
        return [row for row in rows if isinstance(row, dict)]
    return []


def source(article: dict[str, Any]) -> dict[str, Any]:
    value = article.get("source")
    return value if isinstance(value, dict) else {}


def source_url(article: dict[str, Any]) -> str:
    return clean(source(article).get("url"), 1800)


def source_level(article: dict[str, Any]) -> str:
    return clean(source(article).get("level"), 120)


def source_host(article: dict[str, Any]) -> str:
    host = (urlsplit(source_url(article)).hostname or "").casefold().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def official_host(host: str) -> bool:
    return any(host == root or host.endswith(f".{root}") for root in OFFICIAL_HOSTS)


def is_primary_article(article: dict[str, Any]) -> bool:
    source_id = clean(article.get("sourceId"), 240)
    return (
        bool(source_url(article))
        and official_host(source_host(article))
        and (
            source_level(article) in PRIMARY_SOURCE_LEVELS
            or source_id.startswith("innovation-listing-primary-")
        )
    )


def article_text(article: dict[str, Any]) -> str:
    mentioned = article.get("mentionedCompanies", [])
    candidates = article.get("companyCandidateNames", [])
    return " ".join(
        [
            clean(article.get("title"), 700),
            clean(article.get("summary"), 1600),
            clean(article.get("company"), 300),
            " ".join(clean(v, 300) for v in mentioned if v) if isinstance(mentioned, list) else "",
            " ".join(clean(v, 300) for v in candidates if v) if isinstance(candidates, list) else "",
        ]
    )


def route_for(text: str, stage: str = "") -> str:
    if "科创板" in text:
        return "STAR"
    if "创业板" in text:
        return "ChiNext"
    if stage.startswith("H股") or stage.startswith("港股") or any(
        term in text for term in ("港交所", "香港联交所", "H股", "港股", "HKEX")
    ):
        return "HK"
    return ""


def route_change_target(text: str) -> str:
    value = clean(text, 4000)
    destination_patterns = (
        ("ChiNext", r"(?:改道|转向|转板|变更为|调整为|更换为|转至|转到)[^。；，,]{0,24}创业板"),
        ("STAR", r"(?:改道|转向|转板|变更为|调整为|更换为|转至|转到)[^。；，,]{0,24}科创板"),
        ("ChiNext", r"由[^。；，,]{0,20}(?:科创板|其他板块)[^。；，,]{0,20}(?:转|改)[^。；，,]{0,16}创业板"),
        ("STAR", r"由[^。；，,]{0,20}(?:创业板|其他板块)[^。；，,]{0,20}(?:转|改)[^。；，,]{0,16}科创板"),
    )
    for route, pattern in destination_patterns:
        if re.search(pattern, value):
            return route
    return ""


def classify_event(text: str) -> dict[str, Any] | None:
    value = clean(text, 4000)
    if not value:
        return None
    hk = any(term in value for term in ("港交所", "香港联交所", "H股", "港股", "HKEX"))

    if any(term in value for term in ("不予注册", "注册申请不予批准", "终止注册")):
        stage, status = "不予注册", "terminated"
    elif any(term in value for term in ("终止审核", "终止上市审核", "撤回上市申请", "撤回IPO", "撤回申请")):
        stage, status = "终止审核", "terminated"
    elif any(term in value for term in ("上市交易", "正式上市", "挂牌上市", "开始上市")):
        stage, status = "已上市", "listed"
    elif hk and any(term in value for term in ("全球发售", "开始招股", "启动招股", "招股章程")):
        stage, status = "H股招股", "issuing"
    elif any(term in value for term in ("发行公告", "发行结果", "网上发行", "网下发行")):
        stage, status = "发行", "issuing"
    elif any(term in value for term in ("同意注册", "予以注册", "注册生效")):
        stage, status = "注册生效", "registered"
    elif any(term in value for term in ("提交注册", "招股说明书（注册稿）", "招股说明书(注册稿)", "注册稿")):
        stage, status = "提交注册", "registration-review"
    elif hk and any(term in value for term in ("聆讯通过", "通过聆讯")):
        stage, status = "港股聆讯通过", "exchange-review"
    elif any(term in value for term in ("上市委审议通过", "上市委会议通过", "上市审核委员会审议通过")):
        stage, status = "上市委审议通过", "exchange-review"
    elif hk and "聆讯" in value:
        stage, status = "港股聆讯", "exchange-review"
    elif any(term in value for term in ("上市委会议", "上市委审议", "上市审核委员会会议")):
        stage, status = "上市委审议", "exchange-review"
    elif (
        any(term in value for term in ("第二轮问询", "二轮问询", "第三轮问询", "三轮问询"))
        or re.search(r"第[二三四五六七八九十0-9]+轮问询", value)
    ) and any(term in value for term in ("回复", "答复")):
        stage, status = "新一轮问询回复", "exchange-review"
    elif any(term in value for term in ("新一轮问询", "第二轮问询", "二轮问询", "第三轮问询", "三轮问询")) or re.search(
        r"第[二三四五六七八九十0-9]+轮问询", value
    ):
        stage, status = "新一轮问询", "exchange-review"
    elif any(
        term in value
        for term in (
            "问询回复",
            "回复审核问询",
            "审核问询回复",
            "回复问询",
            "问询函的回复",
            "问询函回复",
        )
    ):
        stage, status = "问询回复", "exchange-review"
    elif "问询" in value:
        stage, status = "已问询", "exchange-review"
    elif hk and any(term in value for term in ("递表", "提交上市申请", "上市申请版本", "申请版本")):
        stage, status = "H股递表", "exchange-review"
    elif "受理" in value and any(term in value for term in ("上市", "IPO", "交易所", "首发")):
        stage, status = "交易所受理", "exchange-review"
    elif "辅导验收" in value or "验收完成" in value:
        stage, status = "辅导验收", "counselling"
    elif "辅导进展" in value or re.search(r"第[一二三四五六七八九十0-9]+期辅导", value):
        stage, status = "辅导进展", "counselling"
    elif any(term in value for term in ("辅导备案", "上市辅导", "IPO辅导")):
        stage, status = "辅导备案", "counselling"
    else:
        route = route_change_target(value) or route_for(value)
        capital_path = "A+H" if "A+H" in value else ("H+A" if "H+A" in value else "")
        if any(term in value for term in ROUTE_CHANGE_TERMS) and (route or capital_path):
            return {
                "stage": "",
                "lifecycleStatus": "",
                "rank": 0,
                "route": route,
                "capitalMarketPath": capital_path,
                "routeOnly": True,
            }
        return None

    return {
        "stage": stage,
        "lifecycleStatus": status,
        "rank": STAGE_RANK[stage],
        "route": route_for(value, stage),
        "capitalMarketPath": "",
        "routeOnly": False,
    }


def project_aliases(project: dict[str, Any]) -> list[str]:
    aliases = project.get("aliases", [])
    values: list[Any] = [project.get("company")]
    if isinstance(aliases, list):
        values.extend(aliases)
    return unique([clean(value, 240) for value in values if clean(value, 240)], 24)


def structured_article_names(article: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    if article.get("company"):
        values.append(article.get("company"))
    for field in ("mentionedCompanies", "companyCandidateNames"):
        raw = article.get(field)
        if isinstance(raw, list):
            values.extend(raw)
    return unique([clean(value, 260) for value in values if clean(value, 260)], 24)


def match_project(
    article: dict[str, Any],
    watchlist_projects: list[dict[str, Any]],
    lifecycle_projects: list[dict[str, Any]],
) -> tuple[str, int] | None:
    projects: list[tuple[str, int, dict[str, Any]]] = [
        *[("watchlist", index, row) for index, row in enumerate(watchlist_projects)],
        *[("lifecycle", index, row) for index, row in enumerate(lifecycle_projects)],
    ]
    structured = {identity(name) for name in structured_article_names(article) if identity(name)}
    strong: list[tuple[str, int]] = []
    if structured:
        for collection, index, project in projects:
            aliases = {identity(value) for value in project_aliases(project)}
            if structured & aliases:
                strong.append((collection, index))
        if len(set(strong)) == 1:
            return strong[0]
        if len(set(strong)) > 1:
            return None

    haystack = identity(article_text(article))
    if not haystack:
        return None
    weak: list[tuple[str, int]] = []
    for collection, index, project in projects:
        for alias in project_aliases(project):
            key = identity(alias)
            if len(key) >= 4 and key in haystack:
                weak.append((collection, index))
                break
    unique_matches = list(dict.fromkeys(weak))
    return unique_matches[0] if len(unique_matches) == 1 else None


def evidence_entry(article: dict[str, Any]) -> dict[str, str]:
    host = source_host(article)
    if (
        host.endswith("sse.com.cn")
        or host.endswith("szse.cn")
        or host.endswith("hkexnews.hk")
        or host.endswith("hkex.com.hk")
    ):
        kind = "exchange-official"
    elif host.endswith("csrc.gov.cn"):
        kind = "regulatory-official"
    else:
        kind = "broker-official"
    return {
        "title": clean(article.get("title"), 700),
        "url": source_url(article),
        "kind": kind,
        "level": "regulatory",
    }


def current_stage_rank(project: dict[str, Any]) -> int:
    stage = clean(project.get("stage"), 80)
    if stage in STAGE_RANK:
        return STAGE_RANK[stage]
    return STATUS_RANK.get(clean(project.get("lifecycleStatus"), 80), 0)


def current_event_date(project: dict[str, Any]) -> datetime | None:
    return parse_date(project.get("latestEventDate"))


def has_source(project: dict[str, Any], url: str) -> bool:
    if not url:
        return False
    single = project.get("source")
    if isinstance(single, dict) and clean(single.get("url"), 1800) == url:
        return True
    rows = project.get("sources")
    if isinstance(rows, list):
        return any(
            isinstance(row, dict) and clean(row.get("url"), 1800) == url for row in rows
        )
    return False


def effective_event_route(project: dict[str, Any], event: dict[str, Any]) -> str:
    route = clean(event.get("route"), 60)
    if route:
        return route
    if event.get("lifecycleStatus") == "counselling":
        current_route = clean(project.get("route"), 60)
        current_status = clean(project.get("lifecycleStatus"), 80)
        # A mainland IPO counselling filing after an HK listing is an A-side
        # lifecycle restart, but the board remains unknown until evidence says
        # STAR or ChiNext. A terminal A-share project restarting counselling is
        # likewise reset to A-share-TBD rather than inheriting its old board.
        if current_route == "HK" or current_status == "terminated":
            return "A-share-TBD"
    return ""


def should_apply(
    project: dict[str, Any],
    event: dict[str, Any],
    published_at: str,
    url: str,
) -> bool:
    incoming_date = parse_date(published_at)
    existing_date = current_event_date(project)
    if not incoming_date:
        return False
    if existing_date and incoming_date < existing_date:
        return False
    current_rank = current_stage_rank(project)
    current_route = clean(project.get("route"), 60)
    incoming_route = effective_event_route(project, event)
    if event.get("routeOnly"):
        incoming_path = clean(event.get("capitalMarketPath"), 40)
        current_path = clean(project.get("capitalMarketPath"), 40)
        route_changed = bool(incoming_route and incoming_route != current_route)
        path_changed = bool(incoming_path and incoming_path != current_path)
        if not route_changed and not path_changed:
            return False
        if existing_date and incoming_date < existing_date:
            return False
        return True
    explicit_route_switch = bool(
        incoming_route
        and current_route
        and incoming_route != current_route
    )
    restart_after_terminal = bool(
        clean(project.get("lifecycleStatus"), 80) == "terminated"
        and existing_date
        and incoming_date > existing_date
    )
    if (
        event["rank"] < current_rank
        and not explicit_route_switch
        and not restart_after_terminal
    ):
        return False
    same_stage = clean(project.get("stage"), 80) == event["stage"]
    if same_stage and event["rank"] == current_rank and not explicit_route_switch:
        # Re-surfacing the same official stage is not a new material transition.
        # Multi-round inquiries use distinct classified stages above.
        return False
    if existing_date and incoming_date == existing_date:
        if has_source(project, url) and same_stage:
            return False
    return True


def apply_capital_path(project: dict[str, Any], event_route: str, text: str) -> str:
    current = clean(project.get("capitalMarketPath"), 40)
    if "A+H" in text:
        return "A+H"
    if "H+A" in text:
        return "H+A"
    if event_route == "HK":
        if current == "A":
            return "A+H"
        return current if current in {"A+H", "H+A", "H"} else "H"
    if event_route in {"STAR", "ChiNext", "A-share-TBD"}:
        if current == "H":
            return "H+A"
        return current if current in {"A+H", "H+A", "A"} else "A"
    return current or "A"


def merge_source_list(
    project: dict[str, Any],
    evidence: dict[str, str],
) -> list[dict[str, Any]]:
    rows = [row for row in project.get("sources", []) if isinstance(row, dict)]
    single = project.get("source")
    if isinstance(single, dict) and single.get("url"):
        kind = clean(single.get("kind"), 80)
        if "official" in kind or kind in {"exchange-filing", "regulatory"}:
            rows.insert(
                0,
                {
                    "title": clean(single.get("title"), 700),
                    "url": clean(single.get("url"), 1800),
                    "kind": kind or "official",
                    "level": "regulatory",
                },
            )
    urls = {clean(row.get("url"), 1800) for row in rows}
    if evidence["url"] and evidence["url"] not in urls:
        rows.insert(0, evidence)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        url = clean(row.get("url"), 1800)
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(row)
    return deduped[:12]


def event_summary(article: dict[str, Any], event: dict[str, Any]) -> str:
    title = clean(article.get("title"), 700)
    return title or event["stage"]


def update_existing_project(
    project: dict[str, Any],
    article: dict[str, Any],
    event: dict[str, Any],
) -> None:
    text = article_text(article)
    route = effective_event_route(project, event)
    if not event.get("routeOnly"):
        project["stage"] = event["stage"]
        if (
            event["lifecycleStatus"] != "counselling"
            or clean(project.get("lifecycleStatus"), 80) == "terminated"
        ):
            project["lifecycleStatus"] = event["lifecycleStatus"]
    project["latestEventDate"] = date_text(article.get("publishedAt"))
    project["latestEvent"] = event_summary(article, event)
    if route:
        project["route"] = route
    project["capitalMarketPath"] = apply_capital_path(project, route, text)
    project["sources"] = merge_source_list(project, evidence_entry(article))
    project.pop("source", None)


def migrate_watchlist_project(
    project: dict[str, Any],
    article: dict[str, Any],
    event: dict[str, Any],
) -> dict[str, Any]:
    migrated = {
        "id": f"{clean(project.get('id'), 180) or identity(project.get('company'))}-lifecycle",
        "company": clean(project.get("company"), 300),
        "broker": clean(project.get("broker"), 180),
        "sector": clean(project.get("sector"), 180) or "待分类",
        "subsector": clean(project.get("subsector"), 260),
        "route": clean(project.get("route"), 60) or "A-share-TBD",
        "capitalMarketPath": clean(project.get("capitalMarketPath"), 40) or "A",
        "lifecycleStatus": event["lifecycleStatus"],
        "stage": event["stage"],
        "firstGuidanceDate": clean(project.get("firstGuidanceDate"), 40),
        "latestEventDate": date_text(article.get("publishedAt")),
        "latestEvent": event_summary(article, event),
        "stockCode": clean(project.get("stockCode"), 40),
        "fifteenthTags": unique(project.get("fifteenthTags", []), 12),
        "sources": merge_source_list(project, evidence_entry(article)),
        "aliases": unique(project_aliases(project), 20),
    }
    route = effective_event_route(project, event)
    if route:
        migrated["route"] = route
    migrated["capitalMarketPath"] = apply_capital_path(
        migrated,
        route,
        article_text(article),
    )
    return migrated


def update_watchlist_project(
    project: dict[str, Any],
    article: dict[str, Any],
    event: dict[str, Any],
) -> None:
    route = effective_event_route(project, event)
    if not event.get("routeOnly"):
        project["stage"] = event["stage"]
    project["latestEventDate"] = date_text(article.get("publishedAt"))
    project["latestEvent"] = event_summary(article, event)
    if route:
        project["route"] = route
        project["routeConfidence"] = (
            "official"
            if route in {"STAR", "ChiNext", "HK"}
            else "official-a-share-only"
        )
    elif clean(project.get("route"), 60) == "A-share-TBD":
        project["routeConfidence"] = (
            clean(project.get("routeConfidence"), 80) or "official-a-share-only"
        )
    project["capitalMarketPath"] = apply_capital_path(
        project,
        route,
        article_text(article),
    )
    project["source"] = {
        "title": clean(article.get("title"), 700),
        "url": source_url(article),
        "kind": evidence_entry(article)["kind"],
    }
    if event["stage"] == "辅导备案" and not clean(project.get("firstGuidanceDate"), 40):
        project["firstGuidanceDate"] = date_text(article.get("publishedAt"))


def candidate_primary_evidence(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    rows = candidate.get("evidence", [])
    result: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = clean(row.get("url"), 1800)
        host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
        if not url or not official_host(host):
            continue
        if (
            clean(row.get("level"), 120) not in PRIMARY_SOURCE_LEVELS
            and not clean(row.get("sourceId"), 240).startswith(
                "innovation-listing-primary-"
            )
        ):
            continue
        result.append(row)
    result.sort(key=lambda row: clean(row.get("publishedAt"), 80), reverse=True)
    return result


def article_from_candidate_evidence(
    candidate: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": clean(evidence.get("articleId"), 260),
        "sourceId": clean(evidence.get("sourceId"), 240),
        "title": clean(evidence.get("title"), 700),
        "summary": clean(
            evidence.get("summary") or candidate.get("latestEvent"),
            1600,
        ),
        "company": clean(candidate.get("company"), 300),
        "mentionedCompanies": candidate.get("aliases", []),
        "publishedAt": clean(evidence.get("publishedAt"), 80),
        "source": {
            "name": clean(evidence.get("sourceName"), 240),
            "url": clean(evidence.get("url"), 1800),
            "level": clean(evidence.get("level"), 120),
        },
    }


def candidate_route(
    candidate: dict[str, Any],
    article: dict[str, Any],
    event: dict[str, Any],
) -> str:
    explicit = event.get("route", "")
    if explicit:
        return explicit
    route = clean(candidate.get("route"), 60)
    return route if route in {"STAR", "ChiNext", "HK"} else ""


def promotable_candidate(
    candidate: dict[str, Any],
    brokers: set[str],
) -> tuple[dict[str, Any], dict[str, Any], str] | None:
    if clean(candidate.get("status"), 40) != "pending":
        return None
    if clean(candidate.get("candidateClass"), 60) != "listing-candidate":
        return None
    broker = clean(candidate.get("broker"), 180)
    if not broker or broker not in brokers:
        return None
    tags = [
        clean(tag, 120)
        for tag in candidate.get("fifteenthTags", [])
        if clean(tag, 120)
    ]
    if not tags:
        return None
    if clean(candidate.get("evidenceClass"), 80) != "primary-backed":
        return None

    for evidence in candidate_primary_evidence(candidate):
        article = article_from_candidate_evidence(candidate, evidence)
        text = article_text(article)
        if broker not in text:
            # The source query may be broker-scoped, but formal promotion also
            # requires the retrieved official evidence itself to name the broker.
            continue
        event = classify_event(text)
        if not event or event.get("routeOnly"):
            # Route/path-only discoveries can update already tracked entities,
            # but are not sufficient to auto-admit a brand-new project.
            continue
        route = candidate_route(candidate, article, event)
        if event["lifecycleStatus"] != "counselling" and not route:
            # Do not infer STAR/ChiNext merely from the exchange host.
            continue
        return article, event, route
    return None


def new_watchlist_project(
    candidate: dict[str, Any],
    article: dict[str, Any],
    event: dict[str, Any],
    route: str,
) -> dict[str, Any]:
    route_value = route or "A-share-TBD"
    return {
        "id": clean(candidate.get("id"), 180),
        "company": clean(candidate.get("company"), 300),
        "broker": clean(candidate.get("broker"), 180),
        "sector": clean(candidate.get("sector"), 180) or "待分类",
        "subsector": "",
        "route": route_value,
        "routeConfidence": "official" if route else "official-a-share-only",
        "capitalMarketPath": apply_capital_path({}, route_value, article_text(article)),
        "hkStatus": "none",
        "pool": "core" if route_value in {"STAR", "ChiNext"} else "observation",
        "stage": event["stage"],
        "firstGuidanceDate": date_text(article.get("publishedAt")),
        "latestEventDate": date_text(article.get("publishedAt")),
        "latestEvent": event_summary(article, event),
        "everFiledBefore": False,
        "priorFilingSummary": "",
        "fifteenthTags": unique(candidate.get("fifteenthTags", []), 12),
        "source": {
            "title": clean(article.get("title"), 700),
            "url": source_url(article),
            "kind": evidence_entry(article)["kind"],
        },
        "aliases": unique(candidate.get("aliases", []), 20),
    }


def new_lifecycle_project(
    candidate: dict[str, Any],
    article: dict[str, Any],
    event: dict[str, Any],
    route: str,
) -> dict[str, Any]:
    return {
        "id": f"{clean(candidate.get('id'), 180)}-lifecycle",
        "company": clean(candidate.get("company"), 300),
        "broker": clean(candidate.get("broker"), 180),
        "sector": clean(candidate.get("sector"), 180) or "待分类",
        "subsector": "",
        "route": route,
        "capitalMarketPath": apply_capital_path({}, route, article_text(article)),
        "lifecycleStatus": event["lifecycleStatus"],
        "stage": event["stage"],
        "firstGuidanceDate": clean(candidate.get("firstSeenAt"), 40),
        "latestEventDate": date_text(article.get("publishedAt")),
        "latestEvent": event_summary(article, event),
        "stockCode": "",
        "fifteenthTags": unique(candidate.get("fifteenthTags", []), 12),
        "sources": [evidence_entry(article)],
        "aliases": unique(candidate.get("aliases", []), 20),
    }


def max_as_of(
    *payloads: dict[str, Any],
    extra_dates: Iterable[str] = (),
) -> str:
    values = [
        clean(payload.get("asOf"), 40)
        for payload in payloads
        if isinstance(payload, dict)
    ]
    values.extend(extra_dates)
    dates = [date_text(value) for value in values]
    valid = [value for value in dates if value]
    return max(valid) if valid else ""


def reconcile(
    articles_payload: Any,
    watchlist_payload: dict[str, Any],
    lifecycle_payload: dict[str, Any],
    queue_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    watchlist = deepcopy(
        watchlist_payload if isinstance(watchlist_payload, dict) else {}
    )
    lifecycle = deepcopy(
        lifecycle_payload if isinstance(lifecycle_payload, dict) else {}
    )
    watch_projects = [
        row for row in watchlist.get("projects", []) if isinstance(row, dict)
    ]
    life_projects = [
        row for row in lifecycle.get("projects", []) if isinstance(row, dict)
    ]

    applied: list[dict[str, str]] = []
    skipped_non_primary = 0

    rows = sorted(
        article_rows(articles_payload),
        key=lambda row: date_text(row.get("publishedAt")),
    )
    for article in rows:
        source_id = clean(article.get("sourceId"), 240)
        if not source_id.startswith("innovation-listing-"):
            continue
        if not is_primary_article(article):
            skipped_non_primary += 1
            continue
        event = classify_event(article_text(article))
        if not event:
            continue
        match = match_project(article, watch_projects, life_projects)
        if match is None:
            continue
        collection, index = match
        target = watch_projects[index] if collection == "watchlist" else life_projects[index]
        if not should_apply(
            target,
            event,
            clean(article.get("publishedAt"), 80),
            source_url(article),
        ):
            continue

        if collection == "watchlist":
            if event.get("routeOnly") or event["lifecycleStatus"] == "counselling":
                update_watchlist_project(target, article, event)
            else:
                migrated = migrate_watchlist_project(target, article, event)
                company = clean(target.get("company"), 300)
                watch_projects.pop(index)
                life_projects.append(migrated)
                applied.append(
                    {
                        "company": company,
                        "action": "migrate-to-lifecycle",
                        "stage": event["stage"],
                        "date": date_text(article.get("publishedAt")),
                    }
                )
                continue
        else:
            update_existing_project(target, article, event)

        applied.append(
            {
                "company": clean(target.get("company"), 300),
                "action": "update",
                "stage": event["stage"] or "路线变更",
                "date": date_text(article.get("publishedAt")),
            }
        )

    brokers = {
        clean(value, 180)
        for value in watchlist.get("brokers", [])
        if clean(value, 180)
    }
    known = {
        identity(value)
        for row in [*watch_projects, *life_projects]
        for value in project_aliases(row)
    }
    queue_rows = (
        queue_payload.get("candidates", [])
        if isinstance(queue_payload, dict)
        else []
    )
    for candidate in queue_rows if isinstance(queue_rows, list) else []:
        if not isinstance(candidate, dict):
            continue
        company_key = identity(candidate.get("company"))
        if not company_key or company_key in known:
            continue
        promoted = promotable_candidate(candidate, brokers)
        if not promoted:
            continue
        article, event, route = promoted
        if event["lifecycleStatus"] == "counselling":
            project = new_watchlist_project(candidate, article, event, route)
            watch_projects.append(project)
            action = "auto-promote-watchlist"
        else:
            project = new_lifecycle_project(candidate, article, event, route)
            life_projects.append(project)
            action = "auto-promote-lifecycle"
        for value in project_aliases(project):
            known.add(identity(value))
        applied.append(
            {
                "company": clean(project.get("company"), 300),
                "action": action,
                "stage": event["stage"],
                "date": date_text(article.get("publishedAt")),
            }
        )

    watchlist["projects"] = watch_projects
    lifecycle["projects"] = life_projects
    latest = max_as_of(
        watchlist,
        lifecycle,
        extra_dates=[row["date"] for row in applied if row.get("date")],
    )
    if latest:
        watchlist["asOf"] = latest
        lifecycle["asOf"] = latest

    report = {
        "changed": (
            serialize(watchlist) != serialize(watchlist_payload)
            or serialize(lifecycle) != serialize(lifecycle_payload)
        ),
        "appliedCount": len(applied),
        "applied": applied,
        "skippedNonPrimary": skipped_non_primary,
    }
    return watchlist, lifecycle, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--articles", type=Path, default=ARTICLES_PATH)
    parser.add_argument("--watchlist", type=Path, default=WATCHLIST_PATH)
    parser.add_argument("--lifecycle", type=Path, default=LIFECYCLE_PATH)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    articles = load_json(args.articles, {"articles": []})
    watchlist = load_json(args.watchlist, {"projects": [], "brokers": []})
    lifecycle = load_json(args.lifecycle, {"projects": []})
    queue = load_json(args.queue, {"candidates": []})

    expected_watchlist, expected_lifecycle, report = reconcile(
        articles,
        watchlist,
        lifecycle,
        queue,
    )

    if args.check:
        if (
            serialize(expected_watchlist) != serialize(watchlist)
            or serialize(expected_lifecycle) != serialize(lifecycle)
        ):
            print(json.dumps(report, ensure_ascii=False))
            return 1
        print(json.dumps({**report, "check": "clean"}, ensure_ascii=False))
        return 0

    args.watchlist.write_text(serialize(expected_watchlist), encoding="utf-8")
    args.lifecycle.write_text(serialize(expected_lifecycle), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
