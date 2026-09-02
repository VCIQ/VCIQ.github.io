from __future__ import annotations

import unittest

from tools.source_quality_review_queue import build_queue, validate_queue


DISCLOSURE_CONFIG = {
    "officialSources": {
        "cninfo": {
            "name": "巨潮资讯",
            "hosts": ["cninfo.com.cn"],
        },
        "hkex": {
            "name": "香港交易所披露易",
            "hosts": ["hkexnews.hk"],
        },
        "sec": {
            "name": "美国证券交易委员会 SEC",
            "hosts": ["sec.gov"],
        },
        "eastmoney": {
            "name": "东方财富公告",
            "hosts": ["eastmoney.com"],
        },
    }
}


def health_source(name: str = "Example") -> dict:
    return {
        "name": name,
        "platform": "test",
        "evidenceGrade": "C",
        "performance": {
            "reviewState": "retain",
            "runs": 30,
        },
    }


class SourceQualityReviewQueueTest(unittest.TestCase):
    def test_articles_require_exact_runtime_source_id(self) -> None:
        state = {
            "generatedAt": "2026-09-02T00:00:00+00:00",
            "sources": {
                "source-a": health_source("Source A"),
                "source-a-copy": health_source("Source A Copy"),
            },
        }
        articles = {
            "articles": [
                {
                    "id": "article-a",
                    "sourceId": "source-a",
                    "title": "Exact source",
                    "publishedAt": "2026-09-02",
                    "source": {
                        "name": "Source A",
                        "url": "https://example.com/a",
                    },
                },
                {
                    "id": "article-b",
                    "sourceId": "other-source",
                    "title": "Similar name only",
                    "publishedAt": "2026-09-02",
                    "source": {
                        "name": "Source A Copy",
                        "url": "https://example.com/b",
                    },
                },
            ]
        }

        queue = build_queue(state, articles, {}, {}, DISCLOSURE_CONFIG)
        rows = {row["sourceId"]: row for row in queue["sources"]}
        self.assertEqual(
            [record["recordId"] for record in rows["source-a"]["records"]],
            ["article-a"],
        )
        self.assertEqual(rows["source-a-copy"]["records"], [])
        self.assertEqual(rows["source-a-copy"]["status"], "insufficient-records")

    def test_regulatory_disclosures_use_configured_hosts_only(self) -> None:
        state = {
            "generatedAt": "2026-09-02T00:00:00+00:00",
            "sources": {
                "regulatory:cninfo": health_source("巨潮资讯"),
                "regulatory:hkex": health_source("香港交易所披露易"),
                "regulatory:sec": health_source("SEC"),
                "regulatory:eastmoney": health_source("东方财富公告"),
            },
        }
        disclosures = {
            "companies": {
                "demo": {
                    "name": "Demo Corp",
                    "events": [
                        {
                            "id": "cninfo-1",
                            "title": "CNINFO filing",
                            "publishedAt": "2026-09-01",
                            "source": {
                                "name": "巨潮资讯",
                                "url": "https://static.cninfo.com.cn/finalpage/a.pdf",
                            },
                        },
                        {
                            "id": "hkex-1",
                            "title": "HKEX filing",
                            "publishedAt": "2026-08-31",
                            "source": {
                                "name": "香港交易所披露易",
                                "url": "https://www1.hkexnews.hk/listedco/a.pdf",
                            },
                        },
                        {
                            "id": "sec-1",
                            "title": "SEC filing",
                            "publishedAt": "2026-08-30",
                            "source": {
                                "name": "SEC",
                                "url": "https://www.sec.gov/Archives/edgar/data/1/a.htm",
                            },
                        },
                        {
                            "id": "eastmoney-1",
                            "title": "Fallback database record",
                            "publishedAt": "2026-08-29",
                            "fallback": True,
                            "source": {
                                "name": "东方财富公告",
                                "url": "https://data.eastmoney.com/notices/detail/a.html",
                            },
                        },
                        {
                            "id": "unknown-1",
                            "title": "Unconfigured host",
                            "publishedAt": "2026-08-28",
                            "source": {
                                "name": "Not a regulator",
                                "url": "https://example.com/fake",
                            },
                        },
                    ],
                }
            }
        }

        queue = build_queue(state, {}, disclosures, {}, DISCLOSURE_CONFIG)
        rows = {row["sourceId"]: row for row in queue["sources"]}
        self.assertEqual(rows["regulatory:cninfo"]["records"][0]["recordId"], "cninfo-1")
        self.assertEqual(rows["regulatory:hkex"]["records"][0]["recordId"], "hkex-1")
        self.assertEqual(rows["regulatory:sec"]["records"][0]["recordId"], "sec-1")
        self.assertEqual(
            rows["regulatory:eastmoney"]["records"][0]["recordId"],
            "eastmoney-1",
        )
        queued_ids = {
            record["recordId"]
            for row in rows.values()
            for record in row["records"]
        }
        self.assertNotIn("unknown-1", queued_ids)

    def test_reviewed_source_is_removed_once_target_is_met(self) -> None:
        state = {
            "generatedAt": "2026-09-02T00:00:00+00:00",
            "sources": {"source-a": health_source()},
        }
        reviews = {"source-a": {"reviewedRecords": 20}}
        queue = build_queue(state, {}, {}, reviews, DISCLOSURE_CONFIG)
        self.assertEqual(queue["sourceCount"], 0)
        self.assertEqual(queue["sources"], [])

    def test_partial_review_exposes_needed_count_and_traceable_candidate_pool(self) -> None:
        state = {
            "generatedAt": "2026-09-02T00:00:00+00:00",
            "sources": {"source-a": health_source()},
        }
        articles = {
            "articles": [
                {
                    "id": f"article-{index:02d}",
                    "sourceId": "source-a",
                    "title": f"Article {index}",
                    "publishedAt": f"2026-08-{index:02d}",
                    "source": {"url": f"https://example.com/{index}"},
                }
                for index in range(1, 21)
            ]
        }
        reviews = {"source-a": {"reviewedRecords": 8}}
        queue = build_queue(state, articles, {}, reviews, DISCLOSURE_CONFIG)
        row = queue["sources"][0]
        self.assertEqual(row["reviewNeeded"], 12)
        self.assertEqual(row["sampleCandidateCount"], 20)
        self.assertEqual(row["status"], "ready")
        self.assertEqual(len(row["sampleDigest"]), 16)
        self.assertEqual(row["records"][0]["recordId"], "article-20")

    def test_insufficient_records_stay_visible_instead_of_faking_coverage(self) -> None:
        state = {
            "generatedAt": "2026-09-02T00:00:00+00:00",
            "sources": {"source-a": health_source()},
        }
        articles = {
            "articles": [
                {
                    "id": "only-record",
                    "sourceId": "source-a",
                    "title": "Only record",
                    "publishedAt": "2026-09-01",
                    "source": {"url": "https://example.com/only"},
                }
            ]
        }
        queue = build_queue(state, articles, {}, {}, DISCLOSURE_CONFIG)
        row = queue["sources"][0]
        self.assertEqual(row["reviewNeeded"], 20)
        self.assertEqual(row["availableRecordCount"], 1)
        self.assertEqual(row["status"], "insufficient-records")
        self.assertEqual(queue["insufficientRecordSourceCount"], 1)

    def test_queue_is_deterministic_and_valid(self) -> None:
        state = {
            "generatedAt": "2026-09-02T00:00:00+00:00",
            "sources": {"source-a": health_source()},
        }
        articles = {
            "articles": [
                {
                    "id": "article-new",
                    "sourceId": "source-a",
                    "publishedAt": "2026-09-02",
                    "source": {"url": "https://example.com/new"},
                },
                {
                    "id": "article-old",
                    "sourceId": "source-a",
                    "publishedAt": "2026-09-01",
                    "source": {"url": "https://example.com/old"},
                },
            ]
        }
        first = build_queue(state, articles, {}, {}, DISCLOSURE_CONFIG)
        second = build_queue(state, articles, {}, {}, DISCLOSURE_CONFIG)
        self.assertEqual(first, second)
        self.assertEqual(validate_queue(first), [])


if __name__ == "__main__":
    unittest.main()
