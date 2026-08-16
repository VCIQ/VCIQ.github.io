from __future__ import annotations

import json
import unittest

from tools import crawl_articles
from tools import crawl_official_companies as official
from tools import crawl_official_with_source_categories as official_categories
from tools import crawl_with_source_categories as generic_categories
from tools.validate_user_source_coverage import evaluate_coverage


def shopify_source() -> dict:
    return {
        "id": "source-auto-shopify",
        "name": "Shopify 官方网站",
        "url": "https://www.shopify.com",
        "sourceType": "listing-search",
        "sourceCategory": "company",
        "region": "全球",
        "sector": "新消费",
        "company": "Shopify",
        "ticker": "",
        "keywords": ["Shopify"],
        "enabled": True,
    }


def company_source() -> dict:
    return {
        "id": "example-company",
        "name": "Example Company",
        "url": "https://example.com/news",
        "sourceType": "listing-search",
        "sourceCategory": "company",
        "region": "全球",
        "sector": "AI / AGI",
        "company": "Example Company",
        "ticker": "",
        "keywords": ["Example"],
        "enabled": True,
    }


def company_spec(slug: str = "shopify") -> official.CompanySpec:
    return official.CompanySpec(
        slug=slug,
        name="Shopify" if slug == "shopify" else "Example",
        region="加拿大" if slug == "shopify" else "美国",
        sector="新消费" if slug == "shopify" else "AI / AGI",
        homepage=(
            "https://www.shopify.com/news/about-us"
            if slug == "shopify"
            else "https://example.com/"
        ),
        news_urls=(
            ("https://www.shopify.com/news",)
            if slug == "shopify"
            else ("https://example.com/news",)
        ),
        sitemap_urls=(
            ("https://www.shopify.com/sitemap.xml",)
            if slug == "shopify"
            else ("https://example.com/sitemap.xml",)
        ),
        aliases=("Shopify Inc.",) if slug == "shopify" else (),
        entity_aliases=("Shopify", "Shopify Inc.") if slug == "shopify" else ("Example",),
        article_url_patterns=(),
        require_entity_match=False,
        max_items=8,
        max_candidate_links=24,
        max_age_days=730,
        request_timeout=10,
    )


class ShopifySourceCadenceTests(unittest.TestCase):
    def test_generic_router_defers_broad_shopify_homepage(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [shopify_source(), company_source()],
        }

        runtime_specs, sec_specs = generic_categories._custom_sources(config, [])

        self.assertEqual(sec_specs, {})
        self.assertEqual(
            [spec["id"] for spec in runtime_specs],
            ["user-source-example-company"],
        )

    def test_coverage_audits_shopify_as_explicit_official_handoff(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [shopify_source()],
        }

        report = evaluate_coverage(config, {"sourceStatus": []})

        self.assertTrue(report["passed"])
        self.assertEqual(report["enabledConfiguredSources"], 1)
        self.assertEqual(report["runtimeConfiguredSources"], 0)
        self.assertEqual(report["expectedRuntimeStatuses"], 0)
        self.assertEqual(
            report["deferredOfficialRegistrySources"],
            [
                {
                    "id": "source-auto-shopify",
                    "company": "Shopify",
                    "policy": "scoped-official-company-refresh",
                }
            ],
        )

    def test_official_user_source_filter_removes_shopify_duplicate(self) -> None:
        tracking = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [shopify_source(), company_source()],
        }
        original = official_categories._original_load_tracking
        try:
            official_categories._original_load_tracking = (
                lambda *_args, **_kwargs: tracking
            )
            filtered = official_categories._filtered_tracking()
        finally:
            official_categories._original_load_tracking = original

        self.assertEqual(
            [source["id"] for source in filtered["sources"]],
            ["example-company"],
        )

    def test_shopify_full_refresh_scope_keeps_only_curated_indexes(self) -> None:
        scoped = official_categories._scope_official_spec(company_spec())

        self.assertEqual(
            scoped.news_urls,
            official_categories.SHOPIFY_NEWS_URLS,
        )
        self.assertNotIn("https://www.shopify.com/news", scoped.news_urls)
        self.assertEqual(
            scoped.homepage,
            official_categories.SHOPIFY_EDITIONS_URL,
        )
        self.assertEqual(scoped.sitemap_urls, ())
        self.assertEqual(scoped.max_items, 4)
        self.assertEqual(scoped.max_candidate_links, 12)
        self.assertIn("shopify.com", scoped.allowed_hosts)
        self.assertIn("investors.shopify.com", scoped.allowed_hosts)

    def test_shopify_disables_broad_sitemap_and_search_fallbacks(self) -> None:
        shopify = official_categories._scope_official_spec(company_spec())
        example = company_spec("example")
        sitemap_calls: list[str] = []
        search_calls: list[str] = []

        def sitemap_fallback(spec) -> list[str]:
            sitemap_calls.append(spec.slug)
            return ["https://example.com/sitemap.xml"]

        def search_fallback(spec, _user_agent: str) -> list[str]:
            search_calls.append(spec.slug)
            return ["https://example.com/news/update"]

        self.assertEqual(
            official_categories._sitemap_urls_with_source_policy(
                shopify,
                sitemap_fallback,
            ),
            [],
        )
        self.assertEqual(
            official_categories._search_urls_with_source_policy(
                shopify,
                "test-agent",
                search_fallback,
            ),
            [],
        )
        self.assertEqual(sitemap_calls, [])
        self.assertEqual(search_calls, [])

        self.assertEqual(
            official_categories._sitemap_urls_with_source_policy(
                example,
                sitemap_fallback,
            ),
            ["https://example.com/sitemap.xml"],
        )
        self.assertEqual(
            official_categories._search_urls_with_source_policy(
                example,
                "test-agent",
                search_fallback,
            ),
            ["https://example.com/news/update"],
        )
        self.assertEqual(sitemap_calls, ["example"])
        self.assertEqual(search_calls, ["example"])

    def test_shopify_company_profile_remains_published(self) -> None:
        payload = json.loads(
            (crawl_articles.ROOT / "config" / "company_registry.json").read_text(
                encoding="utf-8"
            )
        )
        profile = next(
            company
            for company in payload.get("companies", [])
            if company.get("slug") == "shopify"
        )

        self.assertEqual(profile["name"], "Shopify")
        self.assertEqual(profile["sector"], "新消费")
        self.assertEqual(profile["stage"], "已上市")


if __name__ == "__main__":
    unittest.main()
