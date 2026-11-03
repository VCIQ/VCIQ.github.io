"""CLI preview, health and recovery with real private databases, no live I/O."""
import contextlib
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from tests.social_orchestration_fixtures import result_for, tracking
from tests.test_social_contracts import fixture
from tools.social import shadow_run
from tools.social.batch import ROOT
from tools.social.contracts import digest
from tools.social.guard import protected_snapshot
from tools.social.health import health
from tools.social.policy import load_policy
from tools.social.review import ReviewStore
from tools.social.scheduler_state import SchedulerStore
from tools.social.shadow_state import load, save, run_prefix, request_stop


class ShadowCliTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve() / "private"; self.root.mkdir(mode=0o700)
        self.runtime = fixture("runtime_config")
        self.runtime.update(enabled=True, stateDir=str(self.root), profileRoot=str(self.root / "profiles"), mediacrawlerDir=None)
        self.runtime["platforms"]["xhs"]["enabled"] = True
        self.write("runtime.json", self.runtime)
        self.write("tracking.json", tracking())
        self.write("accounts.json", {"accounts": []})
        self.write("companies.json", {"companies": []})
        policy = load_policy(); policy["budget"]["wallSecondsPerJob"] = 10
        self.write("policy.json", policy)
        self.calls = []
        for target in ("socket.create_connection", "socket.socket.connect", "urllib.request.urlopen", "subprocess.Popen"):
            self.enterContext(patch(target, side_effect=AssertionError("live I/O forbidden")))
        self.enterContext(patch.object(shadow_run, "dispatch", self.execute))

    def write(self, name, value):
        path = self.root / name; path.write_text(json.dumps(value, ensure_ascii=False)); path.chmod(0o600)
        return path

    def execute(self, job, context, **kwargs):
        self.calls.append(job["attemptId"])
        return result_for(job, now=datetime.now(UTC).replace(microsecond=0))

    def invoke(self, command, *more):
        argv = [command, "--state-dir", str(self.root), "--runtime-config", str(self.root / "runtime.json")]
        if command == "run":
            for key, file in (("--config", "tracking.json"), ("--accounts", "accounts.json"), ("--policy", "policy.json")):
                argv += [key, str(self.root / file)]
            argv += ["--companies", "companies.json"]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = shadow_run.main(argv + list(more))
        return code, json.loads(out.getvalue() or err.getvalue())

    def test_preview_never_creates_run_database_or_browser(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        code, report = self.invoke("run")
        self.assertEqual(code, 0); self.assertEqual(report["status"], "preview")
        self.assertFalse(report["writesPerformed"]); self.assertEqual(self.calls, [])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_disabled_default_is_nonmutating(self):
        self.runtime["platforms"]["xhs"]["enabled"] = False; self.write("runtime.json", self.runtime)
        code, report = self.invoke("run")
        self.assertEqual(code, 0); self.assertEqual(report["status"], "disabled")
        self.assertFalse((self.root / "state.sqlite3").exists())

    def test_live_with_disabled_platform_refused(self):
        self.runtime["enabled"] = False; self.write("runtime.json", self.runtime)
        code, report = self.invoke("run", "--live", "--platform", "xhs")
        self.assertEqual(code, 2); self.assertEqual(report["error"], "live_activation_required")
        self.assertEqual(self.calls, [])

    def test_complete_cli_pipeline_and_recovery(self):
        before = protected_snapshot(ROOT)
        code, report = self.invoke("run", "--live")
        self.assertEqual(code, 0, report); self.assertEqual(report["receiptJobs"], 1)
        code, recovered = self.invoke("recover", "--run-id", report["runId"])
        self.assertEqual(code, 0); self.assertFalse(recovered["liveExecuted"]); self.assertEqual(len(self.calls), 1)
        with ReviewStore(self.root, readonly=True) as review: self.assertEqual(review.view()["total"], 1)
        self.assertEqual(before, protected_snapshot(ROOT))

    def test_health_does_not_claim_platform_readiness(self):
        code, report = self.invoke("health")
        self.assertEqual(code, 0); self.assertIsNone(report["content"]); self.assertIsNone(report["review"])
        self.assertEqual(report["runs"], []); self.assertFalse(report["writesPerformed"])
        self.assertTrue(all(p["liveAcceptance"] == "not_attested" for p in report["platforms"].values()))

    def test_health_includes_completed_run_and_review_backlog(self):
        self.invoke("run", "--live")
        before = {p.name: p.read_bytes() for p in self.root.glob("*.sqlite3")}
        code, report = self.invoke("health")
        self.assertEqual(code, 0); self.assertEqual(report["review"]["activeByStatus"], {"pending": 1})
        self.assertTrue(report["runs"][0]["pipelineComplete"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.glob("*.sqlite3")})

    def test_stop_and_explicit_resume_do_not_clear_platform_pause(self):
        with SchedulerStore(self.root, repo_roots=(ROOT,)) as store:
            store.db.execute("INSERT INTO social_platform_state(platform,pause_reason) VALUES('xhs','auth')")
        self.assertEqual(self.invoke("stop")[0], 0)
        self.assertTrue(self.invoke("health")[1]["stopRequested"])
        self.assertEqual(self.invoke("resume", "--confirmed")[0], 0)
        report = self.invoke("health")[1]
        self.assertFalse(report["stopRequested"]); self.assertEqual(report["platforms"]["xhs"]["pauseReason"], "auth")

    def test_resume_cannot_overtake_unfinished_run(self):
        with patch.object(shadow_run.SignalStore, "import_batch", side_effect=RuntimeError()): self.invoke("run", "--live")
        self.invoke("stop")
        code, report = self.invoke("resume", "--confirmed")
        self.assertEqual(code, 2); self.assertEqual(report["error"], "shadow_recovery_required")

    def test_invalid_recovery_id_and_missing_input_are_safe_errors(self):
        code, report = self.invoke("recover", "--run-id", "../PRIVATE")
        self.assertEqual(code, 2); self.assertNotIn("PRIVATE", repr(report))

    def test_readonly_health_refuses_corrupt_report(self):
        _, result = self.invoke("run", "--live")
        path = self.root / run_prefix(result["runId"]) / "report.json"
        value = json.loads(path.read_text()); value["sha256"] = "0" * 64; path.write_text(json.dumps(value))
        code, report = self.invoke("health")
        self.assertEqual(code, 2); self.assertEqual(report["error"], "shadow_journal_checksum")

    def test_runtime_path_mismatch_refused_before_execution(self):
        self.runtime["stateDir"] = str(self.root / "other"); self.write("runtime.json", self.runtime)
        self.assertEqual(self.invoke("run", "--live")[0], 2); self.assertEqual(self.calls, [])

    def test_evaluate_empty_assessment_not_false_success_rate(self):
        self.invoke("run", "--live")
        baseline = {"windowStart": "2026-01-01T00:00:00Z", "windowEnd": "2027-01-01T00:00:00Z", "complete": False, "articleIds": []}
        self.write("baseline.json", baseline)
        self.write("assessment.json", {"baselineHash": digest(baseline), "reviewedBy": "synthetic-reviewer", "events": []})
        code, report = self.invoke("evaluate", "--assessment", "assessment.json", "--baseline", "baseline.json")
        self.assertEqual(code, 0); self.assertEqual(report["status"], "not_evaluated")
        self.assertIsNone(report["additionalValidEvents"]); self.assertFalse(report["liveExecuted"])

    def test_missing_store_not_created_by_evaluate(self):
        self.write("assessment.json", {}); self.write("baseline.json", {})
        self.assertEqual(self.invoke("evaluate", "--assessment", "assessment.json", "--baseline", "baseline.json")[0], 2)
        self.assertFalse((self.root / "signals.sqlite3").exists())

    def test_paused_platform_has_zero_planned_jobs_not_new_queries(self):
        with SchedulerStore(self.root, repo_roots=(ROOT,)) as store:
            store.db.execute("INSERT INTO social_platform_state(platform,pause_reason) VALUES('xhs','auth')")
        code, report = self.invoke("run", "--live")
        self.assertEqual(code, 0); self.assertEqual(report["status"], "idle"); self.assertEqual(self.calls, [])


if __name__ == "__main__": unittest.main()
