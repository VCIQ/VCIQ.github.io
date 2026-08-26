import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "refresh_people_profiles_with_video",
    ROOT / "tools" / "refresh_people_profiles_with_video.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class PeopleVideoEnrichmentTest(unittest.TestCase):
    def setUp(self):
        self.candidate = {
            "slug": "sam-altman",
            "name": "Sam Altman",
            "englishName": "Sam Altman",
            "aliases": ["Sam Altman"],
            "handles": ["sama"],
            "sectors": ["AI / AGI"],
            "override": {
                "roleHint": "OpenAI 首席执行官",
                "organizationHints": ["OpenAI"],
                "productHints": ["ChatGPT"],
            },
        }

    def test_tracking_identity_parser_recovers_malformed_bilingual_labels(self):
        self.assertEqual(
            MODULE.parse_tracking_identity("黄仁勋(Jensen Huang"),
            ("黄仁勋", "Jensen Huang", ""),
        )
        self.assertEqual(
            MODULE.parse_tracking_identity("克莱门特·德朗格（Clément Delangue）"),
            ("克莱门特·德朗格", "Clément Delangue", ""),
        )
        self.assertEqual(
            MODULE.parse_tracking_identity("埃隆·马斯克 @elonmusk"),
            ("埃隆·马斯克", "", "elonmusk"),
        )

    def test_candidate_collection_normalizes_identity_without_changing_public_slug(self):
        tracking = {
            "tracks": [
                {
                    "name": "AI / AGI",
                    "enabled": True,
                    "people": [
                        "黄仁勋(Jensen Huang",
                        "克莱门特·德朗格(Clément Delangue",
                    ],
                }
            ]
        }
        people, _ = MODULE.collect_candidates(tracking, {"people": [], "organizationAccounts": []})
        by_slug = {person["slug"]: person for person in people}

        jensen = by_slug["jensen-huang"]
        self.assertEqual(jensen["name"], "黄仁勋")
        self.assertEqual(jensen["englishName"], "Jensen Huang")
        self.assertIn("黄仁勋", jensen["aliases"])
        self.assertIn("Jensen Huang", jensen["aliases"])
        self.assertNotIn("黄仁勋(Jensen Huang", jensen["aliases"])

        clement = by_slug["cl-ment-delangue"]
        self.assertEqual(clement["name"], "克莱门特·德朗格")
        self.assertEqual(clement["englishName"], "Clément Delangue")
        self.assertNotIn("克莱门特·德朗格(Clément Delangue", clement["aliases"])

    def test_online_enrichment_adds_all_video_paths(self):
        youtube = {
            "title": "Sam Altman interview on AI",
            "date": "2026-07-25",
            "type": "interview",
            "url": "https://www.youtube.com/watch?v=abc1234",
            "source": "YouTube · Example Channel",
        }
        wechat = {
            "title": "Sam Altman 微信公开对话",
            "date": "2026-07-24",
            "type": "qa",
            "url": "https://channels.weixin.qq.com/a",
            "source": "微信视频号 · 测试账号",
        }
        articles = [{"title": "Sam Altman 公众号访谈"}]
        with patch.object(MODULE.core, "fetch_wikipedia", return_value=None), patch.object(
            MODULE.core, "fetch_wikidata", return_value=None
        ), patch.object(
            MODULE, "discover_person_video_materials", return_value=[youtube]
        ) as direct, patch.object(
            MODULE, "discover_embedded_wechat_video_materials", return_value=[wechat]
        ) as embedded:
            profile = MODULE.enrich_candidate(
                self.candidate, None, articles, offline=False
            )
        direct.assert_called_once_with(self.candidate)
        embedded.assert_called_once_with(self.candidate, articles)
        urls = [item["url"] for item in profile["materials"]]
        self.assertIn(youtube["url"], urls)
        self.assertIn(wechat["url"], urls)
        self.assertIn(youtube["url"], profile["sources"])
        self.assertIn(wechat["url"], profile["sources"])

    def test_offline_validation_never_calls_video_sources(self):
        with patch.object(
            MODULE,
            "discover_person_video_materials",
            side_effect=AssertionError("network discovery must be skipped"),
        ), patch.object(
            MODULE,
            "discover_embedded_wechat_video_materials",
            side_effect=AssertionError("article discovery must be skipped"),
        ):
            profile = MODULE.enrich_candidate(
                self.candidate, None, [], offline=True
            )
        self.assertEqual(profile["materials"], [])

    def test_previous_video_is_retained_when_new_discovery_returns_nothing(self):
        previous = {
            "materials": [
                {
                    "title": "Sam Altman 公开对话",
                    "date": "2026-07-20",
                    "type": "qa",
                    "url": "https://www.bilibili.com/video/BV1existing",
                    "source": "Bilibili",
                }
            ],
            "summary": "",
            "background": "",
            "role": "",
            "organizations": [],
            "products": [],
            "works": [],
            "books": [],
            "concepts": [],
        }
        with patch.object(MODULE.core, "fetch_wikipedia", return_value=None), patch.object(
            MODULE.core, "fetch_wikidata", return_value=None
        ), patch.object(
            MODULE, "discover_person_video_materials", return_value=[]
        ), patch.object(
            MODULE, "discover_embedded_wechat_video_materials", return_value=[]
        ):
            profile = MODULE.enrich_candidate(
                self.candidate, previous, [], offline=False
            )
        self.assertEqual(
            profile["materials"][0]["url"], previous["materials"][0]["url"]
        )
        self.assertEqual(
            profile["speeches"][0]["url"], previous["materials"][0]["url"]
        )


if __name__ == "__main__":
    unittest.main()
