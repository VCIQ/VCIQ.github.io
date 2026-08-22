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
        MODULE._RESEARCH_QUERY_MAP = {}
        MODULE._RESEARCH_TASK_MAP = {}
        MODULE._RESEARCH_QUEUE_STATS = {}
        MODULE._RESEARCH_ATTEMPTS = []
        MODULE._RESEARCH_DATE = ""
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
        self.assertEqual(MODULE._RESEARCH_ATTEMPTS, [])

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
        self.assertEqual(MODULE._RESEARCH_ATTEMPTS, [])

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

    def test_scheduled_research_records_only_identity_gated_new_direct_urls(self):
        old = {
            "title": "Sam Altman 旧访谈",
            "date": "2026-08-10",
            "type": "interview",
            "url": "https://www.youtube.com/watch?v=existing",
            "source": "YouTube · Existing",
        }
        new = {
            "title": "Sam Altman 世界模型完整访谈",
            "date": "2026-08-21",
            "type": "interview",
            "url": "https://www.bilibili.com/video/BV1new",
            "source": "Bilibili · 新访谈",
        }
        previous = {
            "materials": [old],
            "summary": "",
            "background": "",
            "role": "",
            "organizations": [],
            "products": [],
            "works": [],
            "books": [],
            "concepts": [],
        }
        MODULE._RESEARCH_QUERY_MAP = {"sam-altman": ["Sam Altman 世界模型 完整访谈"]}
        MODULE._RESEARCH_TASK_MAP = {
            "sam-altman": {
                "taskId": "person-research-world-model",
                "taskType": "viewpoint_verification",
            }
        }
        MODULE._RESEARCH_DATE = "2026-08-22"
        with patch.object(MODULE.core, "fetch_wikipedia", return_value=None), patch.object(
            MODULE.core, "fetch_wikidata", return_value=None
        ), patch.object(
            MODULE, "discover_person_video_materials", return_value=[old, new]
        ) as direct, patch.object(
            MODULE, "discover_embedded_wechat_video_materials", return_value=[]
        ):
            MODULE.enrich_candidate(self.candidate, previous, [], offline=False)

        discovery_candidate = direct.call_args.args[0]
        self.assertEqual(
            discovery_candidate["override"]["videoQueries"],
            ["Sam Altman 世界模型 完整访谈"],
        )
        self.assertEqual(len(MODULE._RESEARCH_ATTEMPTS), 1)
        attempt = MODULE._RESEARCH_ATTEMPTS[0]
        self.assertEqual(attempt["taskId"], "person-research-world-model")
        self.assertEqual(attempt["researchDate"], "2026-08-22")
        self.assertEqual(attempt["query"], "Sam Altman 世界模型 完整访谈")
        self.assertEqual(attempt["acceptedEvidenceCount"], 2)
        self.assertEqual(attempt["newEvidenceCount"], 1)
        by_platform = {row["source"]: row for row in attempt["platforms"]}
        self.assertEqual(by_platform["YouTube"]["acceptedEvidenceCount"], 1)
        self.assertEqual(by_platform["YouTube"]["newEvidenceCount"], 0)
        self.assertEqual(by_platform["Bilibili"]["acceptedEvidenceCount"], 1)
        self.assertEqual(by_platform["Bilibili"]["newEvidenceCount"], 1)

    def test_curated_video_query_precedence_is_reflected_in_recorded_attempt(self):
        curated = {**self.candidate, "override": {**self.candidate["override"], "videoQueries": ["Sam Altman curated query"]}}
        MODULE._RESEARCH_QUERY_MAP = {"sam-altman": ["scheduled query"]}
        MODULE._RESEARCH_TASK_MAP = {
            "sam-altman": {"taskId": "task", "taskType": "first_party_evidence"}
        }
        MODULE._RESEARCH_DATE = "2026-08-22"
        with patch.object(MODULE.core, "fetch_wikipedia", return_value=None), patch.object(
            MODULE.core, "fetch_wikidata", return_value=None
        ), patch.object(MODULE, "discover_person_video_materials", return_value=[]), patch.object(
            MODULE, "discover_embedded_wechat_video_materials", return_value=[]
        ):
            MODULE.enrich_candidate(curated, None, [], offline=False)
        self.assertEqual(MODULE._RESEARCH_ATTEMPTS[0]["query"], "Sam Altman curated query")


if __name__ == "__main__":
    unittest.main()
