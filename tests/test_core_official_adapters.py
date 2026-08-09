from __future__ import annotations

import unittest

from tools import core_official_adapters


class CoreOfficialAdaptersTests(unittest.TestCase):
    def test_install_adds_core_companies_without_duplicates(self) -> None:
        class NewsSource:
            def __init__(
                self,
                source_id,
                name,
                index_url,
                company,
                company_slug,
                region,
                sector,
                path_prefixes,
            ):
                self.id = source_id
                self.name = name
                self.index_url = index_url
                self.company = company
                self.company_slug = company_slug
                self.region = region
                self.sector = sector
                self.path_prefixes = path_prefixes

        source_type = NewsSource

        class FakeCrawler:
            NEWS_SOURCES = (
                source_type(
                    "openai",
                    "OpenAI",
                    "",
                    "OpenAI",
                    "openai",
                    "美国",
                    "AI / AGI",
                    ("/index/",),
                ),
            )
            NewsSource = source_type

            @staticmethod
            def crawl_news_source(*_args, **_kwargs):
                return [], {}

        core_official_adapters.install(FakeCrawler)
        first_ids = [source.id for source in FakeCrawler.NEWS_SOURCES]
        self.assertIn("deepseek", first_ids)
        self.assertIn("bytedance", first_ids)
        self.assertIn("google-deepmind", first_ids)
        self.assertIn("minimax", first_ids)
        self.assertIn("zhipu-ai", first_ids)
        self.assertIn("unitree", first_ids)
        self.assertIn("spacex", first_ids)
        self.assertIn("cerebras", first_ids)
        self.assertIn("scale-ai", first_ids)
        self.assertEqual(len(first_ids), len(set(first_ids)))

        first_crawl = FakeCrawler.crawl_news_source
        core_official_adapters.install(FakeCrawler)
        second_ids = [source.id for source in FakeCrawler.NEWS_SOURCES]
        self.assertEqual(first_ids, second_ids)
        self.assertIs(first_crawl, FakeCrawler.crawl_news_source)

    def test_adapter_set_keeps_core_count_bounded(self) -> None:
        self.assertGreaterEqual(len(core_official_adapters.CORE_OFFICIAL_SOURCES), 10)
        self.assertLessEqual(len(core_official_adapters.CORE_OFFICIAL_SOURCES), 16)
        self.assertTrue(
            all(row["path_prefixes"] for row in core_official_adapters.CORE_OFFICIAL_SOURCES)
        )

    def test_current_first_party_newsroom_routes_are_explicit(self) -> None:
        sources = {
            row["id"]: row for row in core_official_adapters.CORE_OFFICIAL_SOURCES
        }
        self.assertEqual(
            sources["google-deepmind"]["index_url"],
            "https://deepmind.google/blog/",
        )
        self.assertEqual(
            sources["google-deepmind"]["path_prefixes"],
            ("/blog/",),
        )
        self.assertEqual(
            sources["spacex"]["index_url"],
            "https://ir.spacex.com/updates/",
        )
        self.assertIn(
            "/updates/releases-details/",
            sources["spacex"]["path_prefixes"],
        )
        self.assertIn(
            "/updates/releases/details/",
            sources["spacex"]["path_prefixes"],
        )

    def test_unitree_listing_parser_uses_first_party_index_metadata(self) -> None:
        body = """
        <html><body>
          <a href="/news/38">
            Kung Fu Meets Spring, Unitree SFG Robots Present Cyber Real Kung Fu
            2026-05-31 Media Coverage
          </a>
          <a href="/news/40/">
            Unitree Announces H2 Plus, an NVIDIA Isaac GR00T Reference Humanoid Robot
            for Academic Research 2026-06-01 Media Coverage
          </a>
          <a href="/products/g1">G1</a>
          <a href="https://example.com/news/999">Untrusted 2026-06-02</a>
        </body></html>
        """
        entries = core_official_adapters._parse_unitree_listing_entries(body)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["publishedAt"], "2026-06-01")
        self.assertEqual(entries[0]["url"], "https://www.unitree.com/news/40/")
        self.assertIn("H2 Plus", entries[0]["title"])
        self.assertEqual(entries[1]["publishedAt"], "2026-05-31")
        self.assertEqual(entries[1]["url"], "https://www.unitree.com/news/38")


if __name__ == "__main__":
    unittest.main()
