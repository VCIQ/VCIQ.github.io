"""PR-07 byte integrity and cross-file regressions. No network or browser."""
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.social_storage_fixtures import SEALED_AT, combined, no_result, sample
from tools.social import batch
from tools.social.contracts import ContractError, canonical_bytes
from tools.social.guard import GuardError


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "private"
        self.root.mkdir(mode=0o700)
        self.rows = sample()

    def build(self, rows=None):
        return batch.build_batch(*(rows or self.rows), created_at=SEALED_AT)

    def seal(self, rows=None, relative="batches/one"):
        return batch.seal_batch(self.root, relative, *(rows or self.rows), created_at=SEALED_AT)

    def write_manifest(self, value, relative="batches/one"):
        (self.root / relative / "manifest.json").write_bytes(canonical_bytes(value) + b"\n")

    def test_all_five_platforms_round_trip_same_run(self):
        run = self.rows[0][0]["runId"]
        rows = combined(*(sample(p, run_id=run) for p in ("wechat", "xhs", "wb", "bili", "zhihu")))
        sealed = self.seal(rows)
        loaded = batch.read_batch(self.root, "batches/one")
        self.assertEqual(loaded, sealed)
        self.assertEqual(loaded.manifest["counts"], dict(jobs=5, receipts=5, observations=5))

    def test_input_not_mutated_and_bundle_bytes_immutable(self):
        before = copy.deepcopy(self.rows)
        bundle = self.build()
        bundle.manifest["sealed"] = False
        bundle.records("observations.jsonl")[0]["title"] = "changed"
        self.assertEqual(before, self.rows)
        self.assertTrue(bundle.manifest["sealed"])
        self.assertNotEqual(bundle.records("observations.jsonl")[0]["title"], "changed")

    def test_same_seal_is_idempotent(self):
        first, second = self.seal(), self.seal()
        self.assertEqual(first, second)
        self.assertEqual({p.name for p in (self.root / "batches/one").iterdir()}, set(batch.FILES) | {"manifest.json"})

    def test_changed_destination_is_never_overwritten(self):
        before = self.seal()
        with self.assertRaisesRegex(ContractError, "destination_conflict"):
            self.seal(sample(keyword="another"))
        self.assertEqual(batch.read_batch(self.root, "batches/one"), before)

    def test_row_order_does_not_change_fingerprint(self):
        rows = combined(self.rows, sample("wb", run_id=self.rows[0][0]["runId"]))
        self.assertEqual(self.build(rows).fingerprint, self.build(tuple(list(reversed(r)) for r in rows)).fingerprint)

    def test_normal_empty_and_failure_batches_have_receipts(self):
        for status in ("empty", "network_error"):
            bundle = self.build(no_result(sample(), status=status))
            self.assertEqual(bundle.records("observations.jsonl"), [])
            self.assertEqual(bundle.records("query_receipts.jsonl")[0]["status"], status)

    def test_missing_receipt_rejected_before_writes(self):
        with self.assertRaises(ContractError):
            self.seal((self.rows[0], [], self.rows[2]))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_duplicate_job_and_duplicate_receipt_rejected(self):
        for rows in ((self.rows[0] * 2, self.rows[1] * 2, self.rows[2]),
                     (self.rows[0], self.rows[1] * 2, self.rows[2])):
            with self.assertRaises(ContractError): self.build(rows)

    def test_duplicate_observation_rejected_not_silently_deduplicated(self):
        rows = copy.deepcopy(self.rows)
        rows[2].append(copy.deepcopy(rows[2][0]))
        with self.assertRaisesRegex(ContractError, "duplicate_observation"):
            self.build(rows)

    def test_orphan_observation_rejected(self):
        self.rows[2][0]["attemptId"] = sample()[0][0]["attemptId"]
        with self.assertRaisesRegex(ContractError, "observation_reference"): self.build()

    def test_observation_query_job_platform_and_tracks_match(self):
        for key, value in (("queryId", "a" * 64), ("jobId", "b" * 64), ("trackRefs", ["different"])):
            rows = copy.deepcopy(self.rows); rows[2][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ContractError, "job_mismatch"):
                self.build(rows)

    def test_receipt_references_matching_job(self):
        self.rows[1][0]["queryId"] = "a" * 64
        with self.assertRaisesRegex(ContractError, "receipt_job_mismatch"): self.build()

    def test_mixed_run_rejected(self):
        other = sample("wb")
        with self.assertRaisesRegex(ContractError, "run_mismatch"):
            self.build(combined(self.rows, other))

    def test_mixed_configuration_rejected(self):
        other = sample("wb", run_id=self.rows[0][0]["runId"])
        other[0][0]["configHash"] = "a" * 64
        with self.assertRaisesRegex(ContractError, "mixed_configuration"):
            self.build(combined(self.rows, other))

    def test_observation_outside_receipt_time_rejected(self):
        self.rows[2][0]["observedAt"] = "2026-10-24T12:00:00Z"
        with self.assertRaisesRegex(ContractError, "observation_time"): self.build()

    def test_manifest_cannot_predate_completion(self):
        with self.assertRaisesRegex(ContractError, "sealed_before_completion"):
            batch.build_batch(*self.rows, created_at="2026-10-23T11:00:00Z")

    def test_emitted_count_matches_actual_file(self):
        with self.assertRaisesRegex(ContractError, "emitted_count"):
            self.build((self.rows[0], self.rows[1], []))

    def test_receipt_record_budget_and_page_order_checked(self):
        rows = copy.deepcopy(self.rows)
        rows[1][0]["counts"].update(rawRows=21, rejectedRows=20)
        with self.assertRaisesRegex(ContractError, "record_budget"): self.build(rows)
        rows = copy.deepcopy(self.rows)
        rows[1][0]["pageReceipts"][0]["pageIndex"] = 2
        with self.assertRaisesRegex(ContractError, "page_budget_or_order"): self.build(rows)

    def test_integer_counts_not_integral_floats(self):
        self.rows[1][0]["counts"]["rawRows"] = 1.0
        with self.assertRaisesRegex(ContractError, "integer_required"): self.build()

    def test_hash_bytes_and_rows_are_independently_verified(self):
        bundle = self.seal()
        for key, value in (("sha256", "0" * 64), ("bytes", 1), ("rows", 2)):
            m = bundle.manifest
            target = next(r for r in m["files"] if r["path"] == "observations.jsonl")
            target[key] = value
            self.write_manifest(m)
            with self.subTest(key=key), self.assertRaises(ContractError):
                batch.read_batch(self.root, "batches/one")
        self.write_manifest(bundle.manifest)

    def test_changed_payload_is_rejected(self):
        self.seal()
        path = self.root / "batches/one/observations.jsonl"
        path.write_bytes(path.read_bytes().replace(b'"unknown"', b'"UNKNOWN"', 1))
        with self.assertRaisesRegex(ContractError, "checksum_mismatch"):
            batch.read_batch(self.root, "batches/one")

    def test_truncated_jsonl_even_with_rehashed_manifest_rejected(self):
        bundle = self.seal()
        path = self.root / "batches/one/observations.jsonl"
        raw = path.read_bytes().rstrip(b"\n"); path.write_bytes(raw)
        m = bundle.manifest
        for r in m["files"]:
            if r["path"] == path.name:
                r.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        self.write_manifest(m)
        with self.assertRaisesRegex(ContractError, "truncated_jsonl"):
            batch.read_batch(self.root, "batches/one")

    def test_missing_manifest_and_extra_files_rejected(self):
        self.seal()
        (self.root / "batches/one/extra").write_text("synthetic")
        with self.assertRaisesRegex(ContractError, "file_set"): batch.read_batch(self.root, "batches/one")
        (self.root / "batches/one/extra").unlink()
        (self.root / "batches/one/manifest.json").unlink()
        with self.assertRaisesRegex(ContractError, "file_set"): batch.read_batch(self.root, "batches/one")

    def test_duplicate_json_keys_nonfinite_and_invalid_utf8_rejected(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(ContractError): batch.decode(raw)

    def test_oversize_file_and_line_rejected(self):
        self.seal()
        with patch.object(batch, "MAX_FILE", 20), self.assertRaises(ContractError):
            batch.read_batch(self.root, "batches/one")
        with patch.object(batch, "MAX_LINE", 20), self.assertRaises(ContractError): self.build()

    def test_sensitive_fields_rejected_without_echo(self):
        self.rows[2][0]["excerpt"] = "Cookie: SYNTHETIC_PRIVATE"
        with self.assertRaises(ContractError) as caught: self.build()
        self.assertNotIn("SYNTHETIC_PRIVATE", str(caught.exception))

    def test_path_traversal_absolute_and_symlink_rejected(self):
        for relative in ("../outside", "/absolute", "batches/../../outside", "a\\b"):
            with self.subTest(relative=relative), self.assertRaises(GuardError): self.seal(relative=relative)
        (self.root / "link").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(GuardError): self.seal(relative="link/batch")

    @unittest.skipUnless(os.name == "posix", "POSIX file permissions")
    def test_public_permissions_and_hardlinks_rejected(self):
        self.seal()
        p = self.root / "batches/one/jobs.jsonl"
        p.chmod(0o644)
        with self.assertRaises(GuardError): batch.read_batch(self.root, "batches/one")
        p.chmod(0o600)
        os.link(p, self.root / "second-link")
        with self.assertRaises(GuardError): batch.read_batch(self.root, "batches/one")

    def test_interrupted_write_does_not_publish_target(self):
        original = batch.write_private
        def fail_manifest(root, relative, raw, roots):
            if relative.endswith("manifest.json"): raise OSError("synthetic interruption")
            return original(root, relative, raw, roots)
        with patch.object(batch, "write_private", side_effect=fail_manifest), self.assertRaises(OSError): self.seal()
        self.assertFalse((self.root / "batches/one").exists())
        with self.assertRaises(ContractError): batch.read_batch(self.root, "batches/one")


if __name__ == "__main__": unittest.main()
