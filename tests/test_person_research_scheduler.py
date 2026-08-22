from __future__ import annotations

import unittest

from tools.person_research_outcomes import empty_memory, record_attempt
from tools.person_research_scheduler import (
    MAX_ACTIVE_QUERY_SLOTS,
    MAX_DAILY_PEOPLE,
    MAX_DAILY_TASKS,
    MAX_TASKS_PER_PERSON,
    build_daily_queue,
    scheduled_queries_by_slug,
)


def task(
    task_id: str,
    *,
    task_type: str = "first_party_evidence",
    priority: str = "P1",
    status: str = "open",
    queries: list[str] | None = None,
    basis: int = 0,
    candidates: int = 0,
):
    return {
        "id": task_id,
        "taskType": task_type,
        "priority": priority,
        "status": status,
        "target": "世界模型",
        "question": f"研究问题 {task_id}",
        "successCriteria": "取得满足独立性要求的公开证据。",
        "searchQueries": queries if queries is not None else [f"人物 {task_id}"],
        "evidenceBasis": [
            {"title": f"basis-{index}", "url": f"https://example.com/b/{index}"}
            for index in range(basis)
        ],
        "candidateEvidence": [
            {"title": f"candidate-{index}", "url": f"https://example.com/c/{index}"}
            for index in range(candidates)
        ],
    }


def person(slug: str, *, recent: bool = False):
    materials = []
    if recent:
        materials = [
            {
                "title": "近期公开演讲",
                "date": "2026-08-20",
                "type": "speech",
                "url": f"https://example.com/{slug}/recent",
            },
            {
                "title": "近期采访",
                "date": "2026-08-10",
                "type": "interview",
                "url": f"https://example.com/{slug}/recent-2",
            },
        ]
    return {"slug": slug, "name": slug, "materials": materials}


def outcome_event(task_id: str, person_slug: str, research_date: str, *, new: int = 0):
    accepted = 1 if new else 0
    return {
        "taskId": task_id,
        "personSlug": person_slug,
        "taskType": "first_party_evidence",
        "executor": "person_video",
        "query": f"{person_slug} query {research_date}",
        "researchDate": research_date,
        "attemptedAt": f"{research_date}T01:00:00Z",
        "acceptedEvidenceCount": accepted,
        "newEvidenceCount": new,
        "platforms": [
            {
                "source": "YouTube",
                "rawRows": 0,
                "acceptedEvidenceCount": accepted,
                "newEvidenceCount": new,
                "failed": False,
                "acceptedUrls": ["https://youtube.com/example"] if accepted else [],
            }
        ],
    }


