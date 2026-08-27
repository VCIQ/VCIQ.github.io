from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "research-agent-v1.yml"
PAGES_WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"


class ResearchAgentWorkflowTest(unittest.TestCase):
    def test_research_runs_share_the_repository_writer_lock(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: vciq-repository-writer-${{ github.ref }}", text)
        self.assertIn("queue: max", text)
        self.assertNotIn("queue: single", text)
        self.assertNotIn("cancel-in-progress:", text)

    def test_research_has_daily_reusable_manual_and_implementation_entrypoints(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("  workflow_call:", text)
        self.assertIn('cron: "30 21 * * *"', text)
        self.assertIn('timezone: "Asia/Taipei"', text)
        self.assertIn("  workflow_dispatch:", text)
        self.assertIn("  push:\n", text)
        self.assertIn("      - tools/research_agent.py", text)
        self.assertIn("      - tools/research_agent_evidence_policy.py", text)
        self.assertIn("      - tools/research_agent_article_events.py", text)
        self.assertIn("      - tools/research_agent_enhanced_runtime.py", text)
        self.assertNotIn("workflow_run:", text)
        self.assertNotIn('workflows: ["Refresh public intelligence"]', text)

    def test_api_fallback_is_published_as_degraded_and_can_raise_a_persistent_alert(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('health_status = "degraded" if status.endswith("-fallback") else "success"', text)
        self.assertIn('--status "$RESEARCH_HEALTH_STATUS"', text)
        self.assertIn("fallback_streak", text)
        self.assertIn('if [ "${FALLBACK_STREAK:-0}" -ge 3 ]', text)
        self.assertIn("Research Agent 连续规则降级", text)
        self.assertIn("issues: write", text)

    def test_terminal_pages_deployment_dispatches_research(self) -> None:
        pages = PAGES_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("run_research_after_deploy:", pages)
        self.assertIn("Continue to Research Agent after terminal publication", pages)
        self.assertIn("inputs.run_research_after_deploy == true", pages)
        self.assertIn("gh workflow run research-agent-v1.yml --ref main", pages)
        self.assertIn("actions: write", pages)

    def test_research_still_validates_runtime_and_control_plane_before_generation(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "python -m unittest tests.test_research_agent tests.test_research_agent_workflow",
            text,
        )
        self.assertIn("tools/research_agent_article_events.py", text)
        self.assertIn("python -m unittest tests.test_research_agent_runtime", text)
        self.assertIn("python -m unittest tests.test_research_agent_evidence_policy", text)
        self.assertIn("python -m unittest tests.test_research_agent_article_events", text)
        self.assertIn("python -m unittest tests.test_research_agent_publication_handoff", text)
        self.assertIn("python tools/run_pipeline.py check", text)


if __name__ == "__main__":
    unittest.main()
