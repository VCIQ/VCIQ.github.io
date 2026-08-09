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

    def test_spacex_release_allowlist_rejects_non_first_party_urls(self) -> None:
        allowed = (
            "https://ir.spacex.com/updates/releases-details/2026/SpaceX-Results/default.aspx",
            "https://ir.spacex.com/updates/releases/details/2026/SpaceX-Results/default.aspx",
        )
        for url in allowed:
            with self.subTest(url=url):
                self.assertTrue(core_official_adapters._spacex_release_url_allowed(url))

        rejected = (
            "https://example.com/updates/releases-details/2026/SpaceX-Results/default.aspx",
            "http://ir.spacex.com/updates/releases-details/2026/SpaceX-Results/default.aspx",
            "https://ir.spacex.com/updates/",
            "https://ir.spacex.com/financials/sec-filings-details/default.aspx",
        )
        for url in rejected:
            with self.subTest(url=url):
                self.assertFalse(core_official_adapters._spacex_release_url_allowed(url))

    def test_spacex_search_fallback_publishes_only_after_first_party_fetch(self) -> None:
        first_party = (
            "https://ir.spacex.com/updates/releases-details/2026/"
            "SpaceX-to-Post-Second-Quarter-2026-Results/default.aspx"
        )
        evil = (
            "https://example.com/updates/releases-details/2026/"
            "Fake-SpaceX-Release/default.aspx"
        )
        rss = f"""
        <rss><channel>
          <item><link>{first_party}</link></item>
          <item><link>{evil}</link></item>
        </channel></rss>
        """
        fetches: list[str] = []
        parsed: list[str] = []

        class Source:
            id = "spacex"
            name = "SpaceX"
            index_url = "https://ir.spacex.com/updates/"
            company = "SpaceX"
            company_slug = "spacex"
            region = "美国"
            sector = "商业航天"

        class FakeCrawler:
            MAX_NEWS_PER_SOURCE = 10

            @staticmethod
            def normalize_url(url):
                return url

            @staticmethod
            def crawl_news_source(_source, _user_agent):
                raise RuntimeError("no dated articles parsed from 0 discovered links")

            @staticmethod
            def fetch_text(url, _user_agent):
                fetches.append(url)
                if url.startswith("https://www.bing.com/search?"):
                    return rss
                if url == first_party:
                    return "<html>first-party SpaceX release</html>"
                raise AssertionError(f"unexpected fetch: {url}")

            @staticmethod
            def parse_news_article(_source, url, body):
                parsed.append(url)
                if url != first_party or "first-party" not in body:
                    return None
                return {"sourceId": "spacex", "source": {"url": url}}

            @staticmethod
            def _status(source_id, name, status, scanned, accepted, **kwargs):
                return {
                    "id": source_id,
                    "name": name,
                    "status": status,
                    "scanned": scanned,
                    "accepted": accepted,
                    **kwargs,
                }

        core_official_adapters._install_spacex_search_adapter(FakeCrawler)
        articles, status = FakeCrawler.crawl_news_source(Source(), "test-agent")
        self.assertEqual(len(articles), 1)
        self.assertEqual(parsed, [first_party])
        self.assertNotIn(evil, fetches)
        self.assertEqual(status["urlDiscovery"], "bing-site-filter")
        self.assertTrue(status["firstPartyFetched"])
        self.assertEqual(status["accepted"], 1)


if __name__ == "__main__":
    unittest.main()
