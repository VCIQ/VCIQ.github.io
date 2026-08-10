from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tools import expand_tracking_entities as expander


def _fake_fetch(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    host = parsed.netloc

    if host.endswith("wikipedia.org") and query.get("action") == ["opensearch"]:
        term = query["search"][0]
        return json.dumps([term, [f"{term}条目"], [""], [""]])
    if host.endswith("wikipedia.org") and query.get("list") == ["search"]:
        return json.dumps(
            {
                "query": {
                    "search": [
                        {"title": "灵巧手"},
                        {"title": "宇树科技"},
                        {"title": "Figure AI"},
                    ]
                }
            }
        )
    if host == "news.google.com":
        return "<rss><channel><title>feed</title><item><title>灵巧手</title></item></channel></rss>"
    if host == "suggestion.baidu.com":
        return 'window.baidu.sug({q:"seed",p:false,s:["人形机器人 灵巧手","人形机器人 触觉传感器"]});'
    if host == "suggestqueries.google.com":
        return json.dumps(["seed", ["embodied intelligence", "humanoid actuator"]])
    if host == "api.openalex.org":
        return json.dumps(
            {
                "results": [
                    {
                        "related_concepts": [
                            {"display_name": "Robot learning", "score": 0.7},
                            {"display_name": "noise", "score": 0.1},
                        ]
                    }
                ]
            }
        )
    if host == "www.wikidata.org" and query.get("action") == ["wbsearchentities"]:
        term = query["search"][0]
        if term == "宇树科技":
            return json.dumps({"search": [{"id": "Q100"}]})
        if term == "Figure AI":
            return json.dumps({"search": [{"id": "Q200"}]})
        return json.dumps({"search": []})
    if host == "www.wikidata.org" and query.get("action") == ["wbgetentities"]:
        entity = query["ids"][0]
        if entity == "Q100":
            claims = {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q4830453"}}
                        }
                    }
                ],
                "P856": [
                    {"mainsnak": {"datavalue": {"value": "https://www.unitree.com/"}}}
                ],
                "P17": [
                    {"mainsnak": {"datavalue": {"value": {"id": "Q148"}}}}
                ],
            }
            return json.dumps({"entities": {"Q100": {"claims": claims}}})
        if entity == "Q200":
            claims = {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q4830453"}}
                        }
                    }
                ],
                "P17": [
                    {"mainsnak": {"datavalue": {"value": {"id": "Q30"}}}}
                ],
            }
            return json.dumps({"entities": {"Q200": {"claims": claims}}})
    return ""


def _diverse_fetch(url: str) -> str:
    """Every seed resolves to its own unrelated morelike titles, so no
    candidate is ever confirmed by a second seed (score stays at 2.0)."""

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    host = parsed.netloc
    if host.endswith("wikipedia.org") and query.get("action") == ["opensearch"]:
        term = query["search"][0]
        return json.dumps([term, [f"{term}主题"], [""], [""]])
    if host.endswith("wikipedia.org") and query.get("list") == ["search"]:
        base = query["srsearch"][0].replace("morelike:", "")
        return json.dumps(
            {
                "query": {
                    "search": [
                        {"title": f"{base}关联技术甲"},
                        {"title": f"{base}关联技术乙"},
                    ]
                }
            }
        )
    if host == "www.wikidata.org" and query.get("action") == ["wbsearchentities"]:
        return json.dumps({"search": []})
    return ""


class ExpandTrackingEntitiesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.config_path = base / "user_tracking.json"
        self.ledger_path = base / "tracking_auto_discovery.json"
        self.articles_path = base / "articles.json"
        self.capture_path = base / "tracking_capture_inbox.json"
        self.intents_path = base / "tracking_intents.json"
        self._original_config = expander.CONFIG_PATH
        self._original_ledger = expander.LEDGER_PATH
        self._original_articles = expander.ARTICLES_PATH
        self._original_capture = expander.MANUAL_CAPTURE_PATH
        self._original_intents = expander.MANUAL_INTENTS_PATH
        self._original_runtime = expander.MANUAL_RUNTIME_PATH
        expander.CONFIG_PATH = self.config_path
        expander.LEDGER_PATH = self.ledger_path
        expander.ARTICLES_PATH = self.articles_path
        expander.MANUAL_CAPTURE_PATH = self.capture_path
        expander.MANUAL_INTENTS_PATH = self.intents_path
        expander.MANUAL_RUNTIME_PATH = self.config_path

    def tearDown(self) -> None:
        expander.CONFIG_PATH = self._original_config
        expander.LEDGER_PATH = self._original_ledger
        expander.ARTICLES_PATH = self._original_articles
        expander.MANUAL_CAPTURE_PATH = self._original_capture
        expander.MANUAL_INTENTS_PATH = self._original_intents
        expander.MANUAL_RUNTIME_PATH = self._original_runtime
        self.tmp.cleanup()

    def _write_config(self, config: dict) -> None:
        self.config_path.write_text(
            json.dumps(config, ensure_ascii=False), encoding="utf-8"
        )

    def _read_config(self) -> dict:
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def _read_ledger(self) -> dict:
        return json.loads(self.ledger_path.read_text(encoding="utf-8"))

    def _base_config(self, **track_overrides) -> dict:
        track = {
            "slug": "robotics",
            "name": "人形机器人",
            "enabled": True,
            "custom": False,
            "keywords": ["人形机器人整机"],
            "people": [],
            "sampleCompanies": [],
        }
        track.update(track_overrides)
        return {
            "schemaVersion": 1,
            "tracks": [track],
            "listedCompanies": [],
            "sources": [],
        }

    def test_symbolic_technology_validation_preserves_identity(self) -> None:
        values = ["C", "C++", "C#", ".NET", "NET", "A/B", "AB"]
        self.assertEqual(
            [expander.validate_keyword(value) for value in values], values
        )
        self.assertEqual(expander.clean_candidate(".NET"), ".NET")

    def test_expands_keywords_companies_and_sources_from_public_web(self) -> None:
        # v2: the track NAME is no longer fed to Wikipedia, so cross-seed
        # confirmation comes from two concrete keyword seeds.
        self._write_config(
            self._base_config(keywords=["人形机器人整机", "双足机器人"])
        )
        rc = expander.run(["--only-track", "robotics"], fetch_text=_fake_fetch)
        self.assertEqual(rc, 0)

        config = self._read_config()
        track = config["tracks"][0]
        self.assertIn("灵巧手", track["keywords"])
        self.assertIn("宇树科技", track["sampleCompanies"])
        sources = config["sources"]
        self.assertTrue(
            any(source["url"] == "https://www.unitree.com/" for source in sources)
        )
        auto_source = next(
            source for source in sources if source["url"] == "https://www.unitree.com/"
        )
        self.assertEqual(auto_source["region"], "中国")
        self.assertEqual(auto_source["sourceCategory"], "company")
        self.assertEqual(auto_source["sector"], "人形机器人")

        ledger = self._read_ledger()
        kinds = {(row["kind"], row["value"]) for row in ledger["added"]}
        self.assertIn(("keywords", "灵巧手"), kinds)
        self.assertIn(("sampleCompanies", "宇树科技"), kinds)
        self.assertIn(("sources", "https://www.unitree.com/"), kinds)

    def test_seeds_keywords_for_brand_new_track(self) -> None:
        self._write_config(
            self._base_config(slug="embodied", name="具身智能", custom=True, keywords=[])
        )
        rc = expander.run(["--seed-new-only"], fetch_text=_fake_fetch)
        self.assertEqual(rc, 0)
        track = self._read_config()["tracks"][0]
        self.assertTrue(track["keywords"], "seeding must import keywords directly")
        # Seeding only fills the keyword area; other kinds stay untouched.
        self.assertEqual(track["people"], [])
        self.assertEqual(track["sampleCompanies"], [])

    def test_seed_new_only_skips_tracks_with_keywords(self) -> None:
        self._write_config(self._base_config())
        calls: list[str] = []

        def counting_fetch(url: str) -> str:
            calls.append(url)
            return _fake_fetch(url)

        rc = expander.run(["--seed-new-only"], fetch_text=counting_fetch)
        self.assertEqual(rc, 0)
        self.assertEqual(calls, [], "no network use when nothing needs seeding")
        self.assertEqual(self._read_config()["tracks"][0]["keywords"], ["人形机器人整机"])

    def test_removed_entries_become_tombstones_and_never_return(self) -> None:
        self._write_config(self._base_config())
        self.ledger_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "updatedAt": "",
                    "tracks": {},
                    "added": [
                        {
                            "track": "robotics",
                            "kind": "keywords",
                            "value": "灵巧手",
                            "addedAt": "2026-07-01T00:00:00+00:00",
                            "evidence": ["wikipedia-morelike"],
                        }
                    ],
                    "removed": [],
                }
            ),
            encoding="utf-8",
        )
        rc = expander.run(["--only-track", "robotics"], fetch_text=_fake_fetch)
        self.assertEqual(rc, 0)
        ledger = self._read_ledger()
        removed = {(row["kind"], row["value"]) for row in ledger["removed"]}
        self.assertIn(("keywords", "灵巧手"), removed)
        track = self._read_config()["tracks"][0]
        self.assertNotIn("灵巧手", track["keywords"])

    def test_corpus_mining_promotes_professional_entities(self) -> None:
        """The site's own crawled articles are the primary supply: recurring
        companies, people, title terms and productive publisher domains for a
        track become config candidates without relying on encyclopedias."""

        self._write_config(
            self._base_config(slug="semiconductor", name="半导体", keywords=["HBM"])
        )
        article = {
            "trackSlugs": ["semiconductor"],
            "title": "中芯国际宣布 CoWoS-L 先进封装产能翻倍，HBM4 需求旺盛",
            "region": "中国",
            "company": "中芯国际",
            "mentionedCompanies": ["中芯国际"],
            "mentionedPeople": ["梁孟松"],
            "source": {"name": "科创板日报", "url": "https://www.chinastarmarket.cn/a/1"},
        }
        articles = []
        for index in range(4):
            row = json.loads(json.dumps(article))
            row["source"]["url"] = f"https://www.chinastarmarket.cn/a/{index}"
            # Terms must recur across at least two distinct outlets.
            row["source"]["name"] = "科创板日报" if index % 2 == 0 else "集微网"
            articles.append(row)
        self.articles_path.write_text(
            json.dumps({"articles": articles}, ensure_ascii=False),
            encoding="utf-8",
        )

        def corpus_fetch(url: str) -> str:
            if "news.google.com" in url:
                return (
                    "<rss><channel><title>feed</title>"
                    "<item><title>中芯国际扩产 CoWoS-L 封装线</title></item>"
                    "</channel></rss>"
                )
            if "wbsearchentities" in url:
                return json.dumps({"search": []})
            return ""

        rc = expander.run(["--only-track", "semiconductor"], fetch_text=corpus_fetch)
        self.assertEqual(rc, 0)
        config = self._read_config()
        track = config["tracks"][0]
        self.assertIn("中芯国际", track["sampleCompanies"])
        self.assertIn("梁孟松", track["people"])
        self.assertTrue(
            any("CoWoS" in keyword for keyword in track["keywords"]),
            f"expected CoWoS term in {track['keywords']}",
        )
        media = [
            source
            for source in config["sources"]
            if source["url"] == "https://chinastarmarket.cn/" or
               source["url"] == "https://www.chinastarmarket.cn/"
        ]
        self.assertTrue(media, "productive publisher domain must become a source")
        self.assertEqual(media[0]["sourceCategory"], "media")

    def test_reference_only_relations_do_not_pollute_existing_tracks(self) -> None:
        """Existing tracks must not import encyclopedia-only relations when
        no accepted article or current news confirms them."""

        self._write_config(
            self._base_config(
                slug="semiconductor",
                name="半导体",
                keywords=["GPU", "先进封装"],
            )
        )
        rc = expander.run(
            ["--only-track", "semiconductor"], fetch_text=_diverse_fetch
        )
        self.assertEqual(rc, 0)
        track = self._read_config()["tracks"][0]
        added = [
            keyword for keyword in track["keywords"] if "关联技术" in keyword
        ]
        self.assertEqual(added, [])

    def test_prunes_reference_only_keywords_and_role_fragments(self) -> None:
        config = self._base_config(
            keywords=["人形机器人整机", "植物分类学"],
            people=["Alice Chen", "Company Development", "作为自动驾"],
        )
        ledger = expander.empty_ledger()
        ledger["added"] = [
            {"track": "robotics", "kind": "keywords", "value": "植物分类学", "evidence": ["wikipedia-morelike"]},
            {"track": "robotics", "kind": "people", "value": "Company Development", "evidence": ["sample-company-core-team"]},
            {"track": "robotics", "kind": "people", "value": "作为自动驾", "evidence": ["sample-company-core-team"]},
        ]
        pruned = expander.prune_low_quality_auto_entries(ledger, config)
        self.assertEqual(len(pruned), 3)
        track = config["tracks"][0]
        self.assertEqual(track["keywords"], ["人形机器人整机"])
        self.assertEqual(track["people"], ["Alice Chen"])
        self.assertEqual(ledger["added"], [])

    def test_ignored_recommendations_block_candidates(self) -> None:
        self._write_config(
            self._base_config(
                ignoredRecommendations={"companies": ["宇树科技"], "keywords": []}
            )
        )
        rc = expander.run(["--only-track", "robotics"], fetch_text=_fake_fetch)
        self.assertEqual(rc, 0)
        track = self._read_config()["tracks"][0]
        self.assertNotIn("宇树科技", track["sampleCompanies"])

    def test_manual_history_has_protected_seed_budget(self) -> None:
        profile = {
            "tracks": {
                "robotics": {
                    "seedTerms": [
                        {"value": "人工固定技术", "score": 5},
                        {"value": "人工固定公司", "score": 4},
                    ]
                }
            }
        }
        track = self._base_config(
            keywords=[f"自动词{index}" for index in range(10)],
            sampleCompanies=[f"自动公司{index}" for index in range(6)],
        )["tracks"][0]
        seeds = expander.track_seed_terms(track, False, profile)

        self.assertEqual(seeds[:4], ["人形机器人", "自动词0", "自动词1", "自动词2"])
        # Noisy legacy history is capped at one slot; v2 pinned edges can use
        # two without displacing the protected track/technology core.
        self.assertIn("人工固定技术", seeds)
        self.assertNotIn("人工固定公司", seeds)
        self.assertLessEqual(len(seeds), 8)

    def test_pinned_runtime_duplicates_backfill_the_eight_slot_plan(self) -> None:
        profile = {
            "tracks": {
                "robotics": {
                    "seedTerms": [
                        {"value": "K0", "kind": "keywords", "score": 5, "pinned": True},
                        {"value": "K1", "kind": "keywords", "score": 5, "pinned": True},
                    ]
                }
            }
        }
        track = self._base_config(
            name="Track",
            keywords=[f"K{index}" for index in range(6)],
            sampleCompanies=["Co"],
            people=["Jane Doe"],
        )["tracks"][0]

        seeds = expander.track_seed_terms(track, False, profile)

        self.assertEqual(len(seeds), 8)
        self.assertEqual(seeds[-2:], ["Co Track", "Jane Doe Track"])
        self.assertIn("K3", seeds)
        self.assertIn("K4", seeds)

    def test_pinned_actor_runtime_duplicates_also_backfill_core_terms(self) -> None:
        profile = {
            "tracks": {
                "robotics": {
                    "seedTerms": [
                        {
                            "value": "Co",
                            "kind": "sampleCompanies",
                            "score": 5,
                            "pinned": True,
                        },
                        {
                            "value": "Jane Doe",
                            "kind": "people",
                            "score": 5,
                            "pinned": True,
                        },
                    ]
                }
            }
        }
        track = self._base_config(
            name="Track",
            keywords=[f"K{index}" for index in range(6)],
            sampleCompanies=["Co"],
            people=["Jane Doe"],
        )["tracks"][0]

        seeds = expander.track_seed_terms(track, False, profile)

        self.assertEqual(len(seeds), 8)
        self.assertEqual(seeds.count("Co Track"), 1)
        self.assertEqual(seeds.count("Jane Doe Track"), 1)
        self.assertIn("K4", seeds)

    def test_held_manual_identity_cannot_be_reactivated_by_automation(self) -> None:
        self._write_config(self._base_config(keywords=["人形机器人整机", "双足机器人"]))
        self.capture_path.write_text(
            json.dumps(
                {
                    "records": [
                        {
                            "entityType": "company",
                            "canonicalName": "宇树科技",
                            "status": "queued",
                            "trackSlugs": ["robotics"],
                            "capturedAt": "2026-08-09T00:00:00Z",
                            "reasons": ["市场竞争"],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        rc = expander.run(["--only-track", "robotics"], fetch_text=_fake_fetch)

        self.assertEqual(rc, 0)
        self.assertNotIn("宇树科技", self._read_config()["tracks"][0]["sampleCompanies"])

    def test_held_manual_source_blocks_the_entire_canonical_host(self) -> None:
        track = self._base_config()["tracks"][0]
        profile = {
            "tracks": {
                "robotics": {
                    "held": {
                        "keywords": [],
                        "people": [],
                        "sampleCompanies": [],
                        "sources": ["https://www.example.com/news/feed"],
                    }
                }
            }
        }
        blocked = expander.blocked_values(
            expander.empty_ledger(), track, "sources", profile
        )
        self.assertTrue(expander.value_is_blocked(blocked, "https://example.com/"))
        self.assertTrue(expander.value_is_blocked(blocked, "http://www.example.com/rss"))

    def test_offline_run_changes_nothing(self) -> None:
        self._write_config(self._base_config())

        def offline(url: str) -> str:
            raise OSError("offline")

        rc = expander.run(["--only-track", "robotics"], fetch_text=offline)
        self.assertEqual(rc, 0)
        track = self._read_config()["tracks"][0]
        self.assertEqual(track["keywords"], ["人形机器人整机"])
        self.assertFalse(self.ledger_path.exists())

    def test_keyword_validation_rejects_generic_and_urls(self) -> None:
        self.assertEqual(expander.validate_keyword("人工智能"), "")
        self.assertEqual(expander.validate_keyword("https://example.com"), "")
        self.assertEqual(expander.validate_keyword("what is AND query"), "")
        self.assertEqual(expander.validate_keyword("灵巧手"), "灵巧手")
        self.assertEqual(expander.validate_keyword("  Robot   learning  "), "Robot learning")


if __name__ == "__main__":
    unittest.main()
