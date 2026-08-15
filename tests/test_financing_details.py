import unittest

from tools.financing_details import (
    enrich_financing_articles,
    extract_financing_details,
    validate_financing_details,
)


class FinancingDetailsTests(unittest.TestCase):
    def test_chinese_round_and_amount_preserve_literal_evidence(self) -> None:
        details = extract_financing_details(
            "星海芯片完成数亿元A轮融资，由产业基金领投"
        )
        self.assertEqual(
            details,
            {
                "status": "completed",
                "round": "A轮",
                "amount": {"original": "数亿元", "currency": "CNY"},
            },
        )

    def test_english_round_amount_and_valuation_are_separated(self) -> None:
        details = extract_financing_details(
            "Acme closes $35M Series B at a $500M valuation"
        )
        self.assertEqual(details["status"], "completed")
        self.assertEqual(details["round"], "Series B")
        self.assertEqual(details["amount"], {"original": "$35M", "currency": "USD"})
        self.assertEqual(
            details["valuation"],
            {"original": "$500M", "currency": "USD"},
        )

    def test_summary_can_supply_disclosed_amount_without_guessing(self) -> None:
        details = extract_financing_details(
            "灵拓机器人完成B+轮融资",
            "公司披露本轮融资金额为人民币2.5亿元。",
        )
        self.assertEqual(details["round"], "B+轮")
        self.assertEqual(
            details["amount"],
            {"original": "人民币2.5亿元", "currency": "CNY"},
        )

    def test_explicit_euro_seed_financing_is_normalized(self) -> None:
        details = extract_financing_details(
            "Nova Robotics secures €18 million seed financing"
        )
        self.assertEqual(details["round"], "Seed")
        self.assertEqual(
            details["amount"],
            {"original": "€18 million", "currency": "EUR"},
        )

    def test_amount_must_bind_to_current_round_not_revenue_arr_order_or_history(self) -> None:
        cases = (
            (
                "Acme with $100M revenue closes Series B funding",
                "",
            ),
            (
                "Acme closes Series C funding",
                "ARR reached $50M before the financing close.",
            ),
            (
                "公司本轮完成B轮融资",
                "此前累计融资3亿元。",
            ),
            (
                "公司完成A轮融资",
                "此前获得2亿元订单。",
            ),
        )
        for title, summary in cases:
            with self.subTest(title=title, summary=summary):
                details = extract_financing_details(title, summary)
                self.assertIsNotNone(details)
                self.assertNotIn("amount", details)

    def test_current_round_amount_wins_over_prior_round_amount(self) -> None:
        details = extract_financing_details(
            "公司完成B轮融资",
            "上一轮融资1亿元，本轮融资2亿元。",
        )
        self.assertEqual(
            details["amount"],
            {"original": "2亿元", "currency": "CNY"},
        )

    def test_vague_billion_scale_language_is_not_invented_as_money(self) -> None:
        details = extract_financing_details("桥介数物完成新一轮亿级融资")
        self.assertEqual(details, {"status": "completed"})

    def test_forward_looking_or_debt_items_get_no_envelope(self) -> None:
        titles = (
            "某公司计划进行B轮融资",
            "Acme closes a $100M debt financing facility",
            "某创投基金完成20亿元募资",
        )
        for title in titles:
            with self.subTest(title=title):
                self.assertIsNone(extract_financing_details(title))

    def test_enrichment_removes_financing_payload_from_non_financing_rows(self) -> None:
        rows = enrich_financing_articles(
            [
                {
                    "title": "Acme launches new robot",
                    "summary": "",
                    "type": "产品发布",
                    "financing": {"status": "completed", "round": "A轮"},
                },
                {
                    "title": "Acme closes $20M Series A funding",
                    "summary": "",
                    "type": "融资",
                },
            ]
        )
        self.assertNotIn("financing", rows[0])
        self.assertEqual(rows[1]["financing"]["round"], "Series A")

    def test_validation_rejects_fabricated_or_invalid_envelopes(self) -> None:
        article = {
            "title": "Acme launches new robot",
            "summary": "",
            "type": "产品发布",
            "financing": {
                "status": "completed",
                "amount": {"original": "$20M", "currency": "USD"},
            },
        }
        errors = validate_financing_details(article)
        self.assertIn("invalid:financing-type", errors)
        self.assertIn("invalid:financing-semantics", errors)

    def test_validation_rejects_money_not_bound_to_current_financing(self) -> None:
        article = {
            "title": "Acme with $100M revenue closes Series B funding",
            "summary": "",
            "type": "融资",
            "financing": {
                "status": "completed",
                "round": "Series B",
                "amount": {"original": "$100M", "currency": "USD"},
            },
        }
        self.assertIn(
            "invalid:financing-amount-evidence",
            validate_financing_details(article),
        )

    def test_lead_investors_must_be_subset_when_both_lists_exist(self) -> None:
        article = {
            "title": "Acme closes $20M Series A funding",
            "summary": "",
            "type": "融资",
            "financing": {
                "status": "completed",
                "investors": ["Alpha Capital"],
                "leadInvestors": ["Beta Ventures"],
            },
        }
        self.assertIn(
            "invalid:financing-lead-subset",
            validate_financing_details(article),
        )


if __name__ == "__main__":
    unittest.main()