class PersonResearchSchedulerTests(unittest.TestCase):
    def test_high_value_recent_viewpoint_task_outranks_cold_evidence_gap(self):
        agenda = {
            "generatedAt": "2026-08-22T00:00:00Z",
            "people": {
                "recent-person": {
                    "personName": "Recent Person",
                    "tasks": [task(
                        "viewpoint",
                        task_type="viewpoint_verification",
                        priority="P0",
                        basis=2,
                    )],
                },
                "cold-person": {
                    "personName": "Cold Person",
                    "tasks": [task(
                        "first-party",
                        task_type="first_party_evidence",
                        priority="P0",
                    )],
                },
            },
        }
        people = {"people": [person("recent-person", recent=True), person("cold-person")]}
        queue = build_daily_queue(agenda, people)
        self.assertEqual(queue["queue"][0]["personSlug"], "recent-person")
        self.assertGreater(queue["queue"][0]["score"], queue["queue"][1]["score"])
        self.assertEqual(
            queue["queue"][0]["score"],
            sum(queue["queue"][0]["scoreBreakdown"].values()),
        )
        self.assertEqual(queue["queue"][0]["scoreBreakdown"]["researchHistory"], 0)

    def test_supported_and_blocked_tasks_do_not_enter_execution_queue(self):
        agenda = {
            "generatedAt": "2026-08-22T00:00:00Z",
            "people": {
                "p": {
                    "personName": "P",
                    "tasks": [
                        task("open"),
                        task("supported", status="supported"),
                        task("blocked", status="blocked"),
                    ],
                }
            },
        }
        queue = build_daily_queue(agenda, {"people": [person("p")]})
        self.assertEqual([row["taskId"] for row in queue["queue"]], ["open"])
        self.assertEqual(queue["candidateTaskCount"], 1)

    def test_daily_people_task_and_per_person_limits_are_enforced(self):
        agenda_people = {}
        people = []
        for index in range(16):
            slug = f"person-{index:02d}"
            people.append(person(slug, recent=index < 3))
            agenda_people[slug] = {
                "personName": slug,
                "tasks": [
                    task(f"{slug}-a", priority="P0"),
                    task(f"{slug}-b", priority="P1"),
                    task(f"{slug}-c", priority="P2"),
                ],
            }
        queue = build_daily_queue(
            {"generatedAt": "2026-08-22T00:00:00Z", "people": agenda_people},
            {"people": people},
        )
        self.assertLessEqual(queue["selectedPeopleCount"], MAX_DAILY_PEOPLE)
        self.assertLessEqual(queue["selectedTaskCount"], MAX_DAILY_TASKS)
        counts = {}
        for row in queue["queue"]:
            counts[row["personSlug"]] = counts.get(row["personSlug"], 0) + 1
        self.assertTrue(all(value <= MAX_TASKS_PER_PERSON for value in counts.values()))

    def test_active_query_budget_is_one_slot_per_person_and_bounded(self):
        agenda_people = {}
        people = []
        for index in range(14):
            slug = f"video-{index:02d}"
            people.append(person(slug))
            agenda_people[slug] = {
                "personName": slug,
                "tasks": [
                    task(f"{slug}-one", priority="P0", queries=[f"{slug} first"]),
                    task(f"{slug}-two", priority="P1", queries=[f"{slug} second"]),
                ],
            }
        queue = build_daily_queue(
            {"generatedAt": "2026-08-22T00:00:00Z", "people": agenda_people},
            {"people": people},
        )
        allocated = [row for row in queue["queue"] if row["queryBudget"] > 0]
        self.assertLessEqual(len(allocated), MAX_ACTIVE_QUERY_SLOTS)
        self.assertEqual(len({row["personSlug"] for row in allocated}), len(allocated))
        self.assertTrue(all(len(row["searchQueries"]) == 1 for row in allocated))
        query_map = scheduled_queries_by_slug(queue)
        self.assertEqual(set(query_map), {row["personSlug"] for row in allocated})
        self.assertTrue(all(len(queries) == 1 for queries in query_map.values()))

    def test_execution_candidate_gets_cross_channel_executor_without_video_budget(self):
        agenda = {
            "generatedAt": "2026-08-22T00:00:00Z",
            "people": {
                "exec": {
                    "personName": "Exec",
                    "tasks": [task(
                        "execution",
                        task_type="execution_verification",
                        priority="P1",
                        status="candidate_found",
                        queries=[],
                        candidates=1,
                    )],
                }
            },
        }
        queue = build_daily_queue(agenda, {"people": [person("exec", recent=True)]})
        row = queue["queue"][0]
        self.assertEqual(row["executor"], "cross_channel")
        self.assertEqual(row["queryBudget"], 0)
        self.assertGreater(row["scoreBreakdown"]["crossValidation"], 0)

    def test_recent_productive_attempt_adds_small_history_bonus(self):
        agenda = {
            "generatedAt": "2026-08-22T00:00:00Z",
            "people": {
                "p": {
                    "personName": "P",
                    "tasks": [task("productive", priority="P1")],
                }
            },
        }
        memory = empty_memory()
        record_attempt(memory, outcome_event("productive", "p", "2026-08-21", new=1))
        queue = build_daily_queue(agenda, {"people": [person("p")]}, memory)
        row = queue["queue"][0]
        self.assertEqual(row["scoreBreakdown"]["researchHistory"], 6)
        self.assertEqual(row["researchMemory"]["yieldingAttempts"], 1)
        self.assertTrue(any("新增" in reason for reason in row["whyNow"]))
        self.assertEqual(row["score"], sum(row["scoreBreakdown"].values()))

    def test_cooldown_keeps_task_visible_but_reallocates_active_query_slot(self):
        agenda = {
            "generatedAt": "2026-08-22T00:00:00Z",
            "people": {
                "cooled": {
                    "personName": "Cooled",
                    "tasks": [task("cooled-task", priority="P0", queries=["cooled query"])],
                },
                "ready": {
                    "personName": "Ready",
                    "tasks": [task("ready-task", priority="P1", queries=["ready query"])],
                },
            },
        }
        memory = empty_memory()
        record_attempt(memory, outcome_event("cooled-task", "cooled", "2026-08-20"))
        record_attempt(memory, outcome_event("cooled-task", "cooled", "2026-08-21"))
        queue = build_daily_queue(
            agenda,
            {"people": [person("cooled"), person("ready")]},
            memory,
        )
        by_task = {row["taskId"]: row for row in queue["queue"]}
        self.assertIn("cooled-task", by_task)
        self.assertTrue(by_task["cooled-task"]["cooldownActive"])
        self.assertEqual(by_task["cooled-task"]["queryBudget"], 0)
        self.assertEqual(by_task["cooled-task"]["searchQueries"], [])
        self.assertEqual(by_task["ready-task"]["queryBudget"], 1)
        self.assertEqual(queue["allocatedQuerySlots"], 1)


if __name__ == "__main__":
    unittest.main()
