"""Synthetic observed-crawl tests. No network, live crawler or GitHub writes."""
from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from tools.company_profile_writer_crawl_observer import (
    ObservedCrawlError, observe_selected_company_crawls,
)

START = "2026-11-08T13:00:00+00:00"
TIMES = (
    "2026-11-08T13:01:00+00:00",
    "2026-11-08T13:04:00+00:00",
    "2026-11-08T13:05:00+00:00",
    "2026-11-08T13:06:00+00:00",
)
SHA = "a" * 40


def company(slug, *, updated="2026-11-08T13:03:00+00:00", state="ok"):
    profile = {
        "slug": slug,
        "name": slug,
        "updatedAt": updated,
        "status": state,
        "background": "Company background",
        "technology": "Research",
        "products": ["engine"],
        "sources": [
            {"url": f"https://{slug}.example/about"},
            {"url": f"https://{slug}.example/research"},
        ],
        "warnings": [],
        "evidenceScore": 80,
    }
    status = {
        "kind": "company",
        "slug": slug,
        "name": slug,
        "status": state,
        "fetchedPages": 2,
        "acceptedSections": 5,
        "retainedPrevious": False,
        "elapsedSeconds": 1.4,
    }
    return profile, status


class Fixture:
    def __init__(self, slugs=("alpha",)):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "tools").mkdir()
        (self.root / "tools/crawl_venture_profiles.py").write_text("# synthetic only\n")
        (self.root / "public/data").mkdir(parents=True)
        self.path = self.root / "public/data/venture_profiles.json"
        self.slugs = list(slugs)
        self.selection = {
            "generatedAt": START,
            "selectedSlugs": list(slugs),
            "selectedCount": len(slugs),
        }
        self.urls = {s: f"https://{s}.example/" for s in slugs}
        self.snapshot = {
            "companies": {},
            "sourceStatus": [],
            "qualityGate": {"passed": True},
        }
        for slug in slugs:
            profile, status = company(slug, updated="2026-11-07T12:00:00+00:00")
            self.snapshot["companies"][slug] = profile
            self.snapshot["sourceStatus"].append(status)
        self._write()
        self.commands = []
        self.returncode = 0
        self.mutate = None
        self.ticks = [TIMES[0], TIMES[1], TIMES[3]]

    def close(self):
        self.temp.cleanup()

    def _write(self):
        self.path.write_text(json.dumps(self.snapshot, sort_keys=True))

    def clock(self):
        return datetime.fromisoformat(self.ticks.pop(0))

    def runner(self, command, *, cwd, timeout):
        self.commands.append((tuple(command), cwd, timeout))
        slug = command[command.index("--slug") + 1]
        if self.returncode == 0:
            profile, status = company(slug)
            self.snapshot["companies"][slug] = profile
            self.snapshot["sourceStatus"] = [
                row for row in self.snapshot["sourceStatus"]
                if not (row["kind"] == "company" and row["slug"] == slug)
            ] + [status]
            if self.mutate:
                self.mutate(self.snapshot, slug)
            self._write()
        return subprocess.CompletedProcess(command, self.returncode)

    def observe(self, **overrides):
        kwargs = {
            "checkout_root": self.root,
            "pre_crawl_selection": self.selection,
            "pinned_official_urls": self.urls,
            "base_sha": SHA,
            "run_id": "synthetic-run-1",
            "run_started_at": START,
            "run_command": self.runner,
            "clock": self.clock,
            "authorized": True,
        }
        kwargs.update(overrides)
        return observe_selected_company_crawls(**kwargs)


class ObservedCompanyCrawlTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.close()

    def test_success_records_exact_command_and_fail_closed_verdict(self):
        result = self.f.observe()
        self.assertTrue(result["ok"])
        self.assertEqual(result["verifiedCompanyCount"], 1)
        self.assertEqual(result["baseSha"], SHA)
        self.assertEqual(len(result["receipts"]), 1)
        self.assertEqual(result["receipts"][0]["slug"], "alpha")
        self.assertEqual(result["receipts"][0]["exitCode"], 0)
        self.assertEqual(self.f.commands[0][0][-8:], (
            "--kind", "company", "--slug", "alpha",
            "--workers", "1", "--max-pages", "6",
        ))
        self.assertEqual(self.f.commands[0][1], self.f.root.resolve())
        self.assertEqual(self.f.commands[0][2], 600)
        self.assertFalse(result["markProcessedAuthorized"])
        self.assertFalse(result["mergeAuthorized"])
        self.assertFalse(result["publicationAuthorized"])
        self.assertFalse(result["sourceFetchCryptographicallyAttested"])

    def test_two_selected_slugs_capture_in_order(self):
        self.f.close()
        self.f = Fixture(("alpha", "beta"))
        self.f.ticks = list(TIMES)
        result = self.f.observe()
        self.assertEqual([r["slug"] for r in result["receipts"]], ["alpha", "beta"])
        self.assertEqual(len(self.f.commands), 2)

    def test_unauthorized_execution_never_calls_runner(self):
        with self.assertRaisesRegex(ObservedCrawlError, "NOT_AUTHORIZED"):
            self.f.observe(authorized=False)
        self.assertEqual(self.f.commands, [])

    def test_nonzero_exit_is_failure_even_if_global_snapshot_is_green(self):
        self.f.returncode = 2
        with self.assertRaisesRegex(ObservedCrawlError, "PROCESS_FAILED"):
            self.f.observe()
        self.assertEqual(len(self.f.commands), 1)

    def test_wrong_command_result_is_rejected(self):
        def forged(command, **kwargs):
            return subprocess.CompletedProcess(["sh", "-c", "true"], 0)
        with self.assertRaisesRegex(ObservedCrawlError, "PROCESS_FAILED"):
            self.f.observe(run_command=forged)

    def test_runner_exception_is_redacted_and_fails(self):
        def broken(command, **kwargs):
            raise RuntimeError("private token should not be shown")
        with self.assertRaisesRegex(ObservedCrawlError, "^CRAWL_OBSERVER_PROCESS_FAILED$"):
            self.f.observe(run_command=broken)

    def test_unmodified_profile_does_not_prove_new_crawl(self):
        def no_op(command, **kwargs):
            return subprocess.CompletedProcess(command, 0)
        with self.assertRaisesRegex(ObservedCrawlError, "UNCHANGED_PROFILE"):
            self.f.observe(run_command=no_op)

    def test_retained_previous_profile_fails_final_receipt_gate(self):
        def retained(snapshot, slug):
            snapshot["companies"][slug]["status"] = "retained"
            for row in snapshot["sourceStatus"]:
                if row["slug"] == slug:
                    row["status"] = "retained"
                    row["retainedPrevious"] = True
        self.f.mutate = retained
        with self.assertRaisesRegex(ObservedCrawlError, "NOT_FRESH"):
            self.f.observe()

    def test_later_crawl_tampering_previous_profile_is_detected(self):
        self.f.close()
        self.f = Fixture(("alpha", "beta"))
        self.f.ticks = list(TIMES)
        def mutate(snapshot, slug):
            if slug == "beta":
                snapshot["companies"]["alpha"]["technology"] = "tampered"
        self.f.mutate = mutate
        with self.assertRaisesRegex(ObservedCrawlError, "DIGEST_MISMATCH"):
            self.f.observe()

    def test_duplicate_json_keys_rejected_before_running(self):
        self.f.path.write_text(
            '{"companies":{},"companies":{},"sourceStatus":[],"qualityGate":{}}'
        )
        with self.assertRaisesRegex(ObservedCrawlError, "DUPLICATE_JSON_KEY"):
            self.f.observe()
        self.assertEqual(self.f.commands, [])

    def test_snapshot_symlink_is_never_followed(self):
        original = self.f.root / "original.json"
        self.f.path.rename(original)
        self.f.path.symlink_to(original)
        with self.assertRaisesRegex(ObservedCrawlError, "SYMLINK_SNAPSHOT"):
            self.f.observe()
        self.assertEqual(self.f.commands, [])

    def test_missing_status_from_exit_zero_rejected(self):
        def missing(snapshot, slug):
            snapshot["sourceStatus"] = []
        self.f.mutate = missing
        with self.assertRaisesRegex(ObservedCrawlError, "COMPANY_EVIDENCE_MISSING"):
            self.f.observe()

    def test_invalid_official_url_fails_before_runner(self):
        with self.assertRaisesRegex(ObservedCrawlError, "SOURCE_OR_TIME_INVALID"):
            self.f.observe(pinned_official_urls={"alpha": "http://alpha.example"})
        self.assertEqual(self.f.commands, [])

    def test_wrong_slug_or_duplicate_selection_rejected(self):
        self.f.selection["selectedSlugs"] = ["alpha", "alpha"]
        self.f.selection["selectedCount"] = 2
        with self.assertRaisesRegex(ObservedCrawlError, "SELECTION_INVALID"):
            self.f.observe()
        self.assertEqual(self.f.commands, [])

    def test_too_many_slugs_are_rejected(self):
        self.f.selection["selectedSlugs"] = ["a" + str(i) for i in range(11)]
        self.f.selection["selectedCount"] = 11
        with self.assertRaisesRegex(ObservedCrawlError, "SELECTION_INVALID"):
            self.f.observe()

    def test_selection_earlier_than_run_is_rejected(self):
        self.f.selection["generatedAt"] = "2026-11-07T13:00:00+00:00"
        with self.assertRaisesRegex(ObservedCrawlError, "STALE_SELECTION"):
            self.f.observe()

    def test_execution_clock_outside_window_blocks_before_running(self):
        self.f.ticks = ["2026-11-08T15:00:00+00:00"]
        with self.assertRaisesRegex(ObservedCrawlError, "RUN_WINDOW_INVALID"):
            self.f.observe()
        self.assertEqual(self.f.commands, [])

    def test_final_quality_gate_failed_blocks_even_with_valid_receipts(self):
        def quality(snapshot, slug):
            snapshot["qualityGate"]["passed"] = False
        self.f.mutate = quality
        with self.assertRaisesRegex(ObservedCrawlError, "INPUT_INVALID"):
            self.f.observe()

    def test_invalid_sha_or_run_id_fails_before_runner(self):
        for kwargs in ({"base_sha": "not-a-sha"}, {"run_id": "../unsafe"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ObservedCrawlError, "IDENTITY_INVALID"):
                    self.f.observe(**kwargs)
        self.assertEqual(self.f.commands, [])


if __name__ == "__main__":
    unittest.main()
