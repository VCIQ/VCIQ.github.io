from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "scheduled-sync.yml"


class ScheduledSyncWorkflowTest(unittest.TestCase):
    def test_complete_refresh_preserves_pending_repository_writers(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: vciq-repository-writer-", text)
        self.assertIn("github.ref", text)
        self.assertIn("queue: max", text)
        self.assertNotIn("queue: single", text)
        self.assertIn("must not evict candidate onboarding or reconciliation", text)
        self.assertNotIn("cancel-in-progress:", text)

    def test_full_refresh_runs_once_daily_after_the_us_close(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "30 6 * * *"', text)
        self.assertIn('timezone: "Asia/Taipei"', text)
        self.assertNotIn("4-22/2", text)

    def test_tracking_config_changes_start_one_full_refresh(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("      - config/user_tracking.json", text)

    def test_source_portfolio_runtime_changes_start_one_full_refresh(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        for path in (
            "tools/article_publication_gate.py",
            "tools/core_official_adapters.py",
            "tools/source_portfolio.py",
            "tools/full_refresh_input_guard.py",
        ):
            with self.subTest(path=path):
                self.assertIn(f"      - {path}", text)
                self.assertIn(f"            {path}", text)

        for test_module in (
            "tests.test_article_publication_gate",
            "tests.test_core_official_adapters",
            "tests.test_source_portfolio",
            "tests.test_full_refresh_input_guard",
        ):
            with self.subTest(test_module=test_module):
                self.assertIn(test_module, text)

    def test_test_only_changes_do_not_start_a_production_full_refresh(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("      - tests/**/*.py", text)
        self.assertNotIn("      - tests/**", text)

    def test_stale_queued_refresh_skips_network_crawl(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("  preflight:\n", text)
        self.assertIn("outputs:\n      current: ${{ steps.input-currentness.outputs.current }}", text)
        self.assertIn("id: input-currentness", text)
        self.assertIn("python tools/full_refresh_input_guard.py", text)
        self.assertIn('--target origin/main', text)
        self.assertIn('--github-output "$GITHUB_OUTPUT"', text)
        self.assertIn("  crawl:\n    needs: preflight", text)
        self.assertIn("if: needs.preflight.outputs.current == 'true'", text)

        preflight_block = text.split("  preflight:\n", 1)[1].split("\n  crawl:\n", 1)[0]
        self.assertNotIn("crawl_with_wechat_registry.py --source all", preflight_block)
        self.assertNotIn("gh workflow run scheduled-sync.yml", preflight_block)

    def test_full_refresh_covers_required_source_families(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        required_commands = (
            "python tools/crawl_with_wechat_registry.py --source all",
            "python tools/validate_professional_media_snapshot.py --require-articles",
            "python tools/crawl_listed_company_disclosures.py",
            "python tools/cninfo_structured_disclosures.py --require-events",
            "python -m tools.publish_us_ir_baselines",
            "python -m tools.us_ir_baseline_disclosures",
            "python -m tools.us_ir_baseline_disclosures --check --require-events",
            "python tools/eastmoney_transport.py",
            "python tools/validate_full_refresh.py",
        )
        for command in required_commands:
            with self.subTest(command=command):
                self.assertIn(command, text)

    def test_successful_publication_gate_explicitly_dispatches_entity_reconciliation(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Continue through entity reconciliation before publication", text)
        self.assertIn("steps.data-update.outcome == 'success'", text)
        self.assertIn("steps.data-update.outputs.superseded != 'true'", text)
        self.assertIn("gh workflow run company-candidate-discovery.yml --ref main", text)
        self.assertIn("-f publish_after_reconciliation=true", text)
        self.assertIn("actions: write", text)

    def test_newer_refresh_inputs_supersede_the_unpublished_snapshot(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("REFRESH_INPUT_PATHS=(", text)
        self.assertIn("supersede_if_refresh_inputs_changed()", text)
        self.assertIn("python tools/full_refresh_input_guard.py", text)
        self.assertIn('--base "$GITHUB_SHA"', text)
        self.assertIn('--target "$target_ref"', text)
        self.assertIn("git fetch origin main", text)
        self.assertIn("supersede_if_refresh_inputs_changed origin/main", text)
        self.assertNotIn("supersede_if_refresh_inputs_changed HEAD", text)
        self.assertIn("superseded=true", text)
        self.assertIn("Restart superseded refresh from current main", text)
        self.assertIn("steps.data-update.outputs.superseded == 'true'", text)
        self.assertIn("gh workflow run scheduled-sync.yml --ref main", text)
        self.assertIn("Full refresh superseded", text)

        rebase_block = text.split("git pull --rebase -X theirs origin main", 1)[1]
        supersede = rebase_block.index("supersede_if_refresh_inputs_changed origin/main")
        governance = rebase_block.index("python tools/tracking_source_governance.py\n")
        validate = rebase_block.index("python tools/validate_full_refresh.py")
        self.assertLess(supersede, governance)
        self.assertLess(governance, validate)

    def test_superseded_refresh_does_not_publish_source_health_or_reconcile(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "steps.data-update.outputs.superseded != 'true'",
            text.split("- name: Sync persistent source health issue", 1)[1].split("env:", 1)[0],
        )
        self.assertIn(
            "steps.data-update.outputs.superseded != 'true'",
            text.split("- name: Continue through entity reconciliation before publication", 1)[1].split("env:", 1)[0],
        )

    def test_full_crawl_persists_audit_without_semantic_article_changes(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("No semantic public-data changes; publishing the completed full-crawl audit.", text)
        self.assertNotIn("No semantic public data changes; skipping Git commit and Pages build.", text)

    def test_full_refresh_validates_shared_source_health_summary(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("tools/source_health_summary.py", text)
        self.assertIn("tests.test_source_health_summary", text)
        self.assertIn("Require canonical source health summary", text)
        self.assertIn("python tools/source_health_summary.py --check", text)

    def test_rebase_recanonicalizes_source_health_without_double_counting_streaks(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        rebase_block = text.split("git pull --rebase -X theirs origin main", 1)[1]
        normalize = rebase_block.index("python tools/source_health_summary.py\n")
        governance_apply = rebase_block.index("python tools/tracking_source_governance.py\n")
        governance_check = rebase_block.index("python tools/tracking_source_governance.py --check")
        validate = rebase_block.index("python tools/validate_full_refresh.py")
        self.assertLess(normalize, governance_apply)
        self.assertLess(governance_apply, governance_check)
        self.assertLess(governance_check, validate)
        self.assertNotIn("python tools/update_source_health.py", rebase_block)

    def test_health_driven_governance_is_persisted_and_tracking_is_rebuilt(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        rebase_block = text.split("git pull --rebase -X theirs origin main", 1)[1]
        governance = rebase_block.index("python tools/tracking_source_governance.py\n")
        enrich = rebase_block.index("python tools/enrich_tracking_snapshot.py")
        validate = rebase_block.index("python tools/validate_full_refresh.py")
        self.assertLess(governance, enrich)
        self.assertLess(enrich, validate)
        self.assertIn("GOVERNANCE_PATHS=(", text)
        self.assertIn("config/user_tracking.json", text)
        self.assertIn("config/tracking_auto_discovery.json", text)
        self.assertIn('git add "${DATA_PATHS[@]}" "${CONTROL_PATHS[@]}" "${GOVERNANCE_PATHS[@]}"', text)

    def test_rebase_rebuilds_quality_gate_before_full_refresh_validation(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        rebase_block = text.split("git pull --rebase -X theirs origin main", 1)[1]
        retention = rebase_block.index("python tools/snapshot_retention.py")
        rebuild = rebase_block.index("python tools/refresh_article_quality_gate.py")
        finalize = rebase_block.index("python tools/finalize_full_refresh.py")
        validate = rebase_block.index("python tools/validate_full_refresh.py")
        self.assertLess(retention, rebuild)
        self.assertLess(rebuild, finalize)
        self.assertLess(finalize, validate)
        self.assertIn("tools/refresh_article_quality_gate.py", text)
        self.assertIn("tests.test_refresh_article_quality_gate", text)


if __name__ == "__main__":
    unittest.main()
