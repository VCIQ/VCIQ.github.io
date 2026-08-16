from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import crawl_articles
from tools import snapshot_retention


def article(article_id: str, published_at: str, importance: int = 70) -> dict:
    return {
        "id": article_id,
        "sourceId": "test-source",
        "title": f"Article {article_id}",
        "summary": "Snapshot rolling-retention test article.",
        "type": "公司动态",
        "region": "全球",
        "sector": "AI / AGI",
        "company": "科技产业",
        "publishedAt": published_at,
        "importance": importance,
        "source": {
            "name": "Test",
            "url": f"https://example.com/{article_id}",
            "level": "媒体报道",
            "platform": "Test",
        },
    }


def eastmoney_article(
    article_id: str,
    published_at: str,
    source_id: str,
    importance: int = 70,
) -> dict:
    row = article(article_id, published_at, importance)
    row["sourceId"] = source_id
    row["source"] = {
        "name": "东方财富",
        "url": f"https://finance.eastmoney.com/a/{article_id}.html",
        "level": "媒体报道",
        "platform": "东方财富",
    }
    return row


def official_company_article(
    article_id: str,
    published_at: str,
    source_id: str,
    importance: int = 70,
) -> dict:
    row = article(article_id, published_at, importance)
    row.update(
        {
            "sourceId": source_id,
            "company": "Shopify",
            "companySlug": "shopify",
            "sector": "新消费",
        }
    )
    row["source"] = {
        "name": "Shopify 官方动态",
        "url": f"https://www.shopify.com/news/{article_id}",
        "level": "官方披露",
        "platform": "官方网站",
    }
    return row


class SnapshotRetentionTest(unittest.TestCase):
    def test_newest_articles_displace_oldest_at_capacity(self) -> None:
        rows = [
            article("oldest", "2026-07-01"),
            article("middle", "2026-07-02"),
            article("newest", "2026-07-03"),
        ]
        retained = snapshot_retention.retain_latest_articles(rows, capacity=2)
        self.assertEqual([row["id"] for row in retained], ["newest", "middle"])

    def test_same_day_uses_importance_then_id_deterministically(self) -> None:
        rows = [
            article("a", "2026-07-03", 70),
            article("b", "2026-07-03", 90),
            article("c", "2026-07-03", 90),
        ]
        retained = snapshot_retention.retain_latest_articles(rows, capacity=2)
        self.assertEqual([row["id"] for row in retained], ["c", "b"])

    def test_duplicate_canonical_urls_keep_the_newest_record(self) -> None:
        older = article("older", "2026-07-02", 95)
        newer = article("newer", "2026-07-03", 70)
        older["source"]["url"] = (
            "https://Example.com/news/item/?utm_source=feed&spm=tracking#section"
        )
        newer["source"]["url"] = "https://example.com/news/item"

        retained = snapshot_retention.retain_latest_articles(
            [older, newer],
            capacity=10,
        )

        self.assertEqual([row["id"] for row in retained], ["newer"])
        self.assertEqual(
            snapshot_retention.canonical_article_url(older),
            "https://example.com/news/item",
        )

    def test_payload_records_the_formal_retention_policy(self) -> None:
        payload = {
            "schemaVersion": 3,
            "articleCount": 3,
            "articles": [
                article("oldest", "2026-07-01"),
                article("newest", "2026-07-03"),
                article("middle", "2026-07-02"),
            ],
        }
        next_payload, removed = snapshot_retention.apply_retention(payload, capacity=2)
        self.assertEqual(removed, 1)
        self.assertEqual(next_payload["articleCount"], 2)
        self.assertEqual(
            [row["id"] for row in next_payload["articles"]],
            ["newest", "middle"],
        )
        self.assertEqual(
            next_payload["snapshotRetention"]["overflowAction"],
            "discard-oldest",
        )
        self.assertEqual(
            next_payload["snapshotRetention"]["deduplicateBy"],
            "canonical-source-url",
        )
        self.assertEqual(
            next_payload["snapshotRetention"]["sourceStatusAccounting"],
            "retained-official-company-and-eastmoney-rows",
        )
        self.assertEqual(snapshot_retention.validate_retention(next_payload, 2), [])

    def test_retention_closes_eastmoney_source_accounting_after_tail_drop(self) -> None:
        eastmoney_a = "official-user-东方财富"
        eastmoney_b = "official-user-东方财富-半导体信源"
        payload = {
            "schemaVersion": 3,
            "articleCount": 3,
            "articles": [
                eastmoney_article("old-retained", "2026-07-01", eastmoney_a),
                eastmoney_article("mid-retained", "2026-07-02", eastmoney_b),
                eastmoney_article("new-current", "2026-07-03", eastmoney_a),
            ],
            "sourceStatus": [
                {"id": eastmoney_a, "status": "ok", "accepted": 2, "newAccepted": 1, "retainedPrevious": True, "retainedPreviousCount": 1},
                {"id": eastmoney_b, "status": "ok", "accepted": 1, "newAccepted": 0, "retainedPrevious": True, "retainedPreviousCount": 1},
            ],
        }
        next_payload, removed = snapshot_retention.apply_retention(payload, capacity=2)
        self.assertEqual(removed, 1)
        statuses = {row["id"]: row for row in next_payload["sourceStatus"]}
        self.assertEqual(statuses[eastmoney_a]["accepted"], 1)
        self.assertEqual(statuses[eastmoney_a]["newAccepted"], 1)
        self.assertEqual(statuses[eastmoney_a]["retainedPreviousCount"], 0)
        self.assertNotIn("retainedPrevious", statuses[eastmoney_a])
        self.assertEqual(statuses[eastmoney_b]["accepted"], 1)
        self.assertEqual(statuses[eastmoney_b]["retainedPreviousCount"], 1)

    def test_retention_closes_official_company_accounting_after_tail_drop(self) -> None:
        shopify = "official-shopify"
        payload = {
            "schemaVersion": 3,
            "articleCount": 2,
            "articles": [
                official_company_article("old-shopify", "2026-07-01", shopify),
                article("newer-other-source", "2026-07-03"),
            ],
            "sourceStatus": [
                {
                    "id": shopify,
                    "name": "Shopify 官方动态",
                    "companySlug": "shopify",
                    "status": "ok",
                    "accepted": 1,
                    "failed": 0,
                }
            ],
        }

        next_payload, removed = snapshot_retention.apply_retention(payload, capacity=1)

        self.assertEqual(removed, 1)
        status = next_payload["sourceStatus"][0]
        self.assertEqual(status["acceptedBeforeRetention"], 1)
        self.assertEqual(status["accepted"], 0)
        self.assertEqual(status["status"], "empty")
        self.assertFalse(
            any(
                row.get("sourceId") == shopify
                for row in next_payload["articles"]
            )
        )

    def test_core_merge_already_applies_the_same_replacement_rule(self) -> None:
        existing = [
            article("oldest", "2026-07-01"),
            article("middle", "2026-07-02"),
        ]
        incoming = [article("newest", "2026-07-03")]
        with patch.object(crawl_articles, "MAX_ARTICLES", 2):
            merged = crawl_articles.merge_articles(existing, incoming)
        self.assertEqual([row["id"] for row in merged], ["newest", "middle"])


if __name__ == "__main__":
    unittest.main()
