#!/usr/bin/env python3
"""Read-only live-feed audit for the two pre-listing tracking tracks.

This runs only the eight generated discovery routes for PR #692. It reuses the
production crawler adapters, writes a temporary candidate snapshot in the
GitHub Actions workspace for the existing coverage validator, and emits a
separate JSON audit artifact. It never commits or publishes the fetched data.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import crawl_with_source_categories as base  # noqa: E402
from tools import crawl_with_wechat_registry as registry  # noqa: E402

TARGET_TRACKS = {
    "track-jq5v2n": {"name": "拟上市重点企业", "expected_companies": 20},
    "track-6l9y0y": {"name": "拟上市观察企业", "expected_companies": 22},
}
ROUTE_SUFFIXES = ("bing", "google-cn", "google-us", "toutiao")


def normalize(value: Any) -> str:
    import re
    import unicodedata

    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\s._:：\-—–/／|｜,，;；、&＆+＋()（）\[\]【】]+", "", text)


def article_text(article: dict[str, Any]) -> str:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    values = [
        article.get("title"),
        article.get("summary"),
        article.get("company"),
        article.get("sector"),
        source.get("name"),
    ]
    return " ".join(str(value or "") for value in values)


def install_production_adapters() -> None:
    """Mirror the production crawler entrypoint's adapter installation order."""
    crawler = base.tracking.crawler

    registry.core_official_adapters.install(crawler)
    registry.http_policy_bridge.install(crawler)
    registry.search_index_feed_redirects.install(crawler)
    registry.wechat_fetch_compat.install(registry.wechat_public_sources)
    registry.wechat_registry_bridge.install(registry.wechat_public_sources)
    registry.wechat_original_redirect_bridge.install(
        registry.wechat_public_sources,
        registry.wechat_registry_bridge,
    )
    registry.wechat_index_context_guard.install(registry.wechat_registry_bridge)
    registry.wechat_index_record_fallback.install(
        registry.wechat_public_sources,
        registry.wechat_registry_bridge,
    )
    registry.wechat_sogou_redirect_compat.install(registry.wechat_sogou_index)
    registry.wechat_sogou_link_compat.install(registry.wechat_sogou_index)
    registry.wechat_public_index_title_fallback.install(
        registry.wechat_registry_bridge,
        registry.wechat_sogou_index,
    )
    registry.wechat_public_aggregator.install(registry.wechat_sogou_index)
    registry.wechat_sogou_bridge.install(registry.wechat_public_sources)
    registry.toutiao_public_feed.install(base.tracking)
    registry._install_professional_media()
    registry._install_source_governance()
    registry._install_snapshot_quality()

    base._install_strict_tracking_validation()
    base.tracking_taxonomy.install(base.tracking)
    base.x_rate_limit.install(crawler)
    base.wechat_public_sources.install(base.tracking)
    base.tracking._custom_sources = base._custom_sources
    base._install_generic_adapter()
    base.configure_crawler()
    base._install_empty_sec_guard()


