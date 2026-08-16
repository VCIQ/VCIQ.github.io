#!/usr/bin/env python3
"""Actually attempt the generated discovery routes for staged new tracks.

This is a PR-validation utility, not a production shortcut. After the Batch 2
activation simulator has added the proposed tracks to the CI working copy of
``config/user_tracking.json``, this command:

1. regenerates the exact per-track discovery specs used by production;
2. performs a real network attempt for every expected route;
3. records the returned source status in the CI working copy of the article
   snapshot; and
4. merges any newly discovered articles without fabricating successful status.

The subsequent production snapshot validator therefore sees a route as
"completed" only after this command has actually called its adapter. Network
errors remain explicit ``error`` statuses; they are never rewritten to ``ok``.
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
PROPOSAL_PATH = ROOT / "config" / "user_tracking.new_tracks.batch2.json"
SNAPSHOT_PATH = ROOT / "public" / "data" / "articles.json"


def load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return payload


def target_slugs(proposal: dict[str, Any]) -> list[str]:
    rows = proposal.get("proposedTracks")
    if not isinstance(rows, list):
        raise ValueError("proposal requires proposedTracks")
    slugs: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        slug = str(row.get("slug") or "").strip()
        if slug and slug not in slugs:
            slugs.append(slug)
    if not slugs:
        raise ValueError("proposal contains no track slugs")
    return slugs


def generated_specs(
    config: dict[str, Any], proposal: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    sanitized = strict_tracking_config.sanitize_tracking_config(config)
    tracks = tracking._enabled_tracks(sanitized)
    requested = target_slugs(proposal)
    enabled = {str(track.get("slug") or "") for track in tracks}
    missing = sorted(set(requested) - enabled)
    if missing:
        raise ValueError(
            "proposed tracks are not active in candidate config: " + ", ".join(missing)
        )

    all_specs = taxonomy.generated_track_sources(tracks, tracking)
    expected_ids = [
        source_id
        for slug in requested
        for source_id in taxonomy.expected_source_ids(slug)
    ]
    expected_set = set(expected_ids)
    specs = [spec for spec in all_specs if str(spec.get("id") or "") in expected_set]
    actual_ids = {str(spec.get("id") or "") for spec in specs}
    if actual_ids != expected_set:
        missing_ids = sorted(expected_set - actual_ids)
        extra_ids = sorted(actual_ids - expected_set)
        raise ValueError(
            f"generated discovery mismatch: missing={missing_ids} extra={extra_ids}"
        )
    return specs, expected_ids


def probe_spec(
    spec: dict[str, Any], user_agent: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if spec.get("adapter") == "toutiao_feed":
        return toutiao_public_feed.crawl_toutiao_source(spec, user_agent, crawler)
    return crawler._crawl_config_source(spec, user_agent)


def probe_specs(
    specs: list[dict[str, Any]], *, workers: int = 4
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    articles: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    user_agent = crawler.DEFAULT_USER_AGENT

    with ThreadPoolExecutor(max_workers=max(1, min(6, workers, len(specs)))) as executor:
        future_map = {
            executor.submit(probe_spec, spec, user_agent): spec for spec in specs
        }
        for future in as_completed(future_map):
            spec = future_map[future]
            try:
                incoming, status = future.result()
            except Exception as exc:  # A real failed attempt remains an error status.
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


def _article_key(article: dict[str, Any]) -> str:
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
    expected_ids: list[str],
) -> dict[str, Any]:
    expected = set(expected_ids)
    status_ids = {str(item.get("id") or "") for item in statuses}
    if status_ids != expected:
        raise ValueError(
            f"probe status mismatch: expected={sorted(expected)} actual={sorted(status_ids)}"
        )

    existing_articles = [
        item for item in snapshot.get("articles", []) if isinstance(item, dict)
    ]
    seen = {_article_key(item) for item in existing_articles if _article_key(item)}
    added = 0
    for article in incoming:
        key = _article_key(article)
        if not key or key in seen:
            continue
        existing_articles.append(article)
        seen.add(key)
        added += 1

    existing_statuses = [
        item
        for item in snapshot.get("sourceStatus", [])
        if isinstance(item, dict) and str(item.get("id") or "") not in expected
    ]
    snapshot["articles"] = existing_articles
    snapshot["articleCount"] = len(existing_articles)
    snapshot["sourceStatus"] = sorted(
        [*existing_statuses, *statuses], key=lambda item: str(item.get("id") or "")
    )
    snapshot["batch2DiscoveryProbe"] = {
        "mode": "real-route-attempt",
        "expectedRoutes": len(expected_ids),
        "completedRoutes": len(statuses),
        "productiveRoutes": sum(int(item.get("accepted", 0) or 0) > 0 for item in statuses),
        "failedRoutes": sum(item.get("status") == "error" for item in statuses),
        "addedArticles": added,
        "sourceIds": expected_ids,
    }
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracking", type=Path, default=TRACKING_PATH)
    parser.add_argument("--proposal", type=Path, default=PROPOSAL_PATH)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    config = load_object(args.tracking)
    proposal = load_object(args.proposal)
    snapshot = load_object(args.snapshot)
    specs, expected_ids = generated_specs(config, proposal)
    incoming, statuses = probe_specs(specs, workers=args.workers)
    result = merge_probe_results(snapshot, incoming, statuses, expected_ids)
    args.snapshot.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = result["batch2DiscoveryProbe"]
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
