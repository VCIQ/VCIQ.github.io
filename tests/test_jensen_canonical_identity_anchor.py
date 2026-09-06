import importlib.util
import json
import unittest
from pathlib import Path

from tools import refresh_people_profiles as core

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_COLLECT = core.collect_candidates
ORIGINAL_ENRICH = core.enrich_candidate
SPEC = importlib.util.spec_from_file_location(
    "refresh_people_profiles_with_video_jensen_anchor",
    ROOT / "tools" / "refresh_people_profiles_with_video.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
try:
    SPEC.loader.exec_module(MODULE)
finally:
    # Importing the production video refresh module intentionally installs its
    # entrypoints on the shared core module. This test only needs the helper
    # behavior, so restore shared state before unittest discovery imports later
    # modules in the same Python process.
    core.collect_candidates = ORIGINAL_COLLECT
    core.enrich_candidate = ORIGINAL_ENRICH


class JensenCanonicalIdentityAnchorTest(unittest.TestCase):
    def test_chinese_only_and_bilingual_tracking_seeds_collapse_to_jensen_huang(self):
        overrides = json.loads(
            (ROOT / "config" / "person_profile_overrides.json").read_text(encoding="utf-8")
        )
        tracking = {
            "tracks": [
                {
                    "slug": "ai",
                    "name": "AI / AGI",
                    "enabled": True,
                    "people": ["黄仁勋"],
                },
                {
                    "slug": "semiconductor",
                    "name": "半导体",
                    "enabled": True,
                    "people": ["黄仁勋(Jensen Huang"],
                },
            ]
        }

        people, excluded = MODULE.collect_candidates(tracking, overrides)
        matches = [person for person in people if person["name"] == "黄仁勋"]

        self.assertEqual(excluded, [])
        self.assertEqual(len(matches), 1)
        jensen = matches[0]
        self.assertEqual(jensen["slug"], "jensen-huang")
        self.assertEqual(jensen["englishName"], "Jensen Huang")
        self.assertEqual(set(jensen["sectors"]), {"AI / AGI", "半导体"})
        self.assertIn("黄仁勋", jensen["aliases"])
        self.assertIn("Jensen Huang", jensen["aliases"])
        self.assertNotEqual(jensen["slug"], "person-4d6ca4357c")


if __name__ == "__main__":
    unittest.main()
