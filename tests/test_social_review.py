"""Real private SQLite review transactions and immutable decisions; no platform I/O."""
import copy
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from tests.social_review_fixtures import add, rows, registry, request
from tools.social.contracts import ContractError
from tools.social.guard import GuardError
from tools.social.review import ReviewStore, DB_NAME
from tools.social.signal_store import SignalStore


class ReviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "private"; self.root.mkdir(mode=0o700)
        self.source = SignalStore(self.root, timeout=0.05); self.addCleanup(self.source.close)
        self.store = ReviewStore(self.root, timeout=0.05); self.addCleanup(self.store.close)
        self.index = registry(); add(self.source)

    def sync(self): return self.store.materialize(self.source, self.index)
    def item(self): return self.store.view()["items"][0]["item"]
    def decide(self, command=None, apply=True): return self.store.decide(self.source, self.index, command or request(self.item()), apply=apply)

    def test_materialize_pins_before_publishing(self):
        self.sync()
        self.assertEqual(self.source.counts()["evidence_pins"], 1)
        self.assertEqual(self.store.view()["total"], 1)
        self.assertFalse(self.item()["subject"]["companyId"])

    def test_sync_is_idempotent_and_keeps_terminal_status(self):
        self.sync(); self.decide(); version = self.store.queue_version()
        self.assertFalse(self.sync()["changed"])
        self.assertEqual(self.store.queue_version(), version)
        self.assertEqual(self.item()["status"], "accepted")

    def test_accept_never_promotes(self):
        self.sync(); result = self.decide()
        self.assertEqual(result["promotionStatus"], "awaiting-primary-evidence")
        self.assertFalse(result["factVerified"])
        self.assertFalse(result["productionChanged"])

    def test_reject_is_terminal(self):
        self.sync(); self.decide(request(self.item(), "rejected"))
        self.assertEqual(self.item()["status"], "rejected")
        with self.assertRaisesRegex(ContractError, "final_decision_conflict"): self.decide()

    def test_repeat_same_request_no_new_decision(self):
        self.sync(); command = request(self.item()); self.decide(command)
        before = self.store.db.total_changes
        result = self.decide(command)
        self.assertFalse(result["changed"]); self.assertTrue(result["replayed"])
        self.assertEqual(before, self.store.db.total_changes)

    def test_same_request_id_different_payload_rejected(self):
        self.sync(); command = request(self.item()); self.decide(command)
        command["note"] = "changed note"
        with self.assertRaisesRegex(ContractError, "request_id_conflict"): self.decide(command)

    def test_new_request_same_final_action_does_not_rewrite_actor(self):
        self.sync(); command = request(self.item()); self.decide(command)
        command["requestId"] = str(uuid4()); command["reviewedBy"] = "other-actor"
        self.assertFalse(self.decide(command)["changed"])
        actual = self.store.view()["items"][0]["decision"]["request"]["reviewedBy"]
        self.assertEqual(actual, "synthetic-reviewer")

    def test_preview_is_readonly_and_not_applied(self):
        self.sync(); command = request(self.item())
        files = {p.name: p.read_bytes() for p in self.root.glob("*.sqlite3")}
        with SignalStore(self.root, readonly=True) as source, ReviewStore(self.root, readonly=True) as store:
            self.assertFalse(store.decide(source, self.index, command)["applied"])
        self.assertEqual(files, {p.name: p.read_bytes() for p in self.root.glob("*.sqlite3")})
        self.assertEqual(self.item()["status"], "pending")

    def test_wrong_fingerprint_rejected(self):
        self.sync(); command = request(self.item()); command["candidateFingerprint"] = "f" * 64
        with self.assertRaisesRegex(ContractError, "evidence_changed"): self.decide(command)

    def test_stale_queue_rejected(self):
        self.sync(); command = request(self.item()); command["seenQueueVersion"] = "f" * 64
        with self.assertRaisesRegex(ContractError, "queue_stale"): self.decide(command)

    def test_changed_source_rejected_even_before_queue_rebuild(self):
        self.sync(); command = request(self.item())
        add(self.source, rows(at="2026-10-25T12:00:00Z", excerpt="新版证据"))
        with self.assertRaisesRegex(ContractError, "evidence_changed"): self.decide(command)

    def test_changed_evidence_creates_new_pending_revision(self):
        self.sync(); old = self.item(); self.decide(request(old))
        add(self.source, rows(at="2026-10-25T12:00:00Z", excerpt="新版证据")); self.sync()
        self.assertEqual(self.item()["status"], "pending")
        self.assertNotEqual(old["candidateKey"], self.item()["candidateKey"])
        self.assertEqual(self.store.view(history=True)["items"][0]["item"]["status"], "accepted")

    def test_inactive_candidate_rejected_but_exact_replay_allowed(self):
        self.sync(); command = request(self.item()); self.decide(command)
        add(self.source, rows(at="2026-10-25T12:00:00Z", excerpt="新版证据")); self.sync()
        self.assertTrue(self.decide(command)["replayed"])
        command["requestId"] = str(uuid4())
        with self.assertRaisesRegex(ContractError, "candidate_stale"): self.decide(command)

    def test_metric_changes_do_not_reopen_review(self):
        self.sync(); self.decide(); version = self.store.queue_version()
        newer = rows(at="2026-10-25T12:00:00Z"); newer[2][0]["metrics"]["likes"]["value"] = 100
        add(self.source, newer); self.sync()
        self.assertEqual(self.store.queue_version(), version)
        self.assertEqual(self.item()["status"], "accepted")

    def test_old_rejection_not_lost_when_same_revision_returns(self):
        self.sync(); self.decide(request(self.item(), "rejected"))
        add(self.source, rows(at="2026-10-25T12:00:00Z", excerpt="changed")); self.sync()
        add(self.source, rows(at="2026-10-26T12:00:00Z")); self.sync()
        self.assertEqual(self.item()["status"], "rejected")

    def test_saved_evidence_survives_retention(self):
        self.sync(); old = self.item()["evidence"][0]
        add(self.source, rows(at="2026-10-25T12:00:00Z", excerpt="changed")); self.sync()
        plan = self.source.retention_plan("2026-10-26T00:00:00Z")
        self.assertEqual(plan["versions"], 0)
        self.assertTrue(self.source.db.execute("SELECT 1 FROM versions WHERE content_hash=?", (old["contentHash"],)).fetchone())

    def test_pin_failure_prevents_queue_publication(self):
        with patch.object(self.source, "pin_evidence", side_effect=RuntimeError("synthetic")):
            with self.assertRaises(RuntimeError): self.sync()
        self.assertEqual(self.store.view()["total"], 0)

    def test_queue_failure_rolls_back_but_safe_orphan_pin_remains(self):
        with patch.object(self.store, "_write_item", side_effect=RuntimeError("synthetic")):
            with self.assertRaises(RuntimeError): self.sync()
        self.assertEqual(self.store.view()["total"], 0)
        self.assertEqual(self.source.counts()["evidence_pins"], 1)
        self.sync(); self.assertEqual(self.store.view()["total"], 1)

    def test_decision_failure_rolls_back_both_ledger_tables(self):
        self.sync()
        self.store.db.execute("CREATE TRIGGER fail_request BEFORE INSERT ON requests BEGIN SELECT RAISE(ABORT,'synthetic'); END")
        with self.assertRaisesRegex(ContractError, "database_error"): self.decide()
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 0)
        self.assertEqual(self.item()["status"], "pending")

    def test_busy_writer_does_not_partial_commit(self):
        self.sync()
        with ReviewStore(self.root, timeout=0.01) as other, other.transaction():
            with self.assertRaisesRegex(ContractError, "review_busy"): self.decide()
        self.assertEqual(self.item()["status"], "pending")

    def test_missing_pin_rejected(self):
        self.sync(); self.source.db.execute("DELETE FROM evidence_pins")
        with self.assertRaisesRegex(ContractError, "not_pinned"): self.decide()

    def test_registry_change_requires_rebuild(self):
        self.sync(); command = request(self.item())
        self.index = registry({"slug": "one", "name": "合成测试机器人", "aliases": []})
        with self.assertRaisesRegex(ContractError, "evidence_changed"): self.decide(command)

    def test_empty_actor_and_email_rejected(self):
        self.sync()
        for value in (" ", "a@example.invalid"):
            command = request(self.item()); command["reviewedBy"] = value
            with self.assertRaises(ContractError): self.decide(command)

    def test_malformed_request_never_echoes_secret(self):
        self.sync(); command = request(self.item()); command["note"] = "Cookie=PRIVATE"
        with self.assertRaises(ContractError) as caught: self.decide(command)
        self.assertNotIn("PRIVATE", str(caught.exception))

    def test_view_mutation_cannot_change_database(self):
        self.sync(); self.item()["claims"][0] = "mutation"
        self.assertNotEqual(self.item()["claims"][0], "mutation")

    def test_pagination_and_unknown_database(self):
        self.sync()
        with self.assertRaisesRegex(ContractError, "page_bounds"): self.store.view(limit=101)
        other = self.root / "other"; other.mkdir(mode=0o700)
        path = other / DB_NAME
        db = sqlite3.connect(path); db.execute("CREATE TABLE unrelated(x)"); db.commit(); db.close(); path.chmod(0o600)
        with self.assertRaisesRegex(ContractError, "store_schema"): ReviewStore(other)

    def test_readonly_missing_database_not_created(self):
        other = self.root / "other"; other.mkdir(mode=0o700)
        with self.assertRaisesRegex(ContractError, "store_missing"): ReviewStore(other, readonly=True)
        self.assertFalse((other / DB_NAME).exists())

    def test_symlink_and_public_permission_rejected(self):
        other = self.root / "other"; other.mkdir(mode=0o700)
        (other / DB_NAME).symlink_to(self.root / DB_NAME)
        with self.assertRaises(GuardError): ReviewStore(other)
        (self.root / DB_NAME).chmod(0o644)
        with self.assertRaises(GuardError): ReviewStore(self.root)

    def test_no_scheduler_or_production_files_created(self):
        self.sync(); self.decide()
        self.assertFalse((self.root / "state.sqlite3").exists())
        self.assertFalse((self.root / "public").exists())


if __name__ == "__main__": unittest.main()
