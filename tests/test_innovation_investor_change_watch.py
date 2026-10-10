import copy
import unittest

from tools.innovation_investor_change_watch import compare_scout_runs, markdown
from tests.test_innovation_investor_review_queue import fixture, candidate, add

IDENTITIES = {
    "projects": [
        {"id": "chipco", "observedNames": ["ChipCo"]},
        {"id": "oxide", "observedNames": ["Oxide"]},
    ]
}
EVIDENCE = {"records": []}

def compare(cur, prev, roster, evidence=EVIDENCE, identities=IDENTITIES):
    return compare_scout_runs(cur, prev, roster, evidence, identities)

class ChangeWatchTests(unittest.TestCase):
    def test_new_navigation_link_is_not_verified_deal_or_publication(self):
        roster, previous = fixture()
        current = copy.deepcopy(previous)
        current["generatedAt"] = "2026-10-10T03:00:00Z"
        add(current, 0,
            candidate("firm-0", 9, "Investing in ChipCo", "/news/investing-in-chipco"))
        report = compare(current, previous, roster)
        self.assertTrue(report["baselineAvailable"])
        self.assertEqual(report["comparableInstitutions"], 30)
        self.assertEqual(report["newlySeenLinksInComparableWindows"], 1)
        self.assertEqual(report["verifiedNewDealsByThisMonitor"], 0)
        item = report["newlySeenLinks"][0]
        self.assertIsNone(item["publishedAt"])
        self.assertEqual(item["possibleProjectIdsByTitleOrPath"], ["chipco"])
        self.assertFalse(item["verifiedInvestmentEvent"])
        self.assertEqual(item["claimStatus"], "navigation-change-only-unverified")
        self.assertIn("不表示当日发布", markdown(report))

    def test_recovered_page_not_converted_to_twelve_new_articles(self):
        roster, previous = fixture()
        previous["results"][0]["status"] = "unavailable"
        previous["results"][0]["reason"] = "URLError"
        current = copy.deepcopy(previous)
        add(current, 0,
            candidate("firm-0", 1, "Investing in ChipCo", "/news/investing-in-chipco"))
        current["results"][0].pop("reason", None)
        report = compare(current, previous, roster)
        self.assertEqual(report["sourceRecoveredInstitutions"], 1)
        self.assertEqual(report["newlySeenLinksInComparableWindows"], 0)
        self.assertEqual(report["institutions"][0]["comparisonState"], "site-recovered-baseline-unavailable")
        self.assertIsNone(report["institutions"][0]["newlySeenInComparableWindow"])

    def test_failed_current_scan_never_proves_delisting_or_zero_updates(self):
        roster, previous = fixture()
        add(previous, 0, candidate("firm-0", 1, "Investing in ChipCo", "/news/investing-in-chipco"))
        current = copy.deepcopy(previous)
        current["results"][0]["status"] = "unavailable"
        current["results"][0]["reason"] = "robots-unavailable-http-429"
        current["results"][0]["candidates"] = []
        current["candidateCount"] = 0
        report = compare(current, previous, roster)
        self.assertEqual(report["sourceNewlyUnavailableInstitutions"], 1)
        self.assertEqual(report["noLongerInCappedNavigationWindow"], 0)
        self.assertEqual(report["verifiedNewFailuresByThisMonitor"], 0)
        self.assertEqual(report["institutions"][0]["comparisonState"], "site-newly-unavailable")

    def test_disappearance_from_capped_links_not_assumed_deleted_or_company_shutdown(self):
        roster, previous = fixture()
        add(previous, 0, candidate("firm-0", 1, "Investing in ChipCo", "/news/investing-in-chipco"))
        current = copy.deepcopy(previous)
        current["results"][0]["candidates"] = []
        current["results"][0]["status"] = "no-candidates-adapter-review"
        current["candidateCount"] = 0
        report = compare(current, previous, roster)
        self.assertEqual(report["noLongerInCappedNavigationWindow"], 1)
        self.assertTrue(all(not x["confirmedDeleted"] and not x["confirmedExitOrShutdown"]
                            for x in report["noLongerListedLinks"]))
        self.assertEqual(report["verifiedNewFailuresByThisMonitor"], 0)

    def test_missing_historical_artifact_yields_unknown_delta_not_zero(self):
        roster, current = fixture()
        add(current, 1, candidate("firm-1", 1, "New robotics funding", "/news/robotics-funding"))
        report = compare(current, None, roster)
        self.assertFalse(report["baselineAvailable"])
        self.assertIsNone(report["newlySeenLinksInComparableWindows"])
        self.assertIsNone(report["noLongerInCappedNavigationWindow"])
        self.assertIn("不能报告0条变化", markdown(report))

    def test_negative_signal_is_open_original_not_inferred_bankruptcy(self):
        roster, old = fixture()
        now = copy.deepcopy(old)
        add(now, 0, candidate("firm-0", 2, "ChipCo bankruptcy filing", "/news/chipco-bankruptcy"))
        report = compare(now, old, roster)
        self.assertEqual(report["newLinkNegativeTitleSignals"], 1)
        item = report["newlySeenLinks"][0]
        self.assertEqual(item["negativeEventTitleSignals"], ["possible-insolvency"])
        self.assertFalse(item["verifiedNegativeOutcome"])
        self.assertEqual(report["verifiedNewFailuresByThisMonitor"], 0)

    def test_project_name_is_only_hint_and_does_not_match_longer_names(self):
        roster, previous = fixture()
        current = copy.deepcopy(previous)
        add(current, 0,
            candidate("firm-0", 2, "Investing in ChipCompany", "/news/investing-in-chipcompany"),
            candidate("firm-0", 3, "Investing in ChipCo", "/news/investing-in-chipco"))
        report = compare(current, previous, roster)
        matching = {x["title"]: x["possibleProjectIdsByTitleOrPath"] for x in report["newlySeenLinks"]}
        self.assertEqual(matching["Investing in ChipCompany"], [])
        self.assertEqual(matching["Investing in ChipCo"], ["chipco"])

    def test_reviewed_original_source_is_not_recounted_as_a_new_investment(self):
        roster, previous = fixture()
        current = copy.deepcopy(previous)
        add(current, 0, candidate("firm-0", 1, "Investing in ChipCo", "/news/investing-in-chipco"))
        evidence = {"records": [{"source": {"url": "https://www.firm-0.example.org/news/investing-in-chipco/"},
                                 "kind": "investment", "project": "ChipCo", "institutionId": "firm-0"}]}
        report = compare(current, previous, roster, evidence)
        self.assertEqual(report["newlySeenLinksInComparableWindows"], 1)
        self.assertEqual(report["newLinksAlreadyUsingReviewedSource"], 1)
        self.assertEqual(report["verifiedNewDealsByThisMonitor"], 0)
        self.assertTrue(report["newlySeenLinks"][0]["alreadyReviewedAsSourceForInstitution"])

    def test_malformed_foreign_and_forged_claims_fail_before_comparison(self):
        roster, previous = fixture()
        current = copy.deepcopy(previous)
        add(current, 0, candidate("firm-0", 1, "Investing in ChipCo", "/news/investing-in-chipco"))
        for mutation in [
            lambda c: c["results"][0]["candidates"][0].update(investmentRelationConfirmed=True),
            lambda c: c["results"][0]["candidates"][0].update(url="https://malicious.example.org/post"),
            lambda c: c["results"][0].update(institutionId="firm-1"),
        ]:
            edited = copy.deepcopy(current)
            mutation(edited)
            with self.assertRaises(ValueError):
                compare(edited, previous, roster)

    def test_ci_only_compares_production_artifacts_with_read_only_permission(self):
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/innovation-investor-source-scout.yml").read_text(encoding="utf-8")
        self.assertIn("actions: read", workflow)
        self.assertIn("gh run download", workflow)
        self.assertIn("select(.event != \"pull_request\")", workflow)
        self.assertIn("innovation-investor-change-report.json", workflow)
        self.assertIn("innovation-investor-change-report.md", workflow)
        self.assertIn("retention-days: 14", workflow)
        self.assertNotIn("gh issue create", workflow)
        self.assertNotIn("git push", workflow)

if __name__ == "__main__":
    unittest.main()
