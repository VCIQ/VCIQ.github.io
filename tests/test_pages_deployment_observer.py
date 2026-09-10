import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "observe-pages-deployment.yml"


def workflow_shell(source, step_name):
    """Execute the actual embedded Bash, not a Python reimplementation."""
    step = source.split(f"      - name: {step_name}\n", 1)[1]
    step = step.split("\n      - name:", 1)[0]
    return textwrap.dedent(step.split("        run: |\n", 1)[1])


class PagesDeploymentObserverWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_observer_has_permission_to_recover_deferred_publication(self):
        self.assertIn("actions: write", self.source)

    def test_observer_distinguishes_workflow_success_from_real_deployment(self):
        self.assertIn("workflowName,jobs", self.source)
        self.assertIn('select(.name == "deploy")', self.source)
        self.assertIn('deployment_status="deferred"', self.source)
        self.assertIn("deploymentStatus", self.source)
        self.assertIn("deployConclusion", self.source)

    def test_observer_recovers_stale_tracking_snapshot(self):
        self.assertIn("tracking configuration is newer than the article snapshot", self.source)
        self.assertIn('deferred_reason="tracking_snapshot_refresh"', self.source)
        self.assertIn("gh workflow run scheduled-sync.yml", self.source)
        self.assertIn("--ref main", self.source)

    def test_independent_reconciliation_cannot_loop_on_diagnostic_writes(self):
        self.assertIn('cron: "17,47 * * * *"', self.source)
        trigger = self.source.split("\npermissions:", 1)[0]
        self.assertIn('".github/workflows/observe-pages-deployment.yml"', trigger)
        self.assertNotIn("diagnostics/", trigger)
        job = self.source.split("jobs:", 1)[1]
        self.assertIn("github.event_name == 'schedule'", job)
        self.assertIn("github.event_name == 'push'", job)
        self.assertEqual(self.source.count("if: steps.observe.outputs.recorded == 'true'"), 2)
        self.assertIn("group: vciq-pages-observer", self.source)
        self.assertIn("cancel-in-progress: false", self.source)


class PagesObserverShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # jq/bash are already required by the production observer. Missing
        # dependencies fail the tests rather than reporting a skipped success.
        for executable in ("bash", "jq", "python3", "git"):
            if not shutil.which(executable):
                raise RuntimeError(f"Observer shell tests require {executable}")
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "diagnostics").mkdir()
        (self.root / "bin").mkdir()
        self.status_path = self.root / "diagnostics/pages-latest-status.json"
        self.failure_path = self.root / "diagnostics/pages-latest-failure.txt"
        self.output = self.root / "output"
        self.output.write_text("")
        self.calls = self.root / "calls.jsonl"
        self.fixture = self.root / "run.json"
        self.env = {
            "PATH": f"{self.root / 'bin'}:{os.environ['PATH']}",
            "HOME": str(self.root),
            "GITHUB_OUTPUT": str(self.output),
            "GITHUB_REPOSITORY": "VCIQ/VCIQ.github.io",
            "RUNNER_TEMP": str(self.root),
            "EVENT_NAME": "schedule",
            "EVENT_RUN_ID": "",
            "FAKE_LATEST_ID": "3141",
            "FAKE_FIXTURE": str(self.fixture),
            "FAKE_CALLS": str(self.calls),
        }
        fake = self.root / "bin/gh"
        fake.write_text(textwrap.dedent('''\
            #!/usr/bin/env python3
            import json, os, sys
            args = sys.argv[1:]
            with open(os.environ["FAKE_CALLS"], "a") as stream:
                stream.write(json.dumps(args) + "\\n")
            if os.environ.get("FAKE_ERROR"):
                sys.exit(1)
            if args[:2] == ["run", "list"]:
                print(os.environ["FAKE_LATEST_ID"])
            elif args[:2] == ["run", "view"] and "--json" in args:
                with open(os.environ["FAKE_FIXTURE"]) as stream:
                    print(stream.read())
            elif args[:2] == ["run", "view"] and "--log" in args:
                print(os.environ.get("FAKE_BUILD_LOG", ""))
            elif args[:2] == ["run", "view"] and "--log-failed" in args:
                print("test failure log")
            elif args[:2] == ["workflow", "run"]:
                pass
            else:
                sys.exit(92)
            '''))
        fake.chmod(0o755)
        self.set_fixture()

    def set_fixture(self, **overrides):
        payload = {
            "databaseId": 3141, "status": "completed", "conclusion": "success",
            "createdAt": "2026-09-10T05:15:04Z", "updatedAt": "2026-09-10T05:21:17Z",
            "headSha": "a" * 40, "url": "https://github.com/VCIQ/VCIQ.github.io/actions/runs/3141",
            "event": "workflow_dispatch", "workflowName": "Build and deploy GitHub Pages",
            "jobs": [
                {"name": "build", "databaseId": 1, "conclusion": "success"},
                {"name": "deploy", "databaseId": 2, "conclusion": "success"},
            ],
        }
        payload.update(overrides)
        self.fixture.write_text(json.dumps(payload))
        return payload

    def run_step(self, name="Record latest Pages run and real deployment outcome", check=True):
        result = subprocess.run(
            ["bash", "-c", workflow_shell(self.source, name)], cwd=self.root,
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def recorded(self):
        values = dict(line.split("=", 1) for line in self.output.read_text().splitlines())
        return values.get("recorded") == "true"

    def gh_calls(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def test_delayed_old_event_reconciles_latest_completed_run(self):
        self.env["EVENT_RUN_ID"] = "3139"
        self.env["EVENT_NAME"] = "workflow_run"
        self.run_step()
        snapshot = json.loads(self.status_path.read_text())
        self.assertEqual(snapshot["databaseId"], 3141)
        self.assertEqual(snapshot["deploymentStatus"], "deployed")
        self.assertNotIn("jobs", snapshot)
        self.assertTrue(self.recorded())
        args = self.gh_calls()[0]
        self.assertEqual(args[args.index("--status") + 1], "completed")
        self.assertEqual(args[args.index("--branch") + 1], "main")
        self.assertEqual(args[args.index("--workflow") + 1], "pages.yml")

    def test_newer_failure_is_not_hidden_by_an_older_success(self):
        previous = self.set_fixture(databaseId=3140, createdAt="2026-09-10T05:07:20Z")
        self.status_path.write_text(json.dumps(previous))
        self.set_fixture(conclusion="failure", jobs=[
            {"name": "build", "databaseId": 1, "conclusion": "failure"},
            {"name": "deploy", "databaseId": 2, "conclusion": "skipped"},
        ])
        self.run_step()
        self.assertEqual(json.loads(self.status_path.read_text())["deploymentStatus"], "failed")
        self.assertIn("test failure log", self.failure_path.read_text())

    def test_workflow_success_without_successful_deploy_is_never_deployed(self):
        for outcome, expected in (("skipped", "deferred"), ("cancelled", "incomplete"), (None, "incomplete")):
            with self.subTest(outcome=outcome):
                self.set_fixture(jobs=[{"name": "deploy", "conclusion": outcome}])
                self.run_step()
                self.assertEqual(json.loads(self.status_path.read_text())["deploymentStatus"], expected)

    def test_absent_run_preserves_snapshot_without_recovery(self):
        self.status_path.write_text('{"sentinel": true}')
        self.env["FAKE_LATEST_ID"] = ""
        self.run_step()
        self.assertEqual(self.status_path.read_text(), '{"sentinel": true}')
        self.assertFalse(self.recorded())

    def test_api_failure_is_not_written_as_a_success(self):
        self.status_path.write_text('{"sentinel": true}')
        self.env["FAKE_ERROR"] = "1"
        self.assertNotEqual(self.run_step(check=False).returncode, 0)
        self.assertEqual(self.status_path.read_text(), '{"sentinel": true}')
        self.assertFalse(self.recorded())

    def test_mismatched_or_nonterminal_api_result_fails_closed(self):
        for override in ({"databaseId": 3139}, {"status": "in_progress"}, {"jobs": None}):
            with self.subTest(override=override):
                self.set_fixture(**override)
                self.assertNotEqual(self.run_step(check=False).returncode, 0)
                self.assertFalse(self.status_path.exists())
                self.assertFalse(self.recorded())

    def test_old_response_cannot_overwrite_newer_diagnostic(self):
        newer = self.set_fixture(databaseId=3142, createdAt="2026-09-10T06:00:00Z")
        original = json.dumps(newer)
        self.status_path.write_text(original)
        self.set_fixture(updatedAt="2026-09-11T00:00:00Z")
        self.run_step()
        self.assertEqual(self.status_path.read_text(), original)
        self.assertFalse(self.recorded())

    def test_older_observation_of_same_run_cannot_regress_diagnostic(self):
        newer = self.set_fixture(updatedAt="2026-09-11T00:00:00Z")
        original = json.dumps(newer)
        self.status_path.write_text(original)
        self.set_fixture()
        self.run_step()
        self.assertEqual(self.status_path.read_text(), original)
        self.assertFalse(self.recorded())

    def test_scheduled_bootstrap_and_delayed_events_cannot_start_full_refresh(self):
        self.status_path.write_text(json.dumps({
            "databaseId": 3141, "deploymentStatus": "deferred",
            "deferredReason": "tracking_snapshot_refresh",
        }))
        for event, event_id in (("schedule", ""), ("push", ""), ("workflow_run", "3139")):
            with self.subTest(event=event):
                self.env.update(EVENT_NAME=event, EVENT_RUN_ID=event_id)
                self.run_step("Recover a deferred stale-tracking publication")
                self.assertFalse(self.calls.exists())

    def test_current_event_and_manual_recovery_remain_available(self):
        self.status_path.write_text(json.dumps({
            "databaseId": 3141, "deploymentStatus": "deferred",
            "deferredReason": "tracking_snapshot_refresh",
        }))
        for event, event_id in (("workflow_dispatch", ""), ("workflow_run", "3141")):
            with self.subTest(event=event):
                self.env.update(EVENT_NAME=event, EVENT_RUN_ID=event_id)
                self.run_step("Recover a deferred stale-tracking publication")
                self.assertEqual(self.gh_calls()[-1][:3], ["workflow", "run", "scheduled-sync.yml"])

    def test_same_receipt_is_idempotent_and_clears_stale_failure_text(self):
        self.failure_path.write_text("old failure")
        self.run_step()
        first = self.status_path.read_bytes()
        self.run_step()
        self.assertEqual(first, self.status_path.read_bytes())
        self.assertEqual(self.failure_path.read_text(), "")

    def test_deferred_tracking_reason_is_derived_from_the_build_log(self):
        self.set_fixture(jobs=[
            {"name": "build", "databaseId": 1, "conclusion": "success"},
            {"name": "deploy", "databaseId": 2, "conclusion": "skipped"},
        ])
        self.env["FAKE_BUILD_LOG"] = "tracking configuration is newer than the article snapshot"
        self.run_step()
        self.assertEqual(json.loads(self.status_path.read_text())["deferredReason"], "tracking_snapshot_refresh")

    def test_unchanged_diagnostic_does_not_commit_or_push(self):
        self.run_step()
        for args in (["init", "-q"], ["config", "user.name", "Test"],
                     ["config", "user.email", "test@example.invalid"],
                     ["add", "diagnostics"], ["commit", "-qm", "baseline"]):
            subprocess.run(["git", *args], cwd=self.root, env=self.env, check=True,
                           capture_output=True, timeout=15)
        before = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, env=self.env)
        result = self.run_step("Publish diagnostic snapshot")
        after = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, env=self.env)
        self.assertEqual(before, after)
        self.assertIn("already current", result.stdout)


if __name__ == "__main__":
    unittest.main()
