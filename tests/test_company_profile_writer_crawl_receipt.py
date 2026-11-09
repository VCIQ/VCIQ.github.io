"""Synthetic contract tests for selected-company crawl freshness.

No HTTP traffic, no GitHub API, no production data mutation.
"""
from __future__ import annotations

import copy
import unittest

from tools.company_profile_writer_crawl_receipt import (
    CrawlReceiptError, check_selected_crawl_receipts, stable_sha256,
)


START = "2026-11-08T13:00:00+00:00"
CAPTURED = "2026-11-08T13:04:00+00:00"
END = "2026-11-08T13:06:00+00:00"
SOURCE = "https://alpha.example/"


def example(*, state="ok", pages=2, sections=5, score=80):
    profile = {
        "slug": "alpha",
        "name": "Alpha",
        "updatedAt": "2026-11-08T13:03:00+00:00",
        "status": state,
        "background": "Alpha company profile",
        "technology": "Research",
        "products": ["Alpha engine"],
        "sources": [
            {"url": "https://alpha.example/about"},
            {"url": "https://alpha.example/research"},
        ],
        "warnings": [],
        "evidenceScore": score,
    }
    status = {
        "kind": "company",
        "slug": "alpha",
        "name": "Alpha",
        "status": state,
        "fetchedPages": pages,
        "acceptedSections": sections,
        "retainedPrevious": False,
        "elapsedSeconds": 1.4,
    }
    snapshot = {
        "companies": {"alpha": profile},
        "sourceStatus": [status],
        "qualityGate": {"passed": True},
    }
    receipt = {
        "slug": "alpha",
        "exitCode": 0,
        "capturedAt": CAPTURED,
        "statusSha256": stable_sha256(status),
        "profileSha256": stable_sha256(profile),
    }
    return snapshot, [receipt]


def verify(snapshot, receipts, **overrides):
    kw = {
        "selected_slugs": ["alpha"],
        "pinned_official_urls": {"alpha": SOURCE},
        "crawl_snapshot": snapshot,
        "per_company_receipts": receipts,
        "run_started_at": START,
        "run_completed_at": END,
    }
    kw.update(overrides)
    return check_selected_crawl_receipts(**kw)


def rehash(snapshot, receipts):
    receipts[0]["statusSha256"] = stable_sha256(snapshot["sourceStatus"][0])
    receipts[0]["profileSha256"] = stable_sha256(snapshot["companies"]["alpha"])


