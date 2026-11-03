"""Atomicity, idempotency, identity and retention of synthetic shadow evidence."""
import copy
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from tests.social_storage_fixtures import SEALED_AT, combined, no_result, sample
from tools.social.batch import VerifiedBatch, build_batch
from tools.social.contracts import ContractError, content_hash
from tools.social.guard import GuardError
from tools.social.retention import retain
from tools.social.signal_store import DB_NAME, SignalStore


class SignalStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "private"
        self.root.mkdir(mode=0o700)
        self.store = SignalStore(self.root, timeout=0.05)
        self.addCleanup(self.store.close)
        self.rows = sample()

    def bundle(self, rows=None):
        return build_batch(*(rows or self.rows), created_at=SEALED_AT)

    def add(self, rows=None):
        return self.store.import_batch(self.bundle(rows))

    def changed(self, *, at="2026-10-25T12:00:00Z", title="changed synthetic content"):
        rows = sample(at=at)
        rows[2][0]["title"] = title
        rows[2][0]["contentHash"] = content_hash(rows[2][0])
        return rows

    def test_duplicate_batch_changes_nothing(self):
        first = self.add(); before = self.store.counts()
        second = self.add()
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["insertedObservations"], 0)
        self.assertEqual(before, self.store.counts())

    def test_all_five_platforms_share_store_not_identity(self):
        run = self.rows[0][0]["runId"]
        self.add(combined(*(sample(p, run_id=run) for p in ("wechat", "xhs", "wb", "bili", "zhihu"))))
        counts = self.store.counts()
        self.assertEqual(counts["signals"], 5)
        self.assertEqual(counts["observations"], 5)
        self.assertEqual(counts["attempts"], 5)

    def test_two_queries_one_content_two_provenance_records(self):
        self.add()
        self.add(sample(keyword="another literal query"))
        counts = self.store.counts()
        self.assertEqual((counts["signals"], counts["versions"], counts["observations"]), (1, 1, 2))
        queries = {json.loads(r[0])["queryId"] for r in self.store.db.execute("SELECT payload_json FROM observations")}
        self.assertEqual(len(queries), 2)

    def test_content_change_creates_version(self):
        self.add(); result = self.add(self.changed())
        self.assertEqual(result["insertedSignals"], 0)
        self.assertEqual(result["insertedVersions"], 1)
        self.assertEqual(self.store.counts()["versions"], 2)

    def test_engagement_change_does_not_create_content_version(self):
        self.add()
        rows = sample(at="2026-10-26T12:00:00Z")
        rows[2][0]["metrics"]["likes"]["value"] = 99
        self.add(rows)
        current = self.store.get_signal(rows[2][0]["signalId"])
        self.assertEqual(self.store.counts()["versions"], 1)
        self.assertEqual(current["latest"]["metrics"]["likes"]["value"], 99)

    def test_older_batch_does_not_roll_back_latest_content_or_metrics(self):
        recent = self.changed(); recent[2][0]["metrics"]["likes"]["value"] = 42
        self.add(recent)
        self.add(self.changed(at="2026-10-20T12:00:00Z", title="older"))
        current = self.store.get_signal(recent[2][0]["signalId"])
        self.assertEqual(current["latest"]["title"], "changed synthetic content")
        self.assertEqual(current["latest"]["metrics"]["likes"]["value"], 42)
        self.assertTrue(current["firstSeenAt"].startswith("2026-10-20"))
        self.assertTrue(current["lastSeenAt"].startswith("2026-10-25"))

    def test_equal_time_selection_is_import_order_independent(self):
        first, second = self.changed(title="A"), self.changed(title="B")
        self.add(first); self.add(second)
        root2 = Path(self.tmp.name) / "second"; root2.mkdir(mode=0o700)
        with SignalStore(root2) as store:
            store.import_batch(self.bundle(second)); store.import_batch(self.bundle(first))
            self.assertEqual(self.store.get_signal(first[2][0]["signalId"]), store.get_signal(first[2][0]["signalId"]))

    def test_empty_and_failure_do_not_clear_existing_data(self):
        self.add()
        for status in ("empty", "network_error"):
            self.add(no_result(sample(), status=status))
        counts = self.store.counts()
        self.assertEqual((counts["signals"], counts["versions"], counts["observations"]), (1, 1, 1))
        self.assertEqual(counts["attempts"], 3)

    def test_partial_keeps_evidence_and_original_failure_receipt(self):
        self.rows[1][0].update(status="partial", completeness="incomplete", stopReason="network", errorCode="SYNTHETIC_LATER_FAILURE")
        self.add()
        receipt = json.loads(self.store.db.execute("SELECT receipt_json FROM attempts").fetchone()[0])
        self.assertEqual(receipt["status"], "partial")
        self.assertEqual(self.store.counts()["observations"], 1)

    def test_same_run_different_manifest_is_conflict(self):
        self.add(); before = self.store.counts()
        rows = copy.deepcopy(self.rows)
        rows[2][0]["title"] = "different"; rows[2][0]["contentHash"] = content_hash(rows[2][0])
        with self.assertRaisesRegex(ContractError, "run_conflict"): self.add(rows)
        self.assertEqual(before, self.store.counts())

    def test_attempt_cannot_be_reused_by_another_run(self):
        self.add(); before = self.store.counts()
        rows = copy.deepcopy(self.rows)
        run = str(uuid4())
        for group in rows:
            for row in group: row["runId"] = run
        with self.assertRaisesRegex(ContractError, "attempt_reuse"): self.add(rows)
        self.assertEqual(before, self.store.counts())

    def test_transaction_failure_rolls_back_every_table(self):
        before = self.store.counts()
        original = self.store._add_observation
        def fail_after_insert(doc):
            original(doc)
            raise RuntimeError("synthetic crash")
        with patch.object(self.store, "_add_observation", side_effect=fail_after_insert), self.assertRaises(RuntimeError): self.add()
        self.assertEqual(before, self.store.counts())
        self.assertTrue(self.add()["ok"])

    def test_sqlite_error_rolls_back_and_does_not_echo_sql(self):
        before = self.store.counts()
        with patch.object(self.store, "_add_observation", side_effect=sqlite3.IntegrityError("PRIVATE SQL")), self.assertRaises(ContractError) as caught: self.add()
        self.assertNotIn("PRIVATE", str(caught.exception))
        self.assertEqual(before, self.store.counts())

    def test_busy_writer_fails_without_partial_commit(self):
        other = sqlite3.connect(self.store.path, isolation_level=None)
        try:
            other.execute("BEGIN IMMEDIATE")
            with self.assertRaisesRegex(ContractError, "store_busy"): self.add()
        finally:
            other.execute("ROLLBACK"); other.close()
        self.assertEqual(self.store.counts()["batches"], 0)
        self.assertTrue(self.add()["ok"])

    def test_forged_verified_type_is_revalidated(self):
        bundle = self.bundle(); files = dict(bundle.payloads)
        files["observations.jsonl"] += b"\n"
        forged = VerifiedBatch(bundle.manifest_bytes, tuple(files.items()))
        with self.assertRaises(ContractError): self.store.import_batch(forged)
        self.assertEqual(self.store.counts()["batches"], 0)

    def test_bvid_cannot_map_to_two_aids_atomic_rollback(self):
        first = sample("bili")
        first[2][0]["nativeAliases"] = ["bvid:BV1xx411c7mD"]
        self.add(first); before = self.store.counts()
        second = sample("bili")
        doc = second[2][0]
        doc.update(nativeId="987654321", signalId="bili:video:987654321", canonicalUrl="https://www.bilibili.com/video/av987654321", nativeAliases=["bvid:BV1xx411c7mD"])
        doc["contentHash"] = content_hash(doc)
        with self.assertRaisesRegex(ContractError, "alias_identity_conflict"): self.add(second)
        self.assertEqual(before, self.store.counts())

    def test_aid_cannot_claim_second_bvid(self):
        first = sample("bili"); first[2][0]["nativeAliases"] = ["bvid:BV1xx411c7mD"]
        self.add(first)
        second = sample("bili"); second[2][0]["nativeAliases"] = ["bvid:BV1xx411c7mE"]
        with self.assertRaisesRegex(ContractError, "aid_alias_conflict"): self.add(second)

    def test_alias_enrichment_does_not_create_content_version(self):
        self.add(sample("bili"))
        second = sample("bili"); second[2][0]["nativeAliases"] = ["bvid:BV1xx411c7mD"]
        self.add(second)
        self.assertEqual(self.store.counts()["versions"], 1)
        self.assertEqual(self.store.counts()["aliases"], 1)

    def test_wrong_canonical_identity_rejected(self):
        self.rows[2][0]["canonicalUrl"] = "https://www.xiaohongshu.com/explore/000000000000000000000099"
        with self.assertRaisesRegex(ContractError, "url_identity"): self.add()
        self.assertEqual(self.store.counts()["signals"], 0)

    def test_answer_parent_is_immutable_but_not_primary_key(self):
        rows = sample("zhihu")
        doc = rows[2][0]
        doc.update(contentType="answer", nativeId="123", signalId="zhihu:answer:123", canonicalUrl="https://www.zhihu.com/question/456/answer/123", textScope="answer_excerpt", nativeAliases=[])
        doc["contentHash"] = content_hash(doc)
        self.add(rows)
        second = sample("zhihu")
        other = copy.deepcopy(doc)
        for key in ("jobId", "queryId", "runId", "attemptId"):
            other[key] = second[0][0][key]
        other["canonicalUrl"] = "https://www.zhihu.com/question/789/answer/123"
        second[2][0] = other
        with self.assertRaisesRegex(ContractError, "answer_parent_conflict"): self.add(second)

    def test_unknown_alias_family_rejected(self):
        self.rows[2][0]["nativeAliases"] = ["unverified:alias"]
        with self.assertRaisesRegex(ContractError, "alias_not_supported"): self.add()

    def test_readonly_open_and_returned_objects_do_not_write(self):
        self.add()
        before = self.store.path.read_bytes()
        with SignalStore(self.root, readonly=True) as store:
            result = store.get_signal(self.rows[2][0]["signalId"])
            result["latest"]["title"] = "local mutation"
            with self.assertRaisesRegex(ContractError, "readonly"): store.import_batch(self.bundle())
        self.assertEqual(before, self.store.path.read_bytes())
        self.assertNotEqual(self.store.get_signal(self.rows[2][0]["signalId"])["latest"]["title"], "local mutation")

    def test_missing_readonly_database_is_not_created(self):
        root = Path(self.tmp.name) / "empty"; root.mkdir(mode=0o700)
        with self.assertRaisesRegex(ContractError, "store_missing"): SignalStore(root, readonly=True)
        self.assertEqual(list(root.iterdir()), [])

    def test_unknown_database_is_not_migrated_or_overwritten(self):
        root = Path(self.tmp.name) / "foreign"; root.mkdir(mode=0o700)
        path = root / DB_NAME
        with sqlite3.connect(path) as db: db.execute("CREATE TABLE foreign_data(value TEXT)")
        path.chmod(0o600)
        before = path.read_bytes()
        with self.assertRaisesRegex(ContractError, "schema_version"): SignalStore(root)
        self.assertEqual(before, path.read_bytes())

    def test_migration_fingerprint_mismatch_rejected(self):
        self.store.db.execute("UPDATE storage_meta SET migration_hash=?", ("0" * 64,))
        with self.assertRaisesRegex(ContractError, "migration_mismatch"): SignalStore(self.root)

    def test_database_symlink_and_sidecar_symlink_rejected(self):
        root = Path(self.tmp.name) / "linked"; root.mkdir(mode=0o700)
        (root / DB_NAME).symlink_to(self.store.path)
        with self.assertRaises(GuardError): SignalStore(root)
        (root / DB_NAME).unlink()
        (root / (DB_NAME + "-journal")).symlink_to(self.store.path)
        with self.assertRaises(GuardError): SignalStore(root)

    def test_evidence_pin_is_idempotent_and_cannot_retarget(self):
        self.add(); doc = self.rows[2][0]
        self.assertTrue(self.store.pin_evidence("review:one", doc["signalId"], doc["contentHash"]))
        self.assertFalse(self.store.pin_evidence("review:one", doc["signalId"], doc["contentHash"]))
        newer = self.changed(); self.add(newer)
        with self.assertRaisesRegex(ContractError, "reference_conflict"):
            self.store.pin_evidence("review:one", doc["signalId"], newer[2][0]["contentHash"])

    def test_missing_evidence_cannot_be_pinned(self):
        with self.assertRaisesRegex(ContractError, "evidence_missing"):
            self.store.pin_evidence("review:missing", self.rows[2][0]["signalId"], self.rows[2][0]["contentHash"])

    def test_retention_never_removes_current_version(self):
        self.add()
        plan = self.store.retention_plan("2026-10-30T00:00:00Z")
        self.assertEqual(plan["versions"], 0)

    def test_pinned_old_version_and_its_observations_survive(self):
        self.add(); doc = self.rows[2][0]
        self.store.pin_evidence("review:pinned", doc["signalId"], doc["contentHash"])
        self.add(self.changed())
        plan = self.store.retention_plan("2026-10-30T00:00:00Z")
        self.assertEqual(plan["versions"], 0)
        self.assertEqual(self.store.counts()["observations"], 2)

    def test_retention_preview_readonly_apply_requires_hash(self):
        self.add(); self.add(self.changed())
        changes = self.store.db.total_changes
        preview = retain(self.store, "2026-10-30T00:00:00Z")
        self.assertFalse(preview["applied"])
        self.assertEqual(preview["versions"], 1)
        self.assertEqual(changes, self.store.db.total_changes)
        with self.assertRaisesRegex(ContractError, "plan_hash_required"):
            retain(self.store, preview["cutoff"], apply=True)

    def test_retention_tombstone_prevents_replay_resurrection(self):
        self.add(); self.add(self.changed())
        before = "2026-10-30T00:00:00Z"
        plan = self.store.retention_plan(before)
        result = self.store.apply_retention(before, plan["planHash"])
        self.assertEqual(result["versionsRemoved"], 1)
        self.assertEqual(self.store.counts()["observations"], 1)
        self.assertTrue(self.add()["duplicate"])
        self.assertEqual(self.store.counts()["versions"], 1)
        self.assertEqual(self.store.counts()["attempts"], 2)
        self.assertEqual(self.store.counts()["batches"], 2)

    def test_retention_plan_invalidated_by_new_evidence_pin(self):
        self.add(); self.add(self.changed())
        before = "2026-10-30T00:00:00Z"; plan = self.store.retention_plan(before)
        doc = self.rows[2][0]
        self.store.pin_evidence("review:late", doc["signalId"], doc["contentHash"])
        with self.assertRaisesRegex(ContractError, "stale_plan"):
            self.store.apply_retention(before, plan["planHash"])
        self.assertEqual(self.store.counts()["versions"], 2)

    def test_retention_future_or_naive_time_rejected(self):
        for value in ("2036-10-30T00:00:00Z", "2026-10-30", "not-a-date"):
            with self.subTest(value=value), self.assertRaises(ContractError): self.store.retention_plan(value)

    def test_scheduler_database_is_not_created_by_content_import(self):
        self.add()
        self.assertFalse((self.root / "state.sqlite3").exists())


if __name__ == "__main__": unittest.main()
