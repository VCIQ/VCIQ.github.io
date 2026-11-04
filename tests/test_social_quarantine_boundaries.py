"""Additional fail-closed cases using only synthetic private SQLite fixtures."""
import json
import unittest
from unittest.mock import patch

import tests.test_social_quarantine as fixtures
from tools.social import quarantine
from tools.social.contracts import ContractError
from tools.social.scheduler_state import SchedulerStore
from tools.social.shadow_state import load, save


class QuarantineBoundaryTests(unittest.TestCase):
    # Reuse fixture helpers without inheriting or rediscovering the original tests.
    setUp = fixtures.QuarantineTests.setUp
    execute = fixtures.QuarantineTests.execute
    preview = fixtures.QuarantineTests.preview
    apply = fixtures.QuarantineTests.apply
    files = fixtures.QuarantineTests.files

    def test_missing_scheduler_is_not_recreated_or_accepted(self):
        path = self.root / "state.sqlite3"
        path.rename(self.root / "preserved-state.sqlite3")
        with self.assertRaisesRegex(ContractError, "scheduler_missing"):
            self.preview()
        self.assertFalse(path.exists())

    def test_missing_query_history_is_not_assumed_unused(self):
        with SchedulerStore(self.root, repo_roots=self.roots) as store:
            store.db.execute("DELETE FROM social_query_state WHERE query_id=?", (self.bad_job["queryId"],))
        with self.assertRaisesRegex(ContractError, "scheduler_incomplete"):
            self.preview()

    def test_missing_platform_history_is_not_assumed_unpaused(self):
        with SchedulerStore(self.root, repo_roots=self.roots) as store:
            store.db.execute("DELETE FROM social_platform_state WHERE platform='wechat'")
        with self.assertRaisesRegex(ContractError, "scheduler_incomplete"):
            self.preview()

    def test_checkpoint_payload_is_included_in_aggregate_budget(self):
        paths = ["shadow.stop", self.prefix + "/intent.json", self.prefix + "/journal.json",
            self.prefix + "/report.json", self.prefix + "/results/" + self.valid_job["attemptId"] + ".json",
            "pending/" + self.valid_job["attemptId"] + ".json", self.pending_path]
        file_bytes = sum((self.root / path).stat().st_size for path in paths)
        before = self.files()
        # Files alone fit exactly; adding the SQLite checkpoint must fail.
        with patch.object(quarantine, "MAX_EVIDENCE_BYTES", file_bytes):
            with self.assertRaisesRegex(ContractError, "evidence_limit"):
                self.preview()
        self.assertEqual(before, self.files())

    def test_small_per_file_inputs_cannot_bypass_total_budget(self):
        with patch.object(quarantine, "MAX_EVIDENCE_BYTES", 32):
            with self.assertRaisesRegex(ContractError, "evidence_limit"):
                self.preview()

    def test_corrupt_archived_report_is_not_replaced_by_current_report(self):
        fingerprint = self.preview()["fingerprint"]
        self.apply(fingerprint)
        decision = load(self.root, self.prefix + "/quarantine.json", self.roots)
        original = json.loads(decision["originalReportRaw"])
        original["sha256"] = "0" * 64
        decision["originalReportRaw"] = json.dumps(original)
        save(self.root, self.prefix + "/quarantine.json", decision, self.roots)
        with self.assertRaisesRegex(ContractError, "checksum"):
            self.apply(fingerprint)

    def test_no_valid_receipts_means_no_content_database(self):
        aid = self.valid_job["attemptId"]
        (self.root / "pending" / (aid + ".json")).unlink()
        (self.root / self.prefix / "results" / (aid + ".json")).unlink()
        with SchedulerStore(self.root, repo_roots=self.roots) as store:
            store.db.execute("DELETE FROM social_query_results WHERE attempt_id=?", (aid,))
        journal = load(self.root, self.prefix + "/journal.json", self.roots)
        journal["attempts"][aid] = "not_started"
        save(self.root, self.prefix + "/journal.json", journal, self.roots)
        result = self.apply()
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["runHealthy"])
        self.assertEqual(result["validReceiptJobs"], 0)
        self.assertFalse((self.root / "signals.sqlite3").exists())
        self.assertFalse((self.root / "reviews.sqlite3").exists())

    def test_pause_after_preview_prevents_application(self):
        fingerprint = self.preview()["fingerprint"]
        with SchedulerStore(self.root, repo_roots=self.roots) as store:
            store.db.execute("UPDATE social_platform_state SET pause_reason='rate_limit' WHERE platform='wechat'")
        with self.assertRaisesRegex(ContractError, "platform_pause"):
            self.apply(fingerprint)
        self.assertFalse((self.root / self.prefix / "quarantine.json").exists())


if __name__ == "__main__":
    unittest.main()
