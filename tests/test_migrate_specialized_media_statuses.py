from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tools.migrate_article_entities import load_company_route_slugs, migrate


SOURCE_ID = "official-user-东方财富"


def tracking() -> dict:
    return {
        "sources": [
            {
                "id": "source-track-eastmoney",
                "name": "东方财富",
                "url": "https://www.eastmoney.com/default.html",
                "sourceType": "listing-search",
                "sourceCategory": "media",
                "company": "",
                "enabled": True,
            }
        ]
    }


def article(*, source_id: str = SOURCE_ID, internal: bool = False) -> dict:
    value = {
        "id": "eastmoney-detail",
        "sourceId": source_id,
        "title": "三星电子与博通合作开发先进内存芯片",
        "summary": "双方签署先进内存芯片合作协议。",
        "company": "科技产业",
        "publishedAt": "2026-07-25",
        "source": {
            "name": "东方财富",
            "url": "https://finance.eastmoney.com/a/202607253821110827.html",
            "level": "媒体报道",
            "platform": "东方财富",
        },
    }
    if internal:
        value["_eastmoneyBatchOrigin"] = "retained"
    return value


def status(source_id: str = SOURCE_ID) -> dict:
    return {
        "id": source_id,
        "name": "东方财富 官方动态",
        "company": "东方财富",
        "status": "ok",
        "accepted": 1,
        "failed": 0,
        "platform": "东方财富",
    }


