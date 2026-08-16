from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime

from tools import crawl_articles
from tools import crawl_official_with_source_categories as category_crawler
from tools import snapshot_retention
from tools.crawl_official_companies import load_registry


class ProductionOfficialCompanyRegistryTests(unittest.TestCase):
    def test_registry_matches_catalog_and_contains_google(self) -> None:
        specs = load_registry()
        by_slug = {spec.slug: spec for spec in specs}
        self.assertIn("google", by_slug)
        self.assertEqual(by_slug["google"].name, "Google")
        self.assertEqual(by_slug["google"].region, "美国")
        self.assertEqual(by_slug["google"].sector, "AI / AGI")
        self.assertIn("blog.google", by_slug["google"].allowed_hosts)

    def test_precise_company_regions_map_to_public_article_contract(self) -> None:
        specs = load_registry()
        by_slug = {spec.slug: spec for spec in specs}
        self.assertEqual(by_slug["shopify"].region, "加拿大")
        self.assertEqual(category_crawler._public_article_region("中国"), "中国")
        self.assertEqual(category_crawler._public_article_region("美国"), "美国")
        self.assertEqual(category_crawler._public_article_region("全球"), "全球")
        self.assertEqual(category_crawler._public_article_region("加拿大"), "全球")

    def test_official_article_adapter_normalizes_before_quality_validation(self) -> None:
        official = category_crawler.official_tracking.official
        original_article_from_page = official._article_from_page
        original_replace_batches = official.replace_official_source_batches

        def article_from_page(_spec, _url: str, _body: str):
            return {"region": "加拿大", "title": "Shopify official update"}

        try:
            official._article_from_page = article_from_page
            category_crawler.install_public_region_adapter()
            article = official._article_from_page(None, "https://example.com", "")
            self.assertIsNotNone(article)
            self.assertEqual(article["region"], "全球")
            self.assertEqual(article["title"], "Shopify official update")
        finally:
            official._article_from_page = original_article_from_page
            official.replace_official_source_batches = original_replace_batches

    def test_retained_shopify_batches_are_repaired_when_recrawl_fails(self) -> None:
        official = category_crawler.official_tracking.official
        original_article_from_page = official._article_from_page
        original_replace_batches = official.replace_official_source_batches
        original_load_registry = official.load_registry
        published_at = datetime.now(UTC).date().isoformat()
        legacy_shopify = {
            "id": "legacy-shopify",
            "sourceId": "official-shopify",
            "title": "Shopify official update",
            "summary": "Shopify published an official company update.",
            "type": "公司动态",
            "region": "加拿大",
            "sector": "AI / AGI",
            "company": "Shopify",
            "companySlug": "shopify",
            "publishedAt": published_at,
            "importance": 80,
            "source": {
                "name": "Shopify",
                "url": "https://www.shopify.com/news/legacy-update",
                "level": "官方披露",
                "platform": "官方网站",
            },
        }
        user_shopify_spec = official.CompanySpec(
            slug="user-shopify",
            name="Shopify",
            region="全球",
            sector="AI / AGI",
            homepage="https://www.shopify.com/",
            news_urls=("https://www.shopify.com/news",),
            sitemap_urls=("https://www.shopify.com/sitemap.xml",),
            aliases=(),
            entity_aliases=("Shopify",),
            article_url_patterns=(r"/news/",),
            require_entity_match=False,
            max_items=6,
            max_candidate_links=24,
            max_age_days=730,
            request_timeout=10,
        )
        legacy_user_shopify = {
            **legacy_shopify,
            "id": "legacy-user-shopify",
            "sourceId": user_shopify_spec.source_id,
        }
        unrelated_media = {
            **legacy_shopify,
            "id": "unrelated-media",
            "sourceId": "media-example",
            "company": "Example Media",
            "companySlug": "example-media",
            "source": {
                **legacy_shopify["source"],
                "url": "https://media.example/legacy-update",
                "level": "媒体报道",
                "platform": "Example Media",
            },
        }
        base_specs = original_load_registry()

        def active_registry(*_args, **_kwargs):
            return [*base_specs, user_shopify_spec]

        def replace_batches(_existing, _incoming, _statuses):
            return [
                dict(legacy_shopify),
                dict(legacy_user_shopify),
                dict(unrelated_media),
            ]

        try:
            official.load_registry = active_registry
            official.replace_official_source_batches = replace_batches
            category_crawler.install_public_region_adapter()
            merged = official.replace_official_source_batches(
                [],
                [],
                [
                    {"id": "official-shopify", "status": "error"},
                    {"id": user_shopify_spec.source_id, "status": "error"},
                ],
            )
            for article in merged[:2]:
                self.assertEqual(article["region"], "全球")
                self.assertNotIn(
                    "invalid:region",
                    crawl_articles.validate_article(article),
                )
            self.assertEqual(
                merged[2]["region"],
                "加拿大",
                "the repair must not hide invalid regions from unrelated sources",
            )
        finally:
            official._article_from_page = original_article_from_page
            official.replace_official_source_batches = original_replace_batches
            official.load_registry = original_load_registry

    def test_committed_shopify_rows_obey_public_region_contract(self) -> None:
        official = category_crawler.official_tracking.official
        payload = json.loads(official.OUTPUT_PATH.read_text(encoding="utf-8"))

        # Schema v2 snapshots were produced before official-company status counts
        # were reconciled after global retention. Migrate that historical fixture
        # in memory; once schema v3 is committed this branch is no longer used.
        retention = payload.get("snapshotRetention")
        retention = retention if isinstance(retention, dict) else {}
        if int(retention.get("schemaVersion", 0) or 0) < snapshot_retention.RETENTION_SCHEMA_VERSION:
            payload, _ = snapshot_retention.apply_retention(payload)

        shopify_rows = [
            article
            for article in payload.get("articles", [])
            if article.get("sourceId") == "official-shopify"
        ]
        shopify_status = next(
            (
                status
                for status in payload.get("sourceStatus", [])
                if status.get("id") == "official-shopify"
            ),
            None,
        )

        self.assertIsNotNone(shopify_status)
        self.assertEqual(
            int(shopify_status.get("accepted", 0) or 0),
            len(shopify_rows),
        )
        for article in shopify_rows:
            self.assertEqual(article.get("region"), "全球")
            self.assertNotIn(
                "invalid:region",
                crawl_articles.validate_article(article),
            )


if __name__ == "__main__":
    unittest.main()
