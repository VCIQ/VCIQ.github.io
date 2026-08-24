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
        self.assertEqual(normalized["items"][0]["duplicateCount"], 1)
        self.assertEqual(normalized["items"][0]["relatedSources"], [])
        self.assertNotEqual(normalized["contentHash"], "producer-hash-is-not-trusted")
        self.assertEqual(len(normalized["contentHash"]), 64)

    def test_accepts_only_compact_public_event_cluster_evidence(self):
        value = self.base()
        value["items"][0].update({
            "eventClusterId": "intel-event-abc",
            "duplicateCount": 3,
            "relatedSources": [{
                "source": "搜狐",
                "href": "https://sohu.example/story",
                "title": "OpenAI 推出青少年版 ChatGPT",
                "publishedAt": "2026-08-18T04:30:00Z",
            }],
        })
        normalized = normalize_projection(value)
        item = normalized["items"][0]
        self.assertEqual(item["eventClusterId"], "intel-event-abc")
        self.assertEqual(item["duplicateCount"], 3)
        self.assertEqual(item["relatedSources"][0]["source"], "搜狐")
        self.assertEqual(
            set(item["relatedSources"][0]),
            {"source", "href", "title", "publishedAt"},
        )

    def test_rejects_private_or_control_fields(self):
        value = self.base()
        value["items"][0]["queries"] = ["private alert query"]
        with self.assertRaisesRegex(ValueError, "non-public fields"):
            normalize_projection(value)

    def test_rejects_private_fields_inside_related_source(self):
        value = self.base()
        value["items"][0]["relatedSources"] = [{
            "source": "Example 2",
            "href": "https://example.net/story",
            "title": "same event",
            "publishedAt": "2026-08-18T04:30:00Z",
            "query": "private query",
        }]
        with self.assertRaisesRegex(ValueError, "non-public fields"):
            normalize_projection(value)

    def test_rejects_too_many_related_sources(self):
        value = self.base()
        value["items"][0]["relatedSources"] = [
            {
                "source": f"Source {index}",
                "href": f"https://source{index}.example/story",
                "title": "same event",
                "publishedAt": "2026-08-18T04:30:00Z",
            }
            for index in range(4)
        ]
        with self.assertRaisesRegex(ValueError, "at most 3"):
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