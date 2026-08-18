import copy
import unittest

from tools.ranked_intelligence_projection import normalize_projection


class RankedIntelligenceProjectionTests(unittest.TestCase):
    def base(self):
        return {
            "schemaVersion": 1,
            "generatedAt": "2026-08-18T06:00:00Z",
            "source": "google-alerts-rss",
            "contentHash": "producer-hash-is-not-trusted",
            "items": [{
                "id": "https://example.com/story",
                "title": "OpenAI 发布新产品",
                "summary": "公开摘要",
                "href": "https://example.com/story",
                "source": "Example",
                "publishedAt": "2026-08-18T05:00:00Z",
                "priority": "P0",
                "score": 96,
                "eventTypes": ["Product"],
                "entities": [{"objectType": "company", "name": "OpenAI"}],
                "tracks": ["AI / AGI"],
            }],
        }

    def test_normalizes_and_recomputes_hash(self):
        normalized = normalize_projection(self.base())
        self.assertEqual(normalized["schemaVersion"], 1)
        self.assertEqual(normalized["items"][0]["score"], 96)
        self.assertNotEqual(normalized["contentHash"], "producer-hash-is-not-trusted")
        self.assertEqual(len(normalized["contentHash"]), 64)

    def test_rejects_private_or_control_fields(self):
        value = self.base()
        value["items"][0]["queries"] = ["private alert query"]
        with self.assertRaisesRegex(ValueError, "non-public fields"):
            normalize_projection(value)

    def test_rejects_feed_or_credential_urls(self):
        value = self.base()
        value["items"][0]["href"] = "https://user:secret@example.com/story"
        with self.assertRaisesRegex(ValueError, "credentials"):
            normalize_projection(value)

    def test_hash_changes_only_when_items_change(self):
        first = normalize_projection(self.base())
        later = self.base()
        later["generatedAt"] = "2026-08-18T07:00:00Z"
        second = normalize_projection(later)
        self.assertEqual(first["contentHash"], second["contentHash"])
        changed = copy.deepcopy(later)
        changed["items"][0]["score"] = 97
        third = normalize_projection(changed)
        self.assertNotEqual(first["contentHash"], third["contentHash"])


if __name__ == "__main__":
    unittest.main()
