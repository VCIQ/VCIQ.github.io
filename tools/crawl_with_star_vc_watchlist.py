#!/usr/bin/env python3
"""Run the standard intelligence crawler with verified STAR VC watchlist shards.

The STAR Market investor pipeline publishes a small derived watchlist from
manifest-verified prospectus shareholder relationships. This adapter adds those
institution-name shards as independent public discovery sources without writing
them into browser-managed ``config/user_tracking.json``.

Google News RSS is used for discovery because the repository's existing Bing RSS
sources currently complete successfully but return zero scanned items on hosted
runners. Each logical watchlist shard therefore gets a Chinese and an English
Google News source while retaining the same verified institution membership.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:  # Imported by tests as tools.crawl_with_star_vc_watchlist.
    from . import crawl_with_wechat_registry as base
    from . import tracking_taxonomy as taxonomy
except ImportError:  # Executed directly with python tools/...
    import crawl_with_wechat_registry as base
    import tracking_taxonomy as taxonomy

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
        common = {
            "adapter": "rss",
            "platform": "Google News",
            "sourceLevel": "待交叉验证",
            "sourceCategory": "company",
            "sector": "风险投资",
            "maxItems": 8,
            "keywords": names,
            "strictTitleKeywords": False,
            "enabled": True,
        }
        sources.extend(
            [
                {
                    **common,
                    "id": f"{SOURCE_PREFIX}{shard_id}-google-cn",
                    "name": f"科创板投资机构 · 风险投资 · {index} · Google News 中文",
                    "url": taxonomy._google_news_url(query, chinese=True),
                    "region": "中国",
                },
                {
                    **common,
                    "id": f"{SOURCE_PREFIX}{shard_id}-google-us",
                    "name": f"科创板投资机构 · 风险投资 · {index} · Google News 英文",
                    "url": taxonomy._google_news_url(query, chinese=False),
                    "region": "美国",
                },
            ]
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
