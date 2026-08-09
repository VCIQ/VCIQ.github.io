#!/usr/bin/env python3
"""Build an evidence-backed review pool for previously unknown companies.

Only structured company fields are considered. Titles and summaries never create
new companies by themselves. The output is a review queue. A reviewed
candidate becomes a formal route only after a versioned onboarding request passes
registry, official-source and profile publication gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

try:
    from .resolve_company_entities import CompanyRegistry, load_registry, normalize_identity
except ImportError:
    from resolve_company_entities import CompanyRegistry, load_registry, normalize_identity

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
DECISIONS_PATH = ROOT / "config" / "company_candidate_decisions.json"
CAPTURE_INBOX_PATH = ROOT / "config" / "tracking_capture_inbox.json"
OUTPUT_PATH = ROOT / "config" / "company_candidate_review_queue.json"
MINIMUM_SCORE = 35
GENERIC_NAMES = {
    "",
    "科技产业",
    "产业",
    "行业",
    "公司",
    "科技公司",
    "未识别",
    "资本动态",
    "项目",
    "企业",
}
HIGH_SIGNAL_TYPES = {"融资", "产业投资", "并购", "IPO", "产品发布", "技术突破", "监管文件"}
PRIMARY_SOURCE_LEVELS = {"官方披露", "原始材料", "监管文件", "交易所公告"}
VALID_DECISIONS = {"pending", "accepted", "rejected", "merged", "published"}


def clean(value: Any, limit: int = 1000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def normalized_host(value: Any) -> str:
    host = (urlsplit(clean(value, 2000)).hostname or "").casefold().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def parse_time(value: Any) -> datetime | None:
    text = clean(value, 60)
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


def safe_candidate_name(value: Any) -> str:
    name = clean(value, 120).strip(" ,，:：;；|｜-—")
    key = normalize_identity(name)
    if not name or name in GENERIC_NAMES or len(key) < 2:
        return ""
    if len(name) > 100 or re.search(r"https?://|@", name, re.IGNORECASE):
        return ""
    if name.count(" ") > 7 or re.fullmatch(r"[\d._-]+", name):
        return ""
    if re.fullmatch(r"(?:融资|投资|产品|技术|政策|研究|市场|新闻|报告|财报|公告)+", name):
        return ""
    return name


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def decision_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = payload.get("decisions") if isinstance(payload, dict) else {}
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for raw_key, raw_value in raw.items():
        if not isinstance(raw_value, dict):
            continue
        key = normalize_identity(raw_key)
        status = clean(raw_value.get("status"), 20)
        if not key or status not in VALID_DECISIONS:
            continue
        result[key] = {
            "status": status,
            "note": clean(raw_value.get("note"), 300),
            "mergedSlug": clean(raw_value.get("mergedSlug"), 100),
            "decidedAt": clean(raw_value.get("decidedAt"), 80),
            "reviewedBy": clean(raw_value.get("reviewedBy"), 120),
            "onboarding": raw_value.get("onboarding")
            if isinstance(raw_value.get("onboarding"), dict)
            else {},
        }
    return result


def known_aliases(registry: CompanyRegistry) -> set[str]:
    return set(registry.by_alias)


def structured_names(article: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    company = article.get("company")
    if company not in (None, ""):
        values.append(company)
    mentioned = article.get("mentionedCompanies")
    if isinstance(mentioned, list):
        values.extend(mentioned)
    candidates = article.get("companyCandidateNames")
    if isinstance(candidates, list):
        values.extend(candidates)

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        name = safe_candidate_name(value)
        key = normalize_identity(name)
        if not name or not key or key in seen:
            continue
        result.append(name)
        seen.add(key)
    return result


def candidate_id(key: str) -> str:
    readable = re.sub(r"[^a-z0-9]+", "-", key.casefold()).strip("-")[:40] or "company"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return f"candidate-{readable}-{digest}"


def unique(values: Iterable[str], limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = clean(value, 1000)
        if not item or item in seen:
            continue
        result.append(item)
        seen.add(item)
        if len(result) >= limit:
            break
    return result


def _score_candidate(row: dict[str, Any], reference: datetime) -> tuple[int, list[str]]:
    article_count = len(row["articleIds"])
    source_count = len(row["sourceHosts"])
    event_types = set(row["eventTypes"])
    score = min(20, article_count * 5)
    reasons: list[str] = []
    manual_capture_count = len(row.get("manualCaptureIds", []))

    if manual_capture_count:
        score += 35
        reasons.append(f"{manual_capture_count} 条管理员文章采集")

    if article_count >= 2:
        reasons.append(f"{article_count} 条结构化公司记录")
    if source_count >= 3:
        score += 25
        reasons.append(f"{source_count} 个独立公开来源")
    elif source_count >= 2:
        score += 15
        reasons.append("至少两个独立公开来源")

    high_signals = sorted(event_types & HIGH_SIGNAL_TYPES)
    if high_signals:
        score += 20
        reasons.append(f"出现{'、'.join(high_signals[:3])}等高信号事件")

    if row["primaryEvidence"]:
        score += 20
        reasons.append("存在官方、原始或监管来源")

    last_seen = parse_time(row["lastSeenAt"])
    if last_seen and last_seen >= reference - timedelta(days=90):
        score += 10
        reasons.append("最近 90 天仍有公开活动")

    display_name = row["displayName"]
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", display_name))
    latin_count = len(re.findall(r"[a-z0-9]", display_name.casefold()))
    if cjk_count >= 3 or latin_count >= 6:
        score += 5

    return min(100, score), reasons[:5]


def build_candidate_snapshot(
    articles_payload: dict[str, Any],
    registry: CompanyRegistry,
    decisions_payload: dict[str, Any] | None = None,
    captures_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    known = known_aliases(registry)
    decisions = decision_map(decisions_payload or {})
    groups: dict[str, dict[str, Any]] = {}

    generated_at = clean(articles_payload.get("generatedAt"), 60)
    reference = parse_time(generated_at) or datetime.now(UTC)

    for article in articles_payload.get("articles", []):
        if not isinstance(article, dict):
            continue
        source = article.get("source") if isinstance(article.get("source"), dict) else {}
        source_url = clean(source.get("url"), 1200)
        source_host = normalized_host(source_url) or clean(source.get("name"), 200)
        source_level = clean(source.get("level"), 80)
        article_id = clean(article.get("id"), 200)
        published_at = clean(article.get("publishedAt"), 60)
        event_type = clean(article.get("type"), 80)
        sector = clean(article.get("sector"), 100)
        region = clean(article.get("region"), 40)

        for name in structured_names(article):
            key = normalize_identity(name)
            if not key or (key in known and key not in decisions):
                continue
            row = groups.setdefault(
                key,
                {
                    "names": Counter(),
                    "articleIds": set(),
                    "sourceHosts": set(),
                    "sourceUrls": [],
                    "eventTypes": set(),
                    "sectors": Counter(),
                    "regions": Counter(),
                    "publishedTimes": [],
                    "primaryEvidence": False,
                    "manualCaptureIds": set(),
                },
            )
            row["names"][name] += 1
            if article_id:
                row["articleIds"].add(article_id)
            if source_host:
                row["sourceHosts"].add(source_host)
            if source_url:
                row["sourceUrls"].append(source_url)
            if event_type:
                row["eventTypes"].add(event_type)
            if sector:
                row["sectors"][sector] += 1
            if region:
                row["regions"][region] += 1
            parsed_time = parse_time(published_at)
            if parsed_time:
                row["publishedTimes"].append(parsed_time)
            if source_level in PRIMARY_SOURCE_LEVELS:
                row["primaryEvidence"] = True

    for capture in (captures_payload or {}).get("records", []):
        if not isinstance(capture, dict):
            continue
        if clean(capture.get("status"), 20) not in {"queued", "applied"}:
            continue
        if clean(capture.get("entityType"), 20) != "company":
            continue
        name = safe_candidate_name(capture.get("canonicalName"))
        key = normalize_identity(name)
        if not name or not key or (key in known and key not in decisions):
            continue

        source = capture.get("source") if isinstance(capture.get("source"), dict) else {}
        source_url = clean(source.get("url"), 1200)
        source_host = normalized_host(source_url) or clean(source.get("sourceName"), 200)
        capture_id = clean(capture.get("id"), 200) or candidate_id(f"capture-{key}")
        captured_at = clean(capture.get("capturedAt"), 60)
        event_type = clean(source.get("eventType"), 80) or "人工关注"
        track_names = capture.get("trackNames") if isinstance(capture.get("trackNames"), list) else []

        row = groups.setdefault(
            key,
            {
                "names": Counter(),
                "articleIds": set(),
                "sourceHosts": set(),
                "sourceUrls": [],
                "eventTypes": set(),
                "sectors": Counter(),
                "regions": Counter(),
                "publishedTimes": [],
                "primaryEvidence": False,
                "manualCaptureIds": set(),
            },
        )
        row["names"][name] += 1
        row["articleIds"].add(capture_id)
        row["manualCaptureIds"].add(capture_id)
        if source_host:
            row["sourceHosts"].add(source_host)
        if source_url:
            row["sourceUrls"].append(source_url)
        if event_type:
            row["eventTypes"].add(event_type)
        for track_name in track_names:
            sector = clean(track_name, 100)
            if sector:
                row["sectors"][sector] += 1
        parsed_time = parse_time(captured_at)
        if parsed_time:
            row["publishedTimes"].append(parsed_time)

    candidates: list[dict[str, Any]] = []
    for key, raw in groups.items():
        display_name = sorted(
            raw["names"].items(),
            key=lambda item: (-item[1], -len(item[0]), item[0].casefold()),
        )[0][0]
        published_times: list[datetime] = raw["publishedTimes"]
        first_seen = min(published_times).isoformat() if published_times else ""
        last_seen = max(published_times).isoformat() if published_times else ""
        row = {
            **raw,
            "displayName": display_name,
            "firstSeenAt": first_seen,
            "lastSeenAt": last_seen,
        }
        score, reasons = _score_candidate(row, reference)
        decision = decisions.get(key, {})
        status = decision.get("status", "pending")
        if score < MINIMUM_SCORE and not decision:
            continue

        aliases = sorted(raw["names"], key=lambda name: (-raw["names"][name], name.casefold()))
        sectors = sorted(raw["sectors"], key=lambda value: (-raw["sectors"][value], value))
        regions = sorted(raw["regions"], key=lambda value: (-raw["regions"][value], value))
        candidates.append(
            {
                "id": candidate_id(key),
                "decisionKey": key,
                "name": display_name,
                "aliases": aliases[:8],
                "region": regions[0] if regions else "全球",
                "sector": sectors[0] if sectors else "待分类",
                "score": score,
                "status": status,
                "reasons": reasons,
                "firstSeenAt": first_seen,
                "lastSeenAt": last_seen,
                "articleCount": len(raw["articleIds"]),
                "captureCount": len(raw["manualCaptureIds"]),
                "captureIds": sorted(raw["manualCaptureIds"])[:20],
                "sourceCount": len(raw["sourceHosts"]),
                "sourceHosts": sorted(raw["sourceHosts"])[:10],
                "sourceArticleIds": sorted(raw["articleIds"])[:20],
                "sourceUrls": unique(raw["sourceUrls"], 10),
                "eventTypes": sorted(raw["eventTypes"]),
                "note": decision.get("note", ""),
                "mergedSlug": decision.get("mergedSlug", ""),
                "decidedAt": decision.get("decidedAt", ""),
                "reviewedBy": decision.get("reviewedBy", ""),
                "onboarding": decision.get("onboarding", {}),
            }
        )

    status_order = {"pending": 0, "accepted": 1, "published": 2, "merged": 3, "rejected": 4}
    candidates.sort(
        key=lambda row: (
            status_order.get(row["status"], 9),
            -int(row["score"]),
            str(row["lastSeenAt"]),
            str(row["name"]).casefold(),
        )
    )
    counts = Counter(row["status"] for row in candidates)
    return {
        "schemaVersion": 1,
        "generatedAt": generated_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "candidateCount": len(candidates),
        "pendingCount": counts["pending"],
        "acceptedCount": counts["accepted"],
        "rejectedCount": counts["rejected"],
        "mergedCount": counts["merged"],
        "publishedCount": counts["published"],
        "candidates": candidates,
    }


def semantic_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.pop("generatedAt", None)
    return result


def write_snapshot(snapshot: dict[str, Any], path: Path = OUTPUT_PATH) -> bool:
    previous = load_json(path, {})
    if semantic_payload(previous) == semantic_payload(snapshot):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--articles", type=Path, default=ARTICLES_PATH)
    parser.add_argument("--decisions", type=Path, default=DECISIONS_PATH)
    parser.add_argument("--captures", type=Path, default=CAPTURE_INBOX_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    articles = load_json(args.articles, {"articles": []})
    decisions = load_json(args.decisions, {"decisions": {}})
    captures = load_json(args.captures, {"records": []})
    snapshot = build_candidate_snapshot(articles, load_registry(), decisions, captures)
    if args.check:
        current = load_json(args.output, {})
        if semantic_payload(current) != semantic_payload(snapshot):
            raise SystemExit("company candidate snapshot is not current")
        print(json.dumps({"valid": True, "candidateCount": snapshot["candidateCount"]}))
        return 0

    changed = write_snapshot(snapshot, args.output)
    print(
        json.dumps(
            {
                "changed": changed,
                "candidateCount": snapshot["candidateCount"],
                "pendingCount": snapshot["pendingCount"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
