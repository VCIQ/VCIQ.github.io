from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import person_research_agent as planner
from tools.person_identity_contract import validate_generated_person_identity
from tools.person_research_scheduler import build_daily_queue, scheduled_queries_by_slug

ROOT = Path(__file__).resolve().parents[1]


def profile(name: str, slug: str) -> dict:
    return {"name": name, "englishName": name, "slug": slug, "materials": [], "organizations": []}


class PersonIdentityContractTests(unittest.TestCase):
    def test_shared_fixtures(self):
        fixtures = json.loads((ROOT / "tests/fixtures/person-identity-contract.json").read_text())
        for row in fixtures:
            with self.subTest(case=row["case"]):
                self.assertEqual(validate_generated_person_identity(row["candidate"]), row["expected"])

    def test_invalid_entities_cannot_enter_either_planner_entrypoint(self):
        for name in ("Class Presiden Thomas Sonderman", "Massachusetts Governo Chris Ballance", "混合专家模型"):
            person = profile(name, "invalid")
            self.assertEqual(planner.build_person_tasks(person, [], "2026-09-11"), [])
            agenda = planner.build_agenda({"people": [person]}, {"articles": []})
            self.assertEqual(agenda["people"], {})
            self.assertEqual(agenda["taskCount"], 0)

    def test_valid_identity_is_not_rewritten_and_task_semantics_are_unchanged(self):
        person = profile("Chris Ballance", "chris-ballance")
        before = copy.deepcopy(person)
        actual = planner.build_person_tasks(person, [], "2026-09-11")
        with patch.object(planner, "validate_generated_person_identity", return_value={"valid": True}):
            legacy = planner.build_person_tasks(person, [], "2026-09-11")
        self.assertTrue(actual)
        self.assertEqual(actual, legacy)
        self.assertEqual(person, before)

    def test_stale_agenda_does_not_spend_capacity_on_invalid_or_missing_identities(self):
        people = {"people": [profile("Chris Ballance", "chris"), profile("Class Presiden Thomas Sonderman", "bad")]}
        stale_task = {"id": "stale", "taskType": "first_party_evidence", "priority": "P0", "status": "open", "searchQueries": ["bad official"]}
        good_tasks = planner.build_person_tasks(people["people"][0], [], "2026-09-11")
        agenda = {"generatedAt": "2026-09-11", "people": {
            "bad": {"personName": "bad", "tasks": [stale_task]},
            "missing": {"personName": "Chris Ballance", "tasks": [stale_task]},
            "chris": {"personName": "Chris Ballance", "tasks": good_tasks},
        }}
        queue = build_daily_queue(agenda, people, {})
        self.assertTrue(queue["queue"])
        self.assertEqual({row["personSlug"] for row in queue["queue"]}, {"chris"})
        self.assertNotIn("bad", scheduled_queries_by_slug(queue))
        self.assertEqual(queue["candidateTaskCount"], len(good_tasks))

    def test_all_retained_production_tasks_equal_pre_gate_planner_output(self):
        people = json.loads((ROOT / "public/data/people.json").read_text())
        articles = json.loads((ROOT / "public/data/articles.json").read_text())
        with patch.object(planner, "validate_generated_person_identity", return_value={"valid": True}):
            legacy = planner.build_agenda(people, articles)
        current = planner.build_agenda(people, articles)
        self.assertTrue(current["people"])
        accepted = {p["slug"] for p in people["people"] if validate_generated_person_identity(p)["valid"]}
        self.assertTrue(set(current["people"]) <= accepted)
        for slug, row in current["people"].items():
            self.assertEqual(row, legacy["people"][slug], slug)
        self.assertEqual(current["taskCount"], sum(len(row["tasks"]) for row in current["people"].values()))


if __name__ == "__main__":
    unittest.main()
