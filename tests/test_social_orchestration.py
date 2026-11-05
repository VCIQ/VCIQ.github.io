"""Real journals/SQLite with injected collectors: no browser or remote platform."""
import copy
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from tests.social_orchestration_fixtures import NOW, result_for, tracking
from tests.test_social_contracts import fixture
from tools.social.contracts import PLATFORMS, ContractError, digest
from tools.social.guard import protected_snapshot
from tools.social.policy import load_policy
from tools.social.query_registry import build_query_registry
from tools.social.review import ReviewStore
from tools.social.scheduler import plan_jobs
from tools.social.scheduler_state import SchedulerStore, read_state
from tools.social.shadow_run import Coordinator, ROOT
from tools.social.shadow_state import load, save, request_stop, run_lock, run_prefix, stopped
from tools.social.signal_store import SignalStore
from workers.mediacrawler.upstream import PIN


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve() / "private"; self.root.mkdir(mode=0o700)
        self.roots = (ROOT,)
        self.runtime = fixture("runtime_config")
        self.runtime.update(enabled=True, stateDir=str(self.root), profileRoot=str(self.root / "profiles"), mediacrawlerDir=None)
        for p in PLATFORMS: self.runtime["platforms"][p]["enabled"] = True
        self.runtime_file = self.root / "runtime.json"
        self.save_runtime()
        self.policy = load_policy()
        self.policy["budget"].update(jobsPerPlatformPerRun=2, wallSecondsPerJob=10)
        self.calls, self.now = [], NOW
        self.coordinator = Coordinator(self.root, executor=self.execute, clock=lambda: self.now, monotonic=lambda: 0)
        for target in ("socket.create_connection", "socket.socket.connect", "urllib.request.urlopen", "subprocess.Popen"):
            self.enterContext(patch(target, side_effect=AssertionError("no external I/O")))

    def save_runtime(self):
        self.runtime_file.write_text(json.dumps(self.runtime)); self.runtime_file.chmod(0o600)

    def execute(self, job, context, **kwargs):
        self.calls.append(job["attemptId"])
        return result_for(job, now=self.now)

    def prepare(self, words=("机器人",), platforms=("xhs",)):
        self.registry = build_query_registry(tracking(words), self.policy, platforms=platforms)
        self.plan = plan_jobs(self.registry, read_state(self.root, repo_roots=self.roots), self.now, self.policy,
            vciq_commit="a" * 40, config_hash=digest({"synthetic": True}), upstream_commit=PIN)
        self.run_id = self.plan["jobs"][0]["runId"] if self.plan["jobs"] else None
        return self.plan

    def run_it(self, **options):
        return self.coordinator.run(self.plan, self.registry, self.policy, [], runtime=self.runtime,
            runtime_file=self.runtime_file, live=True, grant={"synthetic": True}, **options)

    def counts(self):
        with SignalStore(self.root, readonly=True) as source: return source.counts()

    def crashed_intent(self, *, result=False, checkpoint=False):
        self.prepare()
        prefix = run_prefix(self.run_id)
        save(self.root, prefix + "/intent.json", {"schemaVersion": 1, "plan": self.plan, "contexts": self.registry.by_id(),
            "policy": self.policy, "companies": []}, self.roots, exclusive=True)
        job = self.plan["jobs"][0]
        with SchedulerStore(self.root, repo_roots=self.roots) as store:
            store.sync(self.registry); store.claim(job, self.now)
            if checkpoint: store.finish(job, result_for(job), self.now, cadence_hours=24)
        save(self.root, prefix + "/journal.json", {"runId": self.run_id, "attempts": {job["attemptId"]: "started"}, "collectorInvocations": 1}, self.roots)
        if result: save(self.root, prefix + "/results/" + job["attemptId"] + ".json", result_for(job), self.roots, exclusive=True)
        return prefix, job

    def test_five_platforms_complete_storage_and_review(self):
        before = protected_snapshot(ROOT)
        self.prepare(platforms=PLATFORMS); result = self.run_it()
        self.assertTrue(result["ok"], result); self.assertTrue(result["batchIntegrityChecked"])
        self.assertEqual(result["receiptJobs"], 5); self.assertEqual(self.counts()["signals"], 5)
        with ReviewStore(self.root, readonly=True) as review:
            self.assertEqual(review.view()["total"], 5)
            self.assertTrue(all(r["item"]["status"] == "pending" for r in review.view()["items"]))
        self.assertEqual(before, protected_snapshot(ROOT))

    def test_recover_completed_is_readonly_and_never_requeries(self):
        self.prepare(); self.run_it()
        before = {p.name: p.read_bytes() for p in self.root.glob("*.sqlite3")}
        result = self.coordinator.recover(self.run_id)
        self.assertTrue(result["replayed"]); self.assertFalse(result["liveExecuted"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.glob("*.sqlite3")})

    def test_two_keywords_one_content_two_observations(self):
        self.prepare(words=("机器人", "机器人工程")); result = self.run_it()
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.counts()["signals"], 1); self.assertEqual(self.counts()["observations"], 2)

    def test_auth_failure_pauses_only_affected_platform(self):
        self.prepare(words=("机器人", "机器人产品"), platforms=("xhs", "wb"))
        def execute(job, context, **kwargs):
            self.calls.append(job["platform"])
            return result_for(job, status="auth_required", positive=False) if job["platform"] == "xhs" else result_for(job)
        self.coordinator.executor = execute
        result = self.run_it()
        self.assertFalse(result["ok"]); self.assertEqual(self.calls.count("xhs"), 1); self.assertEqual(self.calls.count("wb"), 2)
        self.assertEqual(result["notCompletedJobs"], 1)
        self.assertEqual(read_state(self.root, repo_roots=self.roots)["platforms"]["xhs"]["pauseReason"], "auth")
        self.assertFalse(stopped(self.root, self.roots))

    def test_partial_rows_saved_without_success_coverage(self):
        self.prepare(); self.coordinator.executor = lambda job, context, **kw: result_for(job, status="partial")
        result = self.run_it(); self.assertFalse(result["ok"]); self.assertEqual(result["observations"], 1)
        state = read_state(self.root, repo_roots=self.roots)
        self.assertIsNone(next(iter(state["queries"].values()))["lastCoveredAt"])

    def test_normal_empty_stored_with_receipt_not_missing(self):
        self.prepare(); self.coordinator.executor = lambda job, context, **kw: result_for(job, status="empty", positive=False)
        result = self.run_it(); self.assertTrue(result["ok"], result)
        self.assertEqual(self.counts()["attempts"], 1); self.assertEqual(self.counts()["signals"], 0)

    def test_stop_between_jobs_does_not_fabricate_receipt(self):
        self.prepare(words=("机器人", "机器人产品"))
        def execute(job, context, **kwargs):
            request_stop(self.root, self.roots)
            return self.execute(job, context, **kwargs)
        self.coordinator.executor = execute
        result = self.run_it(); self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["receiptJobs"], 1); self.assertEqual(result["notCompletedJobs"], 1)
        self.assertIn("stopped", [row["status"] for row in result["jobs"]])

    def test_runtime_disable_rechecked_between_jobs(self):
        self.prepare(words=("机器人", "机器人产品"))
        def execute(job, context, **kwargs):
            self.runtime["enabled"] = False; self.save_runtime()
            return self.execute(job, context, **kwargs)
        self.coordinator.executor = execute
        result = self.run_it(); self.assertEqual(len(self.calls), 1)
        self.assertIn("disabled", [row["status"] for row in result["jobs"]])

    def test_unexpected_executor_failure_stops_remaining_jobs(self):
        self.prepare(words=("机器人", "机器人产品"))
        def fail(*a, **kw): raise RuntimeError("secret-value-not-for-logs")
        self.coordinator.executor = fail
        result = self.run_it()
        self.assertTrue(result["checkpointReconciliationRequired"]); self.assertTrue(result["stopRequested"])
        self.assertEqual(result["receiptJobs"], 0); self.assertNotIn("secret-value", repr(result))
        self.assertFalse((self.root / "signals.sqlite3").exists())

    def test_corrupt_result_does_not_advance_scheduler(self):
        self.prepare()
        def execute(job, context, **kw):
            result = result_for(job); result["observations"][0]["contentHash"] = "f" * 64
            return result
        self.coordinator.executor = execute
        result = self.run_it(); self.assertFalse(result["ok"]); self.assertEqual(result["receiptJobs"], 0)
        self.assertIsNone(next(iter(read_state(self.root, repo_roots=self.roots)["queries"].values()))["lastCoveredAt"])

    def test_run_budget_prevents_start_not_fake_timeout(self):
        self.prepare(); result = self.run_it(wall_seconds=10)
        self.assertEqual(self.calls, []); self.assertEqual(result["jobs"][0]["status"], "wall_budget")
        self.assertFalse(result["batchIntegrityChecked"])

    def test_stop_marker_blocks_before_journal_or_scheduler(self):
        self.prepare(); request_stop(self.root, self.roots)
        with self.assertRaisesRegex(ContractError, "stop_requested"): self.run_it()
        self.assertFalse((self.root / "state.sqlite3").exists()); self.assertFalse((self.root / "orchestration").exists())

    def test_live_flag_and_runtime_are_both_required(self):
        self.prepare()
        with self.assertRaisesRegex(ContractError, "activation"):
            self.coordinator.run(self.plan, self.registry, self.policy, [], runtime=self.runtime, runtime_file=self.runtime_file)
        self.runtime["enabled"] = False
        with self.assertRaisesRegex(ContractError, "activation"): self.run_it()
        self.assertFalse((self.root / "state.sqlite3").exists())

    def test_one_coordinator_lock(self):
        self.prepare()
        with run_lock(self.root, self.roots):
            with self.assertRaisesRegex(ContractError, "run_busy"): self.run_it()

    def test_storage_failure_then_offline_recovery(self):
        self.prepare()
        with patch.object(SignalStore, "import_batch", side_effect=RuntimeError("synthetic interruption")):
            result = self.run_it()
        self.assertFalse(result["pipelineComplete"]); self.assertEqual(result["stage"], "import")
        recovered = self.coordinator.recover(self.run_id)
        self.assertTrue(recovered["ok"], recovered); self.assertFalse(recovered["liveExecuted"])
        self.assertEqual(len(self.calls), 1); self.assertEqual(self.counts()["observations"], 1)

    def test_review_failure_does_not_reimport_or_lose_data(self):
        self.prepare()
        with patch.object(ReviewStore, "materialize", side_effect=RuntimeError("synthetic interruption")):
            result = self.run_it()
        before = self.counts(); self.assertEqual(result["stage"], "review")
        self.assertTrue(self.coordinator.recover(self.run_id)["pipelineComplete"])
        self.assertEqual(self.counts()["observations"], before["observations"])
        self.assertEqual(len(self.calls), 1)

    def test_new_run_cannot_overtake_unfinished_storage(self):
        self.prepare()
        with patch.object(SignalStore, "import_batch", side_effect=RuntimeError()): self.run_it()
        self.prepare(words=("另一个机器人",))
        with self.assertRaisesRegex(ContractError, "recovery_required"): self.run_it()

    def test_pending_active_lease_is_not_assumed_dead(self):
        self.crashed_intent(result=True)
        report = self.coordinator.recover(self.run_id)
        self.assertEqual(report["error"], "shadow_worker_may_be_running")
        self.assertTrue(stopped(self.root, self.roots)); self.assertEqual(self.calls, [])

    def test_expired_result_can_import_but_cannot_advance_coverage(self):
        self.crashed_intent(result=True); self.now += timedelta(minutes=5)
        report = self.coordinator.recover(self.run_id)
        self.assertTrue(report["pipelineComplete"], report); self.assertFalse(report["ok"])
        self.assertTrue(report["checkpointReconciliationRequired"]); self.assertEqual(self.counts()["observations"], 1)
        self.assertEqual(self.calls, [])

    def test_checkpoint_before_crash_recovers_without_execution(self):
        self.crashed_intent(checkpoint=True)
        result = self.coordinator.recover(self.run_id)
        self.assertTrue(result["ok"], result); self.assertEqual(self.counts()["observations"], 1)
        self.assertEqual(self.calls, [])

    def test_no_result_after_crash_never_invents_receipt(self):
        self.crashed_intent(); self.now += timedelta(minutes=5)
        result = self.coordinator.recover(self.run_id)
        self.assertTrue(result["pipelineComplete"]); self.assertEqual(result["receiptJobs"], 0)
        self.assertEqual(result["jobs"][0]["status"], "interrupted_without_receipt")

    def test_checkpoint_and_saved_result_conflict_is_blocked(self):
        prefix, job = self.crashed_intent(result=True, checkpoint=True)
        changed = result_for(job); changed["diagnostics"]["retryAfterSeconds"] = 1
        save(self.root, prefix + "/results/" + job["attemptId"] + ".json", changed, self.roots)
        result = self.coordinator.recover(self.run_id)
        self.assertEqual(result["error"], "shadow_checkpoint_conflict")
        self.assertFalse((self.root / "signals.sqlite3").exists())

    def test_frozen_closure_cannot_add_late_result(self):
        prefix, job = self.crashed_intent(); self.now += timedelta(minutes=5)
        first = self.coordinator.recover(self.run_id)
        save(self.root, prefix + "/results/" + job["attemptId"] + ".json", result_for(job), self.roots, exclusive=True)
        second = self.coordinator.recover(self.run_id)
        self.assertEqual(first["receiptJobs"], second["receiptJobs"]); self.assertEqual(second["receiptJobs"], 0)

    def test_result_changed_after_close_cannot_be_imported(self):
        self.prepare()
        with patch.object(SignalStore, "import_batch", side_effect=RuntimeError()): self.run_it()
        job = self.plan["jobs"][0]; relative = run_prefix(self.run_id) + "/results/" + job["attemptId"] + ".json"
        changed = load(self.root, relative, self.roots); changed["diagnostics"]["retryAfterSeconds"] = 1
        save(self.root, relative, changed, self.roots)
        self.assertEqual(self.coordinator.recover(self.run_id)["error"], "shadow_result_changed_after_close")

    def test_tampered_intent_checksum_rejected(self):
        prefix, _ = self.crashed_intent()
        path = self.root / prefix / "intent.json"
        doc = json.loads(path.read_text()); doc["sha256"] = "0" * 64; path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ContractError, "checksum"): self.coordinator.recover(self.run_id)

    def test_plan_budget_and_context_mutation_refused(self):
        self.prepare(); self.plan["jobs"][0]["limits"]["maxRecords"] += 1
        self.plan["planId"] = digest({k: v for k, v in self.plan.items() if k not in {"planId", "generatedAt"}})
        with self.assertRaisesRegex(ContractError, "plan_mismatch"): self.run_it()

    def test_wechat_requires_explicit_combined_grant(self):
        self.prepare(platforms=("wechat",))
        with self.assertRaisesRegex(ContractError, "grant_required"):
            self.coordinator.run(self.plan, self.registry, self.policy, [], runtime=self.runtime, runtime_file=self.runtime_file, live=True)

    def test_invalid_run_id_cannot_escape_state(self):
        for value in ("../escape", "/tmp", "not-uuid"):
            with self.assertRaisesRegex(ContractError, "run_id"): self.coordinator.recover(value)


if __name__ == "__main__": unittest.main()
