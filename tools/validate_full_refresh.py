#!/usr/bin/env python3
"""Validate that a committed snapshot came from one complete crawler run."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from . import crawl_articles
    from . import crawl_official_companies
    from . import crawl_with_tracking
    from . import wechat_source_registry
except ImportError:
    import crawl_articles
    import crawl_official_companies
    import crawl_with_tracking
    import wechat_source_registry

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
TAIPEI = ZoneInfo("Asia/Taipei")
# At the first morning runs, many publishers have not posted yet. From 10:00
# Taipei onward, require a diverse same-day batch, but ramp the article floor
# until noon so a healthy 10:xx run is not failed merely because publishers
# have not yet produced the full daily volume.
FRESHNESS_GATE_HOUR = 10
FULL_DAILY_FRESHNESS_HOUR = 12
MORNING_MIN_TODAY_ARTICLES = 4
MIN_TODAY_ARTICLES = 8
MIN_TODAY_SOURCES = 3
# The verified, sector-aware WeChat registry replaces this legacy broad Bing
# probe at runtime. Requiring both would incorrectly fail a complete run.
RUNTIME_REPLACED_SOURCE_IDS = {"wechat-public-index"}


def _enabled_ids(rows: object) -> set[str]:
    if not isinstance(rows, list):
        return set()
    return {
        str(row.get("id"))
        for row in rows
        if isinstance(row, dict)
        and row.get("id")
        and row.get("enabled", True) is not False
    }


def _parse_completed_at(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(TAIPEI)
    except ValueError:
        return None


def _parse_local_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def main() -> int:
    payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    audit = payload.get("refreshAudit")
    statuses = [item for item in payload.get("sourceStatus", []) if isinstance(item, dict)]
    errors: list[str] = []

    if not isinstance(audit, dict):
        errors.append("missing refreshAudit")
        audit = {}
    if audit.get("mode") != "full" or audit.get("pipelineCompleted") is not True:
        errors.append("snapshot was not finalized by the full refresh pipeline")

    completed_at = str(audit.get("completedAt") or "")
    completed_local = _parse_completed_at(completed_at)
    if not completed_at:
        errors.append("missing refresh completion timestamp")
    elif completed_local is None:
        errors.append("invalid refresh completion timestamp")

    local_date = _parse_local_date(audit.get("localDate"))
    if local_date is None:
        errors.append("missing or invalid refresh local date")
    elif completed_local and local_date != completed_local.date():
        errors.append("refresh local date does not match completion timestamp")

    status_ids = [str(item.get("id") or "") for item in statuses]
    status_id_set = {value for value in status_ids if value}
    if len(status_id_set) != len([value for value in status_ids if value]):
        errors.append("duplicate source status ids")
    if not statuses:
        errors.append("source status ledger is empty")
    if completed_at and any(item.get("lastAttemptAt") != completed_at for item in statuses):
        errors.append("source status ledger contains stale rows")

    config = crawl_articles.load_config()
    expected_core = {source.id for source in crawl_articles.NEWS_SOURCES}
    expected_core.update(_enabled_ids(config.get("feeds")))
    expected_core.update(_enabled_ids(config.get("xProfiles")))
    expected_core.update(_enabled_ids(config.get("papers")))
    expected_core.update(_enabled_ids(config.get("publicDiscovery")))
    expected_core.difference_update(RUNTIME_REPLACED_SOURCE_IDS)

    tracking_config = crawl_with_tracking.load_tracking()
    enabled_tracks = crawl_with_tracking._enabled_tracks(tracking_config)
    expected_wechat = {
        str(spec.get("id"))
        for spec in wechat_source_registry.generated_wechat_sources(
            enabled_tracks,
            crawl_with_tracking,
        )
        if spec.get("id") and spec.get("enabled", True) is not False
    }

    official_specs = crawl_official_companies.load_registry()
    expected_official = {spec.source_id for spec in official_specs}

    missing_core = sorted(expected_core - status_id_set)
    missing_wechat = sorted(expected_wechat - status_id_set)
    missing_official = sorted(expected_official - status_id_set)
    if missing_core:
        errors.append(f"missing core source statuses: {', '.join(missing_core)}")
    if missing_wechat:
        errors.append(
            "missing verified WeChat source statuses: " + ", ".join(missing_wechat)
        )
    if missing_official:
        errors.append(
            "missing official company statuses: " + ", ".join(missing_official)
        )

    quality_gate = payload.get("qualityGate")
    if not isinstance(quality_gate, dict) or quality_gate.get("passed") is not True:
        errors.append("quality gate did not pass")

    coverage = payload.get("trackCoverage")
    if not isinstance(coverage, dict) or not coverage:
        errors.append("tracking coverage is missing")
    else:
        incomplete_tracks = sorted(
            slug
            for slug, row in coverage.items()
            if not isinstance(row, dict)
            or int(row.get("completedSources", 0) or 0)
            < int(row.get("expectedSources", 0) or 0)
        )
        if incomplete_tracks:
            errors.append("incomplete track coverage: " + ", ".join(incomplete_tracks))

    latest_published_at = str(audit.get("latestPublishedAt") or "")
    today_article_count = int(audit.get("todayArticleCount", 0) or 0)
    today_source_count = int(audit.get("todaySourceCount", 0) or 0)
    freshness_enforced = bool(
        completed_local and completed_local.hour >= FRESHNESS_GATE_HOUR
    )
    minimum_today_articles = 0
    if freshness_enforced and completed_local:
        minimum_today_articles = (
            MORNING_MIN_TODAY_ARTICLES
            if completed_local.hour < FULL_DAILY_FRESHNESS_HOUR
            else MIN_TODAY_ARTICLES
        )

    if local_date:
        minimum_recent_date = (local_date - timedelta(days=1)).isoformat()
        if not latest_published_at or latest_published_at < minimum_recent_date:
            errors.append(
                f"latest article is stale: {latest_published_at or 'missing'}"
            )

    if freshness_enforced and local_date:
        expected_date = local_date.isoformat()
        if latest_published_at != expected_date:
            errors.append(
                f"latest article date {latest_published_at or 'missing'} is not {expected_date}"
            )
        if today_article_count < minimum_today_articles:
            errors.append(
                f"insufficient same-day articles: {today_article_count} < {minimum_today_articles}"
            )
        if today_source_count < MIN_TODAY_SOURCES:
            errors.append(
                f"insufficient same-day source diversity: {today_source_count} < {MIN_TODAY_SOURCES}"
            )

    expected_total = len(expected_core | expected_wechat | expected_official)
    attempted_expected = len(
        (expected_core | expected_wechat | expected_official) & status_id_set
    )
    coverage_rate = attempted_expected / expected_total if expected_total else 0.0

    summary = {
        "sourceStatuses": len(statuses),
        "expectedCoreSources": len(expected_core),
        "expectedWeChatSources": len(expected_wechat),
        "expectedOfficialCompanies": len(expected_official),
        "expectedSourceCoverageRate": round(coverage_rate, 4),
        "latestPublishedAt": latest_published_at,
        "todayArticleCount": today_article_count,
        "todaySourceCount": today_source_count,
        "freshnessEnforced": freshness_enforced,
        "minimumTodayArticles": minimum_today_articles,
        "minimumTodaySources": MIN_TODAY_SOURCES if freshness_enforced else 0,
        "errors": errors,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
