from __future__ import annotations

import unittest

from tools import stabilize_venture_profiles as stabilizer


CATALOG = '''
export type Company = {};
export const companies: Company[] = [
  { slug:"anduril", name:"Anduril Industries", englishName:"Anduril Industries", region:"美国", sector:"智能制造", stage:"成长期", status:"运营中", founded:"2017", headquarters:"California", summary:"开发自主系统、传感器和国防软件平台。", product:"Lattice 平台与多类自主飞行器。", source:official("Anduril","https://www.anduril.com/"), confidence:0.96 },
];
export type Institution = {};
export const institutionCatalog: Institution[] = [];
export type IpoCompany = {};
'''


class VentureCatalogBackgroundAnchorTests(unittest.TestCase):
    def test_valid_live_about_copy_cannot_replace_reviewed_identity_summary(self) -> None:
        payload = {
            "schemaVersion": 2,
            "generatedAt": "2026-08-23T04:40:00+00:00",
            "companies": {
                "anduril": {
                    "slug": "anduril",
                    "name": "Anduril Industries",
                    "background": (
                        "Anduril Industries builds advanced autonomous systems and "
                        "defense technology to protect US and allied forces."
                    ),
                    "technology": "Lattice 平台与多类自主飞行器。",
                    "researchTechnology": "Anduril develops autonomous systems.",
                    "products": ["Lattice 平台", "多类自主飞行器"],
                    "technologyProducts": [],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "sources": [],
                    "projectBackground": {
                        "summary": (
                            "Anduril Industries builds advanced autonomous systems and "
                            "defense technology to protect US and allied forces."
                        ),
                        "problemSolved": "",
                        "marketOpportunity": "",
                    },
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }

        stabilized, diagnostics = stabilizer.stabilize_snapshot(payload, CATALOG)
        company = stabilized["companies"]["anduril"]

        self.assertTrue(diagnostics["converged"])
        self.assertEqual(company["background"], "开发自主系统、传感器和国防软件平台。")
        self.assertEqual(
            company["projectBackground"]["summary"],
            "开发自主系统、传感器和国防软件平台。",
        )


if __name__ == "__main__":
    unittest.main()
