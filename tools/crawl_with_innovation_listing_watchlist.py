#!/usr/bin/env python3
"""Add innovation-listing discovery sources to the standard intelligence crawler.

This adapter is deliberately discovery-only. It watches the five selected
broker names for new IPO-counselling announcements, watches the reviewed company
watchlist for listing-progress events, and adds focused discovery shards for
"十五五" hard-tech and A+H/H-share paths.

Results enter the ordinary article/candidate pipeline as unverified discovery
evidence. This module never mutates the reviewed listing route, counselling
status, or formal project pool stored in config/innovation_listing_watchlist.json.
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
A_PLUS_H_TERMS = (
    '"A+H" OR "H股" OR "港股" OR "港交所" OR "18C" OR "特专科技"'
)
PROJECT_SHARD_SIZE = 6
POLICY_THEME_SHARD_SIZE = 4

# Primary-source discovery is intentionally bounded to official domains. Search
# indexes are used only as an index; allowedHosts keeps accepted result URLs on
# the regulator / broker domain itself.
PRIMARY_BROKER_HOSTS: dict[str, tuple[str, ...]] = {
    "中信证券": ("citics.com", "ecitic.com"),
    "中信建投": ("csc108.com",),
    "中金公司": ("cicc.com",),
    "国泰海通": ("gtja.com", "haitong.com"),
    "华泰联合": ("htsc.com", "htsc.com.cn"),
}
PRIMARY_REGULATORY_HOSTS = ("eid.csrc.gov.cn",)
REGULATORY_EVENT_TERMS = (
    "辅导备案 OR 辅导进展 OR 辅导验收 OR 上市辅导 OR 辅导机构 OR IPO"
)


def load_watchlist(path: Path = WATCHLIST_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"brokers": [], "projects": [], "policyThemes": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"brokers": [], "projects": [], "policyThemes": []}
    if not isinstance(payload, dict):
        return {"brokers": [], "projects": [], "policyThemes": []}
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
        # Keep discovery evidence on the existing company/intelligence plane.
        # /innovation-capital is a derived research view, not a fifth core object.
        "sector": "风险投资",
        "region": "中国",
        "maxItems": 8,
        "keywords": keywords,
        "strictTitleKeywords": False,
        "enabled": True,
    }


def _bounded_primary_source(
    source_id: str,
    name: str,
    query: str,
    keywords: list[str],
    *,
    host: str,
    source_level: str,
    platform: str,
) -> dict[str, Any]:
    return {
        "id": source_id,
        "name": name,
        "url": tracking._bing_rss(query),
        "sourceUrl": f"https://{host}/",
        "adapter": "rss",
        "platform": platform,
        "sourceLevel": source_level,
        "sourceCategory": "company",
        "sector": "风险投资",
        "region": "中国",
        "maxItems": 10,
        "keywords": keywords,
        "strictTitleKeywords": False,
        "allowedHosts": [host],
        "enabled": True,
    }


def generated_innovation_sources(payload: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []

    brokers = tracking._unique(payload.get("brokers", []), 10)
    broker_query = tracking._quoted_or_query(brokers, 10) if brokers else ""

    # 1) Broker-centric discovery: new counselling / IPO events for the five
    # selected brokers.
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

    # 1b) Regulatory / broker official discovery. These sources are accepted
    # only when the result URL remains on the configured official domain.
    for index, broker in enumerate(brokers, start=1):
        for host_index, host in enumerate(PRIMARY_BROKER_HOSTS.get(broker, ()), start=1):
            query = f'site:{host} ("{broker}") ({BROKER_EVENT_TERMS})'
            sources.append(
                _bounded_primary_source(
                    f"{SOURCE_PREFIX}primary-broker-{index:02d}-{host_index:02d}",
                    f"科创项目储备 · {broker} · 券商官方",
                    query,
                    [broker],
                    host=host,
                    source_level="官方披露",
                    platform="券商官方网站",
                )
            )
        for host_index, host in enumerate(PRIMARY_REGULATORY_HOSTS, start=1):
            query = f'site:{host} ("{broker}") ({REGULATORY_EVENT_TERMS})'
            sources.append(
                _bounded_primary_source(
                    f"{SOURCE_PREFIX}primary-regulatory-{index:02d}-{host_index:02d}",
                    f"科创项目储备 · {broker} · 监管辅导公示",
                    query,
                    [broker],
                    host=host,
                    source_level="监管文件",
                    platform="证监会辅导公示",
                )
            )

    # 2) A+H/H-share discovery: keep the broker identity explicit so a later
    # deterministic candidate builder can preserve the broker relationship.
    for index, broker in enumerate(brokers, start=1):
        query = f'("{broker}") ({A_PLUS_H_TERMS}) (A股 OR 辅导 OR IPO OR 上市)'
        sources.append(
            _source(
                f"{SOURCE_PREFIX}a-plus-h-{index:02d}",
                f"科创项目储备 · {broker} · A+H/H股发现",
                query,
                [broker, "A+H", "H股", "港股", "港交所"],
            )
        )

    # 3) "十五五" hard-tech discovery: query the existing policy theme taxonomy
    # together with the five-broker set. These are discovery candidates only;
    # theme fit never implies an IPO route or formal pool membership.
    policy_themes = tracking._unique(payload.get("policyThemes", []), 80)
    for offset in range(0, len(policy_themes), POLICY_THEME_SHARD_SIZE):
        themes = policy_themes[offset : offset + POLICY_THEME_SHARD_SIZE]
        if not themes or not broker_query:
            continue
        shard = offset // POLICY_THEME_SHARD_SIZE + 1
        theme_query = tracking._quoted_or_query(themes, POLICY_THEME_SHARD_SIZE)
        query = (
            f"({broker_query}) ({theme_query}) "
            f"(辅导 OR IPO OR 上市 OR 科创板 OR 创业板 OR A股 OR A+H)"
        )
        sources.append(
            _source(
                f"{SOURCE_PREFIX}policy-{shard:02d}",
                f"科创项目储备 · 十五五硬科技发现 · {shard}",
                query,
                [*brokers, *themes],
            )
        )

    # 4) Progress monitoring for the reviewed seed pool.
    company_names = tracking._unique(
        [
            str(project.get("company", "")).strip()
            for project in payload.get("projects", [])
            if isinstance(project, dict)
        ],
        160,
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
