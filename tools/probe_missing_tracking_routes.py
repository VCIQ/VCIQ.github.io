#!/usr/bin/env python3
"""Attempt only tracking discovery routes missing from the candidate snapshot.

Pull requests that add a new enabled Track change the tracking configuration
before the scheduled production crawler has had a chance to create source-status
records for that Track. The normal candidate enrichment must not fabricate those
attempts, but the build gate also must not publish an untested Track.

This PR-only helper closes that gap generically:

* derive the exact generated discovery routes from the candidate tracking config;
* compare them with sourceStatus already present in the committed snapshot;
* actually call each missing adapter (Bing, Google News, Toutiao, etc.);
* keep transport/no-match failures as explicit error statuses rather than
  rewriting them to success; and
* write the attempted statuses and any real discovered articles only into the CI
  working copy. Nothing is committed by this script.

Existing Tracks whose source IDs are already represented incur no network calls.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

try:
    from . import crawl_articles as crawler
    from . import crawl_with_tracking as tracking
    from . import strict_tracking_config
    from . import toutiao_public_feed
    from . import tracking_taxonomy as taxonomy
except ImportError:
    import crawl_articles as crawler
    import crawl_with_tracking as tracking
    import strict_tracking_config
    import toutiao_public_feed
    import tracking_taxonomy as taxonomy

ROOT = Path(__file__).resolve().parents[1]
TRACKING_PATH = ROOT / "config" / "user_tracking.json"
SNAPSHOT_PATH = ROOT / "public" / "data" / "articles.json"


def load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return payload


def candidate_tracks(config: dict[str, Any]) -> list[dict[str, Any]]:
    sanitized = strict_tracking_config.sanitize_tracking_config(config)
    return tracking._enabled_tracks(sanitized)


def missing_source_specs(
    config: dict[str, Any], snapshot: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    tracks = candidate_tracks(config)
    specs = taxonomy.generated_track_sources(tracks, tracking)
    existing_status_ids = {
        str(item.get("id") or "").strip()
        for item in snapshot.get("sourceStatus", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    expected_ids = [
        source_id
        for track in tracks
        for source_id in taxonomy.expected_source_ids(str(track.get("slug") or "").strip())
    ]
    missing_ids = [source_id for source_id in expected_ids if source_id not in existing_status_ids]
    missing_set = set(missing_ids)
    selected = [spec for spec in specs if str(spec.get("id") or "") in missing_set]
    selected_ids = {str(spec.get("id") or "") for spec in selected}
    if selected_ids != missing_set:
        unresolved = sorted(missing_set - selected_ids)
        raise ValueError(f"missing tracking routes have no generated source spec: {unresolved}")
    return selected, missing_ids


def probe_spec(
    spec: dict[str, Any], user_agent: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if spec.get("adapter") == "toutiao_feed":
        return toutiao_public_feed.crawl_toutiao_source(spec, user_agent, crawler)
    return crawler._crawl_config_source(spec, user_agent)


def probe_specs(
    specs: list[dict[str, Any]], *, workers: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not specs:
        return [], []
    articles: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    user_agent = crawler.DEFAULT_USER_AGENT
    max_workers = max(1, min(6, workers, len(specs)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(probe_spec, spec, user_agent): spec for spec in specs}
        for future in as_completed(futures):
            spec = futures[future]
            try:
                incoming, status = future.result()
            except Exception as exc:
                incoming = []
                status = crawler._status(
                    str(spec.get("id") or ""),
                    str(spec.get("name") or spec.get("id") or ""),
                    "error",
                    0,
                    0,
                    failed=1,
                    platform=str(spec.get("platform") or spec.get("name") or ""),
                    error=f"{type(exc).__name__}: {exc}",
                )
            articles.extend(item for item in incoming if isinstance(item, dict))
            statuses.append(status)
    statuses.sort(key=lambda item: str(item.get("id") or ""))
    return articles, statuses


def article_key(article: dict[str, Any]) -> str:
    article_id = str(article.get("id") or "").strip()
    if article_id:
        return f"id:{article_id}"
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    url = str(source.get("url") or "").strip()
    return f"url:{crawler.normalize_url(url)}" if url else ""


def merge_probe_results(
    snapshot: dict[str, Any],
    incoming: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    expected_missing_ids: list[str],
) -> dict[str, Any]:
    expected = set(expected_missing_ids)
    actual = {str(item.get("id") or "") for item in statuses}
    if actual != expected:
        raise ValueError(
            f"probe status mismatch: expected={sorted(expected)} actual={sorted(actual)}"
        )

    articles = [item for item in snapshot.get("articles", []) if isinstance(item, dict)]
    seen = {article_key(item) for item in articles if article_key(item)}
    added = 0
    for article in incoming:
        key = article_key(article)
        if not key or key in seen:
            continue
        articles.append(article)
        seen.add(key)
        added += 1

    existing_statuses = [
        item
        for item in snapshot.get("sourceStatus", [])
        if isinstance(item, dict) and str(item.get("id") or "") not in expected
    ]
    snapshot["articles"] = articles
    snapshot["articleCount"] = len(articles)
    snapshot["sourceStatus"] = sorted(
        [*existing_statuses, *statuses], key=lambda item: str(item.get("id") or "")
    )
    snapshot["candidateTrackingRouteProbe"] = {
        "mode": "real-missing-route-attempt",
        "expectedRoutes": len(expected_missing_ids),
        "completedRoutes": len(statuses),
        "productiveRoutes": sum(int(item.get("accepted", 0) or 0) > 0 for item in statuses),
        "failedRoutes": sum(item.get("status") == "error" for item in statuses),
        "addedArticles": added,
        "sourceIds": expected_missing_ids,
    }
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracking", type=Path, default=TRACKING_PATH)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-routes", type=int, default=16)
    args = parser.parse_args()

    config = load_object(args.tracking)
    snapshot = load_object(args.snapshot)
    specs, missing_ids = missing_source_specs(config, snapshot)
    if not missing_ids:
        print(json.dumps({"missingRoutes": 0, "action": "none"}, ensure_ascii=False))
        return 0
    if len(missing_ids) > max(1, args.max_routes):
        raise SystemExit(
            f"candidate snapshot is missing {len(missing_ids)} tracking routes; "
            f"limit={args.max_routes}. Refresh/rebase the candidate instead of probing a broadly stale snapshot."
        )

    incoming, statuses = probe_specs(specs, workers=args.workers)
    result = merge_probe_results(snapshot, incoming, statuses, missing_ids)
    args.snapshot.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = result["candidateTrackingRouteProbe"]
    report["statuses"] = [
        {
            "id": item.get("id"),
            "status": item.get("status"),
            "scanned": item.get("scanned", 0),
            "accepted": item.get("accepted", 0),
            "failed": item.get("failed", 0),
            "error": item.get("error", ""),
        }
        for item in statuses
    ]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
