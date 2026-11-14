"""Evidence-linked event counts; never substitute post totals or acceptance."""
import copy
import tempfile
import unittest
from pathlib import Path

from tests.social_review_fixtures import add, rows
from tools.social.contracts import ContractError, digest
from tools.social.evaluate import evaluate
from tools.social.signal_store import SignalStore


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve() / "private"; self.root.mkdir(mode=0o700)
        self.source = SignalStore(self.root); self.addCleanup(self.source.close)
        self.one = add(self.source)
        self.two = add(self.source, rows(platform="wb"))
        self.baseline = {"windowStart": "2026-10-20T00:00:00Z", "windowEnd": "2026-11-01T00:00:00Z", "complete": True, "articleIds": ["production-1"]}
        self.assessment = {"baselineHash": digest(self.baseline), "reviewedBy": "synthetic-reviewer", "events": []}

    def event(self, identity="e1", docs=None, verdict="valid", refs=None):
        return {"eventId": identity, "verdict": verdict,
            "evidence": [{"signalId": d["signalId"], "contentHash": d["contentHash"]} for d in (docs or [self.one])],
            "baselineArticleIds": refs or [], "identityError": False}

    def result(self): return evaluate(self.source, self.assessment, self.baseline)

    def test_multiple_posts_same_event_count_once(self):
        self.assessment["events"] = [self.event(docs=[self.one, self.two])]
        report = self.result(); self.assertEqual(report["additionalValidEvents"], 1)
        self.assertEqual(report["reviewedSignals"], 2); self.assertEqual(report["reviewedEvents"], 1)

    def test_overlap_is_not_additional(self):
        self.assessment["events"] = [self.event(refs=["production-1"])]
        report = self.result(); self.assertEqual(report["additionalValidEvents"], 0); self.assertEqual(report["overlappingValidEvents"], 1)

    def test_incomplete_baseline_never_claims_newness(self):
        self.baseline["complete"] = False; self.assessment["baselineHash"] = digest(self.baseline)
        self.assessment["events"] = [self.event()]
        self.assertIsNone(self.result()["additionalValidEvents"])

    def test_no_reviews_is_unknown_not_zero_quality(self):
        report = self.result(); self.assertEqual(report["status"], "not_evaluated")
        self.assertIsNone(report["validRate"]); self.assertIsNone(report["identityErrorRate"])
        self.assertEqual(report["unreviewedSignals"], 2)

    def test_invalid_uncertain_separate_and_denominator_visible(self):
        self.assessment["events"] = [self.event(verdict="invalid"), self.event("e2", [self.two], "uncertain")]
        report = self.result(); self.assertEqual(report["invalidEvents"], 1); self.assertEqual(report["uncertainEvents"], 1)
        self.assertEqual(report["additionalValidEvents"], 0)

    def test_identity_error_is_explicit_reviewer_label(self):
        value = self.event(); value["identityError"] = True; self.assessment["events"] = [value]
        self.assertEqual(self.result()["identityErrorRate"], 1)

    def test_partial_review_coverage_is_not_extrapolated(self):
        self.assessment["events"] = [self.event()]
        report = self.result(); self.assertEqual(report["reviewCoverage"], 0.5); self.assertEqual(report["unreviewedSignals"], 1)
        self.assertEqual(report["sampling"], "reviewer-selected-not-random")

    def test_duplicate_signal_across_events_rejected(self):
        self.assessment["events"] = [self.event(), self.event("e2")]
        with self.assertRaisesRegex(ContractError, "duplicate_signal"): self.result()

    def test_duplicate_event_ids_rejected(self):
        self.assessment["events"] = [self.event(), self.event(docs=[self.two])]
        with self.assertRaisesRegex(ContractError, "event_shape"): self.result()

    def test_unknown_signal_and_unknown_version_rejected(self):
        event = self.event(); self.assessment["events"] = [event]
        event["evidence"][0]["contentHash"] = "f" * 64
        with self.assertRaisesRegex(ContractError, "evidence_missing"): self.result()
        event["evidence"][0]["signalId"] = "xhs:note:missing"
        with self.assertRaisesRegex(ContractError, "unknown_signal"): self.result()

    def test_unknown_baseline_article_rejected(self):
        self.assessment["events"] = [self.event(refs=["missing"])]
        with self.assertRaisesRegex(ContractError, "unknown_baseline"): self.result()

    def test_window_must_match_first_seen_cohort(self):
        self.baseline["windowStart"] = "2026-10-25T00:00:00Z"; self.assessment["baselineHash"] = digest(self.baseline)
        self.assessment["events"] = [self.event()]
        with self.assertRaisesRegex(ContractError, "outside_cohort"): self.result()

    def test_changed_baseline_hash_rejected(self):
        self.baseline["articleIds"].append("new-id")
        with self.assertRaisesRegex(ContractError, "assessment_shape"): self.result()

    def test_reversed_and_naive_windows_rejected(self):
        for start in ("2027-01-01T00:00:00Z", "2026-10-20T00:00:00"):
            self.baseline["windowStart"] = start
            with self.assertRaises(ContractError): self.result()

    def test_baseline_duplicates_and_sensitive_notes_rejected(self):
        self.baseline["articleIds"] = ["same", "same"]
        with self.assertRaisesRegex(ContractError, "article_ids"): self.result()
        self.baseline["articleIds"] = ["Cookie=PRIVATE"]
        with self.assertRaises(ContractError) as caught: self.result()
        self.assertNotIn("PRIVATE", str(caught.exception))

    def test_readonly_no_fake_cost_or_latency(self):
        before = (self.root / "signals.sqlite3").read_bytes(); inputs = copy.deepcopy([self.assessment, self.baseline])
        report = self.result(); self.assertIsNone(report["cost"]); self.assertIsNone(report["discoveryLatency"])
        self.assertEqual(before, (self.root / "signals.sqlite3").read_bytes()); self.assertEqual(inputs, [self.assessment, self.baseline])


if __name__ == "__main__": unittest.main()
