import unittest

from tools.ranked_intelligence_projection import normalize_projection


class RankedIntelligenceCapacityTests(unittest.TestCase):
    def item(self, index: int):
        return {
            "id": f"item-{index}",
            "title": f"Public item {index}",
            "summary": "public summary",
            "href": f"https://example.com/story/{index}",
            "source": "Example",
            "publishedAt": "2026-09-14T12:00:00Z",
            "priority": "P0" if index % 2 == 0 else "P1",
            "score": 95,
            "eventTypes": ["Technology"],
            "entities": [],
            "tracks": ["AI / AGI"],
            "eventClusterId": "",
            "duplicateCount": 1,
            "relatedSources": [],
        }

    def projection(self, count: int):
        return {
            "schemaVersion": 1,
            "generatedAt": "2026-09-14T12:00:00Z",
            "source": "google-alerts-rss",
            "contentHash": "producer-hash",
            "items": [self.item(index) for index in range(count)],
        }

    def test_accepts_thirty_six_public_items(self):
        normalized = normalize_projection(self.projection(36))
        self.assertEqual(len(normalized["items"]), 36)

    def test_rejects_more_than_thirty_six_public_items(self):
        with self.assertRaisesRegex(ValueError, "at most 36"):
            normalize_projection(self.projection(37))


if __name__ == "__main__":
    unittest.main()
