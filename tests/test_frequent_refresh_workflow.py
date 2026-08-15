from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "frequent-intelligence-refresh.yml"


class FrequentRefreshWorkflowTests(unittest.TestCase):
    def test_lightweight_schedule_reserves_the_full_refresh_window(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "17 0,2,4,8,10,12,14,16,18,20,22 * * *"', text)
        self.assertIn('timezone: "Asia/Taipei"', text)
        self.assertIn("runtime due check also protects the full-refresh window", text)
        self.assertIn("Explain lightweight refresh skip", text)

    def test_lightweight_refresh_uses_the_repository_writer_queue(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: vciq-repository-writer-", text)
        self.assertIn("queue: max", text)
        self.assertNotIn("cancel-in-progress:", text)

    def test_due_check_uses_the_real_news_crawl_clock(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python tools/frequent_refresh_due.py", text)
        self.assertIn("tests.test_frequent_refresh_due", text)
        self.assertNotIn('audit.get("completedAt") or payload.get("generatedAt")', text)
        self.assertIn("ref: main", text)

    def test_lightweight_refresh_has_room_to_finish_a_real_crawl(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("timeout-minutes: 60", text)
        self.assertNotIn("timeout-minutes: 45", text)

    def test_lightweight_refresh_only_crawls_news_families(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python tools/crawl_with_wechat_registry.py --source news", text)
        self.assertIn("python tools/finalize_frequent_refresh.py", text)
        self.assertNotIn("python -m tools.us_ir_baseline_disclosures", text)
        self.assertNotIn("python tools/refresh_market_profiles_enriched.py", text)

    def test_successful_crawl_persists_audit_even_without_new_articles(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("No semantic article changes; publishing the completed source-crawl audit.", text)
        self.assertNotIn("git restore \"${DATA_PATHS[@]}\"", text)

    def test_bot_authored_refresh_reconciles_derived_entities_before_pages(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Reconcile derived entity state before publication", text)
        self.assertIn("steps.data-update.outputs.changed == 'true'", text)
        self.assertIn("gh workflow run company-candidate-discovery.yml --ref main", text)
        self.assertNotIn("gh workflow run pages.yml --ref main", text)
        self.assertIn("actions: write", text)


if __name__ == "__main__":
    unittest.main()