class SpecializedMediaStatusMigrationTests(unittest.TestCase):
    def test_fixed_official_source_wins_over_media_host_fallback(self) -> None:
        official = article(source_id="official-ionq")
        official["id"] = "ionq-detail"
        official["company"] = "IonQ"
        official["source"] = {
            "name": "IonQ",
            "url": "https://ionq.com/news/technical-roadmap",
            "level": "媒体报道",
            "platform": "IonQ",
        }
        ionq_tracking = {
            "sources": [
                {
                    "id": "source-ionq",
                    "name": "IonQ 官方来源",
                    "url": "https://ionq.com/",
                    "sourceCategory": "media",
                    "company": "",
                }
            ]
        }

        migrated, report = migrate(
            {"articleCount": 1, "articles": [official], "sourceStatus": []},
            ionq_tracking,
        )

        self.assertEqual(migrated["articles"][0]["source"]["level"], "官方披露")
        self.assertEqual(migrated["articles"][0]["source"]["platform"], "官方网站")
        self.assertEqual(report["relabelledSources"], 1)

    def test_unknown_official_prefix_is_not_promoted_to_canonical_source(self) -> None:
        unknown = article(source_id="official-sohu")
        unknown["id"] = "unknown-official-detail"
        unknown["source"] = {
            "name": "搜狐网",
            "url": "https://www.sohu.com/a/reposted-story",
            "level": "媒体报道",
            "platform": "搜狐网",
        }
        media_tracking = {
            "sources": [
                {
                    "id": "source-sohu-media",
                    "name": "搜狐网",
                    "url": "https://www.sohu.com/",
                    "sourceCategory": "media",
                    "company": "",
                }
            ]
        }

        migrated, report = migrate(
            {"articleCount": 1, "articles": [unknown], "sourceStatus": []},
            media_tracking,
        )
        migrated_source = migrated["articles"][0]["source"]

        self.assertEqual(migrated_source["level"], "媒体报道")
        self.assertEqual(migrated_source["platform"], "搜狐网")
        self.assertEqual(report["relabelledSources"], 0)

    def test_official_user_media_source_keeps_legacy_identity_for_migration(self) -> None:
        sina_tracking = {
            "sources": [
                {
                    "id": "source-auto-item-ab941d7c",
                    "name": "新浪网 官方网站",
                    "url": "http://www.sina.com.cn",
                    "sourceCategory": "media",
                    # Keep this legacy company label so official-user-新浪网
                    # remains addressable during the migration.
                    "company": "新浪网",
                }
            ]
        }
        legacy = article(source_id="official-user-新浪网")
        legacy["id"] = "sina-detail"
        legacy["title"] = "人工智能行业发布新动态"
        legacy["summary"] = "行业近期披露多项产品进展。"
        legacy["company"] = "新浪网"
        legacy["companySlug"] = "user-新浪网"
        legacy["source"] = {
            "name": "新浪网 官方网站",
            "url": "https://news.sina.com.cn/tech/example.shtml",
            "level": "官方披露",
            "platform": "官方网站",
        }

        migrated, report = migrate(
            {"articleCount": 1, "articles": [legacy], "sourceStatus": []},
            sina_tracking,
            company_route_slugs=set(),
        )
        migrated_article = migrated["articles"][0]

        self.assertEqual(migrated_article["source"]["level"], "媒体报道")
        self.assertEqual(migrated_article["company"], "科技产业")
        self.assertNotIn("companySlug", migrated_article)
        self.assertEqual(report["relabelledSources"], 1)
        self.assertEqual(report["clearedFakeCompanies"], 1)

    def test_tracked_sohu_portal_article_is_downgraded_to_media(self) -> None:
        sohu_tracking = {
            "sources": [
                {
                    "id": "source-auto-item-ca1e1423",
                    "name": "搜狐网",
                    "url": "https://www.sohu.com",
                    "sourceCategory": "media",
                    # Retain the old company label only as a migration alias.
                    "company": "搜狐网",
                }
            ]
        }
        legacy = article(source_id="user-source-source-auto-item-ca1e1423")
        legacy["id"] = "sohu-detail"
        legacy["title"] = "SpaceX 官宣建设最大星际基地"
        legacy["summary"] = "媒体报道商业航天项目进展。"
        legacy["company"] = "搜狐网"
        legacy["companySlug"] = "user-搜狐网"
        legacy["source"] = {
            "name": "搜狐网 官方网站",
            "url": "https://www.sohu.com/a/example",
            "level": "官方披露",
            "platform": "官方网站",
        }

        migrated, report = migrate(
            {"articleCount": 1, "articles": [legacy], "sourceStatus": []},
            sohu_tracking,
            company_route_slugs=set(),
        )
        migrated_article = migrated["articles"][0]

        self.assertEqual(migrated_article["source"]["level"], "媒体报道")
        self.assertEqual(migrated_article["company"], "科技产业")
        self.assertNotIn("companySlug", migrated_article)
        self.assertEqual(report["relabelledSources"], 1)
        self.assertEqual(report["clearedFakeCompanies"], 1)

    def test_invalid_future_date_is_removed(self) -> None:
        future = datetime.now(ZoneInfo("Asia/Taipei")).date() + timedelta(days=1)
        invalid = article(source_id="official-anthropic")
        invalid["publishedAt"] = future.isoformat()
        payload = {
            "articleCount": 1,
            "articles": [invalid],
            "sourceStatus": [],
        }

        migrated, report = migrate(
            payload,
            tracking(),
            remove_invalid_dates=True,
        )

        self.assertEqual(migrated["articles"], [])
        self.assertEqual(migrated["articleCount"], 0)
        self.assertEqual(report["removedInvalidDates"], 1)

    def test_unknown_company_route_is_unlinked(self) -> None:
        unknown = article(source_id="official-google")
        unknown["company"] = "Google"
        unknown["companySlug"] = "google"
        known = article(source_id="official-anthropic")
        known["id"] = "anthropic-detail"
        known["company"] = "Anthropic"
        known["companySlug"] = "anthropic"
        payload = {
            "articleCount": 2,
            "articles": [unknown, known],
            "sourceStatus": [],
        }

        migrated, report = migrate(
            payload,
            tracking(),
            company_route_slugs={"anthropic"},
        )

        by_id = {item["id"]: item for item in migrated["articles"]}
        self.assertNotIn("companySlug", by_id["eastmoney-detail"])
        self.assertEqual(by_id["anthropic-detail"]["companySlug"], "anthropic")
        self.assertEqual(report["removedUnknownCompanySlugs"], 1)

    def test_production_company_routes_include_google(self) -> None:
        routes = load_company_route_slugs()

        self.assertIn("openai", routes)
        self.assertIn("anthropic", routes)
        self.assertIn("google", routes)

    def test_status_is_preserved_when_surviving_article_uses_source_id(self) -> None:
        payload = {
            "articleCount": 1,
            "articles": [article()],
            "sourceStatus": [status()],
        }

        migrated, report = migrate(payload, tracking())

        self.assertEqual(migrated["sourceStatus"], [status()])
        self.assertEqual(report["removedLegacyStatuses"], 0)
        self.assertEqual(report["recoveredSpecializedStatuses"], 0)
        self.assertEqual(migrated["articles"][0]["sourceId"], SOURCE_ID)

    def test_missing_status_is_recovered_from_surviving_articles(self) -> None:
        payload = {
            "articleCount": 1,
            "articles": [article()],
            "sourceStatus": [],
        }

        migrated, report = migrate(payload, tracking())
        recovered = migrated["sourceStatus"][0]

        self.assertEqual(report["recoveredSpecializedStatuses"], 1)
        self.assertEqual(recovered["id"], SOURCE_ID)
        self.assertEqual(recovered["status"], "partial")
        self.assertEqual(recovered["accepted"], 1)
        self.assertEqual(recovered["newAccepted"], 0)
        self.assertEqual(recovered["retainedPreviousCount"], 1)
        self.assertTrue(recovered["retainedPrevious"])
        self.assertTrue(recovered["recoveredStatus"])
        self.assertIn("legacy status migration", recovered["error"])

    def test_recovery_is_idempotent(self) -> None:
        payload = {
            "articleCount": 1,
            "articles": [article()],
            "sourceStatus": [],
        }

        first, first_report = migrate(payload, tracking())
        second, second_report = migrate(first, tracking())

        self.assertEqual(first["sourceStatus"], second["sourceStatus"])
        self.assertEqual(first_report["recoveredSpecializedStatuses"], 1)
        self.assertEqual(second_report["recoveredSpecializedStatuses"], 0)
        self.assertEqual(len(second["sourceStatus"]), 1)

    def test_orphaned_legacy_status_is_removed(self) -> None:
        payload = {
            "articleCount": 0,
            "articles": [],
            "sourceStatus": [status()],
        }

        migrated, report = migrate(payload, tracking())

        self.assertEqual(migrated["sourceStatus"], [])
        self.assertEqual(report["removedLegacyStatuses"], 1)
        self.assertEqual(report["recoveredSpecializedStatuses"], 0)

    def test_unrelated_status_is_not_removed(self) -> None:
        unrelated = {
            "id": "official-anthropic",
            "name": "Anthropic 官方动态",
            "status": "ok",
            "accepted": 1,
        }
        payload = {
            "articleCount": 1,
            "articles": [article()],
            "sourceStatus": [status(), unrelated],
        }

        migrated, report = migrate(payload, tracking())

        self.assertEqual(
            {item["id"] for item in migrated["sourceStatus"]},
            {SOURCE_ID, "official-anthropic"},
        )
        self.assertEqual(report["removedLegacyStatuses"], 0)
        self.assertEqual(report["recoveredSpecializedStatuses"], 0)

    def test_internal_origin_marker_survives_migration_for_refinement(self) -> None:
        payload = {
            "articleCount": 1,
            "articles": [article(internal=True)],
            "sourceStatus": [status()],
        }

        migrated, _ = migrate(payload, tracking())

        self.assertEqual(
            migrated["articles"][0]["_eastmoneyBatchOrigin"],
            "retained",
        )


if __name__ == "__main__":
    unittest.main()
