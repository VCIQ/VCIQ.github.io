"""Strictly offline tests for the opt-in private RSS shadow evidence runner."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from tools import wechat_rss_shadow_private_run as private


class FixedDateTime(datetime):
    current = datetime(2026, 11, 19, 15, 0, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):
        return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)


def report(items=1, source_status="ok", history=None, new=1):
    return {"schemaVersion": 2, "mode": "read-only-shadow", "snapshotStatus": "ok",
            "asOf": FixedDateTime.current.isoformat(),
            "seenHistory": history if history is not None else {
                "id1": {"firstSeenAt": "2026-11-19T15:00:00+00:00",
                        "lastSeenAt": "2026-11-19T15:00:00+00:00"}},
            "sources": [{"sourceId": key, "status": source_status}
                        for key in private.SOURCE_IDS],
            "rows": [{"id": "id1", "sourceId": private.SOURCE_IDS[0],
                      "firstSeenAt": "2026-11-19T15:00:00+00:00", "newSincePrevious": True}]
                    if items else [],
            "summary": {"observed": items, "newSincePrevious": new}}


class PrivateShadowLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        os.chmod(self.path, 0o700)
        self.folder = private.secure_directory(str(self.path))
        FixedDateTime.current = datetime(2026, 11, 19, 15, 0, tzinfo=UTC)
        self.t = patch.object(private, "datetime", FixedDateTime)
        self.t.start()
        self.addCleanup(self.t.stop)

    def fake_run(self, obj, returncode=0):
        return subprocess.CompletedProcess([], returncode, json.dumps(obj, ensure_ascii=False), "")

    def test_secure_external_folder_required(self):
        with self.assertRaises(private.LedgerError):
            private.secure_directory("relative-folder")
        with self.assertRaises(private.LedgerError):
            private.secure_directory(str(private.ROOT))
        os.chmod(self.path, 0o755)
        with self.assertRaises(private.LedgerError):
            private.secure_directory(str(self.path))

    def test_creates_a_new_private_directory_with_0700_permissions(self):
        nested = self.path / "evidence" / "daily"
        result = private.secure_directory(str(nested))
        self.assertEqual(result, nested)
        self.assertEqual(stat.S_IMODE(nested.stat().st_mode), 0o700)

    def test_wrong_source_ids_cannot_be_counted_as_complete(self):
        original = report()
        original["sources"][2]["sourceId"] = "unexpected"
        day1 = datetime(2026, 11, 19, 9, tzinfo=private.NY)
        with patch.object(private.subprocess, "run", return_value=self.fake_run(original)):
            _, result = private.run_once(self.folder, "scheduled", day1)
        self.assertFalse(result["privateRunMeta"]["sampleComplete"])
        self.assertIsNone(result["summary"]["newSincePrevious"])

    def test_private_atomic_write_does_not_overwrite(self):
        target = private.atomic_private_json(self.folder, "scheduled-2026-11-19.json", report())
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(json.loads(target.read_text()), report())
        with self.assertRaises(FileExistsError):
            private.atomic_private_json(self.folder, "scheduled-2026-11-19.json", report(items=0))
        self.assertEqual(json.loads(target.read_text()), report())

    def test_previous_disallows_nonhistory_or_future_artifact(self):
        p = private.atomic_private_json(self.folder, "scheduled-2026-11-19.json", {
            "schemaVersion": 1, "seenHistory": {}, "privateRunMeta": {"runKind": "scheduled"}})
        with self.assertRaises(private.LedgerError):
            private.load_previous(self.folder, datetime(2026, 11, 20).date())
        self.assertTrue(p.exists())

    def test_two_scheduled_runs_inherit_only_private_scheduled_ledger(self):
        day1 = datetime(2026, 11, 19, 9, 0, tzinfo=private.NY)
        with patch.object(private.subprocess, "run", return_value=self.fake_run(report(new=None))) as run:
            file, first = private.run_once(self.folder, "scheduled", day1)
        self.assertEqual(file.name, "scheduled-2026-11-19.json")
        self.assertIsNone(first["summary"]["newSincePrevious"])
        self.assertTrue(first["privateRunMeta"]["observationChainComplete"])
        self.assertEqual(first["privateRunMeta"]["previousLedger"], None)
        self.assertNotIn("--previous-ledger", run.call_args.args[0])

        FixedDateTime.current = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)
        day2 = datetime(2026, 11, 20, 9, 0, tzinfo=private.NY)
        with patch.object(private.subprocess, "run", return_value=self.fake_run(report(new=0))) as run:
            file2, second = private.run_once(self.folder, "scheduled", day2)
        self.assertEqual(file2.name, "scheduled-2026-11-20.json")
        self.assertTrue(second["privateRunMeta"]["observationChainComplete"])
        self.assertEqual(second["privateRunMeta"]["previousLedger"], file.name)
        self.assertIn("--previous-ledger", run.call_args.args[0])
        self.assertEqual(second["summary"]["newSincePrevious"], 0)
        with self.assertRaises(private.LedgerError):
            private.run_once(self.folder, "scheduled", day2)

    def test_failed_audit_persists_history_and_marks_later_run_unknown(self):
        for day in (19, 20, 21):
            FixedDateTime.current = datetime(2026, 11, day, 15, 0, tzinfo=UTC)
            scheduled = datetime(2026, 11, day, 9, 0, tzinfo=private.NY)
            if day == 20:
                response = subprocess.CompletedProcess([], 124, "not JSON", "timeout")
            else:
                response = self.fake_run(report(new=0 if day == 21 else None))
            with patch.object(private.subprocess, "run", return_value=response):
                output, result = private.run_once(self.folder, "scheduled", scheduled)
            self.assertEqual(result["seenHistory"]["id1"]["firstSeenAt"], "2026-11-19T15:00:00+00:00")
            if day >= 20:
                self.assertIsNone(result["summary"]["newSincePrevious"])
                self.assertFalse(result["privateRunMeta"]["observationChainComplete"])
            if day == 20:
                self.assertEqual(result["privateRunMeta"]["auditExitCode"], 124)
            self.assertTrue(output.exists())

    def test_missing_day_is_not_marked_continuous(self):
        private.atomic_private_json(self.folder, "scheduled-2026-11-19.json", {
            **report(), "privateRunMeta": {"runKind": "scheduled", "auditExitCode": 0,
                                            "sampleComplete": True, "observationChainComplete": True}})
        FixedDateTime.current = datetime(2026, 11, 21, 15, 0, tzinfo=UTC)
        with patch.object(private.subprocess, "run", return_value=self.fake_run(report(new=9))):
            _, observed = private.run_once(self.folder, "scheduled",
                                           datetime(2026, 11, 21, 9, 0, tzinfo=private.NY))
        self.assertIsNone(observed["summary"]["newSincePrevious"])
        self.assertIsNone(observed["rows"][0]["newSincePrevious"])
        self.assertEqual(observed["privateRunMeta"]["previousLedger"], "scheduled-2026-11-19.json")

    def test_preflight_is_never_used_as_scheduled_history(self):
        with patch.object(private.subprocess, "run", return_value=self.fake_run(report())):
            _, observed = private.run_once(self.folder, "preflight", None)
        self.assertEqual(observed["privateRunMeta"]["runKind"], "preflight")
        self.assertEqual(private.load_previous(self.folder, datetime(2026, 11, 20).date()), (None, None, False))
        FixedDateTime.current = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)
        with patch.object(private.subprocess, "run", return_value=self.fake_run(report(new=5))):
            _, second = private.run_once(self.folder, "scheduled",
                                         datetime(2026, 11, 20, 9, tzinfo=private.NY))
        self.assertIsNone(second["summary"]["newSincePrevious"])
        self.assertFalse(second["privateRunMeta"]["observationChainComplete"])

    def test_scheduled_run_disallows_asof_override(self):
        with self.assertRaises(private.LedgerError):
            private.run_once(self.folder, "scheduled",
                             datetime(2026, 11, 19, 9, tzinfo=private.NY),
                             as_of="2026-11-19T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
