from __future__ import annotations

import unittest

from tools import crawl_with_tracking as tracking
from tools import professional_media_sources as media


class ProfessionalMediaSourcesTest(unittest.TestCase):
    def test_registry_contains_100_unique_enabled_sources(self) -> None:
        payload = media.load_registry()
        sources = payload["sources"]
        self.assertEqual(len(sources), 100)
        self.assertEqual(len({source["id"] for source in sources}), 100)
        self.assertEqual(len({source["order"] for source in sources}), 100)
        self.assertTrue(all(source["enabled"] for source in sources))

        business_insider = next(
            source for source in sources if source["order"] == 23
        )
        self.assertEqual(business_insider["name"], "Business Insider Tech")
        self.assertEqual(business_insider["host"], "businessinsider.com")
        self.assertIn("Android Authority", business_insider["correctedFrom"])

    def test_every_media_outlet_has_an_independent_execution_source(self) -> None:
        tracks = tracking._enabled_tracks(tracking.load_tracking())
        specs = media.grouped_specs(tracks, tracking)
        enabled = media.enabled_sources()
        enabled_by_id = {source["id"]: source for source in enabled}

        self.assertEqual(len(specs), 100)
        self.assertEqual(len({spec["id"] for spec in specs}), 100)
        self.assertEqual(
            {spec["professionalMedia"][0]["id"] for spec in specs},
            set(enabled_by_id),
        )

        for spec in specs:
            self.assertEqual(spec["adapter"], "professional_media")
            self.assertEqual(spec["sourceLevel"], "媒体报道")
            self.assertTrue(spec["url"].startswith("https://www.bing.com/search?"))
            self.assertEqual(len(spec["allowedHosts"]), 1)
            self.assertEqual(len(spec["professionalMedia"]), 1)
            self.assertLessEqual(spec["maxItems"], 6)
            media_id = spec["professionalMedia"][0]["id"]
            self.assertEqual(spec["id"], f"professional-media-{media_id}")
            self.assertEqual(spec["sourceUrl"], enabled_by_id[media_id]["url"])
            self.assertEqual(spec["directRequestBudget"]["attempts"], 1)
            self.assertLessEqual(
                spec["directRequestBudget"]["candidateLimit"],
                12,
            )

    def test_original_media_name_is_preserved(self) -> None:
        row = {
            "id": "techcrunch",
            "name": "TechCrunch",
            "url": "https://techcrunch.com/",
            "host": "techcrunch.com",
            "pathPrefix": "",
            "region": "美国",
            "focus": ["初创企业", "融资"],
        }
        article = {
            "id": "example",
            "sourceId": "professional-media-techcrunch",
            "region": "全球",
            "source": {
                "name": "TechCrunch",
                "platform": "TechCrunch",
                "url": "https://techcrunch.com/2026/07/26/example/",
                "level": "媒体报道",
            },
        }
        attributed = media.attribute_article(article, [row])
        self.assertIsNotNone(attributed)
        assert attributed is not None
        self.assertEqual(attributed["source"]["name"], "TechCrunch")
        self.assertEqual(attributed["source"]["platform"], "TechCrunch")
        self.assertEqual(attributed["professionalMediaId"], "techcrunch")
        self.assertEqual(attributed["region"], "美国")

    def test_section_scoped_source_rejects_other_site_sections(self) -> None:
        row = {
            "id": "the-startup",
            "name": "The Startup",
            "url": "https://medium.com/swlh",
            "host": "medium.com",
            "pathPrefix": "/swlh",
            "region": "全球",
            "focus": ["创业"],
        }
        self.assertIsNotNone(
            media.match_media("https://medium.com/swlh/example-story", [row])
        )
        self.assertIsNone(
            media.match_media("https://medium.com/another-publication/story", [row])
        )

    def test_empty_search_falls_back_to_registered_original_site(self) -> None:
        class FakeCrawler:
            @staticmethod
            def normalize_url(value: str) -> str:
                return value.rstrip("/")

            @staticmethod
            def fetch_text(
                _url: str,
                _user_agent: str,
                timeout: int = 8,
                attempts: int = 1,
            ) -> str:
                self.assertLessEqual(timeout, 8)
                self.assertEqual(attempts, 1)
                return "<html><body>public index</body></html>"

            @staticmethod
            def parse_feed_items(_body: str, _spec: dict) -> list[dict]:
                return []

            @staticmethod
            def _status(
                source_id: str,
                name: str,
                status: str,
                scanned: int,
                accepted: int,
                *,
                failed: int = 0,
                platform: str = "",
                error: str | None = None,
            ) -> dict:
                result = {
                    "id": source_id,
                    "name": name,
                    "status": status,
                    "scanned": scanned,
                    "accepted": accepted,
                    "failed": failed,
                    "platform": platform,
                }
                if error:
                    result["error"] = error
                return result

        class FakeGeneric:
            @staticmethod
            def detect_language(_url: str, _body: str, _configured: str) -> str:
                return "en"

            @staticmethod
            def localize_keywords(terms: list[str], _language: str) -> list[str]:
                return terms

            @staticmethod
            def discover_feeds(_url: str, _body: str) -> list[str]:
                return []

            @staticmethod
            def discover_candidates(
                _url: str,
                _body: str,
                _keywords: list[str],
                limit: int,
            ) -> list[str]:
                self.assertLessEqual(limit, 12)
                return ["https://techcrunch.com/2026/07/26/example-ai-launch"]

            @staticmethod
            def parse_article(
                spec: dict,
                url: str,
                _body: str,
                _crawler: FakeCrawler,
                _keywords: list[str],
            ) -> dict:
                return {
                    "id": "example",
                    "sourceId": spec["id"],
                    "title": "Example AI launch",
                    "summary": "A dated original-domain technology report.",
                    "type": "产品发布",
                    "region": "全球",
                    "sector": spec["sector"],
                    "company": "科技产业",
                    "publishedAt": "2026-07-26",
                    "importance": 80,
                    "source": {
                        "name": spec["name"],
                        "url": url,
                        "level": "媒体报道",
                        "platform": spec["name"],
                    },
                }

        def empty_primary(spec: dict, _user_agent: str) -> tuple[list[dict], dict]:
            return [], FakeCrawler._status(
                spec["id"],
                spec["name"],
                "empty",
                0,
                0,
                platform=spec["name"],
            )

        spec = {
            "id": "professional-media-techcrunch",
            "name": "TechCrunch",
            "url": "https://www.bing.com/search?format=rss&q=site%3Atechcrunch.com",
            "sourceUrl": "https://techcrunch.com/",
            "adapter": "professional_media",
            "sector": "风险投资",
            "region": "美国",
            "sourceLevel": "媒体报道",
            "keywords": ["AI", "funding"],
            "maxItems": 2,
            "allowedHosts": ["techcrunch.com"],
            "professionalMedia": [
                {
                    "id": "techcrunch",
                    "name": "TechCrunch",
                    "url": "https://techcrunch.com/",
                    "host": "techcrunch.com",
                    "pathPrefix": "",
                    "region": "美国",
                    "focus": ["人工智能", "融资"],
                }
            ],
            "directRequestBudget": {
                "timeoutSeconds": 8,
                "attempts": 1,
                "feedLimit": 2,
                "candidateLimit": 8,
            },
        }

        articles, status = media.crawl_professional_source(
            spec,
            "test-agent",
            FakeCrawler(),
            FakeGeneric(),
            empty_primary,
        )
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["professionalMediaId"], "techcrunch")
        self.assertEqual(articles[0]["source"]["name"], "TechCrunch")
        self.assertTrue(status["attempted"])
        self.assertEqual(status["adapter"], "professional-media-v1")
        self.assertEqual(status["accepted"], 1)
        self.assertEqual(status["scanned"], 1)
        self.assertGreaterEqual(status["transportRequests"], 3)
        self.assertIn("original-site", status["strategies"])
        self.assertIn("original-articles", status["strategies"])


if __name__ == "__main__":
    unittest.main()
