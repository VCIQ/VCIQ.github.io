"""Offline end-to-end export/import/inspect with synthetic private checkpoints."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.social_storage_fixtures import SEALED_AT, sample
from tests.test_social_contracts import fixture
from tools.social import storage_cli
from tools.social.batch import seal_batch
from tools.social.contracts import canonical_bytes, digest
from tools.social.guard import protected_snapshot
from tools.social.ingest import import_from_path
from tools.social.scheduler_state import SchedulerStore
from tools.social.signal_store import SignalStore


class StorageCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "private"; self.root.mkdir(mode=0o700)
        self.runtime = fixture("runtime_config")
        self.runtime.update(stateDir=str(self.root), profileRoot=str(self.root / "profiles"), mediacrawlerDir=None)
        self.write("runtime.json", self.runtime)
        self.rows = sample()
        self.plan = fixture("job_plan")
        self.plan["jobs"] = self.rows[0]
        self.plan["stats"] = dict(registeredQueries=1, eligibleQueries=1, excludedQueries=0, selectedJobs=1, deferredQueries=0)
        self.plan["planId"] = digest({k: v for k, v in self.plan.items() if k not in {"planId", "generatedAt"}})
        self.write("plan.json", self.plan)
        self.results = [{"receipt": self.rows[1][0], "observations": self.rows[2], "hints": [], "diagnostics": {"batchIntegrityChecked": False}}]
        self.write("results.json", self.results)
        for target in ("socket.create_connection", "urllib.request.urlopen", "subprocess.Popen"):
            self.enterContext(patch(target, side_effect=AssertionError("offline I/O boundary")))

    def write(self, name, value):
        path = self.root / name
        path.write_bytes(canonical_bytes(value)); path.chmod(0o600)
        return path

    def call(self, command, *options):
        args = [command, "--state-dir", str(self.root), "--runtime-config", str(self.root / "runtime.json"), *options]
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            code = storage_cli.main(args)
        return code, json.loads(out.getvalue() or err.getvalue())

    def seal(self):
        return self.call("seal", "--plan", str(self.root / "plan.json"), "--results", str(self.root / "results.json"), "--output", "batches/one", "--created-at", SEALED_AT)

    def test_seal_verify_import_inspect_without_live_or_production_change(self):
        before = protected_snapshot(storage_cli.ROOT)
        self.assertEqual(self.seal()[0], 0)
        code, result = self.call("verify", "--batch", "batches/one")
        self.assertEqual(code, 0); self.assertTrue(result["batchIntegrityChecked"])
        code, result = self.call("import", "--batch", "batches/one", "--apply")
        self.assertEqual(code, 0); self.assertFalse(result["liveExecuted"]); self.assertFalse(result["publish"])
        code, result = self.call("inspect")
        self.assertEqual(code, 0); self.assertEqual(result["counts"]["signals"], 1)
        self.assertEqual(before, protected_snapshot(storage_cli.ROOT))

    def test_import_defaults_to_verify_no_database_write(self):
        self.seal()
        code, result = self.call("import", "--batch", "batches/one")
        self.assertEqual(code, 0); self.assertFalse(result["applied"])
        self.assertFalse((self.root / "signals.sqlite3").exists())

    def test_repeat_cli_import_is_idempotent(self):
        self.seal()
        self.call("import", "--batch", "batches/one", "--apply")
        code, result = self.call("import", "--batch", "batches/one", "--apply")
        self.assertEqual(code, 0); self.assertTrue(result["duplicate"])
        self.assertEqual(result["insertedObservations"], 0)

    def test_reseal_without_explicit_time_reuses_original_manifest(self):
        first = self.seal()[1]
        code, second = self.call("seal", "--plan", str(self.root / "plan.json"), "--results", str(self.root / "results.json"), "--output", "batches/one")
        self.assertEqual(code, 0); self.assertEqual(first["manifestHash"], second["manifestHash"])

    def test_corrupt_batch_quarantines_without_opening_database(self):
        self.seal()
        (self.root / "batches/one/observations.jsonl").write_text("PRIVATE CORRUPTION")
        code, result = self.call("import", "--batch", "batches/one", "--apply")
        self.assertEqual(code, 1); self.assertTrue(result["quarantineRecorded"])
        self.assertFalse(result["contentCommitted"])
        self.assertFalse((self.root / "signals.sqlite3").exists())
        record = next((self.root / "quarantine").glob("*.json")).read_text()
        self.assertNotIn("PRIVATE", record)
        self.assertNotIn(str(self.root), record)
        self.assertTrue((self.root / "batches/one/observations.jsonl").exists())

    def test_import_conflict_does_not_change_existing_database(self):
        self.seal(); self.call("import", "--batch", "batches/one", "--apply")
        before = (self.root / "signals.sqlite3").read_bytes()
        self.rows[2][0]["metrics"]["likes"]["value"] = 1
        seal_batch(self.root, "batches/conflicting", *self.rows, created_at=SEALED_AT)
        code, result = self.call("import", "--batch", "batches/conflicting", "--apply")
        self.assertEqual(code, 1); self.assertEqual(result["error"], "store_run_conflict")
        self.assertEqual(before, (self.root / "signals.sqlite3").read_bytes())

    def test_invalid_source_path_not_echoed_in_quarantine(self):
        result = import_from_path(self.root, "../PRIVATE_INPUT_NAME")
        self.assertFalse(result["ok"]); self.assertTrue(result["quarantineRecorded"])
        self.assertNotIn("PRIVATE_INPUT_NAME", next((self.root / "quarantine").glob("*.json")).read_text())

    def test_checkpoint_export_readonly_and_hash_checked(self):
        job = self.rows[0][0]; result = self.results[0]
        with SchedulerStore(self.root, repo_roots=(storage_cli.ROOT,)) as store:
            store.db.execute("INSERT INTO social_query_results VALUES(?,?,?,?,?)", (job["attemptId"], job["queryId"], digest(result), canonical_bytes(result).decode(), result["receipt"]["completedAt"]))
        path = self.root / "state.sqlite3"; before = path.read_bytes()
        code, output = self.call("seal", "--plan", str(self.root / "plan.json"), "--from-checkpoints", "--output", "batches/checkpoint", "--created-at", SEALED_AT)
        self.assertEqual(code, 0); self.assertTrue(output["batchIntegrityChecked"])
        self.assertEqual(before, path.read_bytes())
        self.assertFalse((self.root / "signals.sqlite3").exists())

    def test_missing_checkpoint_does_not_publish_partial_batch(self):
        with SchedulerStore(self.root, repo_roots=(storage_cli.ROOT,)): pass
        code, result = self.call("seal", "--plan", str(self.root / "plan.json"), "--from-checkpoints", "--output", "batches/incomplete")
        self.assertEqual(code, 2); self.assertEqual(result["error"], "checkpoint_result_missing")
        self.assertFalse((self.root / "batches/incomplete").exists())

    def test_checkpoint_hash_mismatch_rejected(self):
        job = self.rows[0][0]; result = self.results[0]
        with SchedulerStore(self.root, repo_roots=(storage_cli.ROOT,)) as store:
            store.db.execute("INSERT INTO social_query_results VALUES(?,?,?,?,?)", (job["attemptId"], job["queryId"], "0" * 64, canonical_bytes(result).decode(), result["receipt"]["completedAt"]))
        code, result = self.call("seal", "--plan", str(self.root / "plan.json"), "--from-checkpoints", "--output", "batches/bad")
        self.assertEqual(code, 2); self.assertEqual(result["error"], "checkpoint_checksum")

    def test_missing_results_and_sensitive_diagnostics_rejected(self):
        self.write("results.json", [])
        self.assertEqual(self.seal()[0], 2)
        rows = copy.deepcopy(self.results); rows[0]["diagnostics"]["Cookie"] = "SYNTHETIC_SECRET"
        self.write("results.json", rows)
        code, result = self.seal()
        self.assertEqual(code, 2); self.assertNotIn("SYNTHETIC_SECRET", repr(result))

    def test_pin_and_retention_preview_do_not_promote_content(self):
        self.seal(); self.call("import", "--batch", "batches/one", "--apply")
        doc = self.rows[2][0]
        code, output = self.call("pin", "--reference", "review:synthetic", "--signal-id", doc["signalId"], "--content-hash", doc["contentHash"])
        self.assertEqual(code, 0); self.assertTrue(output["pinned"])
        self.assertFalse(output["publish"])
        code, output = self.call("retain", "--before", "2026-10-30T00:00:00Z")
        self.assertEqual(code, 0); self.assertFalse(output["applied"])
        self.assertEqual(output["versions"], 0)

    def test_inspect_missing_does_not_create_database(self):
        code, result = self.call("inspect")
        self.assertEqual(code, 2); self.assertEqual(result["error"], "store_missing")
        self.assertFalse((self.root / "signals.sqlite3").exists())

    def test_disabled_runtime_allows_explicit_offline_storage_only(self):
        self.assertFalse(self.runtime["enabled"])
        code, result = self.seal()
        self.assertEqual(code, 0); self.assertFalse(result["liveExecuted"])
        self.assertFalse((self.root / "profiles").exists())

    def test_runtime_path_mismatch_and_input_outside_state_rejected(self):
        self.runtime["stateDir"] = str(Path(self.tmp.name) / "other")
        self.write("runtime.json", self.runtime)
        self.assertEqual(self.seal()[0], 2)
        self.runtime["stateDir"] = str(self.root); self.write("runtime.json", self.runtime)
        code, result = self.call("seal", "--plan", str(Path(self.tmp.name) / "elsewhere.json"), "--results", str(self.root / "results.json"), "--output", "batches/outside")
        self.assertEqual(code, 2); self.assertEqual(result["error"], "input_outside_state")


if __name__ == "__main__": unittest.main()
