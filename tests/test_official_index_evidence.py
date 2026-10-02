"""Regression fixtures for exact-record publication dates and direct RSS inputs."""
import unittest
from dataclasses import replace
from datetime import datetime, UTC, timedelta
from unittest.mock import patch
from tools import crawl_official_companies as c


class OfficialIndexEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.spec = c.CompanySpec(
            slug="example", name="Example", region="美国", sector="半导体",
            homepage="https://example.com/", news_urls=("https://example.com/feed",),
            sitemap_urls=(), aliases=("Example",), entity_aliases=("Example",),
            article_url_patterns=(), require_entity_match=True, max_items=4,
            max_candidate_links=10, max_age_days=90, request_timeout=2,
        )
        self.day = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
        self.url = "https://example.com/news/new-chip"
        self.title = "Example launches a new chip"
        self.detail = f"<h1>{self.title}</h1>"

    def rss(self, date_tag="pubDate", date=None, href=None):
        return (f"<rss><channel><item><title>{self.title}</title>"
                f"<link>{href or self.url}</link><{date_tag}>{date or self.day}</{date_tag}>"
                "</item></channel></rss>")

    def test_configured_rss_is_parsed_and_detail_is_fetched(self):
        def fetch(url, *_args, **_kwargs):
            return self.rss() if url.endswith("/feed") else self.detail if url == self.url else "<html/>"
        with patch.object(c, "fetch_text", side_effect=fetch) as call, \
             patch.object(c, "_discover_sitemap_urls", return_value=([], 0, 0)), \
             patch.object(c, "_search_official_urls", return_value=[]):
            articles, status = c.crawl_company(self.spec, "test")
        self.assertEqual(status["accepted"], 1)
        self.assertIn(self.url, [args.args[0] for args in call.call_args_list])
        self.assertEqual(articles[0]["publicationDateEvidence"]["method"], "official-feed")
        self.assertEqual(articles[0]["publishedAt"], self.day)

    def test_feed_updated_future_and_foreign_domain_are_not_publication_evidence(self):
        tomorrow = (datetime.now(UTC).date() + timedelta(days=3)).isoformat()
        for body in [self.rss("updated"), self.rss(date=tomorrow), self.rss(href="https://other.example/news/a")]:
            self.assertEqual(c._index_publication_evidence(self.spec.news_urls[0], body, self.spec), {})

    def test_anchor_record_needs_exact_detail_title(self):
        body = f'<a href="{self.url}">{self.title} {self.day}</a>'
        evidence = c._index_publication_evidence(self.spec.homepage, body, self.spec)[self.url]
        article = c._article_from_page(self.spec, self.url, self.detail, index_evidence=evidence)
        self.assertEqual(article["publishedAt"], self.day)
        self.assertEqual(article["publicationDateEvidence"]["sourceUrl"], c.normalize_url(self.spec.homepage))
        self.assertIsNone(c._article_from_page(self.spec, self.url, "<h1>Example releases a different chip</h1>", index_evidence=evidence))
        self.assertIsNone(c._article_from_page(self.spec, self.url, self.detail))

    def test_conflicting_dates_are_rejected_even_for_the_same_title(self):
        yesterday = (datetime.now(UTC).date() - timedelta(days=2)).isoformat()
        body = f'<a href="{self.url}">{self.title} {self.day}</a><a href="{self.url}">{self.title} {yesterday}</a>'
        evidence = c._index_publication_evidence(self.spec.homepage, body, self.spec)[self.url]
        self.assertIsNone(c._matched_publication_evidence(self.title, evidence))
        self.assertIsNone(c._article_from_page(self.spec, self.url, self.detail, index_evidence=evidence))

    def test_detail_date_wins_and_old_evidence_is_not_refreshed(self):
        old_day = (datetime.now(UTC).date() - timedelta(days=200)).isoformat()
        evidence = c._index_publication_evidence(self.spec.homepage, self.rss(), self.spec)[self.url]
        old_detail = f'<meta name="date" content="{old_day}">{self.detail}'
        self.assertIsNone(c._article_from_page(self.spec, self.url, old_detail, index_evidence=evidence))

    def test_future_and_conflicting_detail_dates_cannot_use_index_fallback(self):
        evidence = c._index_publication_evidence(self.spec.homepage, self.rss(), self.spec)[self.url]
        for metadata in [
            '<meta property="article:published_time" content="2099-01-01">',
            '<script type="application/ld+json">{"datePublished":"2099-01-01"}</script>',
            f'<meta name="date" content="{self.day}"><meta property="article:published_time" content="2020-01-01">',
        ]:
            self.assertIsNone(c._article_from_page(self.spec, self.url, metadata + self.detail, index_evidence=evidence))

    def test_reviewed_title_suffix_is_not_entity_evidence(self):
        spec = replace(self.spec, title_suffixes=("-ExampleSite",))
        evidence = c._index_publication_evidence(spec.homepage, self.rss(), spec)[self.url]
        article = c._article_from_page(spec, self.url, f'<title>{self.title}-ExampleSite</title>', index_evidence=evidence)
        self.assertEqual(article["title"], self.title)
        other = '<title>Other firm launches a new system-ExampleSite</title>'
        self.assertIsNone(c._article_from_page(spec, self.url, other, index_evidence=evidence))

    def test_evidence_host_rejects_credentials_and_non_http_schemes(self):
        for url in ['ftp://example.com/news/a', 'https://x:y@example.com/news/a']:
            self.assertFalse(c._host_allowed(url, self.spec.allowed_hosts))

    def test_exact_about_news_pattern_does_not_admit_about_or_attachments(self):
        patterns = (r"^https://example\.com/about/news/[0-9]+\.html$",)
        self.assertGreaterEqual(c._candidate_score("https://example.com/about/news/123.html", "", patterns), 4)
        for url in ["https://example.com/about/team", "https://example.com/about/news/f.mp4", "https://example.com/news/report.pdf", "ftp://example.com/news/a"]:
            self.assertLess(c._candidate_score(url, "news", patterns), 4)
        self.assertLess(c._candidate_score("https://example.com/about/news/123.html", "", ("/about/news/",)), 4)
        self.assertLess(c._candidate_score("https://example.com/careers/news/123.html", "news", (r"^https://example\.com/careers/news/[0-9]+\.html$",)), 4)

    def test_index_title_cannot_replace_missing_detail(self):
        evidence = c._index_publication_evidence(self.spec.homepage, self.rss(), self.spec)[self.url]
        self.assertIsNone(c._article_from_page(self.spec, self.url, "<title>Example</title>", index_evidence=evidence))

    def test_atom_published_not_updated_and_namespace_supported(self):
        body = f'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>{self.title}</title><link href="{self.url}"/><published>{self.day}T01:00:00Z</published><updated>2099-01-01T00:00:00Z</updated></entry></feed>'
        evidence = c._index_publication_evidence(self.spec.news_urls[0], body, self.spec)
        self.assertEqual(evidence[self.url][0]["publishedAt"], self.day)


if __name__ == "__main__":
    unittest.main()
