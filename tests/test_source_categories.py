from __future__ import annotations

import unittest

from tools import crawl_official_with_source_categories as official_categories
from tools import crawl_with_source_categories as generic_categories
from tools import migrate_article_entities as migration


class SourceCategoryTests(unittest.TestCase):
    def test_explicit_category_wins(self) -> None:
        self.assertEqual(
            generic_categories.source_category(
                {
                    "sourceCategory": "person",
                    "sourceType": "listing-search",
                    "company": "Some Company",
                }
            ),
            "person",
        )

    def test_sec_source_defaults_to_company(self) -> None:
        self.assertEqual(
            generic_categories.source_category(
                {"sourceType": "sec", "company": "Example"}
            ),
            "company",
        )

    def test_listing_search_defaults_to_media(self) -> None:
        self.assertEqual(
            generic_categories.source_category(
                {"sourceType": "listing-search", "company": "投资界"}
            ),
            "media",
        )

    def test_router_splits_bounded_search_from_adaptive_exceptions(self) -> None:
        tracking = {
            "sources": [
                {
                    "id": "company",
                    "name": "公司官网",
                    "company": "Example Company",
                    "sourceCategory": "company",
                    "sourceType": "listing-search",
                    "url": "https://company.example/news",
                },
                {
                    "id": "media",
                    "name": "行业媒体",
                    "sourceCategory": "media",
                    "sourceType": "listing-search",
                    "url": "https://media.example/news",
                },
                {
                    "id": "person",
                    "name": "研究者博客",
                    "sourceCategory": "person",
                    "sourceType": "listing-search",
                    "url": "https://person.example/blog",
                },
                {
                    "id": "eastmoney",
                    "name": "东方财富",
                    "sourceCategory": "media",
                    "sourceType": "listing-search",
                    "url": "https://www.eastmoney.com/default.html",
                },
            ]
        }

        runtime_specs, sec_specs = generic_categories._custom_sources(tracking, [])
        specs_by_id = {spec["id"]: spec for spec in runtime_specs}

        self.assertEqual(sec_specs, {})
        self.assertEqual(
            set(specs_by_id),
            {
                "user-source-company",
                "user-source-media",
                "user-source-person",
                "user-source-eastmoney",
            },
        )
        self.assertEqual(specs_by_id["user-source-company"]["adapter"], "rss")
        self.assertEqual(specs_by_id["user-source-media"]["adapter"], "rss")
        self.assertEqual(specs_by_id["user-source-person"]["adapter"], "generic_web")
        self.assertEqual(specs_by_id["user-source-eastmoney"]["adapter"], "generic_web")
        self.assertEqual(
            specs_by_id["user-source-company"]["sourceCategory"],
            "company",
        )
        self.assertEqual(
            specs_by_id["user-source-media"]["sourceCategory"],
            "media",
        )
        self.assertEqual(
            specs_by_id["user-source-person"]["sourceCategory"],
            "person",
        )
        self.assertEqual(
            specs_by_id["user-source-eastmoney"]["sourceCategory"],
            "media",
        )
        self.assertEqual(
            specs_by_id["user-source-eastmoney"]["sourceUrl"],
            "https://www.eastmoney.com/",
        )
        self.assertTrue(
            generic_categories._has_publisher_handoff(
                specs_by_id["user-source-eastmoney"]["sourceUrl"]
            )
        )
        self.assertEqual(
            specs_by_id["user-source-company"]["allowedHosts"],
            ["company.example"],
        )
        self.assertEqual(
            specs_by_id["user-source-media"]["allowedHosts"],
            ["media.example"],
        )
        self.assertNotIn("allowedHosts", specs_by_id["user-source-person"])
        self.assertNotIn("allowedHosts", specs_by_id["user-source-eastmoney"])
        self.assertEqual(
            specs_by_id["user-source-company"]["company"],
            "Example Company",
        )

    def _filtered_official_tracking(self, tracking: dict) -> dict:
        original = official_categories._original_load_tracking
        try:
            official_categories._original_load_tracking = lambda _path: tracking
            return official_categories._filtered_tracking()
        finally:
            official_categories._original_load_tracking = original

    def test_official_crawler_keeps_company_sources(self) -> None:
        tracking = {
            "sources": [
                {
                    "id": "company",
                    "name": "公司官网",
                    "sourceCategory": "company",
                    "sourceType": "listing-search",
                    "url": "https://company.example/news",
                },
                {
                    "id": "media",
                    "name": "媒体",
                    "sourceCategory": "media",
                    "sourceType": "listing-search",
                    "url": "https://media.example/news",
                },
            ]
        }

        filtered = self._filtered_official_tracking(tracking)

        self.assertEqual(
            [source["id"] for source in filtered["sources"]],
            ["company"],
        )

    def test_official_crawler_keeps_eastmoney_media_exception(self) -> None:
        tracking = {
            "sources": [
                {
                    "id": "eastmoney",
                    "name": "东方财富",
                    "sourceCategory": "media",
                    "sourceType": "listing-search",
                    "url": "https://www.eastmoney.com/default.html",
                },
                {
                    "id": "other-media",
                    "name": "投资界",
                    "sourceCategory": "media",
                    "sourceType": "listing-search",
                    "url": "https://www.pedaily.cn/",
                },
            ]
        }

        filtered = self._filtered_official_tracking(tracking)

        self.assertEqual(
            [source["id"] for source in filtered["sources"]],
            ["eastmoney"],
        )


class LegacyEntityMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracking = {
            "sources": [
                {
                    "id": "source-track-investment",
                    "name": "投资界",
                    "url": "https://www.pedaily.cn/",
                    "sourceType": "listing-search",
                    "sourceCategory": "media",
                    "company": "",
                }
            ]
        }

    def test_migration_removes_profile_pages_and_fake_company_links(self) -> None:
        payload = {
            "articleCount": 3,
            "articles": [
                {
                    "id": "profile",
                    "sourceId": "official-user-投资界",
                    "title": "侃见财经的文章_投资界",
                    "company": "投资界",
                    "companySlug": "user-投资界",
                    "source": {
                        "name": "投资界",
                        "url": "https://www.pedaily.cn/media/m899",
                        "level": "官方披露",
                    },
                },
                {
                    "id": "fake-company",
                    "sourceId": "official-user-投资界",
                    "title": "人工智能融资观察",
                    "company": "投资界",
                    "companySlug": "user-投资界",
                    "source": {
                        "name": "投资界",
                        "url": "https://www.pedaily.cn/202607/123.shtml",
                        "level": "官方披露",
                    },
                },
                {
                    "id": "real-company",
                    "sourceId": "official-user-投资界",
                    "title": "Anthropic完成新融资",
                    "company": "Anthropic",
                    "companySlug": "anthropic",
                    "source": {
                        "name": "投资界",
                        "url": "https://www.pedaily.cn/202607/456.shtml",
                        "level": "媒体报道",
                    },
                },
            ],
            "sourceStatus": [{"id": "official-user-投资界", "status": "ok"}],
        }

        migrated, report = migration.migrate(payload, self.tracking)

        self.assertEqual(migrated["articleCount"], 2)
        self.assertEqual(report["removedNonArticles"], 1)
        self.assertEqual(report["removedLegacyStatuses"], 0)
        cleaned = next(item for item in migrated["articles"] if item["id"] == "fake-company")
        preserved = next(item for item in migrated["articles"] if item["id"] == "real-company")
        self.assertEqual(cleaned["company"], migration.GENERIC_COMPANY)
        self.assertNotIn("companySlug", cleaned)
        self.assertEqual(cleaned["source"]["level"], "媒体报道")
        self.assertEqual(preserved["company"], "Anthropic")
        self.assertEqual(preserved["companySlug"], "anthropic")
        self.assertEqual(
            migrated["sourceStatus"],
            [{"id": "official-user-投资界", "status": "ok"}],
        )


class SourceRoutingCapacityTests(unittest.TestCase):
    def test_every_enabled_source_produces_a_runtime_spec(self) -> None:
        """Regression: routing must not silently truncate configured sources.

        A batch of media sources once pushed the enabled count past a hard
        [:80] slice; the dropped sources had no runtime spec, so
        validate_user_source_coverage failed every refresh and the public
        snapshot froze."""

        tracking = {
            "sources": [
                {
                    "id": f"media-{index}",
                    "name": f"媒体 {index}",
                    "sourceCategory": "media",
                    "sourceType": "listing-search",
                    "url": f"https://media-{index}.example/news",
                }
                for index in range(127)
            ]
        }
        specs, sec_specs = generic_categories._custom_sources(tracking, [])
        self.assertEqual(len(specs), 127)
        self.assertEqual(sec_specs, {})
        self.assertEqual(
            len({spec["id"] for spec in specs}),
            127,
            "runtime ids must stay unique for coverage accounting",
        )


if __name__ == "__main__":
    unittest.main()
