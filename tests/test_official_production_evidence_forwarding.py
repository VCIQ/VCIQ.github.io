"""Exercise the scheduled entrypoint, not only the unwrapped parser.

Network and the terminal snapshot writer are replaced with deterministic fixtures;
the transport, category, region and tracking adapters are installed normally.
"""
from contextlib import ExitStack, redirect_stdout
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import StringIO
import unittest
from unittest.mock import patch

from tools import crawl_official_companies as official
from tools import crawl_official_with_tracking as tracking
from tools import crawl_official_with_source_categories as categories
from tools import eastmoney_transport as entrypoint


class OfficialProductionEvidenceForwardingTests(unittest.TestCase):
    def setUp(self):
        base = next(s for s in official.load_registry() if s.slug == "amazon")
        self.spec = replace(
            base, slug="fixture-p1", name="Fixture", region="加拿大",
            homepage="https://fixture.example/",
            news_urls=("https://fixture.example/feed",),
            aliases=("Fixture",), entity_aliases=("Fixture",),
            article_url_patterns=(), max_items=1,
        )
        self.url = "https://fixture.example/news/new-chip"
        self.title = "Fixture launches a new AI chip"
        self.day = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
        self.evidence = [{"title": self.title, "publishedAt": self.day,
                          "sourceUrl": self.spec.news_urls[0], "method": "official-feed"}]

    def run_production(self, assertion, *, fetch=None):
        # Restore every module patched by the real installation chain so test
        # ordering cannot leak adapters into other suites.
        with ExitStack() as stack:
            for module in (official, tracking, categories):
                stack.enter_context(patch.dict(module.__dict__, module.__dict__.copy()))
            stack.enter_context(patch.object(official, "load_registry", return_value=[self.spec]))
            stack.enter_context(patch.object(official, "_discover_sitemap_urls", return_value=([], 0, 0)))
            stack.enter_context(patch.object(official, "_search_official_urls", return_value=[]))
            if fetch is not None:
                stack.enter_context(patch.object(official, "fetch_text", new=fetch))
            writer = stack.enter_context(patch.object(official, "write_if_changed"))
            terminal = stack.enter_context(patch.object(official, "main", side_effect=assertion))
            with redirect_stdout(StringIO()):
                result = entrypoint.main()
            terminal.assert_called_once_with()
            writer.assert_not_called()
            self.assertEqual(result, 0)

    def test_positional_evidence_and_rejections_survive_every_adapter(self):
        def check():
            counts = {}
            article = official._article_from_page(
                self.spec, self.url, f"<h1>{self.title}</h1>", counts, self.evidence)
            self.assertIsNotNone(article)
            self.assertEqual(article["publishedAt"], self.day)
            self.assertEqual(article["region"], "全球")
            self.assertEqual(article["publicationDateEvidence"], self.evidence[0])
            self.assertEqual(counts, {})
            return 0
        self.run_production(check)

    def test_keyword_evidence_and_counters_are_not_dropped(self):
        def check():
            counts = {}
            article = official._article_from_page(
                self.spec, self.url, f"<h1>{self.title}</h1>",
                rejection_counts=counts, index_evidence=self.evidence)
            self.assertIsNotNone(article)
            mismatch = [{**self.evidence[0], "title": "A completely different news story"}]
            self.assertIsNone(official._article_from_page(
                self.spec, self.url, f"<h1>{self.title}</h1>",
                rejection_counts=counts, index_evidence=mismatch))
            self.assertEqual(counts, {"missing-or-invalid-publication-date": 1})
            return 0
        self.run_production(check)

    def test_legacy_three_argument_call_remains_supported(self):
        def check():
            body = f'<meta name="date" content="{self.day}"><h1>{self.title}</h1>'
            article = official._article_from_page(self.spec, self.url, body)
            self.assertEqual(article["publishedAt"], self.day)
            self.assertEqual(article["region"], "全球")
            return 0
        self.run_production(check)

    def test_future_and_conflicting_dates_remain_rejected(self):
        def check():
            future = (datetime.now(UTC).date() + timedelta(days=3)).isoformat()
            previous = (datetime.now(UTC).date() - timedelta(days=2)).isoformat()
            for dates in ((future,), (self.day, previous)):
                body = f'<h1>{self.title}</h1>' + ''.join(
                    f'<time datetime="{day}">{day}</time>' for day in dates)
                counts = {}
                self.assertIsNone(official._article_from_page(
                    self.spec, self.url, body, counts, self.evidence))
                self.assertEqual(counts, {"conflicting-or-invalid-detail-publication-date": 1})
            return 0
        self.run_production(check)

    def test_scheduled_chain_crawls_feed_and_fetches_matching_detail(self):
        requested = []
        feed = (f'<rss><channel><item><title>{self.title}</title>'
                f'<link>{self.url}</link><pubDate>{self.day}</pubDate>'
                '</item></channel></rss>')
        def fetch(url, *_args, **_kwargs):
            requested.append(url)
            return feed if url.endswith('/feed') else (
                f'<h1>{self.title}</h1>' if url == self.url else '<html/>')
        def check():
            articles, status = official.crawl_company(self.spec, "fixture-test")
            self.assertEqual((status["status"], status["accepted"], status["failed"]), ("ok", 1, 0))
            self.assertEqual(articles[0]["publicationDateEvidence"]["method"], "official-feed")
            self.assertIn(self.url, requested)
            return 0
        self.run_production(check, fetch=fetch)


if __name__ == "__main__":
    unittest.main()
