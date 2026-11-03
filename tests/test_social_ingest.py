"""PR-07 integrity, replay, revision and retention acceptance; all synthetic."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from tests.test_social_contracts import fixture
from tools.social.batch import read_batch, seal_batch, validate_links
from tools.social.contracts import ContractError, content_hash, digest, query_id
from tools.social.guard import GuardError
from tools.social.ingest import ingest_batch
from tools.social.retention import collect
from tools.social.signal_store import SignalStore

ROOT = Path(__file__).resolve().parents[1]


def synthetic(platform="xhs", *, observed="2026-10-23T12:00:00Z", body=None):
    job, row, receipt = (fixture(kind, platform) for kind in ("crawl_job", "signal_observation", "query_receipt"))
    job.update(runId=str(uuid4()), attemptId=str(uuid4()))
    for key in ("runId", "attemptId", "queryId", "jobId"):
        row[key] = receipt[key] = job[key]
    row["observedAt"] = observed
    if body is not None:
        row["excerpt"] = body
    row["contentHash"] = content_hash(row)
    receipt.update(startedAt=observed, completedAt=observed)
    return job, row, receipt


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.state = Path(self.directory).resolve()
        self.store = self.enterContext(SignalStore(self.state, repo_roots=(ROOT,)))

    def seal(self, triple):
        job, row, receipt = triple
        return seal_batch(self.state, [job], [row], [receipt], roots=(ROOT,))

    def test_I01_replay_same_package_is_idempotent(self):
        triple = synthetic()
        path = self.seal(triple)
        first = ingest_batch(path, self.store)
        second = ingest_batch(path, self.store)
        self.assertEqual(first["insertedObservations"], 1)
        self.assertFalse(second["changed"])
        self.assertEqual(self.store.counts()["signals"], 1)
        self.assertEqual(self.seal(triple), path)

    def test_I02_same_signal_new_keyword_has_two_observations(self):
        first = synthetic()
        ingest_batch(self.seal(first), self.store)
        job, row, receipt = synthetic()
        job["query"]["text"] = "第二个合成关键词"
        job["queryId"] = query_id(job)
        job["jobId"] = digest({"queryId": job["queryId"], "operation": "search"})
        for key in ("queryId", "jobId"):
            row[key] = receipt[key] = job[key]
        row["queryTerms"] = [job["query"]["text"]]
        row["matchedTerms"] = []
        ingest_batch(self.seal((job, row, receipt)), self.store)
        counts = self.store.counts()
        self.assertEqual((counts["signals"], counts["revisions"], counts["observations"]), (1, 1, 2))

    def test_I03_content_change_not_likes_creates_revision(self):
        ingest_batch(self.seal(synthetic()), self.store)
        triple = synthetic(observed="2026-10-24T12:00:00Z")
        triple[1]["metrics"]["likes"] = {"value": 999, "approximate": False}
        ingest_batch(self.seal(triple), self.store)
        self.assertEqual(self.store.counts()["revisions"], 1)
        ingest_batch(self.seal(synthetic(observed="2026-10-25T12:00:00Z", body="事实内容发生变化")), self.store)
        self.assertEqual(self.store.counts()["revisions"], 2)

    def test_I04_import_old_batch_does_not_regress_latest(self):
        newer = synthetic(observed="2026-10-25T12:00:00Z", body="newer")
        older = synthetic(observed="2026-10-23T12:00:00Z", body="older")
        ingest_batch(self.seal(newer), self.store)
        ingest_batch(self.seal(older), self.store)
        self.assertEqual(self.store.latest()[0]["excerpt"], "newer")
        row = self.store.db.execute("SELECT first_seen,last_seen FROM social_content_signals").fetchone()
        self.assertTrue(row[0].startswith("2026-10-23"))
        self.assertTrue(row[1].startswith("2026-10-25"))

    def test_I05_hash_tampering_fails_before_content_mutation(self):
        path = self.seal(synthetic())
        original = self.store.counts()
        with (path / "observations.jsonl").open("ab") as stream: stream.write(b" ")
        with self.assertRaisesRegex(ContractError, "batch_integrity"):
            ingest_batch(path, self.store)
        self.assertEqual(self.store.counts(), original)

    def test_I05_truncation_duplicate_keys_unknown_version(self):
        from tools.social.batch import decode_rows, parse_json
        with self.assertRaisesRegex(ContractError, "truncated_jsonl"):
            decode_rows(b"{}", "crawl_job")
        with self.assertRaisesRegex(ContractError, "duplicate_key"):
            parse_json(b'{"a":1,"a":2}')
        value = synthetic()
        value[0]["schemaVersion"] = 2
        with self.assertRaises(ContractError): self.seal(value)

    def test_I06_symlink_and_extra_file_rejected(self):
        path = self.seal(synthetic())
        (path / "unexpected.txt").write_text("test")
        with self.assertRaisesRegex(ContractError, "batch_file_allowlist"): read_batch(path)
        (path / "unexpected.txt").unlink()
        link = self.state / "link"
        link.symlink_to(path, target_is_directory=True)
        with self.assertRaises(GuardError): read_batch(link)

    def test_I06_missing_receipt_and_cross_run_rejected(self):
        job, row, receipt = synthetic()
        with self.assertRaises(ContractError): validate_links([job], [row], [])
        row["runId"] = str(uuid4())
        with self.assertRaisesRegex(ContractError, "batch_observation_link"):
            validate_links([job], [row], [receipt])

    def test_I07_empty_or_error_does_not_clear_existing(self):
        ingest_batch(self.seal(synthetic()), self.store)
        job, row, receipt = synthetic()
        receipt.update(status="auth_required", completeness="unknown", stopReason="auth", errorCode="SESSION_NOT_READY", pageReceipts=[])
        receipt["counts"] = dict.fromkeys(receipt["counts"], 0)
        path = seal_batch(self.state, [job], [], [receipt], roots=(ROOT,))
        ingest_batch(path, self.store)
        self.assertEqual(self.store.counts()["signals"], 1)

    def test_I08_reviewed_revision_survives_gc(self):
        old = synthetic(observed="2025-01-01T00:00:00Z", body="old")
        ingest_batch(self.seal(old), self.store)
        ingest_batch(self.seal(synthetic(observed="2026-10-23T12:00:00Z", body="new")), self.store)
        preview = collect(self.store, now=datetime(2026, 11, 1, tzinfo=UTC))
        self.assertEqual(preview["eligibleRevisions"], 1)
        self.assertEqual(preview["deletedRevisions"], 0)
        self.store.db.execute("INSERT INTO social_evidence_refs VALUES(?,?,?)", ("test-review", old[1]["signalId"], old[1]["contentHash"]))
        final = collect(self.store, now=datetime(2026, 11, 1, tzinfo=UTC), apply=True)
        self.assertEqual(final["deletedRevisions"], 0)
        self.assertEqual(self.store.counts()["revisions"], 2)

    def test_I09_conflicting_attempt_rolls_back(self):
        triple = synthetic()
        path = self.seal(triple)
        ingest_batch(path, self.store)
        modified = read_batch(path)
        modified["batchHash"] = "a" * 64
        modified["observations"][0]["excerpt"] = "changed"
        modified["observations"][0]["contentHash"] = content_hash(modified["observations"][0])
        before = self.store.counts()
        with self.assertRaisesRegex(ContractError, "content_attempt_conflict"):
            self.store.import_validated(modified)
        self.assertEqual(self.store.counts(), before)

    def test_I09_two_connections_replay_and_backup(self):
        path = self.seal(synthetic())
        with SignalStore(self.state, repo_roots=(ROOT,)) as second:
            ingest_batch(path, self.store)
            self.assertFalse(ingest_batch(path, second)["changed"])
        saved = self.store.backup()
        self.assertTrue(saved.is_file())
        if os.name == "posix": self.assertEqual(saved.stat().st_mode & 0o077, 0)

    def test_alias_conflicts_do_not_merge_different_aids(self):
        first = synthetic("bili")
        first[1]["nativeAliases"] = ["bili:bvid:BV1d54y1g7db"]
        ingest_batch(self.seal(first), self.store)
        self.assertEqual(self.store.resolve_alias("bili:bvid:BV1d54y1g7db"), first[1]["signalId"])
        job, row, receipt = synthetic("bili")
        row.update(nativeId="999", signalId="bili:video:999", canonicalUrl="https://www.bilibili.com/video/av999", nativeAliases=["bili:bvid:BV1d54y1g7db"])
        row["contentHash"] = content_hash(row)
        with self.assertRaisesRegex(ContractError, "alias_conflict_requires_review"):
            ingest_batch(self.seal((job, row, receipt)), self.store)
        self.assertEqual(self.store.counts()["signals"], 1)


if __name__ == "__main__":
    unittest.main()
