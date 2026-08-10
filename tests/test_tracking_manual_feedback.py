from __future__ import annotations

import unittest

from tools.tracking_manual_feedback import (
    build_manual_feedback,
    is_single_manual_value,
    manual_held_values,
    manual_seed_terms,
    manual_source_affinity,
    normalize_identity,
    signal_identity,
)


class TrackingManualFeedbackTests(unittest.TestCase):
    def test_single_entity_guard_preserves_legal_names_and_rejects_bundles(self) -> None:
        self.assertTrue(is_single_manual_value("Pony.ai, Inc."))
        self.assertTrue(is_single_manual_value("Procter & Gamble"))
        self.assertTrue(is_single_manual_value("A/B Test Labs"))
        self.assertFalse(is_single_manual_value("OpenAI，Anthropic"))
        self.assertFalse(is_single_manual_value("Sam Altman、Demis Hassabis"))
        self.assertFalse(is_single_manual_value("阿里云 / Qwen"))
        self.assertFalse(is_single_manual_value("OpenAI\nAnthropic"))

    def test_technology_identity_preserves_semantic_punctuation(self) -> None:
        identities = {
            signal_identity(value, "keywords")
            for value in ("C", "C++", "C#", ".NET", "NET", "A/B", "AB")
        }
        self.assertEqual(len(identities), 7)

    def test_history_becomes_ranked_seeds_holds_affinity_and_relations(self) -> None:
        capture = {
            "records": [
                {
                    "entityType": "topic",
                    "canonicalName": "Open-weight",
                    "status": "applied",
                    "trackSlugs": ["ai", "venture"],
                    "capturedAt": "2026-08-01T00:00:00Z",
                    "reasons": ["技术突破", "个人研究兴趣"],
                    "source": {"url": "https://tech.example.com/a"},
                },
                {
                    "entityType": "company",
                    "canonicalName": "OpenAI",
                    "status": "applied",
                    "trackSlugs": ["ai"],
                    "capturedAt": "2026-08-02T00:00:00Z",
                    "reasons": ["融资机会"],
                    "source": {"url": "https://tech.example.com/b"},
                },
                {
                    "entityType": "company",
                    "canonicalName": "Held Co",
                    "status": "queued",
                    "trackSlugs": ["ai"],
                    "capturedAt": "2026-08-03T00:00:00Z",
                    "reasons": ["市场竞争"],
                    "source": {"url": "https://review.example/c"},
                },
                {
                    "entityType": "person",
                    "canonicalName": "Sam Altman、Demis Hassabis",
                    "status": "applied",
                    "trackSlugs": ["ai"],
                },
            ]
        }
        intents = {
            "entities": [
                {"id": "company:openai", "kind": "company", "name": "OpenAI"},
                {"id": "company:held", "kind": "company", "name": "Held Co"},
                {
                    "id": "source:official",
                    "kind": "source",
                    "name": "Official",
                    "url": "https://official.example/news",
                },
            ],
            "memberships": [
                {
                    "trackId": "track:ai",
                    "entityId": "company:openai",
                    "role": "actor",
                    "state": "rejected",
                    "origins": [{"at": "2026-08-04", "reasons": ["市场竞争"]}],
                },
                {
                    "trackId": "track:ai",
                    "entityId": "company:held",
                    "role": "actor",
                    "state": "active",
                    "origins": [{"at": "2026-08-05", "reasons": ["个人研究兴趣"]}],
                },
                {
                    "trackId": "track:ai",
                    "entityId": "source:official",
                    "role": "source-anchor",
                    "state": "active",
                    "origins": [{"at": "2026-08-05", "reasons": ["技术突破"]}],
                },
            ],
        }

        profile = build_manual_feedback(capture, intents)
        ai = profile["tracks"]["ai"]

        self.assertEqual(profile["rawHistoryRecords"], 4)
        self.assertEqual(profile["historyRecords"], 3)
        self.assertEqual(profile["ignoredHistoryRecords"], 1)
        self.assertNotIn("Sam Altman、Demis Hassabis", manual_seed_terms(profile, "ai"))
        self.assertIn("Held Co", ai["approved"]["sampleCompanies"])
        self.assertNotIn("Held Co", ai["held"]["sampleCompanies"])
        self.assertIn(normalize_identity("OpenAI"), manual_held_values(profile, "ai"))
        self.assertNotIn("OpenAI", ai["approved"]["sampleCompanies"])
        self.assertEqual(manual_source_affinity(profile, "ai", "official.example"), 1)
        self.assertGreaterEqual(manual_source_affinity(profile, "ai", "tech.example.com"), 1)
        self.assertEqual(ai["relatedTracks"][0]["slug"], "venture")
        self.assertEqual(profile["reasonCounts"]["个人研究兴趣"], 2)

    def test_only_current_active_history_creates_positive_track_relations(self) -> None:
        capture = {
            "records": [
                {
                    "entityType": "topic",
                    "canonicalName": "Queued Topic",
                    "status": "queued",
                    "trackSlugs": ["ai", "robotics"],
                },
                {
                    "entityType": "topic",
                    "canonicalName": "Removed Topic",
                    "status": "applied",
                    "trackSlugs": ["ai", "robotics"],
                },
                {
                    "entityType": "topic",
                    "canonicalName": "Pinned Topic",
                    "status": "applied",
                    "trackSlugs": ["ai", "robotics"],
                },
            ]
        }
        runtime = {
            "tracks": [
                {
                    "slug": "ai",
                    "name": "AI",
                    "keywords": ["Pinned Topic"],
                    "people": [],
                    "sampleCompanies": [],
                },
                {
                    "slug": "robotics",
                    "name": "机器人",
                    "keywords": ["Pinned Topic"],
                    "people": [],
                    "sampleCompanies": [],
                },
            ],
            "sources": [],
        }

        profile = build_manual_feedback(capture, {"entities": [], "memberships": []}, runtime)

        self.assertEqual(
            profile["tracks"]["ai"]["relatedTracks"],
            [{"slug": "robotics", "count": 1}],
        )
        self.assertEqual(
            profile["tracks"]["robotics"]["relatedTracks"],
            [{"slug": "ai", "count": 1}],
        )

    def test_v2_rejection_removes_legacy_positive_aggregates(self) -> None:
        capture = {
            "records": [
                {
                    "entityType": "company",
                    "canonicalName": "Only Co",
                    "status": "applied",
                    "trackSlugs": ["ai", "robotics"],
                    "source": {"url": "https://only.example/news"},
                }
            ]
        }
        runtime = {
            "tracks": [
                {
                    "slug": "ai",
                    "name": "AI",
                    "keywords": [],
                    "people": [],
                    "sampleCompanies": ["Only Co"],
                },
                {
                    "slug": "robotics",
                    "name": "机器人",
                    "keywords": [],
                    "people": [],
                    "sampleCompanies": ["Only Co"],
                },
            ],
            "sources": [],
        }
        intents = {
            "entities": [
                {"id": "company:only", "kind": "company", "name": "Only Co"}
            ],
            "memberships": [
                {
                    "trackId": "track:ai",
                    "entityId": "company:only",
                    "role": "actor",
                    "state": "rejected",
                    "origins": [],
                }
            ],
        }

        profile = build_manual_feedback(capture, intents, runtime)

        self.assertEqual(profile["tracks"]["ai"]["sourceHosts"], [])
        self.assertEqual(profile["tracks"]["ai"]["relatedTracks"], [])
        self.assertEqual(profile["tracks"]["robotics"]["relatedTracks"], [])
        self.assertEqual(profile["appliedSignals"], 1)
        self.assertEqual(profile["heldSignals"], 1)


if __name__ == "__main__":
    unittest.main()
