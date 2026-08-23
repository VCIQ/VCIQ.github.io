import unittest

from tools.person_research_outcome_memory import append_attempt, build_payload, task_memory_signal
from tools.person_research_scheduler import build_daily_queue


class PersonResearchOutcomeMemoryTests(unittest.TestCase):
    def test_candidate_found_is_research_yield_not_fact_verification(self):
        memory = append_attempt({}, {
            "taskId": "task-a",
            "personSlug": "alice",
            "researchDate": "2026-08-22",
            "query": "Alice interview",
            "outcome": "candidate_found",
            "candidateCount": 2,
            "sourceHosts": ["youtube.com"],
            "durationMs": 12_000,
        })
        score, reason, cooldown = task_memory_signal(memory, "task-a", "2026-08-22")
        self.assertEqual(score, 6)
        self.assertIn("候选产出", reason)
        self.assertEqual(cooldown, "")
        self.assertEqual(memory["taskStats"]["task-a"]["candidateFound"], 1)
        self.assertEqual(memory["attempts"][0]["durationMs"], 12_000)
        self.assertEqual(memory["attempts"][0]["queryCostUnits"], 1.2)
        self.assertNotIn("supported", memory["attempts"][0])

    def test_cost_stats_are_process_metrics_not_fact_state(self):
        memory = build_payload([
            {
                "taskId": "task-a",
                "taskType": "first_party_evidence",
                "personSlug": "alice",
                "researchDate": "2026-08-20",
                "query": "Alice 演讲",
                "queryStrategy": "topic_speech",
                "outcome": "candidate_found",
                "candidateCount": 1,
                "sourceHosts": ["youtube.com"],
                "durationMs": 10_000,
            },
            {
                "taskId": "task-b",
                "taskType": "first_party_evidence",
                "personSlug": "bob",
                "researchDate": "2026-08-21",
                "query": "Bob 演讲",
                "queryStrategy": "topic_speech",
                "outcome": "no_evidence",
                "candidateCount": 0,
                "sourceHosts": [],
                "durationMs": 30_000,
            },
        ])
        stats = memory["queryStrategyCostStats"]["topic_speech"]
        self.assertEqual(stats["attempts"], 2)
        self.assertEqual(stats["averageCostUnits"], 2)
        self.assertEqual(stats["averageDurationMs"], 20_000)
        self.assertNotIn("supported", memory)

    def test_recent_zero_yield_creates_query_cooldown_without_closing_task(self):
        memory = build_payload([{
            "taskId": "task-a",
            "personSlug": "alice",
            "researchDate": "2026-08-22",
            "query": "Alice interview",
            "outcome": "no_evidence",
            "candidateCount": 0,
            "sourceHosts": [],
        }])
        agenda = {
            "generatedAt": "2026-08-22T12:00:00+00:00",
            "people": {
                "alice": {
                    "personName": "Alice",
                    "tasks": [{
                        "id": "task-a",
                        "taskType": "first_party_evidence",
                        "priority": "P0",
                        "status": "open",
                        "target": "first party material",
                        "question": "Find a first-party interview",
                        "successCriteria": "Verify against the original material",
                        "searchQueries": ["Alice interview"],
                        "evidenceBasis": [],
                        "candidateEvidence": [],
                    }],
                }
            },
        }
        people = {
            "generatedAt": "2026-08-22T12:00:00+00:00",
            "people": [{"slug": "alice", "name": "Alice", "materials": []}],
        }
        queue = build_daily_queue(agenda, people, memory)
        self.assertEqual(queue["selectedTaskCount"], 1)
        self.assertEqual(queue["queue"][0]["status"], "open")
        self.assertEqual(queue["queue"][0]["queryBudget"], 0)
        self.assertEqual(queue["allocatedQuerySlots"], 0)
        self.assertEqual(queue["queue"][0]["cooldownUntil"], "2026-08-25")
        self.assertLess(queue["queue"][0]["scoreBreakdown"]["researchOutcomeMemory"], 0)

    def test_attempt_identity_is_deduplicated(self):
        attempt = {
            "taskId": "task-a",
            "personSlug": "alice",
            "researchDate": "2026-08-22",
            "query": "Alice interview",
            "outcome": "no_evidence",
            "candidateCount": 0,
            "sourceHosts": [],
            "durationMs": 10_000,
        }
        memory = append_attempt({}, attempt)
        memory = append_attempt(memory, {**attempt, "durationMs": 20_000})
        self.assertEqual(memory["attemptCount"], 1)


if __name__ == "__main__":
    unittest.main()
