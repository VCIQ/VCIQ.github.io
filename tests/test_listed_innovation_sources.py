import json
import unittest
from datetime import UTC, datetime
from pathlib import Path

from tools.crawl_official_companies import load_registry, listed_source_receipt, all_sources_failed, _article_from_page
from tools.crawl_articles import validate_article

ROOT = Path(__file__).resolve().parents[1]


class ListedInnovationSourceTests(unittest.TestCase):
    def test_corporate_boilerplate_title_is_not_a_dated_news_event(self):
        spec = next(spec for spec in load_registry() if spec.slug == "zhipu-ai")
        body = """<html><head><meta property="og:title" content="Z.ai - Inspiring AGI to Benefit Humanity">
        <meta property="article:published_time" content="2026-09-30T10:00:00Z"></head>
        <body><h1>Z.ai - Inspiring AGI to Benefit Humanity</h1></body></html>"""
        self.assertIsNone(_article_from_page(spec, spec.homepage + "news/cms-page", body))

    def test_precise_company_region_is_not_replaced_by_its_listing_market(self):
        spec = next(spec for spec in load_registry() if spec.slug == "tsmc")
        today = datetime.now(UTC).date().isoformat()
        article = _article_from_page(spec, "https://pr.tsmc.com/english/news/1234", f"""
        <html><head><meta property="og:title" content="TSMC launches a new advanced chip platform">
        <meta property="article:published_time" content="{today}T10:00:00Z">
        <meta name="description" content="TSMC announces a new advanced chip platform for its technology customers.">
        </head><body><h1>TSMC launches a new advanced chip platform</h1></body></html>
        """)
        self.assertIsNotNone(article)
        self.assertEqual(spec.region, "中国台湾")
        self.assertEqual(article["region"], "全球")
        self.assertNotIn("invalid:region", validate_article(article))

    def test_all_failure_does_not_advance_a_successful_snapshot(self):
        self.assertTrue(all_sources_failed([{"status": "error", "accepted": 0}]))
        self.assertTrue(all_sources_failed([{"status": "empty", "failed": 2, "accepted": 0, "scanned": 0}]))
        self.assertFalse(all_sources_failed([{"status": "empty", "failed": 0, "accepted": 0, "scanned": 1}]))
        self.assertFalse(all_sources_failed([]))

    def test_approved_sources_are_present_without_auto_approving_p2(self):
        approved = json.loads((ROOT / "config/listed_innovation_companies.json").read_text())
        slugs = {row["companySlug"] for row in approved["companies"]}
        registry = {spec.slug: spec for spec in load_registry()}
        self.assertEqual(len(slugs), 40)
        self.assertTrue(slugs <= set(registry))

    def test_receipt_does_not_turn_config_or_failed_fetch_into_coverage(self):
        receipt = listed_source_receipt([
            {"companySlug": "a", "status": "error", "accepted": 0},
            {"companySlug": "b", "status": "ok", "accepted": 2},
            {"companySlug": "unapproved", "status": "ok", "accepted": 5},
        ], {"a", "b", "c"}, generated_at="2026-10-01T00:00:00Z", snapshot_published=False)
        self.assertEqual(receipt["approvedCompanyCount"], 3)
        self.assertEqual(receipt["attemptedCompanyCount"], 2)
        self.assertEqual(receipt["companiesWithNewArticles"], 1)
        self.assertFalse(receipt["snapshotPublished"])
        self.assertEqual(receipt["sources"][0]["status"], "error")


if __name__ == "__main__":
    unittest.main()
