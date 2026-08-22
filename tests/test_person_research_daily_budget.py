from __future__ import annotations

import unittest

from tools.person_research_outcomes import empty_memory, record_attempt
from tools.person_research_scheduler import MAX_ACTIVE_QUERY_SLOTS, build_daily_queue


def task(task_id: str, priority: str = "P1") -> dict:
    return {
        "id": task_id,
        "taskType": "first_party_evidence",
        "priority": priority,
        "status": "open",
        "target": "测试目标",
        "question": f"研究问题 {task_id}",
        "successCriteria": "找到新的身份匹配一手材料。",
        "searchQueries": [f"query {task_id}"],
        "evidenceBasis": [],
        "candidateEvidence": [],
    }


def attempt(task_id: str, slug: str) -> dict:
    return {
        "taskId": task_id,
        "personSlug": slug,
        "taskType": "first_party_evidence",
        "executor": "person_video",
        "query": f"executed {task_id}",
        "researchDate": "2026-08-22",
        "attemptedAt": "2026-08-22T01:00:00Z",
        "acceptedEvidenceCount": 0,
        "newEvidenceCount": 0,
        "platforms": [
            {
                "source": "YouTube",
                "rawRows": 0,
                "acceptedEvidenceCount": 0,
                "newEvidenceCount": 0,
                "failed": False,
                "acceptedUrls": [],
            }
        ],
    }


class PersonResearchDailyBudgetTests(unittest.TestCase):
    def test_same_day_attempt_consumes_budget_and_person_is_not_requeried(self):
        agenda_people = {}
        people = []
        memory = empty_memory()
        for index in range(10):
            slug = f"person-{index}"
            task_id = f"task-{index}"
            agenda_people[slug] = {"personName": slug, "tasks": [task(task_id, "P0" if index < 2 else "P1")]}
            people.append({"slug": slug, "name": slug, "materials": []})
        record_attempt(memory, attempt("task-0", "person-0"))
        record_attempt(memory, attempt("task-1", "person-1"))

        queue = build_daily_queue(
            {"generatedAt": "2026-08-22T00:00:00Z", "people": agenda_people},
            {"people": people},
            memory,
        )

        self.assertEqual(queue["usedQuerySlotsToday"], 2)
        self.assertLessEqual(
            queue["usedQuerySlotsToday"] + queue["allocatedQuerySlots"],
            MAX_ACTIVE_QUERY_SLOTS,
        )
        by_person = {row["personSlug"]: row for row in queue["queue"]}
        self.assertEqual(by_person["person-0"]["queryBudget"], 0)
        self.assertEqual(by_person["person-1"]["queryBudget"], 0)
        self.assertEqual(by_person["person-0"]["searchQueries"], [])
        self.assertEqual(by_person["person-1"]["searchQueries"], [])

    def test_full_daily_budget_blocks_all_new_active_queries_without_hiding_tasks(self):
        agenda_people = {}
        people = []
        memory = empty_memory()
        for index in range(MAX_ACTIVE_QUERY_SLOTS + 2):
            slug = f"person-{index}"
            task_id = f"task-{index}"
            agenda_people[slug] = {"personName": slug, "tasks": [task(task_id)]}
            people.append({"slug": slug, "name": slug, "materials": []})
            if index < MAX_ACTIVE_QUERY_SLOTS:
                record_attempt(memory, attempt(task_id, slug))

        queue = build_daily_queue(
            {"generatedAt": "2026-08-22T00:00:00Z", "people": agenda_people},
            {"people": people},
            memory,
        )

        self.assertEqual(queue["usedQuerySlotsToday"], MAX_ACTIVE_QUERY_SLOTS)
        self.assertEqual(queue["allocatedQuerySlots"], 0)
        self.assertGreater(queue["selectedTaskCount"], 0)
        self.assertTrue(all(row["queryBudget"] == 0 for row in queue["queue"]))


if __name__ == "__main__":
    unittest.main()
