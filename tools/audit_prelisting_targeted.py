#!/usr/bin/env python3
"""Second-pass per-company discovery for the PR #692 pre-listing universe.

Read-only: queries each company independently through the production RSS parser,
writes a JSON artifact, and does not commit or publish fetched articles.
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

TARGETS = ("track-jq5v2n", "track-6l9y0y")
EVENTS = (
    "融资 OR 投资 OR 战略合作 OR 产品发布 OR 量产 OR 商业化 OR "
    "订单 OR IPO OR 上市辅导 OR 招股 OR 研发进展"
)


def install_adapters() -> None:
    crawler = base.tracking.crawler
    registry.core_official_adapters.install(crawler)
    registry.http_policy_bridge.install(crawler)
    registry.search_index_feed_redirects.install(crawler)
    registry.wechat_fetch_compat.install(registry.wechat_public_sources)
    registry.wechat_registry_bridge.install(registry.wechat_public_sources)
    registry.wechat_original_redirect_bridge.install(
        registry.wechat_public_sources, registry.wechat_registry_bridge
    )
    registry.wechat_index_context_guard.install(registry.wechat_registry_bridge)
    registry.wechat_index_record_fallback.install(
        registry.wechat_public_sources, registry.wechat_registry_bridge
    )
    registry.wechat_sogou_redirect_compat.install(registry.wechat_sogou_index)
    registry.wechat_sogou_link_compat.install(registry.wechat_sogou_index)
    registry.wechat_public_index_title_fallback.install(
        registry.wechat_registry_bridge, registry.wechat_sogou_index
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


def normalize(value: Any) -> str:
    import re
    import unicodedata
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\s._:：\-—–/／|｜,，;；、&＆+＋()（）\[\]【】]+", "", text)


def article_text(row: dict[str, Any]) -> str:
    source = row.get("source") if isinstance(row.get("source"), dict) else {}
    return " ".join(str(x or "") for x in (
        row.get("title"), row.get("summary"), row.get("company"),
        row.get("sector"), source.get("name")
    ))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/tmp/prelisting-targeted-audit.json")
    args = parser.parse_args()

    tracking = base.tracking.load_tracking()
    tracks = {
        str(row.get("slug")): row for row in tracking.get("tracks", [])
        if isinstance(row, dict) and row.get("enabled", True) is not False
    }
    companies = []
    for slug in TARGETS:
        row = tracks.get(slug)
        if not row:
            raise SystemExit(f"missing target track {slug}")
        companies.extend((slug, row["name"], name) for name in row.get("sampleCompanies", []))
    if len(companies) != 42 or len({normalize(x[2]) for x in companies}) != 42:
        raise SystemExit("expected exactly 42 unique target companies")

    install_adapters()
    crawler = base.tracking.crawler
    base_config = crawler.load_config()
    merged, sec_specs, active_ids = base.tracking.build_merged_config(base_config, tracking)
    base.tracking._install_runtime_overrides(merged, sec_specs, active_ids)

    specs = []
    for slug, track_name, company in companies:
        query = f'("{company}") ({EVENTS})'
        specs.append({
            "id": f"prelisting-targeted-{slug}-{normalize(company)[:36]}",
            "name": f"{track_name} · {company} · 精准发现",
            "url": base.tracking_taxonomy._google_news_url(query, chinese=True),
            "adapter": "rss",
            "platform": "Google News 中文精准检索",
            "sourceLevel": "待交叉验证",
            "region": "中国",
            "sector": track_name,
            "company": company,
            "keywords": [company],
            "maxItems": 12,
            "strictTitleKeywords": False,
            "enabled": True,
        })

    user_agent = os.environ.get("SEC_USER_AGENT", "").strip() or crawler.DEFAULT_USER_AGENT
    articles, statuses, errors = crawler._crawl_config_group(specs, user_agent)
    status_map = {str(x.get("id")): x for x in statuses}

    results = []
    for slug, track_name, company in companies:
        source_id = f"prelisting-targeted-{slug}-{normalize(company)[:36]}"
        status = status_map.get(source_id, {})
        key = normalize(company)
        matches = []
        for row in articles:
            text = normalize(article_text(row))
            if not key or key not in text:
                continue
            source = row.get("source") if isinstance(row.get("source"), dict) else {}
            matches.append({
                "title": row.get("title"),
                "publishedAt": row.get("publishedAt"),
                "url": source.get("url"),
                "platform": source.get("platform"),
                "sourceLevel": source.get("sourceLevel"),
            })
        results.append({
            "track": track_name,
            "slug": slug,
            "company": company,
            "routeStatus": status.get("status", "missing"),
            "scanned": int(status.get("scanned", 0) or 0),
            "accepted": int(status.get("accepted", 0) or 0),
            "error": status.get("error"),
            "candidateCount": len(matches),
            "candidates": matches[:12],
        })

    report = {
        "schemaVersion": 1,
        "mode": "read-only-per-company-google-news-zh-discovery",
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "gitSha": os.environ.get("GITHUB_SHA", ""),
        "companyCount": len(results),
        "matchedCompanyCount": sum(x["candidateCount"] > 0 for x in results),
        "emptyCompanyCount": sum(x["candidateCount"] == 0 for x in results),
        "routeErrorCount": sum(x["routeStatus"] == "error" for x in results),
        "sourceErrors": errors,
        "companies": results,
        "discoveryOnly": True,
        "officialDisclosureClaimed": False,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "companyCount": report["companyCount"],
        "matchedCompanyCount": report["matchedCompanyCount"],
        "emptyCompanyCount": report["emptyCompanyCount"],
        "routeErrorCount": report["routeErrorCount"],
        "articleCount": len(articles),
        "report": str(out),
    }, ensure_ascii=False))
    return 1 if errors or len(statuses) != 42 else 0


if __name__ == "__main__":
    raise SystemExit(main())
