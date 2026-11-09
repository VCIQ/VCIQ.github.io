"""Synthetic-only, deterministic coverage provenance and bridge regression."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import unittest

from tools.company_profile_refresh_queue import build_queue, mark_processed_events
from tools.company_profile_writer_coverage_attestation import (
    CoverageError, attest_coverage,
)
from tools.company_profile_writer_evidence_handoff import (
    EvidenceBoundWorkspace, EvidenceError, PROFILES,
)
from tools.company_profile_writer_pr_handoff import submit
from tools.ensure_venture_profile_coverage import (
    build_repaired_snapshot, ensure_catalog_coverage,
)
from tools.venture_profile_extraction import parse_catalog
from tests.test_company_profile_writer_evidence_handoff import (
    CATALOG_FIXTURE, FakeGitHub, StubCheckout,
)
from tests.test_company_profile_writer_transition_gate import (
    ARTICLES as SOURCE, NOW, NAMES, sample,
)

UPDATED = NOW.isoformat()
STARTED = (NOW - timedelta(minutes=1)).isoformat()
FINISHED = (NOW + timedelta(minutes=2)).isoformat()


def fixture(*, missing_company: bool = True):
    base_queue, _, _, base_profiles, _ = sample()
    # The existing real snapshot has a list of runtime source statuses.
    # Synthetic profile fixture defaults to a dict because earlier tests
    # don't exercise source-status reconciliation.
    base_profiles["sourceStatus"] = []
    if missing_company:
        del base_profiles["companies"]["anthropic"]
    companies, institutions = parse_catalog(CATALOG_FIXTURE)
    comp, inst, statuses, quality, report = ensure_catalog_coverage(
        base_profiles, companies, institutions, updated_at=UPDATED,
    )
    changed = bool(report["addedCompanies"] or
                   report["addedInstitutions"] or report["addedStatuses"])
    observed = (
        build_repaired_snapshot(base_profiles, comp, inst, statuses, quality,
                                generated_at=UPDATED) if changed else deepcopy(base_profiles)
    )
    return base_queue, base_profiles, observed, {
        **report, "changed": changed,
    }


def attest(base, observed, report, **changes):
    params = {
        "updated_at": UPDATED,
        "run_started_at": STARTED,
        "run_completed_at": FINISHED,
    }
    params.update(changes)
    return attest_coverage(base, observed, CATALOG_FIXTURE, report, **params)


class CoverageAttestationTests(unittest.TestCase):
    def test_missing_catalog_company_has_recomputable_fallback(self):
        _, base, observed, report = fixture()
        result = attest(base, observed, report)
        self.assertEqual(result["addedCompanySlugs"], ("anthropic",))
        self.assertEqual(set(observed["companies"]) - set(base["companies"]), {"anthropic"})
        self.assertTrue(result["needsReview"])
        self.assertFalse(result["mergeAuthorized"])
        self.assertFalse(result["publicationAuthorized"])

    def test_unchanged_prior_profile_cannot_be_replaced(self):
        _, base, observed, report = fixture()
        observed["companies"]["openai"]["name"] = "Unauthorized"
        with self.assertRaisesRegex(CoverageError, "SNAPSHOT_MISMATCH"):
            attest(base, observed, report)

    def test_fake_extra_company_in_report_cannot_authorize_it(self):
        _, base, observed, report = fixture()
        report["addedCompanies"] = ["anthropic", "fake"]
        with self.assertRaisesRegex(CoverageError, "REPORT_MISMATCH"):
            attest(base, observed, report)

    def test_unreported_extra_company_is_not_authorized(self):
        _, base, observed, report = fixture()
        observed["companies"]["fake"] = {"status": "fallback"}
        with self.assertRaisesRegex(CoverageError, "SNAPSHOT_MISMATCH"):
            attest(base, observed, report)

    def test_no_changes_in_report_but_changed_snapshot_rejected(self):
        _, base, observed, report = fixture()
        report["changed"] = False
        with self.assertRaisesRegex(CoverageError, "REPORT_MISMATCH"):
            attest(base, observed, report)

    def test_missing_time_and_time_outside_run_fail_closed(self):
        _, base, observed, report = fixture()
        for kwargs in (
            {"updated_at": "2026-11-07T10:00:00Z"},
            {"run_started_at": "2026-11-09T12:00:00Z"},
            {"run_completed_at": "2026-11-08T06:00:00Z"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(
                CoverageError, "TIME_INVALID"
            ):
                attest(base, observed, report, **kwargs)

    def test_catalog_unparseable_must_not_use_local_registry(self):
        _, base, observed, report = fixture()
        with self.assertRaisesRegex(CoverageError, "CATALOG_INVALID"):
            attest_coverage(
                base, observed, "export const companies = [];",
                report, updated_at=UPDATED, run_started_at=STARTED,
                run_completed_at=FINISHED,
            )

    def test_missing_institution_is_not_approved_for_this_pilot(self):
        _, base, observed, report = fixture()
        catalog = CATALOG_FIXTURE.replace(
            "export type Institution = {",
            '''export type Institution = {};
export const institutionCatalog: Institution[] = [
  { slug:"capital", name:"Capital", source:official("Capital","https://capital.example/") },
];
export type IpoCompany = {''',
        )
        with self.assertRaisesRegex(CoverageError, "INSTITUTIONS_UNSUPPORTED"):
            attest_coverage(base, observed, catalog, report,
                            updated_at=UPDATED, run_started_at=STARTED,
                            run_completed_at=FINISHED)

    def test_stage_output_mutation_after_report_fails_closed(self):
        _, base, observed, report = fixture()
        observed["sourceStatus"] = []
        with self.assertRaisesRegex(CoverageError, "SNAPSHOT_MISMATCH"):
            attest(base, observed, report)

    def test_no_new_company_but_missing_statuses_are_exactly_checked(self):
        _, base, observed, report = fixture(missing_company=False)
        self.assertTrue(report["changed"])
        self.assertEqual(report["addedCompanies"], [])
        result = attest(base, observed, report)
        self.assertEqual(result["addedCompanySlugs"], ())

    def test_stage_attestation_allows_bridge_after_exact_verification(self):
        base_queue, before, coverage, report = fixture()
        intent = build_queue(SOURCE, coverage, NAMES, base_queue,
                             now=NOW, select_limit=1)
        self.assertEqual(intent["selectedSlugs"], ["openai"])
        processed = mark_processed_events(intent, ["openai"], now=NOW)
        candidate = deepcopy(coverage)
        candidate["companies"]["openai"]["updatedAt"] = UPDATED
        final = build_queue(SOURCE, candidate, NAMES, intent, now=NOW,
                            processed_events=processed)
        checkout = StubCheckout(
            baseline=base_queue, profile_before=before,
            selected=intent, after=final, profile_after=candidate,
        )
        wrapper = EvidenceBoundWorkspace(
            checkout, intent, STARTED, FINISHED,
            coverage_snapshot=coverage, coverage_report=report,
            coverage_updated_at=UPDATED,
        )
        github = FakeGitHub()
        result = submit(wrapper, github, run_id="12345", attempt=1, authorized=True)
        self.assertEqual(result["decision"], "draft_pr_opened")
        self.assertEqual(github.calls.count("create_ref"), 2)
        self.assertFalse(result["published"])

    def test_invalid_stage_blocks_before_any_github_request(self):
        base_queue, before, coverage, report = fixture()
        intent = build_queue(SOURCE, coverage, NAMES, base_queue,
                             now=NOW, select_limit=1)
        processed = mark_processed_events(intent, ["openai"], now=NOW)
        candidate = deepcopy(coverage)
        candidate["companies"]["openai"]["updatedAt"] = UPDATED
        final = build_queue(SOURCE, candidate, NAMES, intent,
                            now=NOW, processed_events=processed)
        checkout = StubCheckout(
            baseline=base_queue, profile_before=before,
            selected=intent, after=final, profile_after=candidate,
        )
        forged = deepcopy(report)
        forged["addedCompanies"] = []
        github = FakeGitHub()
        result = submit(EvidenceBoundWorkspace(
            checkout, intent, STARTED, FINISHED,
            coverage_snapshot=coverage, coverage_report=forged,
            coverage_updated_at=UPDATED,
        ), github, run_id="12345", attempt=1, authorized=True)
        self.assertEqual(result["errorCode"], "COVERAGE_REPORT_MISMATCH")
        self.assertEqual(github.calls, [])


if __name__ == "__main__":
    unittest.main()
