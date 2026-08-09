from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "tracking-discovery.yml"


class TrackingDiscoveryWorkflowTests(unittest.TestCase):
    def test_discovery_keeps_schedule_and_manual_dispatch(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        trigger_block = text.split("permissions:", 1)[0]
        self.assertIn('cron: "0 3 * * 0"', trigger_block)
        self.assertIn('timezone: "Asia/Taipei"', trigger_block)
        self.assertIn("workflow_dispatch:", trigger_block)

    def test_policy_rollout_gets_one_non_recursive_governance_pass(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        trigger_block = text.split("permissions:", 1)[0]
        self.assertIn("  push:\n", trigger_block)
        self.assertIn("branches: [main]", trigger_block)
        self.assertIn("- tools/tracking_seed_governance.py", trigger_block)
        self.assertIn("- .github/workflows/tracking-discovery.yml", trigger_block)
        push_block = trigger_block.split("push:", 1)[1].split("schedule:", 1)[0]
        # The governance commit itself changes config only, so this cannot recurse.
        self.assertNotIn("config/user_tracking.json", push_block)
        self.assertNotIn("config/tracking_auto_discovery.json", push_block)

    def test_push_rollout_skips_network_entity_expansion(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        for step_name in (
            "Expand tracking entities from public web sources",
            "Reference the complete investment-institution directory",
            "Reuse verified institution teams and public accounts",
            "Discover founders, core team and public social accounts",
            "Register public communities and media columns",
        ):
            block = text.split(f"- name: {step_name}", 1)[1].split("- name:", 1)[0]
            self.assertIn("if: github.event_name != 'push'", block)
        self.assertIn('DISCOVERY_MODE="govern-only"', text)

    def test_job_has_a_hard_timeout_and_bounded_network_budget(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("timeout-minutes: 45", text)
        self.assertIn("--max-requests 240", text)
        self.assertIn("--max-requests 50", text)
        self.assertIn("--max-requests 70", text)
        self.assertNotIn("--max-requests 420", text)

    def test_mode_is_preserved_for_concurrent_replay(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('echo "mode=$MODE" >> "$GITHUB_OUTPUT"', text)
        self.assertIn("EXPAND_MODE: ${{ steps.expand.outputs.mode }}", text)
        self.assertIn('DISCOVERY_MODE="$EXPAND_MODE"', text)
        self.assertIn('DISCOVERY_MODE="govern-only"', text)

    def test_push_failure_replays_from_latest_main(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("regenerate_from_latest_main()", text)
        self.assertIn("git fetch origin main", text)
        self.assertIn("git reset --hard origin/main", text)
        self.assertIn('if [ "$DISCOVERY_MODE" != "govern-only" ]; then', text)
        self.assertIn("python tools/enrich_tracking_people_from_sample_companies.py", text)
        self.assertIn("python tools/enrich_tracking_person_channels.py", text)
        self.assertIn("python tools/expand_tracking_entities.py", text)
        self.assertIn("python tools/tracking_seed_governance.py --check", text)
        self.assertIn("npm run validate:tracking", text)
        self.assertIn("npm run validate:taxonomy", text)
        self.assertNotIn("git pull --rebase origin main", text)

    def test_compound_entity_integrity_guards_initial_commit_and_replay(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(text.count("npm run validate:tracking-entities"), 2)

        initial = text.split("- name: Validate the expanded config before committing", 1)[1].split(
            "- name: Commit expanded tracking config", 1
        )[0]
        self.assertIn("npm run validate:tracking-entities", initial)
        self.assertLess(
            initial.index("npm run validate:tracking-entities"),
            initial.index("npm run validate:taxonomy"),
        )

        replay = text.split("regenerate_from_latest_main()", 1)[1].split(
            "if ! commit_current_config", 1
        )[0]
        self.assertIn("npm run validate:tracking-entities", replay)
        self.assertLess(
            replay.index("npm run validate:tracking-entities"),
            replay.index("npm run validate:taxonomy"),
        )

    def test_successful_push_relies_on_the_full_refresh_push_trigger(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("if git push origin HEAD:main; then", text)
        self.assertNotIn("gh workflow run scheduled-sync.yml --ref main", text)

    def test_workflow_keeps_the_shared_writer_queue(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: vciq-repository-writer-${{ github.ref }}", text)
        self.assertIn("queue: max", text)


if __name__ == "__main__":
    unittest.main()