from __future__ import annotations

import unittest

from tools.person_research_outcomes import (
    empty_memory,
    memory_summary,
    normalize_memory,
    record_attempt,
    task_feedback,
)


def event(
    research_date: str,
    *,
    query: str | None = None,
    accepted: int = 0,
    new: int = 0,
    failed: bool = False,
):
    query = query or f"测试人物 世界模型 {research_date}"
    return {
        "taskId": "person-research-test-task",
        "personSlug": "test-person",
        "taskType": "viewpoint_verification",
        "executor": "person_video",
        "query": query,
        "researchDate": research_date,
        "attemptedAt": f"{research_date}T01:00:00Z",
        "acceptedEvidenceCount": accepted,
        "newEvidenceCount": new,
        "platforms": [
            {
                "source": "YouTube",
                "rawRows": 4,
                "acceptedEvidenceCount": accepted,
                "newEvidenceCount": new,
                "failed": failed,
                "acceptedUrls": [
                    f"https://www.youtube.com/watch?v=evidence-{index}"
                    for index in range(accepted)
                ],
            },
            {
                "source": "Bilibili",
                "rawRows": 0,
                "acceptedEvidenceCount": 0,
                "newEvidenceCount": 0,
                "failed": failed,
                "acceptedUrls": [],
            },
        ],
    }


class PersonResearchOutcomeMemoryTests(unittest.TestCase):
    def test_new_evidence_is_productive_and_resets_zero_yield_streak(self):
        memory = empty_memory()
        self.assertTrue(record_attempt(memory, event("2026-08-20", accepted=2, new=1)))
        task = memory["taskOutcomes"]["person-research-test-task"]
        self.assertEqual(task["attempts"], 1)
        self.assertEqual(task["acceptedAttempts"], 1)
        self.assertEqual(task["yieldingAttempts"], 1)
        self.assertEqual(task["newEvidenceCount"], 1)
        self.assertEqual(task["zeroYieldStreak"], 0)
        self.assertEqual(task["lastOutcome"], "new_evidence")
        feedback = task_feedback(memory, "person-research-test-task", "2026-08-21")
        self.assertEqual(feedback["score"], 6)
        self.assertFalse(feedback["cooldownActive"])
        self.assertEqual(memory["sourceStats"]["YouTube"]["yieldRate"], 1.0)

    def test_repeated_no_new_evidence_enters_bounded_cooldown(self):
        memory = empty_memory()
        self.assertTrue(record_attempt(memory, event("2026-08-20", accepted=1, new=0)))
        self.assertTrue(record_attempt(memory, event("2026-08-21", accepted=0, new=0)))
        task = memory["taskOutcomes"]["person-research-test-task"]
        self.assertEqual(task["zeroYieldStreak"], 2)
        self.assertEqual(task["lastOutcome"], "no_yield")
        self.assertEqual(task["nextEligibleDate"], "2026-08-23")
        feedback = task_feedback(memory, "person-research-test-task", "2026-08-22")
        self.assertEqual(feedback["score"], -6)
        self.assertTrue(feedback["cooldownActive"])
        self.assertFalse(task_feedback(memory, "person-research-test-task", "2026-08-23")["cooldownActive"])

    def test_third_no_new_attempt_extends_cooldown_without_closing_task(self):
        memory = empty_memory()
        record_attempt(memory, event("2026-08-18", accepted=0, new=0))
        record_attempt(memory, event("2026-08-19", accepted=1, new=0))
        record_attempt(memory, event("2026-08-20", accepted=0, new=0))
        task = memory["taskOutcomes"]["person-research-test-task"]
        self.assertEqual(task["zeroYieldStreak"], 3)
        self.assertEqual(task["nextEligibleDate"], "2026-08-27")
        feedback = task_feedback(memory, "person-research-test-task", "2026-08-22")
        self.assertEqual(feedback["score"], -10)
        self.assertTrue(feedback["cooldownActive"])

    def test_executor_error_does_not_increase_zero_yield_streak(self):
        memory = empty_memory()
        record_attempt(memory, event("2026-08-20", accepted=0, new=0))
        before = memory["taskOutcomes"]["person-research-test-task"]["zeroYieldStreak"]
        record_attempt(memory, event("2026-08-21", accepted=0, new=0, failed=True))
        task = memory["taskOutcomes"]["person-research-test-task"]
        self.assertEqual(task["lastOutcome"], "error")
        self.assertEqual(task["zeroYieldStreak"], before)
        self.assertEqual(task_feedback(memory, "person-research-test-task", "2026-08-22")["score"], -1)

    def test_same_task_date_and_query_is_idempotent(self):
        memory = empty_memory()
        attempt = event("2026-08-20", query="测试人物 完整访谈", accepted=1, new=1)
        self.assertTrue(record_attempt(memory, attempt))
        self.assertFalse(record_attempt(memory, attempt))
        task = memory["taskOutcomes"]["person-research-test-task"]
        self.assertEqual(task["attempts"], 1)
        self.assertEqual(memory["sourceStats"]["YouTube"]["attempts"], 1)

    def test_memory_summary_separates_accepted_from_new_evidence(self):
        memory = empty_memory()
        record_attempt(memory, event("2026-08-20", accepted=2, new=1))
        record_attempt(memory, event("2026-08-21", accepted=1, new=0))
        summary = memory_summary(memory, "2026-08-22")
        self.assertEqual(summary["attemptCount"], 2)
        self.assertEqual(summary["yieldingAttemptCount"], 1)
        self.assertEqual(summary["acceptedEvidenceCount"], 3)
        self.assertEqual(summary["newEvidenceCount"], 1)
        self.assertEqual(summary["zeroYieldAttemptCount"], 1)

    def test_malformed_memory_fails_closed(self):
        normalized = normalize_memory({
            "schemaVersion": 999,
            "taskOutcomes": {
                "": {"personSlug": "x"},
                "valid": {
                    "personSlug": "p",
                    "attempts": "bad",
                    "zeroYieldStreak": -5,
                    "lastOutcome": "invented_truth",
                    "nextEligibleDate": "javascript:alert(1)",
                },
            },
            "sourceStats": {"YouTube": {"attempts": 2, "yieldingAttempts": 99}},
        })
        self.assertEqual(normalized["schemaVersion"], 1)
        self.assertNotIn("", normalized["taskOutcomes"])
        self.assertEqual(normalized["taskOutcomes"]["valid"]["attempts"], 0)
        self.assertEqual(normalized["taskOutcomes"]["valid"]["zeroYieldStreak"], 0)
        self.assertEqual(normalized["taskOutcomes"]["valid"]["lastOutcome"], "")
        self.assertEqual(normalized["taskOutcomes"]["valid"]["nextEligibleDate"], "")
        self.assertEqual(normalized["sourceStats"]["YouTube"]["yieldingAttempts"], 2)


if __name__ == "__main__":
    unittest.main()
