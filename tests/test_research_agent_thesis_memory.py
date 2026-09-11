from __future__ import annotations

import unittest

from tools.research_agent_thesis_memory import build_thesis_memory


def evidence(evidence_id: str, url: str) -> dict:
    return {
        "id": evidence_id,
        "title": f"Evidence {evidence_id}",
        "sourceName": "Official Source",
        "url": url,
        "publishedAt": "2026-09-10",
        "eventDate": "2026-09-10",
        "verificationStatus": "auto_verified",
    }


def report(generated_at: str, direction: str, statement: str, evidence_id: str = "E001") -> dict:
    return {
        "generatedAt": generated_at,
        "analysis": {
            "thesisUpdates": [
                {
                    "entity": "Example Co",
                    "direction": direction,
                    "statement": statement,
                    "evidenceIds": [evidence_id],
                }
            ]
        },
        "evidence": [evidence(evidence_id, f"https://example.com/{evidence_id.lower()}")],
    }


class ResearchAgentThesisMemoryTests(unittest.TestCase):
    def test_identical_thesis_is_reaffirmed_without_duplicate_observation(self) -> None:
        first_report = report(
            "2026-09-10T00:00:00Z",
            "positive",
            "Commercial adoption is accelerating.",
        )
        first_memory = build_thesis_memory({}, first_report)
        self.assertEqual(first_memory["observationCount"], 1)
        first = first_memory["observations"][0]
        self.assertEqual(first["lastTransition"], "initiated")
        self.assertEqual(first["observationCount"], 1)

        previous = {"thesisMemory": first_memory}
        second_report = report(
            "2026-09-11T00:00:00Z",
            "positive",
            "Commercial adoption is accelerating.",
            "E002",
        )
        second_memory = build_thesis_memory(previous, second_report)
        self.assertEqual(second_memory["observationCount"], 1)
        second = second_memory["observations"][0]
        self.assertEqual(second["lastTransition"], "reaffirmed")
        self.assertEqual(second["observationCount"], 2)
        self.assertEqual(len(second["evidence"]), 2)
        self.assertEqual(second_memory["currentObservationIds"], [second["id"]])

    def test_direction_change_creates_new_observation_and_preserves_prior(self) -> None:
        first_report = report(
            "2026-09-10T00:00:00Z",
            "positive",
            "Commercial adoption is accelerating.",
        )
        first_memory = build_thesis_memory({}, first_report)
        first_id = first_memory["observations"][0]["id"]

        second_report = report(
            "2026-09-11T00:00:00Z",
            "negative",
            "Deployment friction is now slowing adoption.",
            "E002",
        )
        second_memory = build_thesis_memory({"thesisMemory": first_memory}, second_report)
        self.assertEqual(second_memory["observationCount"], 2)
        current_id = second_memory["currentObservationIds"][0]
        current = next(row for row in second_memory["observations"] if row["id"] == current_id)
        self.assertEqual(current["lastTransition"], "direction_changed")
        self.assertEqual(current["supersedesId"], first_id)
        self.assertTrue(any(row["id"] == first_id for row in second_memory["observations"]))

    def test_memory_keeps_evidence_snapshots_not_run_local_ids(self) -> None:
        memory = build_thesis_memory(
            {},
            report(
                "2026-09-11T00:00:00Z",
                "mixed",
                "Execution is improving but evidence remains incomplete.",
            ),
        )
        observation = memory["observations"][0]
        self.assertNotIn("evidenceIds", observation)
        self.assertEqual(observation["evidence"][0]["url"], "https://example.com/e001")
        self.assertEqual(observation["evidence"][0]["verificationStatus"], "auto_verified")


if __name__ == "__main__":
    unittest.main()
