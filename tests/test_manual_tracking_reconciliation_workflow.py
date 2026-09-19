from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class ManualTrackingReconciliationWorkflowTests(unittest.TestCase):
    def test_interactive_writers_only_nudge_the_cheap_coordinator(self) -> None:
        for name in ("manual-tracking.yml", "manual-tracking-batch.yml"):
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            handoff = text.split("\n  handoff:\n", 1)[1]
            self.assertIn("Defer heavy tracking reconciliation", handoff)
            self.assertIn(
                "gh workflow run manual-tracking-reconciliation.yml --ref main",
                handoff,
            )
            self.assertIn("actions: write", handoff)
            for workflow in (
                "scheduled-sync.yml",
                "frequent-intelligence-refresh.yml",
                "tracking-discovery.yml",
                "company-candidate-discovery.yml",
                "company-candidate-onboarding.yml",
            ):
                self.assertNotIn(f"gh workflow run {workflow}", handoff)

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
        trigger = text.split("permissions:", 1)[0]
        self.assertIn("push:", trigger)
        self.assertIn("branches: [main]", trigger)
        self.assertIn("tools/manual_tracking.py", trigger)
        self.assertIn("tools/manual_tracking_batch.py", trigger)
        self.assertNotIn("config/tracking_intents.json", trigger)
        self.assertNotIn("config/tracking_capture_inbox.json", trigger)
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
        self.assertIn("for status in queued in_progress", text)
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



class CheckoutFreeManualHandoffTests(unittest.TestCase):
    """Execute the actual workflow commands outside Git, not just string-match.

    The gh stand-in checks repository selection and failure propagation without
    credentials or a network call. Real coordinator recovery is checked separately.
    """

    WORKFLOW_NAMES = ("manual-tracking.yml", "manual-tracking-batch.yml")

    def command(self, name: str) -> str:
        handoff = (WORKFLOWS / name).read_text(encoding="utf-8").split("\n  handoff:\n", 1)[1]
        commands = re.findall(r"^\s+run: (gh workflow run .+)$", handoff, re.MULTILINE)
        self.assertEqual(len(commands), 1, name)
        return commands[0]

    def execute(self, command: str, *, exit_code: int = 0, ambient_repo: str = ""):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            gh = bin_dir / "gh"
            gh.write_text(f"#!{sys.executable}\n" + textwrap.dedent("""\
                import json, os, sys
                from pathlib import Path
                args = sys.argv[1:]
                with Path(os.environ["CALLS_FILE"]).open("a") as output:
                    output.write(json.dumps(args) + "\\n")
                if "--repo" not in args:
                    print("failed to run git: fatal: not a git repository", file=sys.stderr)
                    raise SystemExit(1)
                if args != ["workflow", "run", "manual-tracking-reconciliation.yml",
                            "--ref", "main", "--repo", "VCIQ/VCIQ.github.io"]:
                    print("unexpected dispatch target or arguments", file=sys.stderr)
                    raise SystemExit(2)
                failure = int(os.environ["GH_TEST_EXIT"])
                if failure:
                    print("simulated API authorization or provider failure", file=sys.stderr)
                    raise SystemExit(failure)
                print("coordinator dispatch accepted (test double)")
                """))
            gh.chmod(0o755)
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith(("GIT_", "GH_", "GITHUB_"))}
            env.update({
                "PATH": str(bin_dir) + os.pathsep + env.get("PATH", os.defpath),
                "GITHUB_REPOSITORY": "VCIQ/VCIQ.github.io",
                "GH_TEST_EXIT": str(exit_code),
                "CALLS_FILE": str(root / "calls.jsonl"),
                "GH_TOKEN": "test-only-not-a-credential",
            })
            if ambient_repo:
                env["GH_REPO"] = ambient_repo
            self.assertFalse((root / ".git").exists())
            # A failed handoff must never retry or modify the completed Apply.
            approved = root / "already-approved.json"
            approved.write_text('{"manualDecision":"approved","state":"active"}')
            before = approved.read_bytes()
            result = subprocess.run(
                ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", command],
                cwd=root, env=env, capture_output=True, text=True, timeout=10, check=False,
            )
            self.assertTrue((root / "calls.jsonl").exists(), result.stderr)
            calls = [json.loads(line) for line in (root / "calls.jsonl").read_text().splitlines()]
            self.assertEqual(approved.read_bytes(), before)
            return result, calls

    def test_both_writers_dispatch_once_without_a_checkout(self) -> None:
        for name in self.WORKFLOW_NAMES:
            with self.subTest(workflow=name):
                result, calls = self.execute(self.command(name))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(calls), 1)
                self.assertIn("accepted", result.stdout)

    def test_repository_is_explicit_even_with_conflicting_cli_defaults(self) -> None:
        for name in self.WORKFLOW_NAMES:
            with self.subTest(workflow=name):
                result, calls = self.execute(self.command(name), ambient_repo="unrelated/other")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(calls[0][-2:], ["--repo", "VCIQ/VCIQ.github.io"])

    def test_missing_repo_reproduces_the_reported_failure(self) -> None:
        for name in self.WORKFLOW_NAMES:
            with self.subTest(workflow=name):
                old_command = self.command(name).replace(' --repo "$GITHUB_REPOSITORY"', "")
                result, calls = self.execute(old_command)
                self.assertEqual(result.returncode, 1)
                self.assertIn("fatal: not a git repository", result.stderr)
                self.assertEqual(len(calls), 1)

    def test_real_dispatch_failure_is_not_hidden_or_retried(self) -> None:
        for name in self.WORKFLOW_NAMES:
            for exit_code in (1, 4):
                with self.subTest(workflow=name, code=exit_code):
                    result, calls = self.execute(self.command(name), exit_code=exit_code)
                    self.assertEqual(result.returncode, exit_code)
                    self.assertEqual(len(calls), 1)
                    self.assertNotIn("accepted", result.stdout)

    def test_success_gate_and_least_privilege_are_preserved(self) -> None:
        for name in self.WORKFLOW_NAMES:
            with self.subTest(workflow=name):
                handoff = (WORKFLOWS / name).read_text(encoding="utf-8").split("\n  handoff:\n", 1)[1]
                self.assertIn("needs: apply", handoff)
                self.assertIn("if: needs.apply.outputs.changed == 'true'", handoff)
                self.assertIn("actions: write", handoff)
                self.assertNotIn("contents: write", handoff)
                self.assertNotIn("actions/checkout@", handoff)
                self.assertNotIn("continue-on-error", handoff)
                self.assertNotIn("always()", handoff)
                self.assertNotIn("--mode apply", handoff)



if __name__ == "__main__":
    unittest.main()
