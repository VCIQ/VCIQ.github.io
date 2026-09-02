from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "source-performance-review.yml"


class SourcePerformanceWorkflowTest(unittest.TestCase):
    def test_monthly_review_runs_after_the_daily_refresh_window(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "30 8 1 * *"', text)
        self.assertIn('timezone: "Asia/Taipei"', text)
        self.assertIn("workflow_dispatch:", text)

    def test_review_is_validated_before_commit_and_issue_sync(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("tests.test_source_performance", text)
        self.assertIn("tests.test_source_quality_reviews", text)
        self.assertIn("tests.test_source_quality_review_queue", text)
        self.assertIn("python tools/source_performance_review.py --check", text)
        self.assertIn("python tools/source_quality_review_queue.py --check", text)
        self.assertIn("[月度审查] 信源效能与降级建议", text)
        self.assertIn("public/data/source_performance_review.json", text)
        self.assertIn("public/data/source_quality_review_queue.json", text)
        self.assertIn("docs/source-quality-review-queue.md", text)

    def test_record_queue_does_not_auto_write_human_review_judgements(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("git add config/source_quality_reviews.json", text)
        self.assertIn("不要自动生成误归属结论", text)

    def test_workflow_does_not_delete_or_mutate_source_configuration(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("git rm", text)
        self.assertNotIn("config/user_tracking.json", text)
        self.assertNotIn("config/intelligence_sources.json", text)


if __name__ == "__main__":
    unittest.main()
