#!/usr/bin/env python3
"""Run the standard intelligence crawler with verified STAR VC watchlist shards.

The STAR Market investor pipeline publishes a small derived watchlist from
manifest-verified prospectus shareholder relationships. This adapter adds those
institution-name shards as independent public discovery sources without writing
them into browser-managed ``config/user_tracking.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:  # Imported by tests as tools.crawl_with_star_vc_watchlist.
    from . import crawl_with_wechat_registry as base
except ImportError:  # Executed directly with python tools/...
    import crawl_with_wechat_registry as base

tracking = base.base.tracking
WATCHLIST_PATH = tracking.crawler.ROOT / "config/star_vc_watchlist.json"
SOURCE_PREFIX = "star-vc-watchlist-"
EVENT_TERMS = (
    "投资 OR 融资 OR 募资 OR 新基金 OR 并购 OR IPO OR 退出 OR "
    "investment OR funding OR fund OR acquisition OR portfolio"
)


def load_watchlist(path: Path = WATCHLIST_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"schemaVersion": 1, "institutions": [], "queryShards": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schemaVersion": 1, "institutions": [], "queryShards": []}
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
        return {"schemaVersion": 1, "institutions": [], "queryShards": []}
    return payload


def generated_star_vc_sources(payload: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for index, raw in enumerate(payload.get("queryShards", []), start=1):
        if not isinstance(raw, dict):
            continue
        names = tracking._unique(raw.get("institutionNames", []), 8)
        if not names:
            continue
        shard_id = tracking._slug(raw.get("id") or f"{index:03d}")
        query = f"({tracking._quoted_or_query(names, 8)}) ({EVENT_TERMS})"
        sources.append(
            {
                "id": f"{SOURCE_PREFIX}{shard_id}",
                "name": f"科创板投资机构 · 风险投资 · {index}",
                "url": tracking._bing_rss(query),
                "adapter": "rss",
                "platform": "科创板投资机构追踪",
                "sourceLevel": "待交叉验证",
                "sourceCategory": "company",
                "region": "全球",
                "sector": "风险投资",
                "maxItems": 8,
                "keywords": names,
                "strictTitleKeywords": False,
                "enabled": True,
            }
        )
    return sources


def install() -> None:
    original_build = tracking.build_merged_config
    if getattr(original_build, "_star_vc_watchlist", False):
        return

    def build_merged_config(
        base_config: dict[str, Any], tracking_config: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, tuple[str, str, str, str]], set[str]]:
        config, sec_specs, active_ids = original_build(base_config, tracking_config)
        generated = generated_star_vc_sources(load_watchlist())
        config.setdefault("publicDiscovery", []).extend(generated)
        active_ids.update(spec["id"] for spec in generated)
        return config, sec_specs, active_ids

    setattr(build_merged_config, "_star_vc_watchlist", True)
    tracking.build_merged_config = build_merged_config

    prefixes = tuple(tracking.USER_SOURCE_PREFIXES)
    if SOURCE_PREFIX not in prefixes:
        tracking.USER_SOURCE_PREFIXES = (*prefixes, SOURCE_PREFIX)


def main() -> int:
    install()
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
