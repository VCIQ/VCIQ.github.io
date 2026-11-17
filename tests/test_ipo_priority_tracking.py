import json
import unittest
from datetime import date
from pathlib import Path

from tools.ipo_priority_tracking import daily_tracks, eligible_companies
from tools import crawl_with_tracking

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config" / "ipo_priority_watchlist_20261115.json"
BOARDS = {"科创板": 66, "沪市主板": 19, "深市主板": 16, "创业板": 79, "北交所": 196}


class TestIpoPriorityTracking(unittest.TestCase):
    def test_ipo_groups_only_in_explicit_runtime_merge(self):
        base = {"feeds": [], "publicDiscovery": [], "papers": []}
        tracking = {
            "schemaVersion": 1,
            "tracks": [{
                "slug": "topic",
                "name": "Ordinary Topic",
                "enabled": True,
                "keywords": ["sample"],
                "people": [],
                "sampleCompanies": [],
            }],
            "sources": [],
        }
        self.assertEqual(len(crawl_with_tracking._enabled_tracks(tracking)), 1)
        ordinary, _, _ = crawl_with_tracking.build_merged_config(base, tracking)
        with_ipo, _, _ = crawl_with_tracking.build_merged_config(
            base, tracking, include_ipo_priority=True,
        )
        self.assertEqual(
            len([x for x in ordinary["publicDiscovery"]
                 if x["id"].startswith("user-track-")]), 2,
        )
        self.assertEqual(
            len([x for x in with_ipo["publicDiscovery"]
                 if x["id"].startswith("user-track-ipo-owner-priority-")]), 6,
        )

    def test_all_source_rows_preserved(self):
        items = json.loads(SOURCE.read_text(encoding="utf-8"))["companies"]
        self.assertEqual(len(items), 376)
        self.assertEqual(len({item["id"] for item in items}), 376)
        self.assertEqual(
            {board: sum(item["board"] == board for item in items) for board in BOARDS},
            BOARDS,
        )
        self.assertEqual(sum(item["name"] is None for item in items), 0)
        self.assertEqual(
            sum(item["nameOrigin"] == "manually-read-source-pdf" for item in items),
            82,
        )

    def test_uncertain_names_never_enter_search_batch(self):
        items = eligible_companies(SOURCE)
        self.assertEqual(len(items), 376)
        self.assertTrue(all(item["name"] for item in items))
        self.assertTrue(all(item["ocrQuality"] != "needs_manual_verification" for item in items))

    def test_bounded_rotation_covers_all_eligible_companies(self):
        day0 = date(2026, 11, 16).toordinal()
        seen = set()
        for offset in range(9):
            groups = daily_tracks(date.fromordinal(day0 + offset), SOURCE)
            self.assertLessEqual(len(groups), 3)
            names = [name for group in groups for name in group["sampleCompanies"]]
            self.assertLessEqual(len(names), 45)
            self.assertEqual(len(names), len(set(names)))
            seen.update(names)
        self.assertEqual(len(seen), 376)


if __name__ == "__main__":
    unittest.main()
