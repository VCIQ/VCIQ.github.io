#!/usr/bin/env python3
"""Run the public crawler with category-aware, language-aware source routing.

This module wraps ``crawl_with_tracking`` and replaces only the browser-managed
source conversion and runtime adapter dispatch. RSS and SEC retain their native
adapters; arbitrary public websites use one adaptive multi-stage crawler with
bounded fallbacks and small domain profiles.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:  # Imported by tests as tools.crawl_with_source_categories.
    from . import adaptive_public_sources
    from . import crawl_with_tracking as tracking
    from . import generic_web_sources
    from . import robust_web_fallback
    from . import strict_tracking_config
    from . import tracking_taxonomy
    from . import wechat_public_sources
    from . import x_rate_limit
    from .crawl_tracked_articles import configure_crawler, _install_empty_sec_guard
except ImportError:  # Executed directly with ``python tools/...``.
    import adaptive_public_sources
    import crawl_with_tracking as tracking
    import generic_web_sources
    import robust_web_fallback
    import strict_tracking_config
    import tracking_taxonomy
    import wechat_public_sources
    import x_rate_limit
    from crawl_tracked_articles import configure_crawler, _install_empty_sec_guard


VALID_SOURCE_CATEGORIES = {"company", "media", "person"}
OFFICIAL_REGISTRY_ONLY_SOURCE_IDS = frozenset({"source-auto-shopify"})
OFFICIAL_REGISTRY_ONLY_COMPANIES = frozenset({"shopify"})
OFFICIAL_REGISTRY_ONLY_HOSTS = frozenset({"shopify.com"})


def source_category(raw: dict[str, Any], source_type: str | None = None) -> str:
    """Return an explicit category or safely migrate a legacy source row."""

    explicit = tracking._clean(raw.get("sourceCategory"), 20)
    if explicit in VALID_SOURCE_CATEGORIES:
        return explicit
    normalized_type = source_type or tracking._clean(raw.get("sourceType"), 30)
    if (
        normalized_type == "sec"
        or tracking._clean(raw.get("ticker"), 30)
        or tracking._clean(raw.get("listedCompanyId"), 100)
    ):
        return "company"
    return "media"


def is_official_registry_only_source(raw: dict[str, Any]) -> bool:
    """Return whether a browser-managed source is intentionally handled elsewhere.

    Shopify remains a tracked company, but its broad homepage source is not
    suitable for the lightweight or generic website crawler. The scoped
    official-company adapter handles only Shopify Editions, product news and
    investor-relations pages during the full refresh.
    """

    source_id = tracking._clean(raw.get("id"), 100).casefold()
    if source_id in OFFICIAL_REGISTRY_ONLY_SOURCE_IDS:
        return True
    if source_category(raw) != "company":
        return False
    company = tracking._clean(raw.get("company"), 80).casefold()
    url = tracking._clean(raw.get("url"), 500)
    host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
    return (
        company in OFFICIAL_REGISTRY_ONLY_COMPANIES
        and any(
            host == allowed or host.endswith(f".{allowed}")
            for allowed in OFFICIAL_REGISTRY_ONLY_HOSTS
        )
    )


def _listed_company_index(
    tracking_config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in tracking_config.get("listedCompanies", []):
        if not isinstance(raw, dict):
            continue
        company_id = tracking._clean(raw.get("id"), 100)
        if company_id:
            result[company_id] = raw
    return result


def _category_keywords(
    raw: dict[str, Any],
    category: str,
    track_by_name: dict[str, dict[str, Any]],
) -> list[str]:
    sanitized = dict(raw)
    if category != "company":
        sanitized["company"] = ""
        sanitized["ticker"] = ""
    return tracking._source_keywords(sanitized, track_by_name)


def _source_level(category: str, source_type: str) -> str:
    if source_type == "rss" and category == "person":
        return "原始材料"
    return {
        "company": "官方披露",
        "media": "媒体报道",
        "person": "原始材料",
    }.get(category, "待交叉验证")


def _display_name(raw_name: str, url: str, index: int) -> str:
    if raw_name and not re.match(r"^https?://", raw_name, flags=re.IGNORECASE):
        return raw_name
    host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
    return host or f"用户来源 {index + 1}"


def _custom_sources(
    tracking_config: dict[str, Any], tracks: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str, str, str]]]:
    """Route every enabled user source to RSS, SEC, or adaptive website crawling."""

    runtime_specs: list[dict[str, Any]] = []
    sec_specs: dict[str, tuple[str, str, str, str]] = {}
    track_by_name = {track["name"].casefold(): track for track in tracks}
    listed_by_id = _listed_company_index(tracking_config)

    for index, raw in enumerate(tracking_config.get("sources", [])):
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue
        if is_official_registry_only_source(raw):
            continue

        raw_name = tracking._clean(raw.get("name"), 80)
        source_type = (
            tracking._clean(raw.get("sourceType"), 30) or "listing-search"
        )
        category = source_category(raw, source_type)
        company = tracking._clean(raw.get("company"), 80)
        ticker = tracking._clean(raw.get("ticker"), 30).upper()
        region = tracking._clean(raw.get("region"), 20)
        if region not in {"中国", "美国", "全球"}:
            region = "全球"
        sector = tracking._clean(raw.get("sector"), 60) or "AI / AGI"
        url = adaptive_public_sources.canonical_source_url(
            tracking._clean(raw.get("url"), 500)
        )
        name = _display_name(raw_name, url, index)
        source_id = f"user-source-{tracking._slug(raw.get('id') or name or index)}"

        linked_company = listed_by_id.get(
            tracking._clean(raw.get("listedCompanyId"), 100), {}
        )
        if category == "company":
            company = (
                company
                or tracking._clean(linked_company.get("name"), 80)
                or name
            )
            ticker = (
                ticker
                or tracking._clean(linked_company.get("ticker"), 30).upper()
            )

        if source_type == "sec":
            if category == "company" and ticker:
                company_slug = (
                    tracking._clean(linked_company.get("catalogSlug"), 80)
                    or tracking._slug(company)
                )
                sec_specs[ticker] = (company, company_slug, sector, region)
            continue

        if not re.match(r"^https?://", url, flags=re.IGNORECASE):
            continue

        keywords = _category_keywords(raw, category, track_by_name)
        adapter = "rss" if source_type == "rss" else "generic_web"
        spec: dict[str, Any] = {
            "id": source_id,
            "name": name,
            "url": url,
            "sourceUrl": url,
            "adapter": adapter,
            "platform": (
                {
                    "company": "用户公司 RSS",
                    "media": "用户媒体 RSS",
                    "person": "用户人物 RSS",
                }[category]
                if source_type == "rss"
                else name
            ),
            "sourceCategory": category,
            "sourceLevel": _source_level(category, source_type),
            "region": region,
            "sector": sector,
            "maxItems": 10,
            "keywords": keywords,
            "strictTitleKeywords": False,
            "enabled": True,
        }
        source_language = tracking._clean(raw.get("sourceLanguage"), 20)
        if source_language:
            spec["sourceLanguage"] = source_language
        if category == "company":
            company_slug = (
                tracking._clean(linked_company.get("catalogSlug"), 80)
                or tracking._slug(company)
            )
            spec["company"] = company
            spec["companySlug"] = company_slug
            if ticker:
                spec["ticker"] = ticker
        runtime_specs.append(spec)

    # Route every enabled source except explicit official-registry handoffs.
    # Truncating here would silently ignore configured sources, which
    # validate_user_source_coverage treats as a hard failure; per-source
    # maxItems already bounds crawl volume.
    return runtime_specs, sec_specs


def _install_strict_tracking_validation() -> None:
    original_load_tracking = tracking.load_tracking
    if getattr(original_load_tracking, "_strict_tracking_validation", False):
        return

    def load_tracking(path: Path = tracking.TRACKING_PATH) -> dict[str, Any]:
        raw = original_load_tracking(path)
        return strict_tracking_config.sanitize_tracking_config(raw)

    setattr(load_tracking, "_strict_tracking_validation", True)
    tracking.load_tracking = load_tracking
    tracking._parse_person_label = strict_tracking_config.parse_person_label


def _direct_only_generic_source(spec: dict[str, Any]) -> bool:
    source_url = str(spec.get("sourceUrl") or spec.get("url") or "")
    parts = urlsplit(source_url)
    host = (parts.hostname or "").casefold()
    return (
        generic_web_sources.source_kind(source_url) == "x"
        or (host.endswith("google.com") and parts.path.rstrip("/") == "/alerts")
    )


def _install_generic_adapter() -> None:
    original_install = tracking._install_runtime_overrides
    if getattr(original_install, "_generic_web_adapter", False):
        return

    def install(
        merged: dict[str, Any],
        sec_specs: dict[str, tuple[str, str, str, str]],
        active_ids: set[str],
    ) -> None:
        original_install(merged, sec_specs, active_ids)
        original_crawl_source = tracking.crawler._crawl_config_source
        original_replace_batches = tracking.crawler.replace_source_batches

        def crawl_source(
            spec: dict[str, Any], user_agent: str
        ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            if spec.get("adapter") != "generic_web":
                return original_crawl_source(spec, user_agent)
            if _direct_only_generic_source(spec):
                return generic_web_sources.crawl_generic_source(
                    spec, user_agent, tracking.crawler
                )

            articles, status = adaptive_public_sources.crawl_adaptive_source(
                spec,
                user_agent,
                tracking.crawler,
                generic_web_sources,
                robust_web_fallback,
            )
            if not articles and status.get("status") == "empty":
                status = dict(status)
                status["status"] = "error"
                status["failed"] = max(1, int(status.get("failed", 0) or 0))
                status["error"] = (
                    "No verifiable dated articles discovered; previous snapshot retained"
                )
                status["retainedPrevious"] = True
            return articles, status

        def replace_source_batches(
            existing: list[dict[str, Any]],
            incoming: list[dict[str, Any]],
            statuses: list[dict[str, Any]],
        ) -> list[dict[str, Any]]:
            history_aware = adaptive_public_sources.merge_adaptive_history(
                existing,
                incoming,
                statuses,
                tracking.crawler,
            )
            return original_replace_batches(existing, history_aware, statuses)

        setattr(replace_source_batches, "_adaptive_history", True)
        tracking.crawler._crawl_config_source = crawl_source
        tracking.crawler.replace_source_batches = replace_source_batches

    setattr(install, "_generic_web_adapter", True)
    tracking._install_runtime_overrides = install


def main() -> int:
    _install_strict_tracking_validation()
    tracking_taxonomy.install(tracking)
    x_rate_limit.install(tracking.crawler)
    wechat_public_sources.install(tracking)
    tracking._custom_sources = _custom_sources
    _install_generic_adapter()
    configure_crawler()
    _install_empty_sec_guard()
    return tracking.main()


if __name__ == "__main__":
    raise SystemExit(main())
