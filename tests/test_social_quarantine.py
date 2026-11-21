"""Real private files/SQLite; every collection result is synthetic and offline."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from tests.social_orchestration_fixtures import NOW, result_for, tracking
from tests.test_social_contracts import fixture
from tools.social import quarantine
from tools.social.contracts import ContractError, digest
from tools.social.guard import protected_snapshot
from tools.social.health import health
from tools.social.policy import load_policy
from tools.social.query_registry import build_query_registry
from tools.social.scheduler import plan_jobs
from tools.social.scheduler_state import SchedulerStore, read_state
from tools.social.shadow_run import Coordinator, ROOT
from tools.social.shadow_state import load, save, run_lock, run_prefix, stopped
from tools.social.signal_store import SignalStore
from tools.social.wechat_runner import atomic_json
from workers.mediacrawler.upstream import PIN


class QuarantineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve() / "private"; self.root.mkdir(mode=0o700)
        self.roots = (ROOT,)
        self.runtime = fixture("runtime_config")
        self.runtime.update(enabled=True, stateDir=str(self.root), profileRoot=str(self.root / "profiles"), mediacrawlerDir=None)
        for platform in self.runtime["platforms"]:
            self.runtime["platforms"][platform]["enabled"] = platform == "wechat"
        self.runtime_file = self.root / "runtime.json"
        self.runtime_file.write_text(json.dumps(self.runtime)); self.runtime_file.chmod(0o600)
        self.policy = load_policy()
        self.policy["budget"].update(jobsPerPlatformPerRun=2, recordsPerJob=1, wallSecondsPerJob=10)
        self.registry = build_query_registry(tracking(("机器人", "机器人工程")), self.policy, platforms=("wechat",), providers=("sogou-weixin",))
        self.plan = plan_jobs(self.registry, {}, NOW, self.policy, vciq_commit="a" * 40,
            config_hash=digest({"synthetic": True}), upstream_commit=PIN)
        self.run_id = self.plan["jobs"][0]["runId"]
        self.prefix = run_prefix(self.run_id)
        self.calls = []
        for target in ("socket.create_connection", "socket.socket.connect", "urllib.request.urlopen", "subprocess.Popen"):
            self.enterContext(patch(target, side_effect=AssertionError("external I/O forbidden")))
        self.coordinator = Coordinator(self.root, self.roots, clock=lambda: NOW, monotonic=lambda: 0, executor=self.execute)
        report = self.coordinator.run(self.plan, self.registry, self.policy, [], runtime=self.runtime,
            runtime_file=self.runtime_file, live=True, grant={"synthetic": True})
        self.assertEqual(report.get("error"), "batch_record_budget", report)
        self.now = NOW + timedelta(minutes=5)
        self.valid_job, self.bad_job = self.plan["jobs"]
        self.pending_path = "pending/" + self.bad_job["attemptId"] + ".json"

    def execute(self, job, context, **kwargs):
        self.calls.append(job["attemptId"])
        result = result_for(job, status="network_error", positive=False)
        if len(self.calls) == 2:
            receipt = result["receipt"]
            receipt.update(status="cancelled", stopReason="cancelled", errorCode="REQUEST_BUDGET_EXHAUSTED")
            receipt["counts"].update(searchItems=10, rawRows=3, rejectedRows=3, detailFailures=3)
            receipt["pageReceipts"] = [dict(pageIndex=1, schemaValid=True, contentItems=10, processed=False, hasMore=None)]
        atomic_json(self.root, "pending/" + job["attemptId"] + ".json", result, roots=self.roots)
        return result

    def preview(self):
        return quarantine.preview(self.root, self.run_id, roots=self.roots, now=self.now)

    def apply(self, fingerprint=None, **changes):
        options = dict(expected_fingerprint=fingerprint or self.preview()["fingerprint"], reviewed_by="synthetic-operator",
            workers_stopped=True, roots=self.roots, now=self.now)
        options.update(changes)
        return quarantine.apply(self.root, self.run_id, **options)

    def files(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def change_pending(self, change):
        value = json.loads((self.root / self.pending_path).read_text())
        change(value)
        atomic_json(self.root, self.pending_path, value, roots=self.roots)

    def test_preview_is_readonly_and_has_no_payload(self):
        before = self.files()
        result = self.preview()
        self.assertEqual(before, self.files())
        self.assertEqual(result["invalidReceiptJobs"], 1)
        self.assertEqual(result["validReceiptJobs"], 1)
        self.assertFalse(result["writesPerformed"])
        self.assertNotIn("REQUEST_BUDGET_EXHAUSTED", json.dumps(result))

    def test_apply_preserves_originals_and_never_turns_failure_green(self):
        before, protected = self.files(), protected_snapshot(ROOT)
        state = read_state(self.root, repo_roots=self.roots)
        result = self.apply()
        self.assertTrue(result["ok"], result)  # administrative operation, not crawl health
        self.assertFalse(result["runHealthy"])
        self.assertEqual(result["runStatus"], "degraded")
        self.assertTrue(result["stopRequested"])
        self.assertEqual(result["observations"], 0)
        for path, raw in before.items():
            if path != self.prefix + "/report.json":
                self.assertEqual((self.root / path).read_bytes(), raw, path)
        decision = load(self.root, self.prefix + "/quarantine.json", self.roots)
        self.assertEqual(decision["originalReportRaw"].encode(), before[self.prefix + "/report.json"])
        self.assertEqual(state, read_state(self.root, repo_roots=self.roots))
        self.assertEqual(protected, protected_snapshot(ROOT))
        self.assertEqual(len(self.calls), 2)
        with SignalStore(self.root, readonly=True) as store:
            self.assertEqual(store.counts()["signals"], 0)
            self.assertEqual(store.counts()["attempts"], 1)
        report = load(self.root, self.prefix + "/report.json", self.roots)
        invalid = next(row for row in report["jobs"] if row["status"] == "quarantined_invalid_result")
        self.assertEqual((invalid["rawRows"], invalid["maxRecords"]), (3, 1))
        self.assertFalse(invalid["receiptAccepted"])
        self.assertTrue(report["checkpointReconciliationRequired"])
        self.assertEqual(self.coordinator.unfinished(), [])

    def test_quota_is_not_reset_and_existing_allowance_still_exhausts(self):
        grant = dict(windowStart=NOW.isoformat(), windowEnd=(NOW + timedelta(hours=1)).isoformat(),
            combinedMaxRequests=2, productionReservedRequests=1)
        with SchedulerStore(self.root, repo_roots=self.roots) as store:
            store.consume_request(grant, self.bad_job["attemptId"], NOW)
        raw = (self.root / "state.sqlite3").read_bytes()
        self.apply()
        self.assertEqual(raw, (self.root / "state.sqlite3").read_bytes())
        with SchedulerStore(self.root, repo_roots=self.roots) as store:
            with self.assertRaisesRegex(ContractError, "request_budget_exhausted"):
                store.consume_request(grant, self.bad_job["attemptId"], self.now)

    def test_repeated_application_is_idempotent_and_keeps_actor(self):
        fingerprint = self.preview()["fingerprint"]
        self.apply(fingerprint)
        before = self.files()
        result = self.apply(fingerprint)
        self.assertTrue(result["replayed"])
        self.assertEqual(before, self.files())
        with self.assertRaisesRegex(ContractError, "decision_conflict"):
            self.apply(fingerprint, reviewed_by="other-operator")

    def test_recover_and_health_remain_degraded_without_new_queries(self):
        self.apply()
        report = self.coordinator.recover(self.run_id)
        self.assertFalse(report["ok"]); self.assertFalse(report["liveExecuted"])
        self.assertEqual(report["receiptJobs"], 1)
        view = health(self.root, self.roots)
        self.assertEqual(view["runs"][0]["status"], "degraded")
        self.assertEqual(view["scheduler"]["coveredEver"], 0)
        self.assertTrue(stopped(self.root, self.roots))
        self.assertEqual(len(self.calls), 2)

    def test_expired_lease_alone_does_not_authorize_apply(self):
        with self.assertRaisesRegex(ContractError, "workers_confirmation"):
            self.apply(workers_stopped=False)
        self.assertFalse((self.root / self.prefix / "quarantine.json").exists())

    def test_active_lease_refused_even_with_confirmation(self):
        with self.assertRaisesRegex(ContractError, "active_lease"):
            quarantine.preview(self.root, self.run_id, now=NOW)

    def test_stop_marker_must_exist(self):
        (self.root / "shadow.stop").unlink()
        with self.assertRaisesRegex(ContractError, "stop_required"):
            self.preview()

    def test_malformed_stop_is_not_authorization(self):
        (self.root / "shadow.stop").write_text('{"stop":false}')
        with self.assertRaisesRegex(ContractError, "stop_invalid"):
            self.preview()

    def test_wrong_fingerprint_refused_before_recording(self):
        with self.assertRaisesRegex(ContractError, "fingerprint_changed"):
            self.apply("0" * 64)
        self.assertFalse((self.root / self.prefix / "quarantine.json").exists())

    def test_changed_pending_invalidates_preview(self):
        fingerprint = self.preview()["fingerprint"]
        self.change_pending(lambda r: r["diagnostics"].update(requests=99))
        with self.assertRaisesRegex(ContractError, "fingerprint_changed"):
            self.apply(fingerprint)

    def test_changed_pending_after_apply_is_rejected(self):
        fingerprint = self.preview()["fingerprint"]
        self.apply(fingerprint)
        self.change_pending(lambda r: r["diagnostics"].update(requests=99))
        with self.assertRaisesRegex(ContractError, "evidence_changed"):
            self.apply(fingerprint)

    def test_valid_pending_cannot_be_quarantined(self):
        value = result_for(self.bad_job, status="network_error", positive=False)
        atomic_json(self.root, self.pending_path, value, roots=self.roots)
        with self.assertRaisesRegex(ContractError, "no_invalid_result"):
            self.preview()

    def test_nonempty_result_is_never_discarded(self):
        value = result_for(self.bad_job)
        atomic_json(self.root, self.pending_path, value, roots=self.roots)
        with self.assertRaisesRegex(ContractError, "nonempty_result"):
            self.preview()

    def test_auth_verification_and_rate_limit_cannot_use_quarantine(self):
        original = (self.root / self.pending_path).read_bytes()
        for status, reason in (("auth_required", "auth"), ("verification_required", "verification"), ("rate_limited", "rate_limit")):
            with self.subTest(status=status):
                value = json.loads(original)
                value["receipt"].update(status=status, stopReason=reason)
                atomic_json(self.root, self.pending_path, value, roots=self.roots)
                with self.assertRaisesRegex(ContractError, "restricted_result"):
                    self.preview()

    def test_existing_platform_pause_is_not_cleared(self):
        with SchedulerStore(self.root, repo_roots=self.roots) as store:
            store.db.execute("UPDATE social_platform_state SET pause_reason='auth' WHERE platform='wechat'")
        before = (self.root / "state.sqlite3").read_bytes()
        with self.assertRaisesRegex(ContractError, "platform_pause"):
            self.preview()
        self.assertEqual(before, (self.root / "state.sqlite3").read_bytes())

    def test_missing_started_result_is_not_fabricated(self):
        (self.root / self.pending_path).unlink()
        with self.assertRaisesRegex(ContractError, "missing_execution_evidence"):
            self.preview()

    def test_conflicting_sources_refused(self):
        value = json.loads((self.root / self.pending_path).read_text())
        value["diagnostics"]["requests"] = 8
        save(self.root, self.prefix + "/results/" + self.bad_job["attemptId"] + ".json", value, self.roots)
        with self.assertRaisesRegex(ContractError, "result_conflict"):
            self.preview()

    def test_incorrect_identity_is_not_budget_recovery(self):
        self.change_pending(lambda r: r["receipt"].update(queryId="d" * 64))
        with self.assertRaises(ContractError):
            self.preview()

    def test_unknown_failure_report_refused(self):
        report = load(self.root, self.prefix + "/report.json", self.roots)
        report["error"] = "other_error"
        save(self.root, self.prefix + "/report.json", report, self.roots)
        with self.assertRaisesRegex(ContractError, "known_failure_required"):
            self.preview()

    def test_existing_closure_without_our_audit_refused(self):
        save(self.root, self.prefix + "/closure.json", {"synthetic": True}, self.roots)
        with self.assertRaisesRegex(ContractError, "already_closed"):
            self.preview()

    def test_invalid_checkpoint_is_not_rewritten(self):
        result = json.loads((self.root / self.pending_path).read_text())
        with SchedulerStore(self.root, repo_roots=self.roots) as store:
            store.finish(self.bad_job, result, NOW, cadence_hours=24)
        with self.assertRaisesRegex(ContractError, "unsupported_invalid_result"):
            self.preview()

    def test_existing_valid_saved_file_cannot_be_removed_after_apply(self):
        self.apply()
        (self.root / self.prefix / "results" / (self.valid_job["attemptId"] + ".json")).unlink()
        with self.assertRaisesRegex(ContractError, "evidence_changed"):
            self.preview()

    def test_interrupted_after_audit_retries_without_recollecting(self):
        saved_path = self.root / self.prefix / "results" / (self.valid_job["attemptId"] + ".json")
        saved_path.unlink()  # valid result remains in its checkpoint and pending file
        fingerprint = self.preview()["fingerprint"]
        real_save = quarantine.save
        def interrupt(root, relative, value, roots, **kwargs):
            if relative.endswith("/closure.json"):
                raise OSError("synthetic interruption")
            return real_save(root, relative, value, roots, **kwargs)
        with patch.object(quarantine, "save", side_effect=interrupt):
            with self.assertRaises(OSError):
                self.apply(fingerprint)
        self.assertTrue((self.root / self.prefix / "quarantine.json").exists())
        self.assertTrue(saved_path.exists())
        result = self.apply(fingerprint)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(self.calls), 2)

    def test_import_failure_is_retryable_with_same_decision(self):
        fingerprint = self.preview()["fingerprint"]
        with patch.object(SignalStore, "import_batch", side_effect=RuntimeError("synthetic interruption")):
            first = self.apply(fingerprint)
        self.assertFalse(first["ok"]); self.assertFalse(first["pipelineComplete"])
        self.assertTrue(self.apply(fingerprint)["ok"])
        self.assertEqual(len(self.calls), 2)

    def test_changed_closure_is_rejected(self):
        fingerprint = self.preview()["fingerprint"]
        self.apply(fingerprint)
        closure = load(self.root, self.prefix + "/closure.json", self.roots)
        closure["checkpointReconciliationRequired"] = False
        save(self.root, self.prefix + "/closure.json", closure, self.roots)
        with self.assertRaisesRegex(ContractError, "closure_changed"):
            self.apply(fingerprint)

    def test_actor_and_path_validation(self):
        for actor in (None, "", "email@example.invalid", "PRIVATE\nvalue"):
            with self.subTest(actor=actor), self.assertRaisesRegex(ContractError, "reviewer"):
                self.apply(reviewed_by=actor)
        with self.assertRaises(ContractError):
            quarantine.preview(self.root, "../outside", now=self.now)

    def test_symlinked_pending_refused(self):
        path = self.root / self.pending_path
        other = self.root / "original-pending.json"
        path.rename(other); path.symlink_to(other)
        with self.assertRaises(Exception):
            self.preview()

    def test_public_permissions_refused(self):
        (self.root / self.pending_path).chmod(0o644)
        with self.assertRaises(Exception):
            self.preview()

    def test_cli_default_is_readonly_then_explicit_apply(self):
        args = ["--state-dir", str(self.root), "--runtime-config", str(self.runtime_file), "--run-id", self.run_id]
        before = self.files()
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(quarantine.main(args), 0)
        fingerprint = json.loads(stream.getvalue())["fingerprint"]
        self.assertEqual(before, self.files())
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(quarantine.main(args + ["--apply", "--expected-fingerprint", fingerprint,
                "--reviewed-by", "synthetic-operator", "--confirm-workers-stopped"]), 0)
        self.assertFalse(json.loads(stream.getvalue())["runHealthy"])

    def test_cli_bad_actor_is_not_echoed(self):
        args = ["--state-dir", str(self.root), "--runtime-config", str(self.runtime_file), "--run-id", self.run_id,
            "--apply", "--expected-fingerprint", self.preview()["fingerprint"], "--reviewed-by", "PRIVATE@example.invalid",
            "--confirm-workers-stopped"]
        with contextlib.redirect_stderr(io.StringIO()) as stream:
            self.assertEqual(quarantine.main(args), 2)
        self.assertNotIn("PRIVATE", stream.getvalue())

    def test_coordinator_lock_cannot_be_bypassed(self):
        fingerprint = self.preview()["fingerprint"]
        with run_lock(self.root, self.roots):
            with self.assertRaisesRegex(ContractError, "run_busy"):
                self.apply(fingerprint)


if __name__ == "__main__":
    unittest.main()
