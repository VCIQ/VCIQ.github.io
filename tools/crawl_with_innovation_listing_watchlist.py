#!/usr/bin/env python3
"""Add innovation-listing discovery sources to the standard intelligence crawler.

This adapter is deliberately discovery-only. It watches the five selected
broker names for new IPO-counselling announcements and watches the reviewed
company watchlist for listing-progress events. Results enter the ordinary
article/candidate pipeline as unverified discovery evidence; this module never
mutates the reviewed listing route or counselling status stored in
config/innovation_listing_watchlist.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from . import crawl_with_star_vc_watchlist as base
    from . import tracking_taxonomy as taxonomy
except ImportError:
    import crawl_with_star_vc_watchlist as base
    import tracking_taxonomy as taxonomy

tracking = base.tracking
WATCHLIST_PATH = tracking.crawler.ROOT / "config/innovation_listing_watchlist.json"
SOURCE_PREFIX = "innovation-listing-"
BROKER_EVENT_TERMS = (
    "辅导备案 OR 辅导进展 OR 辅导验收 OR 上市辅导 OR IPO辅导 OR "
    "科创板 OR 创业板 OR A股 OR A+H"
)
PROJECT_EVENT_TERMS = (
    "辅导 OR 验收 OR 受理 OR 问询 OR 上市委 OR 注册 OR 撤回 OR 终止 OR "
    "发行 OR 上市 OR 港交所 OR 聆讯 OR A+H"
)
PROJECT_SHARD_SIZE = 6


def load_watchlist(path: Path = WATCHLIST_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"brokers": [], "projects": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"brokers": [], "projects": []}
    if not isinstance(payload, dict):
        return {"brokers": [], "projects": []}
    return payload


def _source(source_id: str, name: str, query: str, keywords: list[str]) -> dict[str, Any]:
    return {
        "id": source_id,
        "name": name,
        "url": taxonomy._google_news_url(query, chinese=True),
        "adapter": "rss",
        "platform": "Google News",
        "sourceLevel": "待交叉验证",
        "sourceCategory": "company",
        # Keep the discovery evidence on the existing company/intelligence plane.
        # The dedicated /innovation-capital page is a derived research view, not
        # a fifth core research object.
        "sector": "风险投资",
        "region": "中国",
        "maxItems": 8,
        "keywords": keywords,
        "strictTitleKeywords": False,
        "enabled": True,
    }


def generated_innovation_sources(payload: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []

    brokers = tracking._unique(payload.get("brokers", []), 10)
    for index, broker in enumerate(brokers, start=1):
        query = f'("{broker}") ({BROKER_EVENT_TERMS})'
        sources.append(
            _source(
                f"{SOURCE_PREFIX}broker-{index:02d}",
                f"科创项目储备 · {broker} · 新辅导发现",
                query,
                [broker],
            )
        )

    company_names = tracking._unique(
        [
            str(project.get("company", "")).strip()
            for project in payload.get("projects", [])
            if isinstance(project, dict)
        ],
        120,
    )
    for offset in range(0, len(company_names), PROJECT_SHARD_SIZE):
        names = company_names[offset : offset + PROJECT_SHARD_SIZE]
        if not names:
            continue
        shard = offset // PROJECT_SHARD_SIZE + 1
        query = f"({tracking._quoted_or_query(names, PROJECT_SHARD_SIZE)}) ({PROJECT_EVENT_TERMS})"
        sources.append(
            _source(
                f"{SOURCE_PREFIX}projects-{shard:02d}",
                f"科创项目储备 · 已跟踪项目进展 · {shard}",
                query,
                names,
            )
        )

    return sources


def install() -> None:
    base.install()
    original_build = tracking.build_merged_config
    if getattr(original_build, "_innovation_listing_watchlist", False):
        return

    def build_merged_config(
        base_config: dict[str, Any], tracking_config: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, tuple[str, str, str, str]], set[str]]:
        config, sec_specs, active_ids = original_build(base_config, tracking_config)
        generated = generated_innovation_sources(load_watchlist())
        config.setdefault("publicDiscovery", []).extend(generated)
        active_ids.update(spec["id"] for spec in generated)
        return config, sec_specs, active_ids

    setattr(build_merged_config, "_innovation_listing_watchlist", True)
    tracking.build_merged_config = build_merged_config

    prefixes = tuple(tracking.USER_SOURCE_PREFIXES)
    if SOURCE_PREFIX not in prefixes:
        tracking.USER_SOURCE_PREFIXES = (*prefixes, SOURCE_PREFIX)


def main() -> int:
    install()
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
