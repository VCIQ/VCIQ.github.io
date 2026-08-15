import unittest

from tools.article_publication_gate import financing_event_supported
from tools.crawl_articles import infer_event_type


class FinancingEventContractTests(unittest.TestCase):
    def test_completed_primary_market_rounds_are_financing(self) -> None:
        titles = (
            "星海芯片完成数亿元A轮融资，由产业基金领投",
            "机器人公司灵拓完成B+轮融资，老股东继续跟投",
            "Acme closes $35M Series B led by Example Ventures",
            "Nova Robotics secures $18M seed financing",
        )
        for title in titles:
            with self.subTest(title=title):
                self.assertTrue(financing_event_supported(title))
                self.assertEqual(infer_event_type(title)[0], "融资")

    def test_non_primary_market_financing_language_is_not_equity_round_semantics(self) -> None:
        titles = (
            "某公司拟开展30亿元债务融资",
            "某公司完成银行授信及债务融资安排",
            "融资客连续三日加仓半导体板块",
            "某创投基金完成20亿元募资",
            "Acme receives $10M government grant funding",
            "Acme closes a $100M debt financing facility",
            "Index Ventures raises $2B across three funds",
        )
        for title in titles:
            with self.subTest(title=title):
                self.assertFalse(financing_event_supported(title))
                self.assertNotEqual(infer_event_type(title)[0], "融资")

    def test_forward_looking_or_cancelled_rounds_are_not_completed_events(self) -> None:
        titles = (
            "某某科技计划进行B轮融资",
            "某某科技考虑启动新一轮融资",
            "某某科技终止原定融资计划",
            "Acme explores a new funding round",
            "Acme cancels its planned Series C financing",
        )
        for title in titles:
            with self.subTest(title=title):
                self.assertFalse(financing_event_supported(title))
                self.assertNotEqual(infer_event_type(title)[0], "融资")

    def test_forced_financing_label_cannot_override_semantics(self) -> None:
        self.assertNotEqual(
            infer_event_type("某公司发布新一代机器人平台", forced_type="融资")[0],
            "融资",
        )
        self.assertEqual(
            infer_event_type("某公司完成A轮融资", forced_type="融资")[0],
            "融资",
        )


if __name__ == "__main__":
    unittest.main()
