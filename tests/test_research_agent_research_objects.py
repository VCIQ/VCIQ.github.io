from __future__ import annotations

import unittest
from unittest import mock

from tools import research_agent as agent
from tools import research_agent_research_objects as target


def event(event_id: str, *, grade: str = "媒体报道", importance: int = 70) -> dict:
    return {
        "id": event_id,
        "title": f"Event {event_id}",
        "summary": "A tracked research-object event.",
        "publishedAt": "2026-09-11",
        "importance": importance,
        "url": f"https://example.com/{event_id}",
        "sourceName": "Example Source",
        "evidenceGrade": grade,
        "sourceRole": "primary" if grade == "官方披露" else "corroboration",
    }


def snapshot(dataset: str, events: list[dict]) -> dict:
    return {
        "schemaVersion": 1,
        "generatedAt": "2026-09-11T00:00:00Z",
        "datasets": {
            dataset: {
                "object-1": {
                    "slug": "object-1",
                    "name": "Object One",
                    "latestEvents": events,
                }
            }
        },
        "stats": {dataset: 1},
        "contentHash": "fixture",
    }


class ResearchAgentResearchObjectTests(unittest.TestCase):
    def test_injects_canonical_track_and_technology_datasets(self) -> None:
        base = {
            "schemaVersion": 1,
            "generatedAt": "2026-09-11T00:00:00Z",
            "datasets": {"person": {"p": {"name": "Person"}}},
            "stats": {"person": 1},
            "contentHash": "before",
        }
        payload = {
            "schemaVersion": 1,
            "generatedAt": "2026-09-11T00:00:00Z",
            "tracks": {"ai": {"slug": "ai", "name": "AI / AGI"}},
            "technologies": {"codex": {"slug": "codex", "name": "Codex"}},
        }
        with mock.patch.object(target, "_AGENT", agent):
            result = target._inject(base, payload)
        self.assertEqual(result["stats"]["track"], 1)
        self.assertEqual(result["stats"]["technology"], 1)
        self.assertEqual(result["datasets"]["track"]["ai"]["name"], "AI / AGI")
        self.assertEqual(result["datasets"]["technology"]["codex"]["name"], "Codex")

    def test_only_new_object_events_create_external_change_and_evidence_record(self) -> None:
        before = snapshot("technology", [event("old")])
        after = snapshot("technology", [event("new", importance=94), event("old")])
        with mock.patch.object(target, "_ORIGINAL_DIFF_SNAPSHOTS", agent.diff_snapshots):
            changes = target.diff_snapshots(before, after)
        self.assertEqual(len(changes), 1)
        change = changes[0]
        self.assertEqual(change["dataset"], "technology")
        self.assertEqual(change["entityType"], "核心技术")
        self.assertEqual(change["changeType"], "external_event")
        self.assertTrue(change["isResearchCandidate"])
        self.assertEqual(change["importance"], 94)
        self.assertEqual(
            [row["id"] for row in change["record"]["latestEvents"]],
            ["new"],
        )

    def test_window_rotation_without_new_event_is_maintenance(self) -> None:
        before = snapshot("track", [event("same")])
        after = snapshot("track", [{**event("same"), "summary": "metadata refresh"}])
        with mock.patch.object(target, "_ORIGINAL_DIFF_SNAPSHOTS", agent.diff_snapshots):
            changes = target.diff_snapshots(before, after)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["changeType"], "data_maintenance")
        self.assertFalse(changes[0]["isResearchCandidate"])

    def test_core_object_publication_tier_respects_source_strength(self) -> None:
        official = {
            "supportStatus": "supports",
            "qualityStatus": "passed",
            "evidenceGrade": "官方披露",
            "sourceRole": "primary",
        }
        media = {
            "supportStatus": "supports",
            "qualityStatus": "passed",
            "evidenceGrade": "媒体报道",
            "sourceRole": "corroboration",
        }
        with mock.patch.object(target, "_AGENT", agent):
            self.assertEqual(target.publication_tier("technology", [official]), "verified_change")
            self.assertEqual(target.publication_tier("track", [media]), "candidate")

    def test_scope_becomes_active_only_when_object_datasets_exist(self) -> None:
        active = target.research_scope(
            {
                "datasets": {
                    "technology": {"a": {}, "b": {}},
                    "track": {"t": {}},
                    "person": {"p": {}},
                    "ventureCompany": {"c": {}},
                }
            }
        )
        self.assertEqual(active["technology"]["status"], "active")
        self.assertEqual(active["technology"]["count"], 2)
        self.assertEqual(active["track"]["status"], "active")
        self.assertEqual(active["track"]["count"], 1)

        pending = target.research_scope(
            {"datasets": {"person": {}, "ventureCompany": {}}}
        )
        self.assertEqual(pending["technology"]["status"], "pending-artifact")
        self.assertIsNone(pending["technology"]["count"])
        self.assertEqual(pending["track"]["status"], "pending-artifact")


if __name__ == "__main__":
    unittest.main()
