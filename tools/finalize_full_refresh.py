#!/usr/bin/env python3
"""Finalize a completed full-source intelligence refresh.

All source statuses in the snapshot are known to belong to this run because
``prepare_full_refresh.py`` clears the ledger before network crawling starts.
This script stamps those rows with one completion timestamp and publishes a
compact audit summary for the UI and validators.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
BASELINE_PATH = Path(os.environ.get("RUNNER_TEMP", str(ROOT))) / "vciq-refresh-baseline.json"
TAIPEI = ZoneInfo("Asia/Taipei")
PIPELINE_STAGES = [
    "core-and-tracking-sources",
    "official-company-sources",
    "market-profiles",
    "entity-migration",
    "eastmoney-refinement",
    "tracking-enrichment",
    "people-profiles",
]


def _source_key(article: dict) -> str:
    source_id = str(article.get("sourceId") or "").strip()
    if source_id:
        return source_id
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return str(source.get("name") or "unknown").strip() or "unknown"


def _article_identity(article: dict) -> str:
    article_id = str(article.get("id") or "").strip()
    if article_id:
        return article_id
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return str(source.get("url") or "").strip()


def _load_baseline() -> dict | None:
    if not BASELINE_PATH.exists():
        return None
    try:
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    finally:
        BASELINE_PATH.unlink(missing_ok=True)
    return baseline if isinstance(baseline, dict) else None


def _refresh_delta(
    payload: dict,
    articles: list[dict],
) -> tuple[int, int]:
    baseline = _load_baseline()
    previous_audit = payload.get("refreshAudit")
    previous_audit = previous_audit if isinstance(previous_audit, dict) else {}

    if isinstance(baseline, dict):
        baseline_ids = {
            str(value).strip()
            for value in baseline.get("articleIds", [])
            if str(value).strip()
        }
        previous_count = int(baseline.get("articleCount", len(baseline_ids)) or 0)
        new_count = sum(
            bool(identity) and identity not in baseline_ids
            for identity in (_article_identity(article) for article in articles)
        )
        return previous_count, new_count

    return (
        int(previous_audit.get("previousArticleCount", len(articles)) or 0),
        int(previous_audit.get("newArticleCount", 0) or 0),
    )


def main() -> int:
    if not ARTICLES_PATH.exists():
        raise SystemExit(f"missing snapshot: {ARTICLES_PATH}")

    payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("article snapshot must be a JSON object")

    completed_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    local_date = datetime.now(TAIPEI).date().isoformat()
    articles = [item for item in payload.get("articles", []) if isinstance(item, dict)]
    statuses = [item for item in payload.get("sourceStatus", []) if isinstance(item, dict)]
    previous_article_count, new_article_count = _refresh_delta(payload, articles)

    for status in statuses:
        status["lastAttemptAt"] = completed_at

    status_counts = Counter(str(item.get("status") or "unknown") for item in statuses)
    today_articles = [item for item in articles if item.get("publishedAt") == local_date]
    today_sources = Counter(_source_key(item) for item in today_articles)
    latest_published_at = max(
        (str(item.get("publishedAt") or "") for item in articles),
        default="",
    )

    payload["sourceStatus"] = statuses
    payload["refreshAudit"] = {
        "mode": "full",
        "pipelineCompleted": True,
        "completedAt": completed_at,
        "lastNewsCrawlAt": completed_at,
        "lastFullRefreshAt": completed_at,
        "localDate": local_date,
        "stages": PIPELINE_STAGES,
        "articleCount": len(articles),
        "previousArticleCount": previous_article_count,
        "newArticleCount": new_article_count,
        "latestPublishedAt": latest_published_at,
        "todayArticleCount": len(today_articles),
        "todaySourceCount": len(today_sources),
        "todaySources": dict(sorted(today_sources.items())),
        "sourceStatusCount": len(statuses),
        "sourceStatusCounts": dict(sorted(status_counts.items())),
        "healthySourceCount": sum(
            item.get("status") in {"ok", "partial"}
            and int(item.get("accepted", 0) or 0) > 0
            for item in statuses
        ),
        "failedSourceCount": status_counts.get("error", 0),
        "retainedPreviousSourceCount": sum(
            bool(item.get("retainedPrevious")) for item in statuses
        ),
    }

    ARTICLES_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["refreshAudit"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