def merge_snapshot(
    snapshot_path: Path,
    incoming: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
) -> None:
    payload: dict[str, Any] = {}
    if snapshot_path.exists():
        try:
            loaded = json.loads(snapshot_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except (OSError, json.JSONDecodeError):
            payload = {}

    articles = [
        row for row in payload.get("articles", [])
        if isinstance(row, dict)
    ]
    seen = set()
    for row in articles:
        source = row.get("source") if isinstance(row.get("source"), dict) else {}
        identity = str(row.get("id") or source.get("url") or "").strip()
        if identity:
            seen.add(identity)

    added = 0
    for row in incoming:
        source = row.get("source") if isinstance(row.get("source"), dict) else {}
        identity = str(row.get("id") or source.get("url") or "").strip()
        if identity and identity in seen:
            continue
        articles.append(row)
        if identity:
            seen.add(identity)
        added += 1

    target_ids = {str(row.get("id") or "") for row in statuses}
    old_statuses = [
        row for row in payload.get("sourceStatus", [])
        if isinstance(row, dict) and str(row.get("id") or "") not in target_ids
    ]
    payload["articles"] = articles
    payload["articleCount"] = len(articles)
    payload["sourceStatus"] = sorted(
        [*old_statuses, *statuses],
        key=lambda row: str(row.get("id") or ""),
    )
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "snapshot": str(snapshot_path.relative_to(ROOT)),
        "addedArticles": added,
        "totalArticles": len(articles),
        "freshRouteStatuses": len(statuses),
    }, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="/tmp/prelisting-discovery-audit.json",
        help="Path for the read-only audit report artifact.",
    )
    args = parser.parse_args()

    config = base.tracking.load_tracking()
    tracks = {
        str(row.get("slug")): row
        for row in config.get("tracks", [])
        if isinstance(row, dict) and row.get("enabled", True) is not False
    }
    for slug, contract in TARGET_TRACKS.items():
        row = tracks.get(slug)
        if not row:
            raise SystemExit(f"missing enabled target track: {slug}")
        companies = row.get("sampleCompanies", [])
        if len(companies) != contract["expected_companies"]:
            raise SystemExit(
                f"{contract['name']}: expected {contract['expected_companies']} "
                f"companies, found {len(companies)}"
            )
        if len({normalize(name) for name in companies}) != len(companies):
            raise SystemExit(f"{contract['name']}: duplicate company names")

    install_production_adapters()
    crawler = base.tracking.crawler
    base_config = crawler.load_config()
    merged, sec_specs, active_ids = base.tracking.build_merged_config(
        base_config, config
    )
    base.tracking._install_runtime_overrides(merged, sec_specs, active_ids)

    expected_ids = {
        f"user-track-{slug}-{suffix}"
        for slug in TARGET_TRACKS
        for suffix in ROUTE_SUFFIXES
    }
    specs = [
        spec
        for spec in merged.get("publicDiscovery", [])
        if isinstance(spec, dict) and spec.get("id") in expected_ids
        and spec.get("enabled", True) is not False
    ]
    specs_by_id = {str(spec.get("id")): spec for spec in specs}
    missing = sorted(expected_ids - set(specs_by_id))
    if missing:
        raise SystemExit("missing generated discovery routes: " + ", ".join(missing))
    if len(specs) != 8:
        raise SystemExit(f"expected exactly 8 route specs, found {len(specs)}")

    user_agent = os.environ.get("SEC_USER_AGENT", "").strip() or crawler.DEFAULT_USER_AGENT
    incoming, statuses, errors = crawler._crawl_config_group(specs, user_agent)
    status_by_id = {str(row.get("id")): row for row in statuses}

    track_reports = []
    all_company_matches = []
    for slug, contract in TARGET_TRACKS.items():
        track = tracks[slug]
        route_rows = []
        for suffix in ROUTE_SUFFIXES:
            source_id = f"user-track-{slug}-{suffix}"
            status = status_by_id.get(source_id, {})
            route_rows.append({
                "id": source_id,
                "platform": status.get("platform") or specs_by_id[source_id].get("platform"),
                "status": status.get("status", "missing"),
                "scanned": int(status.get("scanned", 0) or 0),
                "accepted": int(status.get("accepted", 0) or 0),
                "failed": int(status.get("failed", 0) or 0),
                "error": status.get("error"),
            })

        companies = []
        for company in track.get("sampleCompanies", []):
            key = normalize(company)
            matches = [
                row for row in incoming
                if key and key in normalize(article_text(row))
            ]
            match_rows = []
            for article in matches[:10]:
                source = article.get("source") if isinstance(article.get("source"), dict) else {}
                match_rows.append({
                    "title": article.get("title"),
                    "publishedAt": article.get("publishedAt"),
                    "url": source.get("url"),
                    "platform": source.get("platform"),
                    "sourceLevel": source.get("sourceLevel"),
                })
            company_row = {
                "name": company,
                "candidateCount": len(matches),
                "candidates": match_rows,
            }
            companies.append(company_row)
            all_company_matches.append({
                "track": contract["name"],
                **company_row,
            })

        track_reports.append({
            "slug": slug,
            "name": contract["name"],
            "companyCount": len(companies),
            "completedRoutes": sum(
                row["status"] in {"ok", "partial", "empty"}
                for row in route_rows
            ),
            "expectedRoutes": len(ROUTE_SUFFIXES),
            "failedRoutes": sum(row["status"] == "error" for row in route_rows),
            "acceptedArticles": sum(row["accepted"] for row in route_rows),
            "routes": route_rows,
            "companies": companies,
        })

    report = {
        "schemaVersion": 1,
        "mode": "read-only-live-discovery-audit",
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "gitSha": os.environ.get("GITHUB_SHA", ""),
        "pullRequestHead": os.environ.get("GITHUB_HEAD_REF", ""),
        "discoveryOnly": True,
        "officialDisclosureClaimed": False,
        "tracks": track_reports,
        "companyCount": sum(row["companyCount"] for row in track_reports),
        "uniqueCompanyCount": len({
            normalize(row["name"]) for row in all_company_matches
        }),
        "matchedCompanyCount": sum(
            row["candidateCount"] > 0 for row in all_company_matches
        ),
        "unmatchedCompanies": [
            row["name"] for row in all_company_matches
            if row["candidateCount"] == 0
        ],
        "sourceErrors": errors,
        "articleCount": len(incoming),
        "routeStatusCount": len(statuses),
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    snapshot_path = ROOT / "public" / "data" / "articles.json"
    merge_snapshot(snapshot_path, incoming, statuses)
    print(json.dumps({
        "report": str(output),
        "companyCount": report["companyCount"],
        "matchedCompanyCount": report["matchedCompanyCount"],
        "routeStatusCount": report["routeStatusCount"],
        "routeErrors": len(errors),
        "articleCount": len(incoming),
    }, ensure_ascii=False))

    return 1 if errors or len(statuses) != 8 else 0


if __name__ == "__main__":
    raise SystemExit(main())
