"""Regression tests for conservative pre-listing subject-role and date rules."""
import unittest
from datetime import date, timedelta

from tools.audit_prelisting_targeted import classify_date_window, classify_subject_role


class PrelistingSubjectRoleTests(unittest.TestCase):
    def test_investee_is_not_misclassified_as_investor(self):
        self.assertEqual(
            classify_subject_role("知乎回应间接投资DeepSeek", "DeepSeek"),
            "investee",
        )

    def test_investor_is_distinguished_from_investee(self):
        self.assertEqual(
            classify_subject_role("知乎战略投资某科技公司", "知乎"),
            "investor",
        )

    def test_funding_subject(self):
        self.assertEqual(
            classify_subject_role("杉数科技完成D轮融资", "杉数科技"),
            "funding_subject",
        )

    def test_partner(self):
        self.assertEqual(
            classify_subject_role("开源中国与共绩科技达成战略合作", "开源中国"),
            "partner",
        )

    def test_mentioned_is_not_funding(self):
        self.assertEqual(
            classify_subject_role("行业报告提及速显微技术路线", "速显微"),
            "mentioned",
        )

    def test_unknown_for_ambiguous_title(self):
        self.assertEqual(classify_subject_role("企业动态观察", "某公司"), "unknown")

    def test_recent_date_window(self):
        recent = (date.today() - timedelta(days=30)).isoformat()
        self.assertEqual(classify_date_window(recent), "last_12_months")

    def test_historical_date_window(self):
        old = (date.today() - timedelta(days=500)).isoformat()
        self.assertEqual(classify_date_window(old), "historical")

    def test_missing_and_invalid_dates(self):
        self.assertEqual(classify_date_window(""), "date_missing")
        self.assertEqual(classify_date_window("2026-99-99"), "date_missing")


if __name__ == "__main__":
    unittest.main()
