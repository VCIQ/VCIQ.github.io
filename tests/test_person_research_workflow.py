from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEDULED = ROOT / ".github" / "workflows" / "scheduled-sync.yml"
VIDEO_CHECKS = ROOT / ".github" / "workflows" / "person-video-checks.yml"


class PersonResearchWorkflowTests(unittest.TestCase):
    def test_full_refresh_treats_person_research_runtime_as_live_input(self) -> None:
        text = SCHEDULED.read_text(encoding="utf-8")
        for path in (
            "tools/person_research_agent.py",
            "tools/person_research_scheduler.py",
            "tools/person_research_outcomes.py",
        ):
            with self.subTest(path=path):
                self.assertIn(f"      - {path}", text)
                self.assertIn(f"            {path}", text)

    def test_full_refresh_persists_outcome_memory_with_people_snapshot(self) -> None:
        text = SCHEDULED.read_text(encoding="utf-8")
        data_block = text.split("DATA_PATHS=(", 1)[1].split(")", 1)[0]
        self.assertIn("public/data/people.json", data_block)
        self.assertIn("public/data/person_research_outcomes.json", data_block)
        self.assertIn('git add "${DATA_PATHS[@]}" "${CONTROL_PATHS[@]}"', text)
        self.assertIn(
            'git add "${DATA_PATHS[@]}" "${CONTROL_PATHS[@]}" "${GOVERNANCE_PATHS[@]}"',
            text,
        )

    def test_rebase_research_pass_documents_same_day_budget_guard(self) -> None:
        text = SCHEDULED.read_text(encoding="utf-8")
        rebase_block = text.split("git pull --rebase -X theirs origin main", 1)[1]
        self.assertIn("Outcome Memory enforces the same-day active-query budget", rebase_block)
        self.assertIn("python tools/refresh_people_profiles_with_video.py", rebase_block)

    def test_person_video_ci_covers_outcome_memory_and_scheduler(self) -> None:
        text = VIDEO_CHECKS.read_text(encoding="utf-8")
        for path in (
            "tools/person_research_scheduler.py",
            "tools/person_research_outcomes.py",
            "tests/test_person_research_outcomes.py",
            "tests/test_person_research_daily_budget.py",
        ):
            with self.subTest(path=path):
                self.assertIn(path, text)
        for module in (
            "tests.test_person_research_scheduler",
            "tests.test_person_research_outcomes",
            "tests.test_person_research_daily_budget",
        ):
            with self.subTest(module=module):
                self.assertIn(module, text)


if __name__ == "__main__":
    unittest.main()
