#!/usr/bin/env python3
"""Attach articles and crawl coverage to every enabled tracking sector.

The crawler's primary ``sector`` remains unchanged. This post-processor adds a
``trackSlugs`` array so one article can support several legitimate tracking
views, and writes per-track crawl coverage plus a deterministic configuration
hash. Pages can therefore refuse to publish a newly configured track until its
sources have actually been attempted.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

try:
    from . import crawl_with_tracking as tracking
    from . import tracking_taxonomy as taxonomy
except ImportError:
    import crawl_with_tracking as tracking
    import tracking_taxonomy as taxonomy

ROOT = Path(__file__).resolve().parents[1]
TRACKING_PATH = ROOT / "config" / "user_tracking.json"
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"


def clean(value: Any, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def clean_list(value: Any, limit: int = 80) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for raw in value:
        item = clean(raw, 160)
        key = item.casefold()
        if not item or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def enabled_tracks(config: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in config.get("tracks", []):
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue
        name = clean(raw.get("name"), 80)
        slug = clean(raw.get("slug"), 80)
        if not name or not slug:
            continue
        result.append(
            {
                "slug": slug,
                "name": name,
                "keywords": clean_list(raw.get("keywords"), 60),
                "people": clean_list(raw.get("people"), 40),
                "sampleCompanies": clean_list(raw.get("sampleCompanies"), 40),
            }
        )
    return result


def canonical_tracks(tracks: list[dict[str, Any]]) -> str:
    return json.dumps(tracks, ensure_ascii=False, separators=(",", ":"))


def tracking_config_hash(tracks: list[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_tracks(tracks).encode("utf-8")).hexdigest()


def _term_counts(
    tracks: list[dict[str, Any]], field: str
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for track in tracks:
        seen: set[str] = set()
        for value in track.get(field, []):
            normalized = taxonomy.normalize_term(value)
            if normalized and normalized not in seen:
                counts[normalized] += 1
                seen.add(normalized)
    return counts


def _unique_terms(
    track: dict[str, Any], field: str, counts: Counter[str]
) -> list[str]:
    return [
        value
        for value in track.get(field, [])
        if counts[taxonomy.normalize_term(value)] == 1
    ]


def _person_terms(track: dict[str, Any]) -> list[str]:
    return tracking._person_search_terms(track.get("people", []))


def _matchable_name_terms(name: str) -> list[str]:
    result: list[str] = []
    for value in taxonomy.name_aliases(name):
        normalized = taxonomy.normalize_term(value)
        cjk = len(re.findall(r"[\u3400-\u9fff]", normalized))
        latin = len(re.findall(r"[a-z0-9]", normalized))
        if cjk >= 2 or latin >= 4:
            result.append(value)
    return result


def article_text(article: dict[str, Any]) -> str:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    values: list[Any] = [
        article.get("title"),
        article.get("summary"),
        article.get("company"),
        article.get("sector"),
        source.get("name"),
    ]
    values.extend(article.get("authors", []) if isinstance(article.get("authors"), list) else [])
    values.extend(
        article.get("institutions", [])
        if isinstance(article.get("institutions"), list)
        else []
    )
    return " ".join(clean(value) for value in values if clean(value))


def _contains(normalized_text: str, value: str) -> bool:
    normalized = taxonomy.normalize_term(value)
    return bool(normalized and normalized in normalized_text)


def assign_track_slugs(
    articles: list[dict[str, Any]], tracks: list[dict[str, Any]]
) -> dict[str, int]:
    keyword_counts = _term_counts(tracks, "keywords")
    company_counts = _term_counts(tracks, "sampleCompanies")
    person_values = [
        {**track, "personSearchTerms": _person_terms(track)} for track in tracks
    ]
    person_counts: Counter[str] = Counter()
    for track in person_values:
        seen: set[str] = set()
        for value in track["personSearchTerms"]:
            normalized = taxonomy.normalize_term(value)
            if normalized and normalized not in seen:
                person_counts[normalized] += 1
                seen.add(normalized)

    matched_counts = Counter[str]()
    backfilled_counts = Counter[str]()

    for article in articles:
        normalized_text = taxonomy.normalize_term(article_text(article))
        sector_key = taxonomy.normalize_term(article.get("sector"))
        assigned: list[str] = []

        for track in person_values:
            slug = track["slug"]
            name_alias_keys = {
                taxonomy.normalize_term(value)
                for value in taxonomy.name_aliases(track["name"])
            }
            direct = sector_key in name_alias_keys
            name_hit = any(
                _contains(normalized_text, value)
                for value in _matchable_name_terms(track["name"])
            )
            keyword_hit = any(
                _contains(normalized_text, value)
                for value in _unique_terms(track, "keywords", keyword_counts)
            )
            company_hit = any(
                _contains(normalized_text, value)
                for value in _unique_terms(
                    track, "sampleCompanies", company_counts
                )
            )
            person_hit = any(
                _contains(normalized_text, value)
                for value in track["personSearchTerms"]
                if person_counts[taxonomy.normalize_term(value)] == 1
            )

            if direct or name_hit or keyword_hit or company_hit or person_hit:
                assigned.append(slug)
                matched_counts[slug] += 1
                if not direct:
                    backfilled_counts[slug] += 1

        article["trackSlugs"] = assigned

    return {
        **{f"matched:{slug}": count for slug, count in matched_counts.items()},
        **{f"backfilled:{slug}": count for slug, count in backfilled_counts.items()},
    }


def build_coverage(
    payload: dict[str, Any], tracks: list[dict[str, Any]], counts: dict[str, int]
) -> dict[str, dict[str, Any]]:
    statuses = [
        item for item in payload.get("sourceStatus", []) if isinstance(item, dict)
    ]
    articles = [
        item for item in payload.get("articles", []) if isinstance(item, dict)
    ]
    generated_at = clean(payload.get("generatedAt"), 60)
    coverage: dict[str, dict[str, Any]] = {}

    for track in tracks:
        slug = track["slug"]
        expected_ids = set(taxonomy.expected_source_ids(slug))
        relevant_statuses = [
            item for item in statuses if clean(item.get("id"), 120) in expected_ids
        ]
        completed = len(relevant_statuses)
        failed = sum(item.get("status") == "error" for item in relevant_statuses)
        healthy = sum(
            item.get("status") in {"ok", "partial"}
            and int(item.get("accepted", 0) or 0) > 0
            for item in relevant_statuses
        )
        scanned = sum(int(item.get("scanned", 0) or 0) for item in relevant_statuses)
        accepted = sum(int(item.get("accepted", 0) or 0) for item in relevant_statuses)
        matched = counts.get(f"matched:{slug}", 0)
        backfilled = counts.get(f"backfilled:{slug}", 0)
        track_articles = [
            article
            for article in articles
            if slug in article.get("trackSlugs", [])
        ]
        source_count = len(
            {
                clean(article.get("source", {}).get("url"), 500)
                for article in track_articles
                if isinstance(article.get("source"), dict)
                and clean(article.get("source", {}).get("url"), 500)
            }
        )

        route_count = len(expected_ids)
        if completed == 0:
            status = "pending"
            label = "等待爬取"
            message = f"配置已写入，但 {route_count} 路赛道发现源尚未完成首次运行。"
        elif completed < len(expected_ids):
            status = "partial"
            label = "部分完成"
            message = f"已完成 {completed}/{len(expected_ids)} 路发现源，等待其余来源。"
        elif matched > 0 and failed == 0:
            status = "ready"
            label = "已完成"
            message = f"{route_count} 路发现均已尝试，当前匹配 {matched} 条公开事件。"
        elif matched > 0:
            status = "partial"
            label = "部分可用"
            message = f"已匹配 {matched} 条事件，但有 {failed} 路来源失败。"
        elif failed == completed:
            status = "error"
            label = "爬取失败"
            message = f"{route_count} 路发现源均失败，请检查外部搜索服务或工作流日志。"
        else:
            status = "empty"
            label = "已运行但无命中"
            message = f"{route_count} 路发现均已尝试，但当前快照没有满足匹配条件的文章。"

        coverage[slug] = {
            "slug": slug,
            "name": track["name"],
            "status": status,
            "label": label,
            "expectedSources": len(expected_ids),
            "completedSources": completed,
            "healthySources": healthy,
            "failedSources": failed,
            "scanned": scanned,
            "accepted": accepted,
            "matchedArticles": matched,
            "backfilledArticles": backfilled,
            "independentSources": source_count,
            "lastRun": generated_at,
            "message": message,
        }

    return coverage


def enrich(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(payload, ensure_ascii=False))
    tracks = enabled_tracks(config)
    articles = [
        item for item in result.get("articles", []) if isinstance(item, dict)
    ]
    result["articles"] = articles
    result["articleCount"] = len(articles)
    counts = assign_track_slugs(articles, tracks)
    result["trackingConfigHash"] = tracking_config_hash(tracks)
    result["trackingEnrichedAt"] = datetime.now(UTC).replace(microsecond=0).isoformat()
    result["trackCoverage"] = build_coverage(result, tracks, counts)
    return result


def main() -> int:
    if not TRACKING_PATH.exists() or not ARTICLES_PATH.exists():
        raise SystemExit("tracking configuration or article snapshot is missing")
    config = json.loads(TRACKING_PATH.read_text(encoding="utf-8"))
    payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not isinstance(payload, dict):
        raise SystemExit("tracking configuration and article snapshot must be objects")
    enriched = enrich(payload, config)
    if enriched != payload:
        ARTICLES_PATH.write_text(
            json.dumps(enriched, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "trackingConfigHash": enriched.get("trackingConfigHash"),
                "tracks": len(enriched.get("trackCoverage", {})),
                "matched": sum(
                    item.get("matchedArticles", 0)
                    for item in enriched.get("trackCoverage", {}).values()
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
