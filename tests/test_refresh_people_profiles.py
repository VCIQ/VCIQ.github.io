import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "refresh_people_profiles", ROOT / "tools" / "refresh_people_profiles.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class PeopleProfilePipelineTest(unittest.TestCase):
    def setUp(self):
        self.tracking = json.loads((ROOT / "config" / "user_tracking.json").read_text(encoding="utf-8"))
        self.overrides = json.loads((ROOT / "config" / "person_profile_overrides.json").read_text(encoding="utf-8"))

    def test_tracking_labels_parse_names_and_handles(self):
        self.assertEqual(MODULE.parse_tracking_label("埃隆·马斯克 @elonmusk"), ("埃隆·马斯克", "elonmusk"))
        self.assertEqual(MODULE.parse_tracking_label("Sam Altman"), ("Sam Altman", ""))

    def test_organization_accounts_are_not_people(self):
        # Organization filtering is a parser contract, not a requirement that
        # production tracking remain polluted with known-bad organization seeds.
        # Inject representative organization accounts directly so governance may
        # remove them from user_tracking.json without weakening this regression.
        tracking = {
            "tracks": [
                {
                    "name": "AI / AGI",
                    "enabled": True,
                    "people": [
                        "Sam Altman",
                        "OpenAI @OpenAI",
                        "Anthropic @AnthropicAI",
                        "The Washington Post @washingtonpost",
                    ],
                }
            ]
        }
        people, excluded = MODULE.collect_candidates(tracking, self.overrides)
        names = {item["name"] for item in people}
        self.assertEqual(names, {"Sam Altman"})
        self.assertNotIn("OpenAI", names)
        self.assertNotIn("Anthropic", names)
        self.assertNotIn("The Washington Post", names)
        self.assertTrue(any("OpenAI" in item for item in excluded))
        self.assertTrue(any("Anthropic" in item for item in excluded))
        self.assertTrue(any("Washington Post" in item for item in excluded))

    def test_same_person_merges_multiple_sectors(self):
        tracking = {
            "tracks": [
                {"name": "AI / AGI", "enabled": True, "people": ["埃隆·马斯克 @elonmusk"]},
                {"name": "商业航天", "enabled": True, "people": ["Elon Musk"]},
            ]
        }
        people, _ = MODULE.collect_candidates(tracking, self.overrides)
        musk = next(item for item in people if item["slug"] == "elon-musk")
        self.assertEqual(set(musk["sectors"]), {"AI / AGI", "商业航天"})
        self.assertIn("elonmusk", musk["handles"])

    def test_wikipedia_wikibase_item_is_the_authoritative_wikidata_identity(self):
        expected = {"id": "Q123", "url": "https://www.wikidata.org/wiki/Q123"}
        with patch.object(MODULE, "fetch_wikidata_entity", return_value=expected) as fetch_entity, patch.object(
            MODULE, "request_json", side_effect=AssertionError("search must not run when Wikipedia supplied a QID")
        ):
            result = MODULE.fetch_wikidata(
                ["Example Person"],
                preferred_id="Q123",
                queries=["Example Person researcher"],
                identity_terms=["Example Lab"],
            )
        self.assertEqual(result, expected)
        fetch_entity.assert_called_once_with("Q123")

    def test_wikidata_search_requires_identity_context_without_wikipedia_qid(self):
        search_payload = {
            "search": [
                {"id": "Q1", "label": "Alex Smith", "description": "association football player"},
                {"id": "Q2", "label": "Alex Smith", "description": "Example Lab artificial intelligence researcher"},
            ]
        }
        with patch.object(MODULE, "request_json", return_value=search_payload), patch.object(
            MODULE, "fetch_wikidata_entity", return_value={"id": "Q2"}
        ) as fetch_entity:
            result = MODULE.fetch_wikidata(
                ["Alex Smith"],
                queries=["Alex Smith Example Lab"],
                identity_terms=["Example Lab", "artificial intelligence researcher"],
            )
        self.assertEqual(result, {"id": "Q2"})
        fetch_entity.assert_called_once_with("Q2", "zh")

    def test_profile_snapshot_has_single_verified_identity_reference(self):
        payload = json.loads((ROOT / "public" / "data" / "people.json").read_text(encoding="utf-8"))
        for person in payload["people"]:
            wikipedia = [item for item in person["materials"] if "wikipedia.org" in item["url"]]
            wikidata = [item for item in person["materials"] if "wikidata.org" in item["url"]]
            self.assertLessEqual(len(wikipedia), 1, person["slug"])
            self.assertLessEqual(len(wikidata), 1, person["slug"])

    def test_unknown_person_without_sources_still_gets_pending_profile(self):
        candidate = {
            "slug": "future-researcher",
            "name": "Future Researcher",
            "englishName": "Future Researcher",
            "aliases": ["Future Researcher"],
            "handles": [],
            "sectors": ["未来赛道"],
            "override": {},
        }
        person = MODULE.enrich_candidate(candidate, None, [], offline=True)
        self.assertEqual(person["status"], "pending")
        self.assertEqual(person["materials"], [])
        self.assertEqual(person["sectors"], ["未来赛道"])

    def test_offline_generation_keeps_every_real_tracked_person(self):
        payload = MODULE.build_payload(offline=True, workers=1)
        self.assertGreaterEqual(payload["personCount"], 15)
        for person in payload["people"]:
            self.assertTrue(person["slug"])
            self.assertTrue(person["name"])
            self.assertTrue(person["sectors"])
            self.assertIn(person["status"], {"complete", "partial", "pending"})
            self.assertIsInstance(person["materials"], list)


if __name__ == "__main__":
    unittest.main()
