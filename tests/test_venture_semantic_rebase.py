from __future__ import annotations

import unittest

from tools import enforce_venture_entity_semantics as semantics
from tools import finalize_venture_profiles as finalizer
from tools import refine_venture_research_evidence as refiner


class VentureSemanticRebaseTests(unittest.TestCase):
    def test_rejects_bare_generic_product_names(self) -> None:
        self.assertFalse(semantics._valid_product("API"))
        self.assertFalse(semantics._valid_product("Platform"))
        self.assertTrue(semantics._valid_product("企业 API"))
        self.assertTrue(semantics._valid_product("Claude Platform"))

    def test_rejects_multi_sentence_product_names_without_rejecting_trailing_punctuation(self) -> None:
        self.assertFalse(
            semantics._valid_product("500 家组织信任。它自主执行了超过 250")
        )
        self.assertFalse(
            semantics._valid_product(
                "即推理的内存层。其技术方案是将数据中心改造为 token 生产线"
            )
        )
        self.assertTrue(semantics._valid_product("灵犀等机器人系列。"))

    def test_accepts_official_short_brand_financing_subject(self) -> None:
        row = {
            "title": "SambaNova Completes First Close of $1B Financing",
            "summary": "SambaNova completed the financing at an $11B valuation.",
            "sourceUrl": "https://sambanova.ai/news/financing",
        }
        self.assertTrue(
            semantics._subject_evidence(
                row,
                ("SambaNova Systems", "SambaNova"),
                "sambanova.ai",
                semantics.FINANCING_ACTION_RE,
            )
        )

    def test_rejects_earnings_guidance_and_time_series_as_financing(self) -> None:
        earnings = (
            "IonQ Posts Q1 Earnings. The company raised full year guidance."
        )
        insar = (
            "IonQ launches automated 3-day repeat InSAR time series data."
        )
        self.assertIsNone(refiner.FINANCING_RE.search(earnings))
        self.assertIsNone(refiner.FINANCING_RE.search(insar))
        self.assertIsNone(refiner.ROUND_RE.search(insar))
        self.assertIsNone(semantics.FINANCING_ACTION_RE.search(earnings))
        self.assertIsNone(semantics.FINANCING_ACTION_RE.search(insar))
        self.assertEqual(
            finalizer.finalize_financing([
                {
                    "date": "2026-06-10",
                    "type": "融资",
                    "title": "IonQ Posts Q1 2026 Earnings with Record Revenue",
                    "summary": "IonQ raised full year guidance after record revenue.",
                    "round": "Growth",
                    "sourceUrl": "https://ionq.com/news/results",
                }
            ]),
            [],
        )

    def test_product_evidence_requires_exact_alias_and_technical_context(self) -> None:
        self.assertFalse(refiner._alias_in_text("ARC", "collaborative research agreement"))
        self.assertTrue(refiner._alias_in_text("ARC", "ARC fusion power system"))
        self.assertEqual(
            refiner._select_required_sentence(
                ["Meet Axiom Space Project Astronaut Emiliano Ventura."],
                required_aliases=("Axiom Station",),
                required_terms=refiner.TECH_TERMS,
            ),
            "",
        )
        self.assertIn(
            "Wafer-Scale Engine",
            refiner._select_required_sentence(
                ["AMD and Cerebras combine the Wafer-Scale Engine for AI inference."],
                required_aliases=("Wafer Scale Engine", "WSE"),
                required_terms=refiner.TECH_TERMS,
            ).replace("-", "-"),
        )

    def test_rejects_weak_roundup_financing_and_placeholder_highlights(self) -> None:
        roundup = {
            "title": "DeepSeek 巨额融资落地 | 创投周报",
            "summary": "DeepSeek 巨额融资落地 | 创投周报",
            "sourceUrl": "https://news.example.com/weekly",
        }
        detailed = {
            "title": "Anthropic raises $2 billion in new funding",
            "summary": "Anthropic completed the transaction to expand model development.",
            "sourceUrl": "https://news.example.com/anthropic",
        }
        self.assertFalse(
            semantics._subject_evidence(
                roundup,
                ("DeepSeek",),
                "deepseek.com",
                semantics.FINANCING_ACTION_RE,
            )
        )
        self.assertTrue(
            semantics._subject_evidence(
                detailed,
                ("Anthropic",),
                "anthropic.com",
                semantics.FINANCING_ACTION_RE,
            )
        )
        cleaned = semantics._sanitize_technology_products(
            [{
                "name": "Claude 模型",
                "description": "公开资料将Claude 模型列为该公司的核心产品或技术平台，具体技术参数以原始来源为准。",
                "technicalHighlights": [
                    "公开资料将Claude 模型列为该公司的核心产品或技术平台，具体技术参数以原始来源为准。"
                ],
                "sourceUrl": "",
            }],
            ("Claude 模型",),
            ("Anthropic",),
        )
        self.assertEqual(cleaned[0]["technicalHighlights"], [])

    def test_unsourced_catalog_description_is_not_a_technical_highlight(self) -> None:
        profile = {
            "name": "智元机器人",
            "slug": "agibot",
            "products": ["灵犀"],
            "technologyProducts": [{
                "name": "灵犀",
                "category": "机器人 / 硬件",
                "description": "核心技术与产品包括远征、灵犀、A2 旗舰版。",
                "technicalHighlights": ["核心技术与产品包括远征、灵犀、A2 旗舰版。"],
                "sourceUrl": "",
            }],
        }
        refined = refiner._refine_products(profile, [])
        self.assertIn("尚未识别", refined[0]["description"])
        self.assertEqual(refined[0]["technicalHighlights"], [])
        self.assertEqual(refined[0]["sourceUrl"], "")

    def test_rejects_navigation_phrases_as_team_names(self) -> None:
        self.assertFalse(semantics._valid_person_name("Discover For App Developers"))
        self.assertFalse(semantics._valid_person_name("Explore Our Technology"))
        self.assertFalse(semantics._valid_person_name("Learn With Developers"))
        self.assertTrue(semantics._valid_person_name("Megan Holston-Alexander"))

    def test_rejects_portfolio_navigation_phrases_as_team_names(self) -> None:
        self.assertFalse(semantics._valid_person_name("Experience Stories Launch Research"))
        self.assertFalse(semantics._valid_person_name("Portfolio Insights Research Hub"))
        self.assertTrue(semantics._valid_person_name("Sarah Guo"))


if __name__ == "__main__":
    unittest.main()
