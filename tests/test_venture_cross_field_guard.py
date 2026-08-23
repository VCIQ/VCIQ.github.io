from __future__ import annotations

import copy
import unittest

from tools import guard_venture_cross_field_noise as guard


CATALOG = '''
export const companies = [
  { slug:"ionq", name:"IonQ", englishName:"IonQ", region:"US", sector:"量子计算", stage:"上市", status:"已上市", summary:"IonQ develops trapped-ion quantum computing systems and services.", product:"离子阱量子计算机、云访问、量子网络技术", source:official("IonQ","https://ionq.com/") },
];
export type Institution = {};
export const institutionCatalog = [];
export type IpoCompany = {};
'''


class VentureCrossFieldGuardTests(unittest.TestCase):
    def payload(self) -> dict:
        return {
            "companies": {
                "ionq": {
                    "slug": "ionq",
                    "name": "IonQ",
                    "background": "About IonQ Founded in 2015 by Dr.",
                    "projectBackground": {
                        "summary": "About IonQ Founded in 2015 by Dr.",
                        "problemSolved": "",
                        "marketOpportunity": "",
                    },
                    "products": [
                        "离子阱量子计算机",
                        "云访问",
                        "量子网络技术",
                        "Jordan Shapiro President & General Manager",
                    ],
                    "technologyProducts": [
                        {
                            "name": "离子阱量子计算机",
                            "category": "平台",
                            "description": "IonQ trapped-ion quantum computer.",
                            "technicalHighlights": [],
                            "sourceUrl": "https://ionq.com/technology",
                        },
                        {
                            "name": "Jordan Shapiro President & General Manager",
                            "category": "技术产品",
                            "description": "A personnel heading incorrectly parsed as a product.",
                            "technicalHighlights": [],
                            "sourceUrl": "https://ionq.com/company/leadership",
                        },
                    ],
                    "team": [
                        {"name": "Massachusetts Governor Chris Ballance", "role": "President"},
                        {"name": "Class President Thomas Sonderman", "role": "CEO"},
                        {"name": "Global AI Sales", "role": "President"},
                        {"name": "Specialty Sales", "role": "Partner"},
                        {"name": "Peter Chapman", "role": "Executive Chair"},
                    ],
                    "financing": [
                        {
                            "date": "",
                            "type": "融资",
                            "title": "IonQ - Executive management",
                            "summary": "He has helped lead and consummate approximately 50 mergers and acquisitions and has helped raise over $5 billion in equity.",
                            "amount": "$5 billion",
                            "round": "",
                            "investors": [],
                            "sourceUrl": "https://ionq.com/company/leadership",
                        },
                        {
                            "date": "2026-06-01",
                            "type": "融资",
                            "title": "IonQ raises $100 million",
                            "summary": "IonQ raised $100 million to expand quantum networking.",
                            "amount": "$100 million",
                            "round": "",
                            "investors": [],
                            "sourceUrl": "https://ionq.com/news/raise",
                        },
                    ],
                    "capitalMarkets": [],
                    "sources": [],
                    "evidenceScore": 100,
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }

    def test_removes_personnel_headings_and_biography_financing(self) -> None:
        cleaned, diagnostics = guard.guard_snapshot(self.payload(), CATALOG)
        profile = cleaned["companies"]["ionq"]

        self.assertEqual([row["name"] for row in profile["team"]], ["Peter Chapman"])
        self.assertEqual(
            profile["products"],
            ["离子阱量子计算机", "云访问", "量子网络技术"],
        )
        self.assertEqual(
            [row["name"] for row in profile["technologyProducts"]],
            ["离子阱量子计算机"],
        )
        self.assertEqual(len(profile["financing"]), 1)
        self.assertEqual(profile["financing"][0]["amount"], "$100 million")
        self.assertEqual(profile["capitalSummary"]["disclosedAmounts"], ["$100 million"])
        self.assertEqual(diagnostics["removedTeamMembers"], 4)
        self.assertEqual(diagnostics["removedProducts"], 1)
        self.assertEqual(diagnostics["removedFinancing"], 1)

    def test_repairs_honorific_truncated_background_from_catalog(self) -> None:
        cleaned, diagnostics = guard.guard_snapshot(self.payload(), CATALOG)
        profile = cleaned["companies"]["ionq"]
        self.assertEqual(
            profile["background"],
            "IonQ develops trapped-ion quantum computing systems and services.",
        )
        self.assertEqual(profile["projectBackground"]["summary"], profile["background"])
        self.assertEqual(diagnostics["repairedBackgrounds"], 1)

    def test_guard_is_idempotent(self) -> None:
        first, _ = guard.guard_snapshot(self.payload(), CATALOG)
        second, diagnostics = guard.guard_snapshot(copy.deepcopy(first), CATALOG)
        self.assertEqual(second, first)
        self.assertEqual(diagnostics["changedCompanies"], 0)


if __name__ == "__main__":
    unittest.main()
