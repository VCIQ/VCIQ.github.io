from __future__ import annotations

import unittest

from tools.person_research_scheduler import (
    MAX_ACTIVE_QUERY_SLOTS,
    MAX_DAILY_MAINTENANCE_TASKS,
    build_daily_queue,
    task_workstream,
)


def task(task_id: str, task_type: str, priority: str = "P0") -> dict:
    return {
        "id": task_id,
        "taskType": task_type,
        "priority": priority,
        "status": "open",
        "target": "AI systems",
        "question": f"Question {task_id}",
        "successCriteria": "Find independent public evidence.",
        "searchQueries": [f"Person {task_id} interview"],
        "evidenceBasis": [],
        "candidateEvidence": [],
    }


def person(slug: str) -> dict:
    return {"slug": slug, "name": slug, "materials": []}


class PersonResearchWorkstreamTests(unittest.TestCase):
    def test_legacy_task_types_infer_stable_workstreams(self) -> None:
        self.assertEqual(task_workstream(task("identity", "identity_verification")), "maintenance")
        self.assertEqual(task_workstream(task("fresh", "freshness_update")), "maintenance")
        self.assertEqual(task_workstream(task("first", "first_party_evidence")), "research")
        self.assertEqual(task_workstream(task("view", "viewpoint_verification")), "research")
        self.assertEqual(task_workstream(task("exec", "execution_verification")), "research")

    def test_maintenance_has_a_hard_daily_cap_and_cannot_displace_research_lane(self) -> None:
        agenda_people = {}
        people = []
        for index in range(8):
            slug = f"person-{index}"
            people.append(person(slug))
            agenda_people[slug] = {
                "personName": slug,
                "tasks": [
                    task(f"research-{index}", "viewpoint_verification", "P1"),
                    task(f"maintenance-{index}", "identity_verification", "P0"),
                ],
            }
        queue = build_daily_queue(
            {"generatedAt": "2026-09-11T00:00:00Z", "people": agenda_people},
            {"people": people},
        )
        self.assertEqual(queue["selectedResearchTaskCount"], 8)
        self.assertEqual(queue["selectedMaintenanceTaskCount"], MAX_DAILY_MAINTENANCE_TASKS)
        self.assertTrue(all(row["workstream"] in {"research", "maintenance"} for row in queue["queue"]))
        research_ids = {row["taskId"] for row in queue["queue"] if row["workstream"] == "research"}
        self.assertEqual(research_ids, {f"research-{index}" for index in range(8)})

    def test_research_uses_active_query_capacity_before_maintenance(self) -> None:
        agenda_people = {}
        people = []
        for index in range(MAX_ACTIVE_QUERY_SLOTS):
            slug = f"research-{index}"
            people.append(person(slug))
            agenda_people[slug] = {
                "personName": slug,
                "tasks": [task(f"r-{index}", "first_party_evidence", "P0")],
            }
        # Use the same selected people so the people cap does not hide the query-lane behavior.
        for index in range(2):
            slug = f"research-{index}"
            agenda_people[slug]["tasks"].append(task(f"m-{index}", "freshness_update", "P0"))

        queue = build_daily_queue(
            {"generatedAt": "2026-09-11T00:00:00Z", "people": agenda_people},
            {"people": people},
        )
        self.assertEqual(queue["allocatedResearchQuerySlots"], MAX_ACTIVE_QUERY_SLOTS)
        self.assertEqual(queue["allocatedMaintenanceQuerySlots"], 0)
        self.assertTrue(
            all(
                row["workstream"] == "research"
                for row in queue["queue"]
                if row["queryBudget"] > 0
            )
        )


if __name__ == "__main__":
    unittest.main()
