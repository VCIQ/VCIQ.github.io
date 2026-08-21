from copy import deepcopy
import unittest

from tools import tracking_source_governance as governance


class TrackingSourceGovernanceEntityPreservationTests(unittest.TestCase):
    def test_source_governance_never_mutates_people_or_sample_companies(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [
                {
                    "slug": "ai",
                    "name": "AI / AGI",
                    "enabled": True,
                    "custom": False,
                    "keywords": ["Qwen"],
                    # Deliberately use compound sentinels here. This test is about
                    # transformation preservation, not whether the input is valid.
                    "people": ["Alice、Bob", "Carol"],
                    "sampleCompanies": ["Alpha / Beta", "OpenAI, Inc."],
                }
            ],
            "sources": [
                {
                    "id": "source-auto-media-example",
                    "name": "Example · AI / AGI信源 · AI / AGI信源",
                    "url": "https://www.example.com/feed",
                    "sourceCategory": "media",
                    "sector": "AI / AGI",
                    "enabled": True,
                }
            ],
        }
        original_tracks = deepcopy(config["tracks"])

        next_config, _, _, _ = governance.normalize_tracking_sources(
            config,
            {"added": [], "removed": []},
            {"sources": {}},
        )

        self.assertEqual(next_config["tracks"], original_tracks)
        self.assertEqual(config["tracks"], original_tracks)


if __name__ == "__main__":
    unittest.main()
