from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.person_research_outcome_memory import build_payload
from tools.person_research_scheduler import (
    MAX_ACTIVE_QUERY_SLOTS,
    MAX_DAILY_PEOPLE,
    MAX_DAILY_TASKS,
    MAX_TASKS_PER_PERSON,
    build_daily_queue,
    scheduled_attempts_by_slug,
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

    def test_query_slot_prefers_higher_expected_yield_per_cost(self):
        attempts = []
        for index in range(3):
            attempts.extend([
                {
                    "taskId": f"slow-{index}",
                    "taskType": "viewpoint_verification",
                    "personSlug": f"slow-{index}",
                    "researchDate": "2026-08-10",
                    "query": "Slow Person 世界模型 演讲",
                    "queryStrategy": "topic_speech",
                    "outcome": "candidate_found",
                    "candidateCount": 1,
                    "sourceHosts": ["youtube.com"],
                    "durationMs": 40_000,
                    "queryCostUnits": 4,
                },
                {
                    "taskId": f"fast-{index}",
                    "taskType": "viewpoint_verification",
                    "personSlug": f"fast-{index}",
                    "researchDate": "2026-08-10",
                    "query": "Fast Person 世界模型 访谈",
                    "queryStrategy": "topic_interview",
                    "outcome": "candidate_found",
                    "candidateCount": 1,
                    "sourceHosts": ["youtube.com"],
                    "durationMs": 10_000,
                    "queryCostUnits": 1,
                },
            ])
        memory = build_payload(attempts)
        agenda = {
            "generatedAt": "2026-08-22T00:00:00Z",
            "people": {
                "slow-person": {
                    "personName": "Slow Person",
                    "tasks": [task(
                        "slow-current",
                        task_type="viewpoint_verification",
                        priority="P0",
                        queries=["Slow Person 世界模型 演讲"],
                    )],
                },
                "fast-person": {
                    "personName": "Fast Person",
                    "tasks": [task(
                        "fast-current",
                        task_type="viewpoint_verification",
                        priority="P0",
                        queries=["Fast Person 世界模型 访谈"],
                    )],
                },
            },
        }
        with patch("tools.person_research_scheduler.MAX_ACTIVE_QUERY_SLOTS", 1):
            queue = build_daily_queue(
                agenda,
                {"people": [person("slow-person"), person("fast-person")]},
                memory,
            )
        allocated = [row for row in queue["queue"] if row["queryBudget"] == 1]
        self.assertEqual(len(allocated), 1)
        self.assertEqual(allocated[0]["personSlug"], "fast-person")
        self.assertGreater(allocated[0]["expectedYieldPerCost"], 0.5)
        self.assertGreater(allocated[0]["allocationUtility"], 0)
        slow = next(row for row in queue["queue"] if row["personSlug"] == "slow-person")
        self.assertGreater(allocated[0]["allocationUtility"], slow["allocationUtility"])

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

    def test_strategy_memory_selects_higher_yield_query_and_preserves_task_state(self):
        attempts = []
        for index in range(3):
            attempts.append({
                "taskId": f"old-direct-{index}",
                "taskType": "first_party_evidence",
                "personSlug": f"old-direct-{index}",
                "researchDate": "2026-08-10",
                "query": "Alice 世界模型",
                "queryStrategy": "topic_direct",
                "outcome": "no_evidence",
                "candidateCount": 0,
                "sourceHosts": [],
            })
            attempts.append({
                "taskId": f"old-speech-{index}",
                "taskType": "first_party_evidence",
                "personSlug": f"old-speech-{index}",
                "researchDate": "2026-08-10",
                "query": "Alice 世界模型 演讲",
                "queryStrategy": "topic_speech",
                "outcome": "candidate_found",
                "candidateCount": 2,
                "sourceHosts": ["youtube.com"],
                "sourceTypeCounts": {"video_platform": 2},
            })
        memory = build_payload(attempts)
        agenda = {
            "generatedAt": "2026-08-22T00:00:00Z",
            "people": {
                "alice": {
                    "personName": "Alice",
                    "tasks": [task(
                        "current",
                        task_type="first_party_evidence",
                        priority="P0",
                        queries=["Alice 世界模型", "Alice 世界模型 演讲"],
                    )],
                }
            },
        }
        queue = build_daily_queue(agenda, {"people": [person("alice")]}, memory)
        row = queue["queue"][0]
        self.assertEqual(row["status"], "open")
        self.assertEqual(row["searchQueries"], ["Alice 世界模型 演讲"])
        self.assertEqual(row["queryStrategy"], "topic_speech")
        self.assertGreater(row["strategySampleSize"], 0)
        self.assertGreater(row["scoreBreakdown"]["researchStrategyROI"], 0)
        self.assertGreater(row["expectedSuccessRate"], 0.5)
        self.assertEqual(row["topHistoricalSourceType"], "video_platform")
        attempt = scheduled_attempts_by_slug(queue)["alice"]
        self.assertEqual(attempt["taskType"], "first_party_evidence")
        self.assertEqual(attempt["queryStrategy"], "topic_speech")


if __name__ == "__main__":
    unittest.main()
