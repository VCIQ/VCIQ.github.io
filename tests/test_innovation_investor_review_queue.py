import copy
import unittest

from tools.innovation_investor_review_queue import (
    build_review_queue, classify_link, render_markdown,
)


def fixture():
    firms = [
        {"id": f"firm-{i}", "name": f"Official Firm {i}",
         "officialUrl": f"https://firm-{i}.example.org/"}
        for i in range(30)
    ]
    source_results = [
        {"institutionId": f"firm-{i}", "sourceUrl": f"https://firm-{i}.example.org/",
         "status": "no-candidates-adapter-review", "candidates": []}
        for i in range(30)
    ]
    return {"institutions": firms}, {
        "mode": "official-page-navigation-discovery-only",
        "autoPublication": False, "generatedAt": "2026-10-09T07:00:00Z",
        "institutionsExamined": 30, "candidateCount": 0, "results": source_results,
    }


def candidate(institution, serial, title, path, **edits):
    row = {
        "id": f"stable-{institution}-{serial}",
        "institutionId": institution,
        "title": title,
        "url": f"https://{institution}.example.org{path}",
        "discoveredOn": f"https://{institution}.example.org/",
        "publishedAt": None, "claimStatus": "unreviewed-navigation-candidate",
        "investmentRelationConfirmed": False,
    }
    row.update(edits)
    return row


def add(scout, institution_index, *rows):
    r = scout["results"][institution_index]
    r["candidates"].extend(rows)
    r["status"] = "candidates-found"
    scout["candidateCount"] += len(rows)


class InvestorReviewQueueTests(unittest.TestCase):
    def test_routing_separates_navigation_investment_speech_people_and_results(self):
        self.assertEqual(classify_link("Investment Policy", "https://a.test/investment_policy"), "navigation")
        self.assertEqual(classify_link("Portfolio", "https://a.test/portfolio"), "navigation")
        self.assertEqual(classify_link("Investing in ChipCo", "https://a.test/announcement/investing-in-chipco"), "investment-lead")
        self.assertEqual(classify_link("AI chips acquired", "https://a.test/news/chipco-acquired"), "outcome-lead")
        self.assertEqual(classify_link("AI thesis podcast", "https://a.test/podcast/talk"), "viewpoint-lead")
        self.assertEqual(classify_link("Sam Investor", "https://a.test/team/sam"), "person-lead")
        self.assertEqual(classify_link("ChipCo", "https://a.test/companies/chipco"), "portfolio-lead")
        self.assertEqual(classify_link("Read more", "https://a.test/perspectives/chips"), "article-lead")

    def test_queue_has_no_automatically_verified_fact(self):
        registry, scout = fixture()
        add(scout, 0,
            candidate("firm-0", 1, "Our Investment in New ChipCo", "/stories/investing-in-chipco"),
            candidate("firm-0", 2, "Our Team", "/team"),
            candidate("firm-0", 3, "The AI chip founder in conversation", "/podcast/interview"),
        )
        q = build_review_queue(scout, registry, {"records": []})
        self.assertEqual(q["mode"], "offline-human-review-queue")
        self.assertFalse(q["autoPublication"])
        self.assertIsNone(q["verifiedInvestmentEvents"])
        self.assertEqual(q["navigationCandidateCount"], 3)
        self.assertEqual(q["actionableReviewLeads"], 2)
        self.assertEqual(q["navigationOnlyCount"], 1)
        self.assertEqual(len(q["priorityReviewCandidateIds"]), 2)
        for row in q["reviewLeads"]:
            self.assertIsNone(row["publishedAt"])
            self.assertFalse(row["publicationAllowed"])
            self.assertFalse(row["investmentRelationConfirmed"])
            self.assertFalse(row["investorSpeechVerified"])
            self.assertFalse(row["realizedReturnVerified"])
            self.assertTrue(row["requiredEvidenceChecks"])
        self.assertIn("不是已核验的投资关系", render_markdown(q))

    def test_reviewer_shortlist_balances_institutions_and_keeps_ids_stable(self):
        registry, scout = fixture()
        for number in range(5):
            add(scout, 0, candidate("firm-0", number, f"Investing in Company {number}", f"/news/investing-in-company-{number}"))
        add(scout, 1, candidate("firm-1", 1, "Investing in Company Other", "/news/investing-in-company-other"))
        queue = build_review_queue(scout, registry, {"records": []})
        picked = queue["priorityReviewCandidateIds"]
        self.assertEqual(len(picked), 4)
        self.assertEqual([p.split("-")[2] for p in picked], ["0", "1", "0", "0"])
        self.assertEqual(picked, build_review_queue(scout, registry, {"records": []})["priorityReviewCandidateIds"])

    def test_existing_reviewed_source_is_a_reference_not_new_verified_deal(self):
        registry, scout = fixture()
        add(scout, 0, candidate("firm-0", 7, "Our investment", "/news/firm-invests"))
        q = build_review_queue(scout, registry, {"records": [
            {"source": {"url": "https://www.firm-0.example.org/news/firm-invests/"}}
        ]})
        self.assertEqual(q["reviewLeads"][0]["reviewState"], "source-in-reviewed-sample")
        self.assertEqual(q["priorityReviewCandidateIds"], [])
        self.assertFalse(q["reviewLeads"][0]["publicationAllowed"])

    def test_rejects_cross_domain_and_query_string(self):
        registry, scout = fixture()
        for url in ["https://evil.example.org/story/invest",
                    "https://firm-0.example.org/news/invest?token=private",
                    "http://firm-0.example.org/news/invest",
                    "https://127.0.0.1/news/invest"]:
            with self.subTest(url=url):
                probe = copy.deepcopy(scout)
                add(probe, 0, candidate("firm-0", 5, "Investing in Test", "/news/investing", url=url))
                with self.assertRaises(ValueError):
                    build_review_queue(probe, registry, {"records": []})

    def test_duplicate_or_missing_institution_never_looks_like_zero_updates(self):
        registry, scout = fixture()
        scout["results"].pop()
        with self.assertRaises(ValueError):
            build_review_queue(scout, registry, {"records": []})
        registry, scout = fixture()
        scout["results"][-1] = copy.deepcopy(scout["results"][0])
        with self.assertRaises(ValueError):
            build_review_queue(scout, registry, {"records": []})

    def test_wrong_candidate_count_and_false_fact_promotion_fail_closed(self):
        registry, scout = fixture()
        add(scout, 0, candidate("firm-0", 1, "Investing in ChipCo", "/news/chipco"))
        for update in [{"candidateCount": 2}, {"autoPublication": True}]:
            with self.subTest(update=update), self.assertRaises(ValueError):
                build_review_queue({**scout, **update}, registry, {"records": []})
        scout["results"][0]["candidates"][0]["investmentRelationConfirmed"] = True
        with self.assertRaises(ValueError):
            build_review_queue(scout, registry, {"records": []})

    def test_leaves_inaccessible_official_homepage_separate_from_empty(self):
        registry, scout = fixture()
        scout["results"][29]["status"] = "unavailable"
        scout["results"][29]["reason"] = "robots-unavailable-http-429"
        q = build_review_queue(scout, registry, {"records": []})
        self.assertEqual(len(q["unavailableInstitutions"]), 1)
        self.assertEqual(q["unavailableInstitutions"][0]["reason"], "robots-unavailable-http-429")
        self.assertEqual(q["navigationCandidateCount"], 0)


if __name__ == "__main__":
    unittest.main()
