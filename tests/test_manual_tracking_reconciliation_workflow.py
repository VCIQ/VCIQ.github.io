from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class ManualTrackingReconciliationWorkflowTests(unittest.TestCase):
    def test_interactive_writers_do_not_dispatch_heavy_work(self) -> None:
        for name in ("manual-tracking.yml", "manual-tracking-batch.yml"):
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            handoff = text.split("\n  handoff:\n", 1)[1]
            self.assertIn("Defer heavy tracking reconciliation", handoff)
            self.assertNotIn("gh workflow run", handoff)
            self.assertIn("permissions: {}", handoff)

    def test_atomic_batch_limit_is_documented_as_transaction_not_throughput(self) -> None:
        text = (WORKFLOWS / "manual-tracking-batch.yml").read_text(encoding="utf-8")
        self.assertIn("Up to 20 normalized requests per atomic writer transaction", text)
        self.assertIn("20-object limit remains a per-transaction safety boundary", text)
        self.assertIn("background throughput limit", text)

    def test_manual_config_pushes_do_not_start_full_or_company_heavy_paths(self) -> None:
        full = (WORKFLOWS / "scheduled-sync.yml").read_text(encoding="utf-8")
        full_trigger = full.split("  schedule:", 1)[0]
        self.assertNotIn("      - config/user_tracking.json", full_trigger)
        self.assertIn('cron: "30 6 * * *"', full)
        self.assertIn("config/user_tracking.json", full)

        discovery = (WORKFLOWS / "company-candidate-discovery.yml").read_text(encoding="utf-8")
        discovery_trigger = discovery.split("permissions:", 1)[0]
        self.assertNotIn("config/tracking_capture_inbox.json", discovery_trigger)
        self.assertNotIn("config/user_tracking.json", discovery_trigger)

        onboarding = (WORKFLOWS / "company-candidate-onboarding.yml").read_text(encoding="utf-8")
        onboarding_trigger = onboarding.split("  workflow_dispatch:", 1)[0]
        self.assertNotIn("config/tracking_capture_inbox.json", onboarding_trigger)

    def test_reconciliation_is_coalesced_low_priority_and_busy_aware(self) -> None:
        text = (WORKFLOWS / "manual-tracking-reconciliation.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "47 * * * *"', text)
        self.assertIn('timezone: "Asia/Taipei"', text)
        self.assertIn("group: vciq-manual-tracking-reconciliation", text)
        self.assertIn("queue: single", text)
        self.assertIn("fetch-depth: 0", text)
        self.assertIn("config/tracking_capture_inbox.json", text)
        self.assertIn("config/tracking_intents.json", text)
        self.assertIn('PENDING_STATES = {"queued", "review", "pending"}', text)
        self.assertIn("05", text)
        self.assertIn("06", text)
        self.assertIn("07", text)
        for workflow in (
            "scheduled-sync.yml",
            "frequent-intelligence-refresh.yml",
            "tracking-discovery.yml",
            "company-candidate-discovery.yml",
            "company-candidate-onboarding.yml",
        ):
            self.assertIn(workflow, text)
        self.assertIn("--status queued", text)
        self.assertIn("--status \"$status\"", text)
        self.assertIn("Heavy writer busy", text)

    def test_reconciliation_has_a_success_watermark_to_avoid_repeat_runs(self) -> None:
        text = (WORKFLOWS / "manual-tracking-reconciliation.yml").read_text(encoding="utf-8")
        self.assertIn("Check whether the latest manual write was already reconciled", text)
        self.assertIn("config: apply authenticated manual tracking", text)
        self.assertIn("last_success", text)
        self.assertIn("already_processed", text)
        self.assertIn("reconciled >= manual", text)

    def test_coordinator_dispatches_at_most_one_matching_heavy_lane_and_never_full_refresh(self) -> None:
        text = (WORKFLOWS / "manual-tracking-reconciliation.yml").read_text(encoding="utf-8")
        dispatch = text.split("- name: Dispatch one coalesced reconciliation", 1)[1].split(
            "- name: Summarize coordinator decision", 1
        )[0]
        self.assertIn("gh workflow run company-candidate-discovery.yml --ref main", dispatch)
        self.assertIn("gh workflow run tracking-discovery.yml --ref main -f mode=full", dispatch)
        self.assertNotIn("gh workflow run scheduled-sync.yml", dispatch)
        self.assertIn("if [ \"$COMPANY_PENDING\" = \"true\" ]", dispatch)

    def test_reconciliation_and_onboarding_prefer_light_refresh(self) -> None:
        discovery = (WORKFLOWS / "company-candidate-discovery.yml").read_text(encoding="utf-8")
        onboarding = (WORKFLOWS / "company-candidate-onboarding.yml").read_text(encoding="utf-8")
        self.assertIn("gh workflow run frequent-intelligence-refresh.yml --ref main", discovery)
        self.assertNotIn("gh workflow run scheduled-sync.yml --ref main", discovery)
        self.assertIn("gh workflow run frequent-intelligence-refresh.yml --ref main", onboarding)
        self.assertNotIn("gh workflow run scheduled-sync.yml --ref main", onboarding)


if __name__ == "__main__":
    unittest.main()
