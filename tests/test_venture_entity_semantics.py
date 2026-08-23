from __future__ import annotations

import copy
import json
import unittest

from tools import enforce_venture_entity_semantics as semantics
from tools import finalize_venture_profiles as finalizer


CATALOG = '''
export const companies = [
  { slug:"anthropic", name:"Anthropic", englishName:"Anthropic", region:"US", sector:"AI", stage:"Growth", status:"未上市", summary:"Anthropic builds reliable AI systems.", product:"Claude 模型、Claude Platform", source:official("Anthropic","https://www.anthropic.com/") },
  { slug:"aurora", name:"Aurora Innovation", englishName:"Aurora Innovation", region:"US", sector:"自动驾驶", stage:"上市", status:"已上市", summary:"Aurora develops autonomous trucking technology.", product:"Aurora Driver", source:official("Aurora","https://aurora.tech/") },
];
export type Institution = {};
export const institutionCatalog = [
  { slug:"fund", name:"Example Capital", englishName:"Example Capital", region:"US", type:"VC", stages:"Seed", sectors:["AI"], source:official("Example Capital","https://example.vc/") },
];
export type IpoCompany = {};
'''


class VentureEntitySemanticTests(unittest.TestCase):
    def test_rejects_third_party_financing_and_year_product(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "Anthropic is an AI safety and research company.",
                    "technology": (
                        "OpenAI models attacked another platform. "
                        "Anthropic builds reliable and steerable AI systems."
                    ),
                    "products": ["Claude 模型", "Claude Platform", "2025"],
                    "team": [],
                    "financing": [
                        {
                            "date": "2026-07-20",
                            "title": "Infinity raises $15M from OpenAI and Anthropic researchers",
                            "summary": "Infinity announced a funding round involving Anthropic researchers.",
                            "sourceUrl": "https://example.com/infinity-round",
                        }
                    ],
                    "capitalMarkets": [],
                    "technologyProducts": [
                        {
                            "name": "Claude 模型",
                            "description": "OpenAI models attacked another platform.",
                            "technicalHighlights": ["OpenAI models attacked another platform."],
                            "sourceUrl": "",
                        },
                        {
                            "name": "2025",
                            "description": "A year label.",
                            "technicalHighlights": [],
                            "sourceUrl": "",
                        },
                    ],
                    "projectBackground": {
                        "summary": "Anthropic is an AI safety company.",
                        "problemSolved": "Ninety-Nine Prolog Problems are exercises.",
                        "marketOpportunity": "Anthropic serves enterprise AI users.",
                    },
                    "sources": [],
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        cleaned, diagnostics = semantics.enforce_snapshot(payload, CATALOG)
        profile = cleaned["companies"]["anthropic"]
        self.assertEqual(profile["products"], ["Claude 模型", "Claude Platform"])
        self.assertEqual(profile["financing"], [])
        self.assertNotIn("OpenAI models attacked", profile["technology"])
        self.assertIn("Anthropic builds reliable", profile["technology"])
        self.assertEqual(profile["projectBackground"]["problemSolved"], "")
        self.assertEqual(len(profile["technologyProducts"]), 1)
        self.assertIn("公开资料将Claude 模型列为", profile["technologyProducts"][0]["description"])
        self.assertEqual(profile["technologyProducts"][0]["technicalHighlights"], [])
        self.assertEqual(diagnostics["removedFinancing"], 1)
        self.assertEqual(diagnostics["removedProducts"], 1)

    def test_rejects_editorial_products_and_navigation_team_names(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "Anthropic builds reliable AI systems.",
                    "technology": "核心技术与产品包括Pharma.AI 平台、Claude Platform、https:、A15D1080.png、New paper explores a model。",
                    "products": [
                        "Anthropic",
                        "英特尔深化智能生态合作",
                        "开始对话",
                        "https:",
                        "www.example.com",
                        "A15D1080.png",
                        "New paper explores Insilico Medicine's generative AI platform Chemistry42",
                        "Cost-Effective Drug Discovery",
                        "Nach01",
                        "Pharma.AI 平台",
                        "Claude Platform",
                    ],
                    "team": [
                        {"name": "Spotlight Megan Holston-Alexander Hear", "role": "Partner"},
                        {"name": "Chris Lyons. The Next", "role": "Partner"},
                        {"name": "Chris Lyons. Black History", "role": "Partner"},
                        {"name": "ML Angela Yeung Awards", "role": "CTO"},
                        {"name": "Solutions Platform Overview AI", "role": "Partner"},
                        {"name": "Sun Microsystems", "role": "Founder"},
                        {"name": "Megan Holston-Alexander", "role": "Partner"},
                    ],
                    "financing": [],
                    "capitalMarkets": [],
                    "technologyProducts": [],
                    "sources": [],
                }
            },
            "institutions": {
                "fund": {
                    "slug": "fund",
                    "name": "Example Capital",
                    "overview": "Example Capital is a venture firm.",
                    "strategy": "Example Capital invests in AI.",
                    "team": [
                        {"name": "General Partner", "role": "Partner"},
                        {"name": "Moses Singer", "role": "CEO"},
                        {"name": "Jane Doe", "role": "Partner"},
                    ],
                    "sources": [],
                }
            },
            "qualityGate": {"passed": True, "checks": {}},
        }
        cleaned, diagnostics = semantics.enforce_snapshot(payload, CATALOG)
        self.assertEqual(
            cleaned["companies"]["anthropic"]["products"],
            ["Pharma.AI 平台", "Claude Platform"],
        )
        self.assertEqual(
            cleaned["companies"]["anthropic"]["technology"],
            "核心技术与产品包括Pharma.AI 平台、Claude Platform。",
        )
        self.assertEqual(
            [row["name"] for row in cleaned["companies"]["anthropic"]["team"]],
            ["Megan Holston-Alexander"],
        )
        self.assertEqual(
            [row["name"] for row in cleaned["institutions"]["fund"]["team"]],
            ["Jane Doe"],
        )
        self.assertEqual(diagnostics["removedProducts"], 9)
        self.assertEqual(diagnostics["removedTeamMembers"], 8)

    def test_rejects_web_dates_files_events_and_clickbait_prose(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "Anthropic builds reliable AI systems.",
                    "technology": "Anthropic develops Claude Platform for enterprise AI.",
                    "researchTechnology": (
                        "过去45天Anthropic狂塞500个技能，网友直呼疯狂，一口气赌OS级深度。 "
                        "Anthropic develops Claude Platform for enterprise AI."
                    ),
                    "products": [
                        "Claude Platform", "November 19", "June 30", "https:",
                        "www.example.com", "A15D1080-6F8C-4C6A-833F-73803D8B7.png",
                        "View C360 Reference Architecture for Insurance",
                        "Explore Agent Library", "F.02 Contributed to the Production of 30",
                        "000 Cars at BMW", "F.03 Arrives at BMW", "Helix-02 Bedroom Tidy",
                        "Commonwealth Fusion Systems Raises $863 Million Series B2 Round",
                        "F.03 Battery Development", "B2B Marketing", "工艺革新",
                        "星河动力 CQ-50 发动机交付速度再提升",
                    ],
                    "team": [],
                    "financing": [{
                        "date": "2021-03-19",
                        "title": "Newsroom",
                        "summary": "A founder raised $900M. Anthropic researchers later commented.",
                        "sourceUrl": "https://www.anthropic.com/newsroom",
                    }],
                    "capitalMarkets": [],
                    "technologyProducts": [],
                    "sources": [],
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        cleaned, diagnostics = semantics.enforce_snapshot(payload, CATALOG)
        company = cleaned["companies"]["anthropic"]
        self.assertEqual(company["products"], ["Claude Platform"])
        self.assertEqual(
            company["researchTechnology"],
            "Anthropic develops Claude Platform for enterprise AI.",
        )
        self.assertEqual(company["financing"], [])
        self.assertEqual(diagnostics["removedProducts"], 16)
        self.assertEqual(diagnostics["removedFinancing"], 1)

    def test_current_snapshot_removes_known_product_and_prose_noise(self) -> None:
        payload = json.loads(semantics.SNAPSHOT_PATH.read_text(encoding="utf-8"))
        catalog_text = semantics.CATALOG_PATH.read_text(encoding="utf-8")
        cleaned, _ = semantics.enforce_snapshot(payload, catalog_text)
        product_names = {
            item
            for profile in cleaned.get("companies", {}).values()
            for item in profile.get("products", [])
        }
        technology_product_names = {
            row.get("name", "")
            for profile in cleaned.get("companies", {}).values()
            for row in profile.get("technologyProducts", [])
            if isinstance(row, dict)
        }
        forbidden_products = {
            "November 19", "June 30", "F.02 Contributed to the Production of 30",
            "000 Cars at BMW", "F.03 Arrives at BMW", "Helix-02 Bedroom Tidy",
            "F.03 Battery Development", "View C360 Reference Architecture for Insurance",
            "Commonwealth Fusion Systems Raises $863 Million Series B2 Round",
            "星河动力 CQ-50 发动机交付速度再提升", "工艺革新",
            "B2B Marketing", "B2C Marketing",
        }
        self.assertTrue(forbidden_products.isdisjoint(product_names))
        self.assertTrue(forbidden_products.isdisjoint(technology_product_names))
        self.assertNotIn(
            "网友直呼疯狂",
            cleaned["companies"]["anthropic"].get("researchTechnology", ""),
        )
        self.assertEqual(cleaned["companies"]["anthropic"]["capitalMarkets"], [])
        self.assertEqual(
            cleaned["companies"]["anthropic"]["exitPerformance"]["status"],
            "暂无公开退出信息",
        )
        self.assertNotIn(
            "工艺革新",
            cleaned["companies"]["galactic-energy"].get("technology", ""),
        )

    def test_rejects_official_aggregation_and_clickbait_capital_events(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "Anthropic builds reliable AI systems.",
                    "technology": "Anthropic develops Claude Platform.",
                    "products": ["Claude Platform"],
                    "team": [],
                    "financing": [{
                        "date": "2021-03-19",
                        "title": "Newsroom",
                        "summary": (
                            "A founder raised $900M before a later mention of Anthropic."
                        ),
                        "sourceUrl": "https://www.anthropic.com/newsroom",
                    }],
                    "capitalMarkets": [{
                        "date": "2026-07-11",
                        "title": "AI史诗级工程却引来愤怒",
                        "summary": "Anthropic announced the acquisition of Bun.",
                        "sourceUrl": "https://news.example.com/clickbait",
                    }],
                    "technologyProducts": [],
                    "sources": [],
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        cleaned, diagnostics = semantics.enforce_snapshot(payload, CATALOG)
        company = cleaned["companies"]["anthropic"]
        self.assertEqual(company["financing"], [])
        self.assertEqual(company["capitalMarkets"], [])
        self.assertEqual(diagnostics["removedFinancing"], 1)
        self.assertEqual(diagnostics["removedCapitalMarkets"], 1)

    def test_recomputes_derived_fields_after_semantic_removal(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "Anthropic builds reliable AI systems.",
                    "technology": "核心技术与产品包括Claude Platform、工艺革新。",
                    "researchTechnology": "核心技术与产品包括Claude Platform、工艺革新。",
                    "products": ["Claude Platform", "工艺革新"],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "technologyProducts": [],
                    "capitalSummary": {"eventCount": 0},
                    "exitPerformance": {
                        "status": "已发生并购或退出事件",
                        "latestDate": "2026-07-11",
                        "latestEvent": "旧媒体标题",
                        "summary": "旧媒体标题。",
                        "sourceUrl": "https://example.com/stale",
                    },
                    "sources": [],
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        cleaned, _ = semantics.enforce_snapshot(payload, CATALOG)
        company = cleaned["companies"]["anthropic"]
        self.assertEqual(company["products"], ["Claude Platform"])
        self.assertEqual(
            company["technology"],
            "核心技术与产品包括Claude Platform。",
        )
        self.assertEqual(company["researchTechnology"], company["technology"])
        self.assertEqual(
            company["exitPerformance"],
            {
                "status": "暂无公开退出信息",
                "latestDate": "",
                "latestEvent": "",
                "summary": "当前未发现上市、并购退出或明确退出安排的可核对公开证据。",
                "sourceUrl": "",
            },
        )

    def test_trims_investor_relations_page_chrome(self) -> None:
        payload = {
            "companies": {
                "aurora": {
                    "slug": "aurora",
                    "name": "Aurora Innovation",
                    "background": (
                        "Aurora Innovation develops autonomous trucking technology. "
                        "1654 Smallman Street Toll-Free: 888-000-0000 Investor Relations "
                        "Transfer Agent Featured News."
                    ),
                    "technology": "Aurora Driver supports autonomous trucking.",
                    "products": ["Aurora Driver"],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "technologyProducts": [],
                    "sources": [],
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        cleaned, _ = semantics.enforce_snapshot(payload, CATALOG)
        background = cleaned["companies"]["aurora"]["background"]
        self.assertIn("autonomous trucking technology", background)
        self.assertNotIn("Toll-Free", background)
        self.assertNotIn("Investor Relations", background)

    def test_catalog_fallback_and_research_technology_filter(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "",
                    "technology": "Claude 模型与 Claude Platform。",
                    "researchTechnology": (
                        "Looped world models are a generic research direction. "
                        "Anthropic expands Claude Platform for enterprise agents."
                    ),
                    "products": ["Claude 模型", "Claude Platform"],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "technologyProducts": [],
                    "projectBackground": {
                        "summary": "Stale summary.",
                        "problemSolved": "",
                        "marketOpportunity": "",
                    },
                    "sources": [],
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        cleaned, _ = semantics.enforce_snapshot(payload, CATALOG)
        profile = cleaned["companies"]["anthropic"]
        self.assertEqual(profile["background"], "Anthropic builds reliable AI systems.")
        self.assertNotIn("Looped world models", profile["researchTechnology"])
        self.assertIn("Anthropic expands Claude Platform", profile["researchTechnology"])
        self.assertEqual(profile["projectBackground"]["summary"], profile["background"])

    def test_capital_summary_matches_structural_finalizer(self) -> None:
        events = [
            {
                "date": "2026-07-20",
                "title": "Anthropic raises a new round",
                "amount": "$2 billion",
                "round": "Growth",
                "investors": ["Example Capital"],
            }
        ]
        self.assertEqual(
            semantics._capital_summary(events),
            finalizer._capital_summary(events),
        )
        self.assertEqual(
            semantics._capital_summary([]),
            finalizer._capital_summary([]),
        )

    def test_keeps_entity_subject_financing(self) -> None:
        row = {
            "title": "Anthropic raises $2 billion in new funding",
            "summary": "Anthropic announced the financing round.",
            "sourceUrl": "https://news.example.com/anthropic-round",
        }
        self.assertTrue(
            semantics._subject_evidence(
                row,
                ("Anthropic",),
                "anthropic.com",
                semantics.FINANCING_ACTION_RE,
            )
        )

    def test_complex_snapshot_reaches_fixed_point_in_one_call(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "Anthropic builds reliable AI systems. Investor Relations Transfer Agent.",
                    "technology": "OpenAI models are discussed. Anthropic develops Claude models.",
                    "products": ["Claude 模型", "2025"],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "technologyProducts": [
                        {
                            "name": "Claude 模型",
                            "description": "Unrelated OpenAI product description.",
                            "technicalHighlights": [],
                            "sourceUrl": "",
                        }
                    ],
                    "projectBackground": {
                        "summary": "Stale derived summary.",
                        "problemSolved": "Unrelated exercise collection.",
                        "marketOpportunity": "Anthropic serves enterprise AI users.",
                    },
                    "capitalSummary": {
                        "eventCount": 9,
                        "summary": "Stale capital summary.",
                    },
                    "sources": [],
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        first, diagnostics = semantics.enforce_snapshot(copy.deepcopy(payload), CATALOG)
        second, second_diagnostics = semantics.enforce_snapshot(copy.deepcopy(first), CATALOG)
        self.assertEqual(first, second)
        self.assertGreaterEqual(diagnostics["internalPasses"], 2)
        self.assertEqual(second_diagnostics["changedCompanies"], 0)
        self.assertEqual(first["companies"]["anthropic"]["products"], ["Claude 模型"])
        self.assertEqual(first["companies"]["anthropic"]["capitalSummary"]["eventCount"], 0)

    def test_is_idempotent(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "Anthropic builds reliable AI systems.",
                    "technology": "Anthropic develops Claude models.",
                    "products": ["Claude 模型"],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "technologyProducts": [],
                    "sources": [],
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        first, _ = semantics.enforce_snapshot(copy.deepcopy(payload), CATALOG)
        second, diagnostics = semantics.enforce_snapshot(copy.deepcopy(first), CATALOG)
        self.assertEqual(first, second)
        self.assertEqual(diagnostics["changedCompanies"], 0)
        self.assertTrue(
            second["qualityGate"]["checks"]["entitySemanticConsistency"]["passed"]
        )


if __name__ == "__main__":
    unittest.main()