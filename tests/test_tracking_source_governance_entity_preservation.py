from copy import deepcopy
import unittest

from tools import add_semiconductor_media_sources
from tools import tracking_source_governance as governance


class TrackingSourceGovernanceEntityPreservationTests(unittest.TestCase):
    def _config(self) -> dict:
        return {
            "schemaVersion": 1,
            "tracks": [
                {
                    "slug": "ai",
                    "name": "AI / AGI",
                    "enabled": True,
                    "custom": False,
                    "keywords": ["Qwen"],
                    # Deliberately use compound sentinels here. These tests prove
                    # source-only transforms preserve entity arrays byte-for-value;
                    # they are not asserting that this input is valid production data.
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

    def test_source_governance_never_mutates_people_or_sample_companies(self) -> None:
        config = self._config()
        original_tracks = deepcopy(config["tracks"])

        next_config, _, _, _ = governance.normalize_tracking_sources(
            config,
            {"added": [], "removed": []},
            {"sources": {}},
        )

        self.assertEqual(next_config["tracks"], original_tracks)
        self.assertEqual(config["tracks"], original_tracks)

    def test_semiconductor_source_registration_never_mutates_tracks(self) -> None:
        config = self._config()
        original_tracks = deepcopy(config["tracks"])

        next_config, _ = add_semiconductor_media_sources.upsert_sources(config)

        self.assertEqual(next_config["tracks"], original_tracks)
        self.assertEqual(config["tracks"], original_tracks)
        self.assertGreater(len(next_config["sources"]), len(config["sources"]) - 1)


if __name__ == "__main__":
    unittest.main()