class SelectedCompanyCrawlReceiptTests(unittest.TestCase):
    def test_fresh_ok_profile_with_approved_sources_passes(self):
        snapshot, receipts = example()
        result = verify(snapshot, receipts)
        self.assertTrue(result["ok"])
        self.assertEqual(result["verifiedCompanyCount"], 1)
        self.assertFalse(result["markProcessedAuthorized"])
        self.assertFalse(result["mergeAuthorized"])
        self.assertFalse(result["publicationAuthorized"])
        self.assertFalse(result["sourceFetchCryptographicallyAttested"])

    def test_strong_partial_profile_passes_when_all_constraints_satisfied(self):
        snap, receipts = example(state="partial", pages=2, sections=4, score=74)
        self.assertTrue(verify(snap, receipts)["ok"])

    def test_retained_old_profile_must_not_mark_selected_event_processed(self):
        snap, receipts = example(state="retained")
        snap["sourceStatus"][0]["retainedPrevious"] = True
        rehash(snap, receipts)
        with self.assertRaisesRegex(CrawlReceiptError, "NOT_FRESH"):
            verify(snap, receipts)

    def test_fallback_without_pages_is_rejected_even_if_global_gate_green(self):
        snap, receipts = example(state="fallback", pages=0, sections=5)
        rehash(snap, receipts)
        with self.assertRaisesRegex(CrawlReceiptError, "NOT_FRESH"):
            verify(snap, receipts)

    def test_successful_subprocess_exit_is_not_sufficient_after_error(self):
        snap, receipts = example()
        snap["sourceStatus"][0]["error"] = "synthetic timeout"
        rehash(snap, receipts)
        with self.assertRaisesRegex(CrawlReceiptError, "NOT_FRESH"):
            verify(snap, receipts)

    def test_weak_partial_evidence_is_rejected(self):
        for field, value in (("evidenceScore", 42), ("sources", [{"url": SOURCE}]),
                             ("technology", "")):
            with self.subTest(field=field):
                snap, receipts = example(state="partial", sections=4)
                snap["companies"]["alpha"][field] = value
                rehash(snap, receipts)
                with self.assertRaisesRegex(CrawlReceiptError, "PARTIAL_TOO_WEAK"):
                    verify(snap, receipts)

    def test_insufficient_new_pages_or_sections_fail(self):
        for key, value in (("fetchedPages", 1), ("acceptedSections", 2)):
            with self.subTest(key=key):
                snap, receipts = example()
                snap["sourceStatus"][0][key] = value
                rehash(snap, receipts)
                with self.assertRaisesRegex(CrawlReceiptError, "INSUFFICIENT_CRAWL"):
                    verify(snap, receipts)

    def test_profile_update_older_than_job_is_rejected(self):
        snap, receipts = example()
        snap["companies"]["alpha"]["updatedAt"] = "2026-11-07T00:00:00+00:00"
        rehash(snap, receipts)
        with self.assertRaisesRegex(CrawlReceiptError, "PROFILE_TIME_INVALID"):
            verify(snap, receipts)

    def test_tampered_receipt_digest_is_rejected(self):
        snap, receipts = example()
        receipts[0]["profileSha256"] = "0" * 64
        with self.assertRaisesRegex(CrawlReceiptError, "DIGEST_MISMATCH"):
            verify(snap, receipts)

    def test_untrusted_url_cannot_pretend_to_be_official_host(self):
        snap, receipts = example()
        snap["companies"]["alpha"]["sources"] = [{"url": "https://fakealpha.example/research"}]
        rehash(snap, receipts)
        with self.assertRaisesRegex(CrawlReceiptError, "OFFICIAL_SOURCE_MISSING"):
            verify(snap, receipts)

    def test_failed_subprocess_or_missing_receipt_fails_closed(self):
        snap, receipts = example()
        receipts[0]["exitCode"] = 1
        with self.assertRaisesRegex(CrawlReceiptError, "NONZERO_EXIT"):
            verify(snap, receipts)
        with self.assertRaisesRegex(CrawlReceiptError, "INPUT_INVALID"):
            verify(snap, [])

    def test_duplicate_selected_status_is_rejected(self):
        snap, receipts = example()
        snap["sourceStatus"].append(copy.deepcopy(snap["sourceStatus"][0]))
        with self.assertRaisesRegex(CrawlReceiptError, "STATUS_DUPLICATE"):
            verify(snap, receipts)

    def test_replayed_receipt_outside_run_window_is_rejected(self):
        snap, receipts = example()
        receipts[0]["capturedAt"] = "2026-11-07T13:04:00+00:00"
        with self.assertRaisesRegex(CrawlReceiptError, "CAPTURE_TIME_INVALID"):
            verify(snap, receipts)

    def test_duplicate_or_unexpected_selected_company_is_rejected(self):
        snap, receipts = example()
        with self.assertRaisesRegex(CrawlReceiptError, "SELECTION_INVALID"):
            verify(snap, receipts, selected_slugs=["alpha", "alpha"])
        with self.assertRaisesRegex(CrawlReceiptError, "INPUT_INVALID"):
            verify(snap, receipts, pinned_official_urls={"other": SOURCE})

    def test_no_selected_companies_is_a_safe_noop(self):
        result = check_selected_crawl_receipts(
            [], {}, {"companies": {}, "sourceStatus": [],
                     "qualityGate": {"passed": True}},
            [], run_started_at=START, run_completed_at=END,
        )
        self.assertEqual(result["verifiedCompanyCount"], 0)
        self.assertFalse(result["markProcessedAuthorized"])

    def test_nonfinite_elapsed_and_unrealistic_duration_rejected(self):
        snap, receipts = example()
        snap["sourceStatus"][0]["elapsedSeconds"] = float("nan")
        with self.assertRaisesRegex(CrawlReceiptError, "JSON_INVALID"):
            rehash(snap, receipts)
        snap, receipts = example()
        with self.assertRaisesRegex(CrawlReceiptError, "RUN_WINDOW_INVALID"):
            verify(snap, receipts, run_completed_at="2026-11-08T15:30:00+00:00")


if __name__ == "__main__":
    unittest.main()
