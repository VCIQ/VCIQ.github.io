"""Regressions for AMD/TSMC publication metadata and Unitree's official API."""

from datetime import UTC, datetime, timedelta
import unittest

from tools import crawl_official_companies as c


class P1RoundThreeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs = {spec.slug: spec for spec in c.load_registry()}

    def test_bare_copyright_year_does_not_conflict_with_real_detail_date(self):
        spec = self.specs["amd"]
        url = "https://ir.amd.com/news-events/press-releases/detail/999/example"
        body = (
            '<h1>AMD launches a new AI accelerator</h1>'
            '<time datetime="2026-09-28T16:05:00">September 28, 2026</time>'
            '<footer><time datetime="2026">2026</time> AMD</footer>'
        )
        article = c._article_from_page(spec, url, body)
        self.assertIsNotNone(article)
        self.assertEqual(article["publishedAt"], "2026-09-28")

    def test_epoch_cms_placeholders_are_ignored_only_with_real_detail_date(self):
        spec = self.specs["tsmc"]
        url = "https://pr.tsmc.com/english/news/9999"
        body = (
            '<title>TSMC September 2026 Technology Update</title>'
            '<script type="application/ld+json">'
            '{"dateCreated":"1969-12-31T08:00:00+08:00",'
            '"datePublished":"1970-01-01T08:00:00+08:00"}'
            '</script>'
            '<time datetime="2026-09-10T12:00:00Z">2026/09/10</time>'
        )
        article = c._article_from_page(spec, url, body)
        self.assertIsNotNone(article)
        self.assertEqual(article["publishedAt"], "2026-09-10")

        counts = {}
        placeholder_only = (
            '<title>TSMC September 2026 Technology Update</title>'
            '<script type="application/ld+json">'
            '{"datePublished":"1970-01-01T08:00:00+08:00"}'
            '</script>'
        )
        evidence = [{
            "title": "TSMC September 2026 Technology Update",
            "publishedAt": "2026-09-10",
            "sourceUrl": "https://pr.tsmc.com/english",
            "method": "official-index-link",
        }]
        self.assertIsNone(
            c._article_from_page(
                spec, url, placeholder_only, counts, index_evidence=evidence
            )
        )
        self.assertEqual(
            counts, {"conflicting-or-invalid-detail-publication-date": 1}
        )

    def test_real_distinct_detail_dates_still_fail_closed(self):
        spec = self.specs["amd"]
        url = "https://ir.amd.com/news-events/press-releases/detail/998/example"
        body = (
            '<h1>AMD launches a new AI accelerator</h1>'
            '<time datetime="2026-09-28T16:05:00">September 28, 2026</time>'
            '<time datetime="2026-09-27T16:05:00">September 27, 2026</time>'
        )
        counts = {}
        self.assertIsNone(c._article_from_page(spec, url, body, counts))
        self.assertEqual(
            counts, {"conflicting-or-invalid-detail-publication-date": 1}
        )

    def test_unitree_api_payload_requires_exact_page_id_and_official_date(self):
        spec = self.specs["unitree"]
        url = "https://www.unitree.com/news/44"
        payload = {
            "code": 100,
            "data": {
                "id": "44",
                "article": {
                    "title": "Welcoming Myanmar President Min Aung Hlaing to Unitree",
                    "description": "Unitree shared its latest robot products and technology.",
                    "publishTime": "2026-08-05 17:45:48",
                },
            },
        }
        article = c._unitree_article_from_payload(spec, url, payload)
        self.assertIsNotNone(article)
        self.assertEqual(article["publishedAt"], "2026-08-05")
        self.assertEqual(
            article["publicationDateEvidence"]["method"], "official-api"
        )
        self.assertIn("id=44", article["publicationDateEvidence"]["sourceUrl"])

        wrong = dict(payload)
        wrong["data"] = dict(payload["data"], id="45")
        counts = {}
        self.assertIsNone(c._unitree_article_from_payload(spec, url, wrong, counts))
        self.assertEqual(counts, {"unitree-api-id-mismatch": 1})

        failed = dict(payload, code=500)
        counts = {}
        self.assertIsNone(c._unitree_article_from_payload(spec, url, failed, counts))
        self.assertEqual(counts, {"unitree-api-status": 1})

    def test_unitree_future_or_old_dates_are_not_admitted(self):
        spec = self.specs["unitree"]
        url = "https://www.unitree.com/news/44"
        base = {
            "code": 100,
            "data": {
                "id": "44",
                "article": {
                    "title": "Unitree announces a new humanoid robot platform",
                    "description": "Unitree introduces its robot platform.",
                },
            },
        }
        future = (datetime.now(UTC).date() + timedelta(days=3)).isoformat()
        old = (datetime.now(UTC).date() - timedelta(days=spec.max_age_days + 10)).isoformat()
        for value in (future, old):
            payload = {**base, "data": {**base["data"], "article": {**base["data"]["article"], "publishTime": value}}}
            self.assertIsNone(c._unitree_article_from_payload(spec, url, payload))


if __name__ == "__main__":
    unittest.main()
