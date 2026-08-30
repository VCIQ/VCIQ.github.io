from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools import research_agent as agent
from tools import research_agent_article_events as article_events


ROOT = Path(__file__).resolve().parents[1]


def article(
    article_id: str,
    *,
    title: str,
    cluster: str = "cluster-1",
    importance: int = 95,
    quality_status: str = "高可信",
    quality_score: int = 88,
    published_at: str = "2026-08-27T08:00:00Z",
    role: str = "corroboration",
    level: str = "媒体报道",
    url: str | None = None,
) -> dict[str, object]:
    return {
        "id": article_id,
        "title": title,
        "summary": f"{title} 的结构化事实摘要",
        "type": "技术突破",
        "region": "全球",
        "sector": "AI / AGI",
        "company": "示例公司",
        "companySlug": "example-company",
        "mentionedCompanies": ["示例公司"],
        "publishedAt": published_at,
        "importance": importance,
        "qualityScore": quality_score,
        "qualityStatus": quality_status,
        "eventClusterId": cluster,
        "sourceRole": role,
        "url": url or f"https://example.com/{article_id}",
        "source": {
            "name": f"Source {article_id}",
            "level": level,
            "sourceRole": role,
        },
    }


class ResearchAgentArticleEventsTest(unittest.TestCase):
    def test_quality_gated_high_value_articles_are_event_deduplicated(self) -> None:
        payload = {
            "qualityGate": {"passed": True},
            "articles": [
                article(
                    "media",
                    title="示例公司发布重大技术突破",
                    importance=94,
                    quality_score=90,
                    role="corroboration",
                    level="媒体报道",
                ),
                article(
                    "official",
                    title="示例公司宣布重大技术突破",
                    importance=98,
                    quality_score=96,
                    role="primary",
                    level="官方披露",
                ),
                article(
                    "low-importance",
                    title="低重要度事件",
                    cluster="cluster-low",
                    importance=70,
                ),
                article(
                    "low-trust",
                    title="低可信事件",
                    cluster="cluster-low-trust",
                    quality_status="低可信",
                ),
                article(
                    "stale",
                    title="过期事件",
                    cluster="cluster-stale",
                    published_at="2026-08-01T08:00:00Z",
                ),
            ],
        }
        payload["articles"][1]["source"].update(
            {
                "publisherName": "示例公司新闻室",
                "platformName": "公司官网",
                "sourceType": "official-newsroom",
            }
        )

        rows = article_events.build_event_rows(
            payload, "2026-08-27T10:00:00+00:00"
        )

        self.assertEqual(len(rows), 1)
        record = next(iter(rows.values()))
        self.assertEqual(record["title"], "示例公司宣布重大技术突破")
        self.assertEqual(record["importance"], 98)
        self.assertEqual(record["qualityScore"], 96)
        self.assertEqual(len(record["sources"]), 2)
        self.assertEqual(record["sources"][0]["level"], "官方披露")
        self.assertEqual(
            record["sources"][0]["publisherName"], "示例公司新闻室"
        )
        self.assertEqual(record["sources"][0]["platformName"], "公司官网")
        self.assertEqual(record["sources"][0]["sourceType"], "official-newsroom")
        self.assertTrue(
            all(source["section"] == "summary" for source in record["sources"])
        )

    def test_article_snapshot_quality_gate_fails_closed(self) -> None:
        candidate = article("event", title="高价值事件")
        self.assertEqual(
            article_events.build_event_rows(
                {"qualityGate": {"passed": False}, "articles": [candidate]},
                "2026-08-27T10:00:00+00:00",
            ),
            {},
        )
        self.assertEqual(
            article_events.build_event_rows(
                {"articles": [candidate]}, "2026-08-27T10:00:00+00:00"
            ),
            {},
        )

    def test_current_production_snapshot_yields_high_value_event_rows(self) -> None:
        payload = json.loads(
            (ROOT / "public" / "data" / "articles.json").read_text(encoding="utf-8")
        )
        gate = payload.get("qualityGate")
        self.assertIsInstance(gate, dict)
        self.assertIs(gate.get("passed"), True)
        raw_articles = payload.get("articles")
        self.assertIsInstance(raw_articles, list)
        published = [
            article_events._parse_datetime(row.get("publishedAt"))
            for row in raw_articles
            if isinstance(row, dict)
        ]
        dates = [value for value in published if value is not None]
        self.assertTrue(dates)
        as_of = max(dates).isoformat()

        rows = article_events.build_event_rows(payload, as_of)

        self.assertGreater(len(rows), 0)
        self.assertLessEqual(len(rows), article_events.MAX_EVENT_ROWS)
        self.assertTrue(
            all(
                int(record.get("importance", 0)) >= article_events.MIN_IMPORTANCE
                and bool(record.get("sources"))
                for record in rows.values()
            )
        )

    def test_intelligence_event_additions_use_external_event_semantics(self) -> None:
        payload = {
            "qualityGate": {"passed": True},
            "articles": [article("event", title="高价值事件", importance=97)],
        }
        rows = article_events.build_event_rows(
            payload, "2026-08-27T10:00:00+00:00"
        )

        had_dataset = article_events.DATASET in agent.EVENT_DATASETS
        old_label = agent.ENTITY_LABELS.get(article_events.DATASET)
        agent.EVENT_DATASETS.add(article_events.DATASET)
        agent.ENTITY_LABELS[article_events.DATASET] = article_events.DATASET_LABEL
        try:
            changes = agent.diff_snapshots(
                {"datasets": {article_events.DATASET: {}}},
                {"datasets": {article_events.DATASET: rows}},
            )
            article_events._normalize_event_changes(changes)
            self.assertEqual(len(changes), 1)
            change = changes[0]
            self.assertEqual(change["dataset"], article_events.DATASET)
            self.assertEqual(change["action"], "added")
            self.assertEqual(change["changeType"], "external_event")
            self.assertTrue(change["isResearchCandidate"])
            self.assertEqual(change["importance"], 97)

            # Rolling-window expiry must not be interpreted as a reversed fact.
            removals = agent.diff_snapshots(
                {"datasets": {article_events.DATASET: rows}},
                {"datasets": {article_events.DATASET: {}}},
            )
            self.assertEqual(removals, [])
        finally:
            if not had_dataset:
                agent.EVENT_DATASETS.discard(article_events.DATASET)
            if old_label is None:
                agent.ENTITY_LABELS.pop(article_events.DATASET, None)
            else:
                agent.ENTITY_LABELS[article_events.DATASET] = old_label

    def test_report_summary_distinguishes_zero_candidates_from_gate_rejection(self) -> None:
        zero_report = {
            "generatedAt": "2026-08-27T10:00:00+00:00",
            "changeSummary": {
                "externalCandidates": 0,
                "qualityRejected": 0,
                "total": 0,
            },
            "analysis": {"executiveSummary": "旧的含混文案"},
            "history": [
                {
                    "generatedAt": "2026-08-27T10:00:00+00:00",
                    "executiveSummary": "旧的含混文案",
                }
            ],
        }
        article_events.normalize_report_summary(zero_report)
        self.assertEqual(
            zero_report["analysis"]["executiveSummary"],
            "本轮未检测到新的外部事实候选。",
        )
        self.assertEqual(
            zero_report["history"][0]["executiveSummary"],
            "本轮未检测到新的外部事实候选。",
        )

        rejected_report = copy.deepcopy(zero_report)
        rejected_report["changeSummary"] = {
            "externalCandidates": 4,
            "qualityRejected": 4,
            "total": 0,
        }
        article_events.normalize_report_summary(rejected_report)
        self.assertEqual(
            rejected_report["analysis"]["executiveSummary"],
            "本轮检测到 4 个外部事实候选，但全部未通过证据质量门。",
        )

        partial_report = copy.deepcopy(zero_report)
        partial_report["analysis"]["executiveSummary"] = "保留已有模型摘要"
        partial_report["changeSummary"] = {
            "externalCandidates": 4,
            "qualityRejected": 2,
            "total": 2,
        }
        article_events.normalize_report_summary(partial_report)
        self.assertEqual(
            partial_report["analysis"]["executiveSummary"], "保留已有模型摘要"
        )


if __name__ == "__main__":
    unittest.main()
