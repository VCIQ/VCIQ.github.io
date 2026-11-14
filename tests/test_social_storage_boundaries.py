"""Additional ingestion resource/context boundaries, all synthetic."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.social_storage_fixtures import SEALED_AT, sample
from tools.social import batch
from tools.social.contracts import ContractError, content_hash
from tools.social.ingest import import_from_path


class StorageBoundaryTests(unittest.TestCase):
    def test_export_stops_before_combining_oversize_payload(self):
        rows = sample()
        with patch.object(batch, "MAX_TOTAL", 20), patch.object(batch, "verify_payloads", side_effect=AssertionError("too late")):
            with self.assertRaisesRegex(ContractError, "file_too_large"):
                batch.build_batch(*rows, created_at=SEALED_AT)

    def test_aggregate_read_budget_not_just_per_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "private"; root.mkdir(mode=0o700)
            bundle = batch.seal_batch(root, "batches/one", *sample(), created_at=SEALED_AT)
            total = sum(len(raw) for _, raw in bundle.payloads)
            with patch.object(batch, "MAX_TOTAL", total - 1), self.assertRaisesRegex(ContractError, "file_too_large"):
                batch.read_batch(root, "batches/one")

    def test_matched_terms_must_belong_to_query_terms(self):
        rows = sample(); rows[2][0]["matchedTerms"] = ["not in query context"]
        with self.assertRaisesRegex(ContractError, "matched_terms"):
            batch.build_batch(*rows, created_at=SEALED_AT)

    def test_postfilter_rejects_unknown_publication(self):
        rows = sample(); rows[0][0]["window"].update(filterMode="post_filter", **{"from": "2026-10-20", "to": "2026-10-23"})
        with self.assertRaisesRegex(ContractError, "publication_window"):
            batch.build_batch(*rows, created_at=SEALED_AT)

    def test_postfilter_checks_known_date(self):
        rows = sample(); rows[0][0]["window"].update(filterMode="post_filter", **{"from": "2026-10-20", "to": "2026-10-23"})
        doc = rows[2][0]
        doc.update(publishedAt="2026-10-22", publishedPrecision="day")
        doc["contentHash"] = content_hash(doc)
        self.assertEqual(batch.build_batch(*rows, created_at=SEALED_AT).manifest["counts"]["observations"], 1)
        doc["publishedAt"] = "2026-10-19"; doc["contentHash"] = content_hash(doc)
        with self.assertRaisesRegex(ContractError, "publication_window"):
            batch.build_batch(*rows, created_at=SEALED_AT)

    def test_staging_directory_or_ancestor_is_not_importable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "private"; root.mkdir(mode=0o700)
            for relative in ("batches/one.staging-test", "batches/one.staging-test/nested"):
                batch.seal_batch(root, relative, *sample(), created_at=SEALED_AT)
                result = import_from_path(root, relative)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"], "batch_unsealed_staging")
            self.assertFalse((root / "signals.sqlite3").exists())


if __name__ == "__main__": unittest.main()
