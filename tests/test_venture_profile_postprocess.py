from __future__ import annotations

import unittest

from tools import sanitize_venture_profiles as sanitizer


class VentureProfilePostprocessTests(unittest.TestCase):
    def test_products_preserve_catalog_and_remove_editorial_labels(self) -> None:
        products = sanitizer.sanitize_products(
            [
                "Claude Platform",
                "Terms of Service: US K-12",
                "Introducing advanced tool use on the Claude Developer Platform",
                "Introducing advanced tool use on the Claude Developer Platform Nov 24, 2025",
                "K-12 teachers",
                "Data Processing Agreement: US K-12",
            ],
            "Claude 模型、企业 API 与安全研究。",
        )
        self.assertEqual(products[:2], ["Claude 模型", "企业 API"])
        self.assertIn("Claude Platform", products)
        self.assertNotIn("Terms of Service: US K-12", products)
        self.assertFalse(any(item.startswith("Introducing ") for item in products))
        self.assertFalse(any("K-12" in item for item in products))

    def test_capital_events_require_explicit_transaction_evidence(self) -> None:
        source_url = "https://www.anthropic.com/news/example"
        financing = sanitizer.sanitize_capital_events(
            [
                {
                    "date": "",
                    "type": "融资",
                    "title": "Economic Futures Research Fund",
                    "summary": "We are sharing a research agenda for an economic research fund.",
                    "amount": "",
                    "round": "",
                    "investors": [],
                    "sourceUrl": source_url,
                },
                {
                    "date": "2026-01-01",
                    "type": "融资",
                    "title": "Company raises Series C",
                    "summary": "The company raised $500 million in a Series C funding round led by Example Capital.",
                    "amount": "$500 million",
                    "round": "Series C",
                    "investors": ["Example Capital"],
                    "sourceUrl": source_url,
                },
            ]
        )
        self.assertEqual(len(financing), 1)
        self.assertEqual(financing[0]["round"], "Series C")

        capital_markets = sanitizer.sanitize_capital_events(
            [
                {
                    "date": "",
                    "type": "资本市场",
                    "title": "Advanced technology company",
                    "summary": "The company builds autonomous defense systems.",
                    "sourceUrl": source_url,
                },
                {
                    "date": "",
                    "type": "并购/退出",
                    "title": "Leadership at Anthropic",
                    "summary": (
                        "The Chief People Officer leads talent acquisition, "
                        "organizational development, and workplace experience."
                    ),
                    "sourceUrl": "https://www.anthropic.com/company/leadership",
                },
                {
                    "date": "2026-01-15",
                    "type": "并购/退出",
                    "title": "Company completes acquisition of Example Labs",
                    "summary": "The company acquired Example Labs in a strategic transaction.",
                    "sourceUrl": source_url,
                },
                {
                    "date": "2026-02-01",
                    "type": "上市",
                    "title": "Company lists on Nasdaq",
                    "summary": "The company completed its IPO and listed on Nasdaq.",
                    "sourceUrl": source_url,
                },
            ],
            capital_market=True,
        )
        self.assertEqual(len(capital_markets), 2)
        self.assertEqual(
            [item["type"] for item in capital_markets],
            ["并购/退出", "上市"],
        )
        self.assertFalse(any("Leadership" in item["title"] for item in capital_markets))

    def test_company_profile_reapplies_team_and_event_filters(self) -> None:
        profile = {
            "slug": "agibot",
            "name": "智元机器人",
            "status": "retained",
            "background": "公司背景",
            "technology": "技术资料",
            "products": ["产品手册", "远征A2"],
            "team": [
                {
                    "name": "关于智元",
                    "role": "合伙人",
                    "summary": "",
                    "sourceUrl": "https://www.zhiyuan-robot.com/",
                },
                {
                    "name": "邓泰华",
                    "role": "创始人",
                    "summary": "",
                    "sourceUrl": "https://www.zhiyuan-robot.com/",
                },
            ],
            "financing": [
                {
                    "date": "",
                    "type": "融资",
                    "title": "公司新闻",
                    "summary": "公司发布了新的机器人产品。",
                    "sourceUrl": "https://www.zhiyuan-robot.com/news",
                }
            ],
            "capitalMarkets": [],
            "sources": [
                {
                    "name": "智元机器人",
                    "url": "https://www.zhiyuan-robot.com/",
                    "level": "官方披露",
                }
            ],
        }
        cleaned = sanitizer.sanitize_company_profile(
            profile,
            aliases=("智元机器人", "AgiBot"),
            catalog_product="远征A2、灵犀X2",
        )
        self.assertEqual([item["name"] for item in cleaned["team"]], ["邓泰华"])
        self.assertEqual(cleaned["products"][:2], ["远征A2", "灵犀X2"])
        self.assertEqual(cleaned["financing"], [])


if __name__ == "__main__":
    unittest.main()
