from __future__ import annotations

import unittest
from datetime import datetime, timezone

from tools import research_agent as agent
from tools import research_agent_evidence_policy as policy


class ResearchAgentEvidencePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        policy.install_evidence_policy(agent)

    def test_market_quote_inherits_parent_timestamp_and_source_type(self) -> None:
        change = {
            "id": "chg-quote",
            "dataset": "marketCompany",
            "entityType": "上市公司",
            "entityId": "demo",
            "entityName": "示例公司",
            "action": "updated",
            "changedFields": ["quote", "priceHistory"],
            "summary": "示例公司行情变化。",
            "importance": 48,
            "before": {"quote": {"price": 10}},
            "after": {"quote": {"price": 11}},
            "changeType": "external_event",
            "record": {
                "quote": {
                    "price": 11,
                    "asOf": "2026-08-24T07:06:19Z",
                    "source": {
                        "name": "新浪财经",
                        "url": "https://finance.example.com/quote/demo",
                    },
                },
                "priceHistory": [
                    {"date": "2026-08-23", "close": 10},
                    {"date": "2026-08-24", "close": 11},
                ],
            },
        }

        changes, evidence = agent.build_evidence_package(
            [change], as_of=datetime(2026, 8, 24, 8, tzinfo=timezone.utc)
        )

        self.assertTrue(changes[0]["eligibleForKeyDevelopment"])
        supporting = [row for row in evidence if row["supportStatus"] == "supports"]
        self.assertEqual(len(supporting), 1)
        self.assertEqual(supporting[0]["evidenceGrade"], "市场数据")
        self.assertEqual(supporting[0]["publishedAt"], "2026-08-24T07:06:19Z")
        self.assertEqual(supporting[0]["title"], "新浪财经 行情数据")
        self.assertIn("quote", supporting[0]["claimFields"])

    def test_dated_news_gets_source_type_without_relaxing_other_checks(self) -> None:
        change = {
            "id": "chg-news",
            "dataset": "marketCompany",
            "entityType": "上市公司",
            "entityId": "demo",
            "entityName": "示例公司",
            "action": "updated",
            "changedFields": ["news"],
            "summary": "示例公司新增新闻。",
            "importance": 48,
            "before": {"news": []},
            "after": {"news": ["new"]},
            "changeType": "external_event",
            "record": {
                "news": [
                    {
                        "title": "示例公司发布新产品",
                        "url": "https://news.example.com/demo",
                        "publishedAt": "2026-08-24T06:00:00Z",
                        "source": "示例媒体",
                    }
                ]
            },
        }

        changes, evidence = agent.build_evidence_package(
            [change], as_of=datetime(2026, 8, 24, 8, tzinfo=timezone.utc)
        )

        self.assertTrue(changes[0]["eligibleForKeyDevelopment"])
        self.assertEqual(evidence[0]["evidenceGrade"], "媒体报道")
        self.assertEqual(evidence[0]["qualityStatus"], "passed")
        self.assertIn("news", evidence[0]["claimFields"])

    def test_generic_ungraded_source_is_still_rejected(self) -> None:
        change = {
            "id": "chg-person",
            "dataset": "person",
            "entityType": "人物",
            "entityId": "person",
            "entityName": "研究者",
            "action": "updated",
            "changedFields": ["role"],
            "summary": "研究者任职变化。",
            "importance": 72,
            "before": {"role": "研究员"},
            "after": {"role": "CTO"},
            "changeType": "external_event",
            "record": {
                "role": "CTO",
                "sources": [
                    {
                        "name": "个人博客",
                        "title": "个人近况",
                        "url": "https://example.com/profile",
                        "publishedAt": "2026-08-24T06:00:00Z",
                    }
                ],
            },
        }

        changes, evidence = agent.build_evidence_package(
            [change], as_of=datetime(2026, 8, 24, 8, tzinfo=timezone.utc)
        )

        self.assertFalse(changes[0]["eligibleForKeyDevelopment"])
        self.assertEqual(evidence[0]["qualityStatus"], "rejected")
        self.assertIn("ungraded", evidence[0]["qualityIssues"])

    def test_scope_reports_active_counts_and_pending_objects(self) -> None:
        scope = policy._research_scope(
            {
                "datasets": {
                    "person": {"a": {}, "b": {}},
                    "ventureCompany": {"c": {}},
                }
            }
        )
        self.assertEqual(scope["person"]["count"], 2)
        self.assertEqual(scope["ventureCompany"]["count"], 1)
        self.assertEqual(scope["technology"]["status"], "pending-artifact")
        self.assertIsNone(scope["technology"]["count"])


if __name__ == "__main__":
    unittest.main()
