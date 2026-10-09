import unittest

from tools.innovation_investor_coverage import audit_coverage, markdown_summary


def sample():
    roster = {"institutions": [{"id": f"firm-{i}", "name": f"Firm {i}"} for i in range(30)]}
    results = []
    for i in range(30):
        status = "candidates-found" if i == 0 else ("unavailable" if i == 1 else "no-candidates-adapter-review")
        candidates = [{
            "institutionId": "firm-0",
            "claimStatus": "unreviewed-navigation-candidate",
            "investmentRelationConfirmed": False,
        }] if i == 0 else []
        results.append({"institutionId": f"firm-{i}", "status": status, "candidates": candidates})
    return roster, {
        "mode": "official-page-navigation-discovery-only",
        "autoPublication": False, "institutionsExamined": 30, "candidateCount": 1,
        "generatedAt": "2026-10-09T06:00:00Z", "results": results,
    }


class CoverageTests(unittest.TestCase):
    def test_distinguishes_reachability_from_event_verification(self):
        roster, scout = sample()
        report = audit_coverage(roster, scout)
        self.assertEqual(report["registeredInstitutions"], 30)
        self.assertEqual(report["attemptedInstitutions"], 30)
        self.assertEqual(report["reachableOfficialHomepages"], 29)
        self.assertEqual(report["retrievalCoveragePercent"], 96.7)
        self.assertEqual(report["homepagesWithNavigationCandidates"], 1)
        self.assertEqual(report["reachableHomepagesWithoutCandidates"], 28)
        self.assertEqual(report["unavailableOfficialHomepages"], 1)
        self.assertIsNone(report["verifiedInvestmentEvents"])
        self.assertIn("不代表投资组合", markdown_summary(report))

    def test_missing_duplicate_or_foreign_results_are_not_silently_covered(self):
        roster, scout = sample()
        for results in [
            scout["results"][:-1],
            [scout["results"][0]] * 30,
            [{**scout["results"][0], "institutionId": "unknown"}] + scout["results"][1:],
        ]:
            with self.subTest(results=results[:1]), self.assertRaises(ValueError):
                audit_coverage(roster, {**scout, "results": results})

    def test_never_promotes_navigation_to_investment_fact(self):
        roster, scout = sample()
        scout["results"][0]["candidates"][0]["investmentRelationConfirmed"] = True
        with self.assertRaises(ValueError):
            audit_coverage(roster, scout)

    def test_counts_must_match_and_no_zero_candidate_success_mislabel(self):
        roster, scout = sample()
        with self.assertRaises(ValueError):
            audit_coverage(roster, {**scout, "candidateCount": 2})
        scout["results"][0]["candidates"] = []
        with self.assertRaises(ValueError):
            audit_coverage(roster, scout)


if __name__ == "__main__":
    unittest.main()
