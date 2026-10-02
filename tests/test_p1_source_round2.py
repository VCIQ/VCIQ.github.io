"""Offline regressions for source paths observed in the official indexes.

These fixtures validate admission mechanics, not live collection or publication.
"""
import json
import re
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from tools import crawl_official_companies as c


class P1RoundTwoSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs = {spec.slug: spec for spec in c.load_registry()}

    def test_aws_observed_detail_is_not_an_about_page(self):
        spec = self.specs["amazon"]
        url = "https://aws.amazon.com/about-aws/whats-new/2026/10/aws-well-architected-agent/"
        self.assertLess(c._candidate_score(url, "", ()), 4)
        self.assertGreaterEqual(c._candidate_score(url, "", spec.article_url_patterns), 4)

    def test_aws_exception_does_not_admit_general_about_or_attachments(self):
        patterns = self.specs["amazon"].article_url_patterns
        for path in ("about-aws/", "about-aws/whats-new/recent/",
                     "about-aws/whats-new/2026/13/invalid-month/",
                     "about-aws/whats-new/2026/10/report.pdf",
                     "about-aws/whats-new/2026/10/private/more"):
            with self.subTest(path=path):
                self.assertLess(c._candidate_score("https://aws.amazon.com/" + path, "", patterns), 4)

    def test_aws_feed_date_still_requires_matching_detail_evidence(self):
        spec = self.specs["amazon"]
        day = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
        url = "https://aws.amazon.com/about-aws/whats-new/2026/10/test-agent"
        title = "AWS launches a test agent"
        feed = f"<rss><channel><item><link>{url}</link><title>{title}</title><pubDate>{day}</pubDate></item></channel></rss>"
        rows = c._index_publication_evidence(spec.news_urls[1], feed, spec)[url]
        self.assertIsNone(c._article_from_page(spec, url, "<title>Amazon</title>", index_evidence=rows))
        article = c._article_from_page(spec, url, f"<h1>{title}</h1>", index_evidence=rows)
        self.assertEqual(article["publishedAt"], day)
        self.assertEqual(article["publicationDateEvidence"]["method"], "official-feed")

    def test_alibaba_press_release_link_is_discovered_without_news_slug(self):
        spec = self.specs["alibaba"]
        url = "https://www.alibabagroup.com/en-US/document-2041385426245124096"
        body = '<a href="/en-US/document-2041385426245124096">Alibaba Group technology partnership</a>'
        old_spec = replace(spec, article_url_patterns=())
        self.assertEqual(c.discover_candidate_urls(spec.news_urls[0], body, old_spec.allowed_hosts, 10)[0], [])
        links, _ = c.discover_candidate_urls(spec.news_urls[0], body, spec.allowed_hosts, 10, spec.article_url_patterns)
        self.assertEqual(links, [url])
        self.assertEqual(spec.news_urls, ("https://www.alibabagroup.com/en-US/news-press-releases",))

    def test_alibaba_pattern_does_not_widen_existing_resource_discovery(self):
        spec = self.specs["alibaba"]
        body = ('<a href="https://unrelated.example/en-US/document-123">news</a>'
                '<a href="/en-US/document-123.pdf">Read</a>'
                '<a href="/en-US/document-not-numeric">Read</a>'
                '<a href="/en-US/media-contacts">Read</a>')
        links, _ = c.discover_candidate_urls(spec.news_urls[0], body, spec.allowed_hosts, 10, spec.article_url_patterns)
        # The legacy generic /media discovery may still return a resources
        # page. The new exact pattern must not add any candidates to it;
        # later detail/date gates remain responsible for publication.
        baseline, _ = c.discover_candidate_urls(spec.news_urls[0], body, spec.allowed_hosts, 10, ())
        self.assertEqual(links, baseline)
        self.assertEqual(links, ["https://www.alibabagroup.com/en-US/media-contacts"])
        for path in ("document-123.pdf", "document-not-numeric", "media-contacts"):
            url = "https://www.alibabagroup.com/en-US/" + path
            self.assertFalse(any(re.fullmatch(pattern, url) for pattern in spec.article_url_patterns))

    def test_alibaba_detail_without_date_is_still_rejected(self):
        spec = self.specs["alibaba"]
        counts = {}
        article = c._article_from_page(spec, "https://www.alibabagroup.com/en-US/document-123", "<h1>Alibaba launches a test platform</h1>", counts)
        self.assertIsNone(article)
        self.assertEqual(counts, {"missing-or-invalid-publication-date": 1})

    def test_p1_identity_and_collection_budgets_stay_fixed(self):
        approval = json.loads(c.LISTED_INNOVATION_PATH.read_text(encoding="utf-8"))
        slugs = {row["companySlug"] for row in approval["companies"]}
        self.assertEqual(len(slugs), 40)
        self.assertTrue({"amazon", "alibaba"} <= slugs)
        for slug in ("amazon", "alibaba"):
            spec = self.specs[slug]
            self.assertEqual((spec.max_items, spec.max_candidate_links, spec.max_age_days), (4, 10, 90))
            self.assertTrue(spec.require_entity_match)


if __name__ == "__main__":
    unittest.main()
