#!/usr/bin/env python3
"""Run the direct website crawler with category-aware source filtering.

Company sources are eligible for the generic direct website crawler. Media and
person sources stay in the category-aware feed/search crawler, except for
Eastmoney, which has a dedicated parser and listed-company attribution adapter
inside ``crawl_official_with_tracking``.

Shopify is kept as a tracked company but its broad homepage is intentionally
excluded from lightweight and duplicate user-source crawling. During the full
official-company refresh, Shopify is limited to Editions, product news and
investor-relations indexes, with broad sitemap and public-search fallbacks
disabled.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable
from urllib.parse import urlsplit

try:  # Imported by tests as tools.crawl_official_with_source_categories.
    from . import crawl_official_with_tracking as official_tracking
    from . import crawl_with_source_categories as source_categories
except ImportError:  # Executed directly with ``python tools/...``.
    import crawl_official_with_tracking as official_tracking
    import crawl_with_source_categories as source_categories


PUBLIC_ARTICLE_REGIONS = frozenset({"中国", "美国", "全球"})
SHOPIFY_SLUG = "shopify"
SHOPIFY_EDITIONS_URL = "https://www.shopify.com/editions"
SHOPIFY_PRODUCT_NEWS_URL = "https://www.shopify.com/news/category/product-news"
SHOPIFY_INVESTOR_URL = "https://www.shopify.com/investors"
SHOPIFY_INVESTOR_HOST_URL = "https://investors.shopify.com/"
SHOPIFY_NEWS_URLS = (
    SHOPIFY_EDITIONS_URL,
    SHOPIFY_PRODUCT_NEWS_URL,
    SHOPIFY_INVESTOR_URL,
    SHOPIFY_INVESTOR_HOST_URL,
)
SHOPIFY_ARTICLE_URL_PATTERNS = (
    r"^https://(?:www\.)?shopify\.com/editions(?:/|$)[^?#]*$",
    r"^https://(?:www\.)?shopify\.com/news/(?!about-us(?:/|$)|category(?:/|$))[^?#]+$",
    r"^https://(?:www\.)?shopify\.com/investors(?:/|$)[^?#]*$",
    r"^https://investors\.shopify\.com/(?!$)[^?#]+$",
)


def _public_article_region(value: Any) -> str:
    """Map precise company geographies onto the public article taxonomy."""

    region = official_tracking.official.clean_text(str(value or ""))
    return region if region in PUBLIC_ARTICLE_REGIONS else "全球"


def _scope_official_spec(spec):
    """Apply the narrow full-refresh policy for Shopify only."""

    if getattr(spec, "slug", "") != SHOPIFY_SLUG:
        return spec
    return replace(
        spec,
        homepage=SHOPIFY_EDITIONS_URL,
        news_urls=SHOPIFY_NEWS_URLS,
        sitemap_urls=(),
        article_url_patterns=SHOPIFY_ARTICLE_URL_PATTERNS,
        max_items=min(int(spec.max_items), 4),
        max_candidate_links=min(int(spec.max_candidate_links), 12),
    )


def _sitemap_urls_with_source_policy(
    spec,
    fallback: Callable[[Any], list[str]],
) -> list[str]:
    if getattr(spec, "slug", "") == SHOPIFY_SLUG:
        return []
    return fallback(spec)


def _search_urls_with_source_policy(
    spec,
    user_agent: str,
    fallback: Callable[[Any, str], list[str]],
) -> list[str]:
    if getattr(spec, "slug", "") == SHOPIFY_SLUG:
        return []
    return fallback(spec, user_agent)


def install_shopify_scope_adapter() -> None:
    """Limit Shopify to curated product and investor indexes in full refreshes."""

    official = official_tracking.official

    original_load_registry = official.load_registry
    if not getattr(original_load_registry, "_shopify_scope_adapter", False):

        def load_registry(*args, **kwargs):
            return [
                _scope_official_spec(spec)
                for spec in original_load_registry(*args, **kwargs)
            ]

        setattr(load_registry, "_shopify_scope_adapter", True)
        official.load_registry = load_registry

    original_default_sitemaps = official._default_sitemap_urls
    if not getattr(
        original_default_sitemaps,
        "_shopify_source_policy",
        False,
    ):

        def default_sitemap_urls(spec):
            return _sitemap_urls_with_source_policy(
                spec,
                original_default_sitemaps,
            )

        setattr(default_sitemap_urls, "_shopify_source_policy", True)
        official._default_sitemap_urls = default_sitemap_urls

    original_search_urls = official._search_official_urls
    if not getattr(original_search_urls, "_shopify_source_policy", False):

        def search_official_urls(spec, user_agent: str):
            return _search_urls_with_source_policy(
                spec,
                user_agent,
                original_search_urls,
            )

        setattr(search_official_urls, "_shopify_source_policy", True)
        official._search_official_urls = search_official_urls


def _registered_public_regions(official: Any) -> dict[str, str]:
    """Resolve the public region expected for every active official source."""

    return {
        spec.source_id: _public_article_region(spec.region)
        for spec in official.load_registry()
    }


def _normalize_registered_official_regions(
    articles: list[dict[str, Any]],
    public_regions: dict[str, str],
) -> list[dict[str, Any]]:
    """Repair retained official rows without masking unrelated bad data.

    Only records whose source id is bound to the active official-site registry
    are rewritten. Unregistered media and discovery records still have to pass
    the shared quality gate with their own region value.
    """

    normalized: list[dict[str, Any]] = []
    for article in articles:
        expected_region = public_regions.get(str(article.get("sourceId", "")))
        if expected_region is None or article.get("region") == expected_region:
            normalized.append(article)
            continue
        repaired = dict(article)
        repaired["region"] = expected_region
        normalized.append(repaired)
    return normalized


def install_public_region_adapter() -> None:
    """Normalize new and retained official-company rows before quality checks.

    The company catalog intentionally keeps precise headquarters geographies
    such as ``加拿大``. Public article records use a coarser three-value region
    contract, so non-China/non-US company regions publish as ``全球``.

    Normalizing only newly parsed pages left one recovery gap: when Shopify was
    temporarily unavailable, the official crawler preserved its previous batch
    unchanged. A legacy ``加拿大`` row could therefore keep failing the shared
    quality gate even though the network failure itself was safely retained.
    The replacement-boundary adapter below repairs both fixed and active
    user-configured official-site batches from their canonical registry specs.
    """

    official = official_tracking.official

    original_article_from_page = official._article_from_page
    if not getattr(original_article_from_page, "_public_region_adapter", False):

        def article_from_page(spec, url: str, body: str):
            article = original_article_from_page(spec, url, body)
            if article is not None:
                article["region"] = _public_article_region(article.get("region"))
            return article

        setattr(article_from_page, "_public_region_adapter", True)
        official._article_from_page = article_from_page

    original_replace_batches = official.replace_official_source_batches
    if not getattr(
        original_replace_batches,
        "_public_region_retained_batch_adapter",
        False,
    ):

        def replace_official_source_batches(existing, incoming, statuses):
            merged = original_replace_batches(existing, incoming, statuses)
            return _normalize_registered_official_regions(
                merged,
                _registered_public_regions(official),
            )

        setattr(
            replace_official_source_batches,
            "_public_region_retained_batch_adapter",
            True,
        )
        official.replace_official_source_batches = replace_official_source_batches


def _is_supported_media_source(raw: dict[str, Any]) -> bool:
    name = official_tracking._clean(raw.get("name"), 80)
    url = official_tracking._clean(raw.get("url"), 500)
    host = (urlsplit(url).hostname or "").casefold()
    return "东方财富" in name or host == "eastmoney.com" or host.endswith(".eastmoney.com")


def _filtered_tracking(path=official_tracking.TRACKING_PATH) -> dict[str, Any]:
    payload = _original_load_tracking(path)
    filtered = dict(payload)
    filtered["sources"] = [
        raw
        for raw in payload.get("sources", [])
        if isinstance(raw, dict)
        and not source_categories.is_official_registry_only_source(raw)
        and (
            source_categories.source_category(raw) == "company"
            or (
                source_categories.source_category(raw) == "media"
                and _is_supported_media_source(raw)
            )
        )
    ]
    return filtered


_original_load_tracking = official_tracking.load_tracking


def main() -> int:
    install_shopify_scope_adapter()
    install_public_region_adapter()
    official_tracking.load_tracking = _filtered_tracking
    return official_tracking.main()


if __name__ == "__main__":
    raise SystemExit(main())
