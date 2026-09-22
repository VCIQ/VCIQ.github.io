#!/usr/bin/env python3
"""Build a conservative review queue for new innovation-listing projects.

The queue is evidence-only. It never mutates the reviewed
config/innovation_listing_watchlist.json. New projects are extracted only from
innovation-listing discovery sources and remain pending until an explicit human
review flow decides otherwise.

The builder intentionally accepts conservative title extraction here because
these articles already passed broker/listing discovery queries. Formal watchlist
promotion must still require human confirmation and stronger evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
WATCHLIST_PATH = ROOT / "config" / "innovation_listing_watchlist.json"
DECISIONS_PATH = ROOT / "config" / "innovation_listing_candidate_decisions.json"
OUTPUT_PATH = ROOT / "config" / "innovation_listing_candidate_review_queue.json"

SOURCE_PREFIX = "innovation-listing-"
MINIMUM_SCORE = 45
VALID_DECISIONS = {"pending", "accepted", "rejected"}
PRIMARY_SOURCE_LEVELS = {
    "官方披露",
    "原始材料",
    "监管文件",
    "交易所公告",
    "券商官方",
}
LISTING_TERMS = (
    "辅导",
    "IPO",
    "上市",
    "科创板",
    "创业板",
    "A股",
    "受理",
    "港交所",
    "H股",
    "A+H",
)
A_PLUS_H_TERMS = ("A+H", "H股", "港股", "港交所", "18C", "特专科技")
GENERIC_NAMES = {
    "",
    "公司",
    "企业",
    "项目",
    "科创板",
    "创业板",
    "A股",
    "IPO",
    "资本市场",
    "科创项目",
    "硬科技",
}
LEGAL_NAME_RE = re.compile(
    r"([A-Za-z0-9\u3400-\u9fff（）()·&＋+\-]{2,80}?"
    r"(?:集团股份有限公司|科技股份有限公司|股份有限公司|有限责任公司|有限公司))"
)
QUOTED_NAME_RE = re.compile(r"[“「『\"]([^”」』\"]{2,48})[”」』\"]")
ACTION_NAME_RE = re.compile(
    r"(?:^|[：:丨|｜、，,；;])"
    r"([A-Za-z0-9\u3400-\u9fff（）()·&＋+\-]{2,40}?)"
    r"(?:正式)?(?:启动|完成|进入|开启|拟|冲刺)"
    r"(?:A股|科创板|创业板|IPO|上市)?(?:IPO|上市)?辅导"
)


def clean(value: Any, limit: int = 2000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def normalize(value: Any) -> str:
    return unicodedata.normalize("NFKC", clean(value, 500)).casefold().replace("＆", "&")


def identity(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", normalize(value))


def unique(values: Iterable[str], limit: int = 40) -> list[str]:
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
        return fallback


def parse_date(value: Any) -> datetime | None:
    text = clean(value, 80)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.fromisoformat(f"{text[:10]}T00:00:00+00:00")
        except ValueError:
            return None
    return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(UTC)


def article_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("articles", [])
        return [row for row in rows if isinstance(row, dict)]
    return []


def generated_at(payload: Any, rows: list[dict[str, Any]]) -> str:
    if isinstance(payload, dict):
        explicit = clean(payload.get("generatedAt"), 80)
        if explicit:
            return explicit
    dates = [parse_date(row.get("publishedAt")) for row in rows]
    valid = [value for value in dates if value is not None]
    return max(valid).isoformat() if valid else ""


def safe_company_name(value: Any, brokers: set[str]) -> str:
    name = clean(value, 120).strip(" ,，:：;；|｜-—·")
    for broker in sorted(brokers, key=len, reverse=True):
        if not name.startswith(broker) or name == broker:
            continue
        remainder = name[len(broker) :].lstrip(" ：:，,、-—")
        remainder = re.sub(
            r"^(?:担任|作为|辅导|保荐|推进|助力|携手|服务|支持|拟|完成|启动|开启)+",
            "",
            remainder,
        ).lstrip(" ：:，,、-—")
        if remainder:
            name = remainder
            break
    key = identity(name)
    if not name or name in GENERIC_NAMES or len(key) < 2:
        return ""
    if name in brokers:
        return ""
    if any(name.startswith(broker) and len(name) <= len(broker) + 8 for broker in brokers):
        return ""
    if re.search(r"https?://|@", name, re.IGNORECASE):
        return ""
    if len(name) > 100 or name.count(" ") > 6:
        return ""
    if any(term in name for term in ("辅导备案", "辅导进展", "辅导验收", "上市辅导")):
        return ""
    if re.fullmatch(r"[\d._+\-]+", name):
        return ""
    return name


def structured_names(article: dict[str, Any], brokers: set[str]) -> list[str]:
    raw: list[Any] = []
    if article.get("company") not in (None, ""):
        raw.append(article.get("company"))
    for field in ("mentionedCompanies", "companyCandidateNames"):
        value = article.get(field)
        if isinstance(value, list):
            raw.extend(value)

    names: list[str] = []
    for value in raw:
        name = safe_company_name(value, brokers)
        if name:
            names.append(name)
    return unique(names, 12)


def title_names(article: dict[str, Any], brokers: set[str]) -> list[str]:
    title = clean(article.get("title"), 500)
    summary = clean(article.get("summary"), 900)
    text = f"{title} {summary}"
    if not any(term.casefold() in text.casefold() for term in LISTING_TERMS):
        return []

    values: list[str] = []
    values.extend(match.group(1) for match in LEGAL_NAME_RE.finditer(text))
    values.extend(match.group(1) for match in QUOTED_NAME_RE.finditer(title))
    values.extend(match.group(1) for match in ACTION_NAME_RE.finditer(title))
    return unique(
        [name for value in values if (name := safe_company_name(value, brokers))],
        12,
    )


def source_level(article: dict[str, Any]) -> str:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return clean(source.get("level"), 80)


def source_url(article: dict[str, Any]) -> str:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return clean(source.get("url"), 1800)


def source_name(article: dict[str, Any]) -> str:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return clean(source.get("name"), 240)


def source_host(article: dict[str, Any]) -> str:
    host = (urlsplit(source_url(article)).hostname or "").casefold().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def broker_from_source(source_id: str, brokers: list[str]) -> str:
    match = re.fullmatch(
        rf"{re.escape(SOURCE_PREFIX)}"
        rf"(?:broker|a-plus-h)-(\d{{2}})",
        source_id,
    )
    if not match:
        match = re.fullmatch(
            rf"{re.escape(SOURCE_PREFIX)}"
            rf"(?:primary-broker|primary-regulatory)-(\d{{2}})-\d{{2}}",
            source_id,
        )
    if not match:
        return ""
    index = int(match.group(1)) - 1
    return brokers[index] if 0 <= index < len(brokers) else ""


def brokers_for_article(article: dict[str, Any], brokers: list[str]) -> list[str]:
    source_id = clean(article.get("sourceId"), 240)
    direct = broker_from_source(source_id, brokers)
    if direct:
        return [direct]
    text = " ".join(
        (
            clean(article.get("title"), 500),
            clean(article.get("summary"), 900),
            clean(article.get("company"), 240),
        )
    )
    return [broker for broker in brokers if broker and broker in text]


def route_for(text: str) -> str:
    if "科创板" in text:
        return "STAR"
    if "创业板" in text:
        return "ChiNext"
    return "A-share-TBD"


def stage_for(text: str) -> str:
    if "辅导验收" in text:
        return "辅导验收"
    if "辅导备案" in text:
        return "辅导备案"
    if "受理" in text and ("交易所" in text or "IPO" in text or "上市" in text):
        return "交易所受理"
    if "上市辅导" in text or "IPO辅导" in text or "辅导" in text:
        return "辅导中"
    return "待核验"


def policy_tags(text: str, themes: list[str]) -> list[str]:
    folded = normalize(text)
    return [theme for theme in themes if normalize(theme) in folded][:8]


def decision_map(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    raw = payload.get("decisions", {})
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        normalized_key = clean(key, 260)
        status = clean(value.get("status"), 30)
        if not normalized_key or status not in VALID_DECISIONS:
            continue
        result[normalized_key] = {
            "status": status,
            "note": clean(value.get("note"), 600),
            "reviewedBy": clean(value.get("reviewedBy"), 160),
            "decidedAt": clean(value.get("decidedAt"), 80),
        }
    return result


def candidate_id(key: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return f"innovation-listing-{digest}"


def candidate_fingerprint(candidate: dict[str, Any]) -> str:
    payload = {
        "decisionKey": candidate["decisionKey"],
        "broker": candidate["broker"],
        "route": candidate["route"],
        "capitalMarketPath": candidate["capitalMarketPath"],
        "stage": candidate["stage"],
        "evidence": [
            {
                "articleId": row.get("articleId", ""),
                "url": row.get("url", ""),
                "level": row.get("level", ""),
            }
            for row in candidate.get("evidence", [])
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def score_evidence(
    *,
    article: dict[str, Any],
    text: str,
    source_id: str,
    structured: bool,
    tags: list[str],
    reference: datetime | None,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    if re.fullmatch(
        rf"{re.escape(SOURCE_PREFIX)}primary-regulatory-\d{{2}}-\d{{2}}",
        source_id,
    ):
        score += 32
        reasons.append("命中证监会辅导公示定向源")
    elif re.fullmatch(
        rf"{re.escape(SOURCE_PREFIX)}primary-broker-\d{{2}}-\d{{2}}",
        source_id,
    ):
        score += 28
        reasons.append("命中券商官方定向源")
    elif re.fullmatch(rf"{re.escape(SOURCE_PREFIX)}(?:broker|a-plus-h)-\d{{2}}", source_id):
        score += 20
        reasons.append("命中五大券商定向发现源")
    elif source_id.startswith(f"{SOURCE_PREFIX}policy-"):
        score += 12
        reasons.append("命中十五五硬科技定向发现源")

    if structured:
        score += 15
        reasons.append("文章已有结构化公司字段")
    else:
        score += 8
        reasons.append("标题满足保守公司名提取规则")

    route = route_for(text)
    if route in {"STAR", "ChiNext"}:
        score += 20
        reasons.append("正文明确出现科创板/创业板路径")
    elif "A股" in text or "IPO" in text:
        score += 10
        reasons.append("出现A股/IPO路径信号")

    stage = stage_for(text)
    if stage in {"辅导验收", "辅导备案", "辅导中"}:
        score += 18
        reasons.append(f"出现{stage}信号")
    elif stage == "交易所受理":
        score += 12
        reasons.append("出现交易所受理信号")

    if any(term in text for term in A_PLUS_H_TERMS):
        score += 15
        reasons.append("出现A+H/H股资本路径信号")

    if tags:
        score += 12
        reasons.append(f"命中十五五主题：{'、'.join(tags[:3])}")

    if source_level(article) in PRIMARY_SOURCE_LEVELS:
        score += 25
        reasons.append("存在官方/监管/交易所一级证据")

    published = parse_date(article.get("publishedAt"))
    if reference and published and published >= reference - timedelta(days=120):
        score += 8
        reasons.append("最近120天的新发现")

    return min(100, score), reasons[:6]


def build_candidate_snapshot(
    articles_payload: Any,
    watchlist_payload: dict[str, Any],
    decisions_payload: Any | None = None,
) -> dict[str, Any]:
    rows = article_rows(articles_payload)
    brokers = [
        clean(value, 120)
        for value in watchlist_payload.get("brokers", [])
        if clean(value, 120)
    ][:10]
    broker_set = set(brokers)
    themes = [
        clean(value, 120)
        for value in watchlist_payload.get("policyThemes", [])
        if clean(value, 120)
    ][:80]
    known = {
        identity(project.get("company"))
        for project in watchlist_payload.get("projects", [])
        if isinstance(project, dict) and identity(project.get("company"))
    }
    decisions = decision_map(decisions_payload or {})
    generated = generated_at(articles_payload, rows)
    reference = parse_date(generated)

    groups: dict[str, dict[str, Any]] = {}

    for article in rows:
        source_id = clean(article.get("sourceId"), 240)
        if not source_id.startswith(SOURCE_PREFIX):
            continue
        # Existing-project shards are for lifecycle monitoring, not candidate
        # creation. Never re-create reviewed projects from those articles.
        if source_id.startswith(f"{SOURCE_PREFIX}projects-"):
            continue

        text = " ".join(
            (
                clean(article.get("title"), 500),
                clean(article.get("summary"), 900),
            )
        )
        if not any(term.casefold() in text.casefold() for term in LISTING_TERMS):
            continue

        article_brokers = brokers_for_article(article, brokers)
        if not article_brokers:
            continue

        structured = structured_names(article, broker_set)
        extracted = unique([*structured, *title_names(article, broker_set)], 16)
        if not extracted:
            continue

        tags = policy_tags(text, themes)
        score, reasons = score_evidence(
            article=article,
            text=text,
            source_id=source_id,
            structured=bool(structured),
            tags=tags,
            reference=reference,
        )
        if score < MINIMUM_SCORE:
            continue

        evidence = {
            "articleId": clean(article.get("id"), 260),
            "sourceId": source_id,
            "title": clean(article.get("title"), 500),
            "url": source_url(article),
            "sourceName": source_name(article),
            "host": source_host(article),
            "level": source_level(article) or "待交叉验证",
            "publishedAt": clean(article.get("publishedAt"), 80),
        }

        for broker in article_brokers:
            for company in extracted:
                key_company = identity(company)
                if not key_company or key_company in known:
                    continue
                decision_key = f"{key_company}|{identity(broker)}"
                row = groups.setdefault(
                    decision_key,
                    {
                        "decisionKey": decision_key,
                        "names": Counter(),
                        "broker": broker,
                        "score": 0,
                        "reasons": [],
                        "routes": Counter(),
                        "paths": Counter(),
                        "stages": Counter(),
                        "sectors": Counter(),
                        "tags": Counter(),
                        "dates": [],
                        "events": [],
                        "evidence": [],
                    },
                )
                row["names"][company] += 1
                row["score"] = max(int(row["score"]), score)
                row["reasons"] = unique([*row["reasons"], *reasons], 8)
                row["routes"][route_for(text)] += 1
                row["paths"]["A+H" if any(term in text for term in A_PLUS_H_TERMS) else "A"] += 1
                row["stages"][stage_for(text)] += 1
                sector = clean(article.get("sector"), 160)
                if sector and sector != "风险投资":
                    row["sectors"][sector] += 1
                for tag in tags:
                    row["tags"][tag] += 1
                date = clean(article.get("publishedAt"), 80)
                if date:
                    row["dates"].append(date[:10])
                event = clean(article.get("title"), 500)
                if event:
                    row["events"].append(event)
                fingerprint = (
                    evidence["articleId"],
                    evidence["url"],
                    evidence["sourceId"],
                )
                existing = {
                    (
                        item.get("articleId", ""),
                        item.get("url", ""),
                        item.get("sourceId", ""),
                    )
                    for item in row["evidence"]
                }
                if fingerprint not in existing:
                    row["evidence"].append(evidence)

    candidates: list[dict[str, Any]] = []
    for decision_key, raw in groups.items():
        names: Counter[str] = raw["names"]
        company = sorted(
            names,
            key=lambda value: (-names[value], -len(value), value.casefold()),
        )[0]
        route = raw["routes"].most_common(1)[0][0]
        path = raw["paths"].most_common(1)[0][0]
        stage = raw["stages"].most_common(1)[0][0]
        sector = raw["sectors"].most_common(1)[0][0] if raw["sectors"] else "待分类"
        tags = [
            item
            for item, _count in sorted(
                raw["tags"].items(),
                key=lambda pair: (-pair[1], pair[0]),
            )
        ][:8]
        dates = sorted(set(raw["dates"]))
        evidence = sorted(
            raw["evidence"],
            key=lambda item: (
                0 if item.get("level") in PRIMARY_SOURCE_LEVELS else 1,
                str(item.get("publishedAt", "")),
                str(item.get("title", "")),
            ),
            reverse=False,
        )[:8]
        primary_count = sum(
            1 for item in evidence if item.get("level") in PRIMARY_SOURCE_LEVELS
        )
        decision = decisions.get(decision_key, {})
        candidate = {
            "id": candidate_id(decision_key),
            "decisionKey": decision_key,
            "company": company,
            "aliases": sorted(names, key=lambda value: (-names[value], value.casefold()))[:8],
            "broker": raw["broker"],
            "sector": sector,
            "route": route,
            "routeConfidence": "discovery",
            "capitalMarketPath": path,
            "stage": stage,
            "firstSeenAt": dates[0] if dates else "",
            "lastSeenAt": dates[-1] if dates else "",
            "latestEvent": raw["events"][0] if raw["events"] else "",
            "fifteenthTags": tags,
            "score": min(100, int(raw["score"]) + min(10, max(0, len(evidence) - 1) * 3)),
            "reasons": raw["reasons"],
            "evidenceClass": "primary-backed" if primary_count else "discovery-only",
            "reviewPriority": "primary-first" if primary_count else "needs-primary-evidence",
            "primaryEvidenceCount": primary_count,
            "evidenceCount": len(evidence),
            "evidence": evidence,
            "status": decision.get("status", "pending"),
            "reviewNote": decision.get("note", ""),
            "reviewedBy": decision.get("reviewedBy", ""),
            "decidedAt": decision.get("decidedAt", ""),
        }
        candidate["candidateFingerprint"] = candidate_fingerprint(candidate)
        candidates.append(candidate)

    candidates.sort(
        key=lambda item: (
            0 if item["status"] == "pending" else 1,
            0 if item["evidenceClass"] == "primary-backed" else 1,
            -int(item["score"]),
            str(item["broker"]),
            str(item["company"]),
        )
    )

    counts = Counter(item["status"] for item in candidates)
    return {
        "schemaVersion": 1,
        "generatedAt": generated,
        "watchlistAsOf": clean(watchlist_payload.get("asOf"), 40),
        "candidateCount": len(candidates),
        "pendingCount": counts["pending"],
        "acceptedCount": counts["accepted"],
        "rejectedCount": counts["rejected"],
        "primaryBackedPendingCount": sum(
            1
            for item in candidates
            if item["status"] == "pending" and item["evidenceClass"] == "primary-backed"
        ),
        "candidates": candidates,
        "governance": {
            "mode": "human-review-required",
            "rule": (
                "自动发现只进入候选队列；不得自动写入 innovation_listing_watchlist.json。"
                "十五五主题只决定发现范围，不推断上市板块。"
                "监管/券商官方证据优先进入人工复核；仅发现型证据须先补一级来源。"
            ),
        },
    }


def serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--articles", type=Path, default=ARTICLES_PATH)
    parser.add_argument("--watchlist", type=Path, default=WATCHLIST_PATH)
    parser.add_argument("--decisions", type=Path, default=DECISIONS_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    articles = load_json(args.articles, {"articles": []})
    watchlist = load_json(args.watchlist, {"brokers": [], "projects": [], "policyThemes": []})
    decisions = load_json(args.decisions, {"decisions": {}})
    if not isinstance(watchlist, dict):
        raise SystemExit("innovation listing watchlist must be an object")

    snapshot = build_candidate_snapshot(articles, watchlist, decisions)
    rendered = serialize(snapshot)

    if args.check:
        try:
            current = args.output.read_text(encoding="utf-8")
        except OSError:
            current = ""
        if current != rendered:
            print("innovation listing candidate review queue is stale")
            return 1
        print(
            json.dumps(
                {
                    "ok": True,
                    "candidateCount": snapshot["candidateCount"],
                    "pendingCount": snapshot["pendingCount"],
                },
                ensure_ascii=False,
            )
        )
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "changed": True,
                "candidateCount": snapshot["candidateCount"],
                "pendingCount": snapshot["pendingCount"],
                "primaryBackedPendingCount": snapshot["primaryBackedPendingCount"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
