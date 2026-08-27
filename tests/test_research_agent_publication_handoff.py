from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLISH_WORKFLOW = ROOT / ".github" / "workflows" / "publish-validated-data.yml"
PAGES_WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"
RESEARCH_WORKFLOW = ROOT / ".github" / "workflows" / "research-agent-v1.yml"


class ResearchAgentPublicationHandoffTest(unittest.TestCase):
    def test_relevant_validated_data_changes_request_one_post_deploy_research_run(self) -> None:
        text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        for workflow_name in (
            "Refresh public intelligence every two hours",
            "Refresh public intelligence",
            "Refresh venture profiles",
            "Refresh all listed-company research PDFs",
            "Refresh institution rankings",
            "Refresh STAR Market investors",
        ):
            self.assertIn(f'"{workflow_name}"', text)
        self.assertIn("SOURCE_HEAD_SHA", text)
        self.assertIn("compare/${SOURCE_HEAD_SHA}...main", text)
        self.assertIn(
            "^public/data/(articles|venture_profiles|institution_entities|market_profiles|people|institution_events|listed_company_disclosures)\\.json$",
            text,
        )
        self.assertIn("run_research_after_deploy=true", text)

    def test_source_performance_review_does_not_self_authorize_research_rerun(self) -> None:
        text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Monthly source performance review", text)
        handoff_case = text.split("case \"${SOURCE_WORKFLOW_NAME:-}\" in", 1)[1].split("esac", 1)[0]
        self.assertNotIn("Monthly source performance review", handoff_case)

    def test_pages_handoff_is_explicit_and_cannot_form_research_pages_loop(self) -> None:
        pages = PAGES_WORKFLOW.read_text(encoding="utf-8")
        research = RESEARCH_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("run_research_after_deploy:", pages)
        self.assertIn(
            "github.event_name == 'workflow_dispatch' && inputs.run_research_after_deploy == true",
            pages,
        )
        self.assertIn("gh workflow run research-agent-v1.yml --ref main", pages)
        self.assertNotIn("workflow_run:", research)
        self.assertNotIn("public/data/research_agent_daily.json", research.split("paths:", 1)[1].split("schedule:", 1)[0])
        self.assertNotIn("public/data/research_agent_snapshot.json", research.split("paths:", 1)[1].split("schedule:", 1)[0])


if __name__ == "__main__":
    unittest.main()
