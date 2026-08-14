#!/usr/bin/env python3
"""Publish an audit marker after a successful lightweight intelligence refresh."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
BASELINE_PATH = Path(os.environ.get("RUNNER_TEMP", str(ROOT))) / "vciq-frequent-refresh-baseline.json"
TAIPEI = ZoneInfo("Asia/Taipei")


def article_identity(article: dict) -> str:
    article_id = str(article.get("id") or "").strip()
    if article_id:
        return article_id
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return str(source.get("url") or "").strip()


def source_key(article: dict) -> str:
    source_id = str(article.get("sourceId") or "").strip()
    if source_id:
        return source_id
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return str(source.get("name") or "unknown").strip() or "unknown"


def load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        return {}
    try:
        value = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}
    finally:
        BASELINE_PATH.unlink(missing_ok=True)


def previous_full_refresh_at(payload: dict) -> str:
    audit = payload.get("refreshAudit")
    if not isinstance(audit, dict):
        return ""
    explicit = str(audit.get("lastFullRefreshAt") or "").strip()
    if explicit:
        return explicit
    if audit.get("pipelineCompleted") is True and str(audit.get("mode") or "") == "full":
        return str(audit.get("completedAt") or "").strip()
    return ""


def main() -> int:
    payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("article snapshot must be a JSON object")

    completed_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    local_date = datetime.now(TAIPEI).date().isoformat()
    articles = [item for item in payload.get("articles", []) if isinstance(item, dict)]
    last_full_refresh_at = previous_full_refresh_at(payload)
    baseline = load_baseline()
    baseline_ids = {
        str(value).strip()
        for value in baseline.get("articleIds", [])
        if str(value).strip()
    }
    previous_count = int(baseline.get("articleCount", len(baseline_ids)) or 0)
    new_count = sum(
        bool(identity) and identity not in baseline_ids
        for identity in (article_identity(article) for article in articles)
    )
    today_articles = [item for item in articles if item.get("publishedAt") == local_date]
    today_sources = Counter(source_key(item) for item in today_articles)
    latest_published_at = max(
        (str(item.get("publishedAt") or "") for item in articles),
        default="",
    )

    audit = {
        "mode": "frequent",
        "pipelineCompleted": True,
        "completedAt": completed_at,
        "lastNewsCrawlAt": completed_at,
        "localDate": local_date,
        "stages": ["core-and-tracking-sources"],
        "articleCount": len(articles),
        "previousArticleCount": previous_count,
        "newArticleCount": new_count,
        "latestPublishedAt": latest_published_at,
        "todayArticleCount": len(today_articles),
        "todaySourceCount": len(today_sources),
        "todaySources": dict(sorted(today_sources.items())),
    }
    if last_full_refresh_at:
        audit["lastFullRefreshAt"] = last_full_refresh_at
    payload["refreshAudit"] = audit
    ARTICLES_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["refreshAudit"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
