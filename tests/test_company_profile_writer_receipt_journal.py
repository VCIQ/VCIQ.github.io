"""Offline journal tests: disposable folders and fake company subprocess results."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.company_profile_writer_receipt_journal import (
    JournalError, RunReceiptJournal, inspect_run,
)
from tools.company_profile_writer_crawl_observer import ObservedCrawlError
from tests.test_company_profile_writer_crawl_observer import Fixture, TIMES

SHA = "a" * 40
DIGEST = "b" * 64
RUN_ID = "synthetic-audit-20261109"


class ReceiptJournalTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.parent = Path(self.scratch.name)
        self.fixture = Fixture()

    def tearDown(self):
        self.fixture.close()
        self.scratch.cleanup()

    def journal(self):
        return RunReceiptJournal(self.parent, authorized=True)

    def test_complete_is_reviewable_but_not_an_authorization(self):
        result = self.fixture.observe(journal=self.journal())
        self.assertTrue(result["localJournalRecorded"])
        outcome = inspect_run(self.parent, "synthetic-run-1")
        self.assertEqual(outcome["state"], "recorded")
        self.assertEqual(outcome["recordedCompanies"], 1)
        self.assertEqual(outcome["requiredCompanies"], 1)
        self.assertFalse(outcome["automaticResumeAuthorized"])
        self.assertFalse(outcome["mergeAuthorized"])
        self.assertFalse(outcome["externalIntegrityAttested"])
        self.assertEqual(len(outcome["journalHeadSha256"]), 64)

    def test_full_receipt_contains_no_source_urls_or_crawler_data(self):
        self.fixture.observe(journal=self.journal())
        folder = self.parent / "run-synthetic-run-1"
        self.assertEqual(sorted(p.name for p in folder.iterdir()), [
            "complete.json", "manifest.json", "receipt-00.json",
        ])
        joined = " ".join(p.read_text() for p in folder.iterdir())
        self.assertNotIn("alpha.example", joined)
        self.assertNotIn("Research", joined)
        self.assertNotIn("private token", joined)
        self.assertIn("baseSha", joined)
        self.assertIn("selectionSha256", joined)

    def test_nonzero_exit_reserves_id_before_execution_and_cannot_resume(self):
        self.fixture.returncode = 2
        with self.assertRaisesRegex(ObservedCrawlError, "PROCESS_FAILED"):
            self.fixture.observe(journal=self.journal())
        status = inspect_run(self.parent, "synthetic-run-1")
        self.assertEqual(status["state"], "incomplete")
        self.assertEqual(status["recordedCompanies"], 0)
        self.assertTrue(status["manualTriageRequired"])
        calls = len(self.fixture.commands)
        self.fixture.returncode = 0
        self.fixture.ticks = [TIMES[0], TIMES[1], TIMES[2], TIMES[-1]]
        with self.assertRaisesRegex(ObservedCrawlError, "JOURNAL_FAILED"):
            self.fixture.observe(journal=self.journal())
        self.assertEqual(len(self.fixture.commands), calls)

    def test_second_slug_failure_leaves_one_verified_entry_for_triage(self):
        self.fixture.close()
        self.fixture = Fixture(("alpha", "beta"))
        self.fixture.ticks = list(TIMES)
        def fail_second(snapshot, slug):
            if slug == "beta":
                snapshot["companies"][slug]["status"] = "retained"
                for row in snapshot["sourceStatus"]:
                    if row.get("slug") == slug:
                        row["status"] = "retained"
                        row["retainedPrevious"] = True
        self.fixture.mutate = fail_second
        with self.assertRaisesRegex(ObservedCrawlError, "NOT_FRESH"):
            self.fixture.observe(journal=self.journal())
        info = inspect_run(self.parent, "synthetic-run-1")
        self.assertEqual((info["state"], info["recordedCompanies"],
                          info["requiredCompanies"]), ("incomplete", 1, 2))
        self.assertTrue(info["manualTriageRequired"])

    def test_corrupt_stored_receipt_is_detected(self):
        self.fixture.observe(journal=self.journal())
        f = self.parent / "run-synthetic-run-1/receipt-00.json"
        body = json.loads(f.read_text())
        body["payload"]["receipt"]["capturedAt"] = "2026-11-08T13:05:00+00:00"
        f.write_text(json.dumps(body))
        with self.assertRaisesRegex(JournalError, "CHAIN_INVALID"):
            inspect_run(self.parent, "synthetic-run-1")

    def test_corrupt_completion_digest_is_detected(self):
        self.fixture.observe(journal=self.journal())
        f = self.parent / "run-synthetic-run-1/complete.json"
        body = json.loads(f.read_text())
        body["headDigest"] = "0" * 64
        f.write_text(json.dumps(body))
        with self.assertRaisesRegex(JournalError, "COMPLETION_INVALID"):
            inspect_run(self.parent, "synthetic-run-1")

    def test_existing_run_directory_never_overwritten(self):
        first = self.journal()
        first.begin(run_id=RUN_ID, base_sha=SHA, selected_slugs=["alpha"],
                    selection_sha256=DIGEST, official_urls_sha256=DIGEST,
                    run_started_at="2026-11-08T13:00:00+00:00")
        second = self.journal()
        with self.assertRaisesRegex(JournalError, "RUN_RESERVED"):
            second.begin(run_id=RUN_ID, base_sha=SHA, selected_slugs=["alpha"],
                         selection_sha256=DIGEST, official_urls_sha256=DIGEST,
                         run_started_at="2026-11-08T13:00:00+00:00")
        self.assertEqual(inspect_run(self.parent, RUN_ID)["state"], "incomplete")

    def test_unapproved_directory_never_reserved(self):
        with self.assertRaisesRegex(JournalError, "EXPLICIT_APPROVAL_REQUIRED"):
            RunReceiptJournal(self.parent)
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_publicly_readable_directory_is_rejected(self):
        os.chmod(self.parent, 0o755)
        try:
            with self.assertRaisesRegex(JournalError, "DIRECTORY_UNSAFE"):
                self.journal()
        finally:
            os.chmod(self.parent, 0o700)

    def test_symlinked_parent_is_rejected(self):
        link = self.parent / "pointer"
        link.symlink_to(self.parent, target_is_directory=True)
        with self.assertRaisesRegex(JournalError, "DIRECTORY_UNSAFE"):
            RunReceiptJournal(link, authorized=True)

    def test_duplicate_or_unexpected_next_receipt_is_rejected(self):
        journal = self.journal()
        journal.begin(run_id=RUN_ID, base_sha=SHA, selected_slugs=["alpha"],
                      selection_sha256=DIGEST, official_urls_sha256=DIGEST,
                      run_started_at="2026-11-08T13:00:00+00:00")
        wrong = {"slug": "wrong", "exitCode": 0,
                 "capturedAt": "2026-11-08T13:05:00+00:00",
                 "statusSha256": DIGEST, "profileSha256": DIGEST}
        with self.assertRaisesRegex(JournalError, "RECEIPT_INVALID"):
            journal.record(wrong)
        with self.assertRaisesRegex(JournalError, "NOT_RECORDABLE"):
            journal.record({**wrong, "slug": "alpha"})
        self.assertEqual(inspect_run(self.parent, RUN_ID)["recordedCompanies"], 0)

    def test_gap_in_saved_sequence_is_never_silently_accepted(self):
        journal = self.journal()
        journal.begin(run_id=RUN_ID, base_sha=SHA, selected_slugs=["alpha", "beta"],
                      selection_sha256=DIGEST, official_urls_sha256=DIGEST,
                      run_started_at="2026-11-08T13:00:00+00:00")
        (self.parent / f"run-{RUN_ID}" / "receipt-01.json").write_text("{}")
        with self.assertRaisesRegex(JournalError, "RECEIPT_GAP"):
            inspect_run(self.parent, RUN_ID)

    def test_unsafe_run_id_does_not_write_outside_private_parent(self):
        journal = self.journal()
        with self.assertRaisesRegex(JournalError, "ID_INVALID"):
            journal.begin(run_id="../escape", base_sha=SHA,
                          selected_slugs=["alpha"],
                          selection_sha256=DIGEST, official_urls_sha256=DIGEST,
                          run_started_at="2026-11-08T13:00:00+00:00")
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_failed_final_verification_does_not_mark_complete(self):
        self.fixture.mutate = lambda snapshot, slug: snapshot["qualityGate"].update(passed=False)
        with self.assertRaisesRegex(ObservedCrawlError, "INPUT_INVALID"):
            self.fixture.observe(journal=self.journal())
        audit = inspect_run(self.parent, "synthetic-run-1")
        self.assertEqual(audit["state"], "incomplete")
        self.assertEqual(audit["recordedCompanies"], 0)

    def test_completed_run_cannot_be_automatically_reserved_again(self):
        self.fixture.observe(journal=self.journal())
        self.fixture.ticks = [TIMES[0], TIMES[1], TIMES[2], TIMES[-1]]
        calls = len(self.fixture.commands)
        with self.assertRaisesRegex(ObservedCrawlError, "JOURNAL_FAILED"):
            self.fixture.observe(journal=self.journal())
        self.assertEqual(len(self.fixture.commands), calls)

    def test_unexpected_extra_file_is_rejected_at_inspection(self):
        self.fixture.observe(journal=self.journal())
        (self.parent / "run-synthetic-run-1/evil-script.py").write_text("pass\n")
        with self.assertRaisesRegex(JournalError, "UNEXPECTED_RECORD"):
            inspect_run(self.parent, "synthetic-run-1")

    def test_record_file_symlink_is_rejected(self):
        self.fixture.observe(journal=self.journal())
        folder = self.parent / "run-synthetic-run-1"
        receipt = folder / "receipt-00.json"
        original = folder / "other.json"
        receipt.rename(original)
        receipt.symlink_to(original)
        with self.assertRaisesRegex(JournalError, "UNEXPECTED_RECORD|READ_FAILED|FILE_UNSAFE"):
            inspect_run(self.parent, "synthetic-run-1")

    def test_failing_disk_write_never_creates_successful_completion(self):
        journal = self.journal()
        journal.begin(run_id=RUN_ID, base_sha=SHA, selected_slugs=["alpha"],
                      selection_sha256=DIGEST, official_urls_sha256=DIGEST,
                      run_started_at="2026-11-08T13:00:00+00:00")
        (self.parent / f"run-{RUN_ID}/receipt-00.json").write_text("{}")
        receipt = {"slug": "alpha", "exitCode": 0,
                   "capturedAt": "2026-11-08T13:04:00+00:00",
                   "statusSha256": DIGEST, "profileSha256": DIGEST}
        with self.assertRaisesRegex(JournalError, "DUPLICATE_RECORD"):
            journal.record(receipt)
        with self.assertRaisesRegex(JournalError, "INCOMPLETE"):
            journal.complete(final_snapshot_sha256=DIGEST,
                             completed_at="2026-11-08T13:06:00+00:00")
        self.assertFalse((self.parent / f"run-{RUN_ID}/complete.json").exists())


if __name__ == "__main__":
    unittest.main()
