from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tools import research_agent as agent


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def seed_data(root: Path, *, product: str = "A", disclosure: bool = False) -> None:
    data = root / "public" / "data"
    write_json(
        data / "venture_profiles.json",
        {
            "generatedAt": "2026-01-01T00:00:00Z",
            "companies": {
                "demo": {
                    "slug": "demo",
                    "name": "示例公司",
                    "updatedAt": "2026-01-01T00:00:00Z",
                    "products": [product],
                    "sources": [
                        {
                            "name": "公司官网",
                            "url": "https://example.com/product",
                            "level": "官方披露",
                        }
                    ],
                }
            },
        },
    )
    write_json(
        data / "institution_entities.json",
        {"entities": [{"id": "inst:1", "name": "示例资本", "sectors": ["AI"]}]},
    )
    write_json(
        data / "market_profiles.json",
        {
            "profiles": {
                "listed": {
                    "slug": "listed",
                    "company": {"name": "示例上市公司"},
                    "updatedAt": "2026-01-01T00:00:00Z",
                    "priceHistory": [
                        {"date": "2026-01-01", "close": 10},
                        {"date": "2026-01-02", "close": 11},
                    ],
                }
            }
        },
    )
    write_json(
        data / "people.json",
        {"people": [{"slug": "person", "name": "研究者", "role": "CEO"}]},
    )
    write_json(data / "institution_events.json", {"events": []})
    events = []
    if disclosure:
        events.append(
            {
                "id": "disclosure-1",
                "companyName": "示例上市公司",
                "publishedAt": "2026-01-03",
                "documentType": "并购与资产交易",
                "title": "重大资产交易公告",
                "source": {
                    "name": "交易所",
                    "url": "https://example.com/disclosure.pdf",
                    "level": "监管文件",
                },
            }
        )
    write_json(
        data / "listed_company_disclosures.json",
        {
            "companies": {
                "listed": {"slug": "listed", "name": "示例上市公司", "events": events}
            }
        },
    )


class ResearchAgentTest(unittest.TestCase):
    def test_canonicalize_ignores_volatile_timestamps(self) -> None:
        left = {"name": "A", "updatedAt": "one", "items": ["b", "a"]}
        right = {"name": "A", "updatedAt": "two", "items": ["a", "b"]}
        self.assertEqual(agent.stable_hash(left), agent.stable_hash(right))

    def test_detects_product_update_and_new_regulatory_disclosure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed_data(root, product="A", disclosure=False)
            before = agent.build_snapshot(
                agent.load_input_payloads(root), "2026-01-02T00:00:00+00:00"
            )
            seed_data(root, product="B", disclosure=True)
            after = agent.build_snapshot(
                agent.load_input_payloads(root), "2026-01-03T00:00:00+00:00"
            )
            changes = agent.diff_snapshots(before, after)
            self.assertTrue(
                any(
                    row["dataset"] == "ventureCompany"
                    and "products" in row["changedFields"]
                    for row in changes
                )
            )
            disclosure = next(row for row in changes if row["dataset"] == "listedDisclosure")
            self.assertEqual(disclosure["action"], "added")
            self.assertGreaterEqual(disclosure["importance"], 96)

    def test_person_snapshot_quarantines_multi_name_and_duplicate_rows(self) -> None:
        rows = agent._person_rows(
            {
                "people": [
                    {"slug": "bad", "name": "王慧文、陈天桥、"},
                    {"slug": "first", "name": "研究者", "sources": []},
                    {
                        "slug": "second",
                        "name": "研究者",
                        "role": "教授",
                        "sources": ["https://example.com/profile"],
                    },
                ]
            }
        )
        self.assertEqual(list(rows), ["second"])
        self.assertEqual(rows["second"]["name"], "研究者")

    def test_person_remove_add_pairs_are_entity_reconciliation(self) -> None:
        previous = {
            "datasets": {
                "person": {
                    "bad": {"name": "王慧文、陈天桥、", "slug": "bad"},
                    "old-id": {"name": "同一人物", "slug": "old-id"},
                }
            }
        }
        current = {
            "datasets": {
                "person": {
                    "wang": {"name": "王慧文", "slug": "wang"},
                    "chen": {"name": "陈天桥", "slug": "chen"},
                    "new-id": {"name": "同一人物", "slug": "new-id"},
                }
            }
        }
        changes = agent.diff_snapshots(previous, current)
        self.assertTrue(changes)
        self.assertTrue(
            all(change["changeType"] != "external_event" for change in changes)
        )
        reconciled = {
            change["entityName"]
            for change in changes
            if change["changeType"] == "entity_reconciliation"
        }
        self.assertTrue({"王慧文、陈天桥、", "王慧文", "陈天桥", "同一人物"} <= reconciled)

    def test_sources_only_change_is_not_an_external_event(self) -> None:
        previous = {
            "datasets": {
                "ventureCompany": {
                    "demo": {"name": "示例公司", "sources": [{"url": "https://a"}]}
                }
            }
        }
        current = {
            "datasets": {
                "ventureCompany": {
                    "demo": {"name": "示例公司", "sources": [{"url": "https://b"}]}
                }
            }
        }
        change = agent.diff_snapshots(previous, current)[0]
        self.assertEqual(change["changeType"], "source_refresh")
        self.assertFalse(change["isResearchCandidate"])

    def test_evidence_ids_are_attached_and_validated(self) -> None:
        change = {
            "id": "chg-1",
            "dataset": "listedDisclosure",
            "entityType": "上市公司公告",
            "entityId": "d1",
            "entityName": "示例公司",
            "action": "added",
            "changedFields": ["title"],
            "summary": "新增公告",
            "importance": 96,
            "before": None,
            "after": {"title": "公告"},
            "record": {
                "title": "公告",
                "source": {"name": "交易所", "url": "https://example.com/a.pdf"},
            },
        }
        changes, evidence = agent.build_evidence_package([change])
        self.assertEqual(changes[0]["evidenceIds"], ["E001"])
        self.assertEqual(evidence[0]["url"], "https://example.com/a.pdf")

    def test_evidence_gate_and_claim_field_binding(self) -> None:
        record = {
            "financing": [{"title": "A轮融资"}],
            "sources": [
                {
                    "title": "公司融资公告",
                    "url": "https://example.com/valid",
                    "level": "官方披露",
                    "publishedAt": "2026-01-02",
                    "section": "financing",
                },
                {
                    "title": "未来公告",
                    "url": "https://example.com/future",
                    "level": "官方披露",
                    "publishedAt": "2026-02-01",
                    "section": "financing",
                },
                {
                    "url": "https://example.com/no-title",
                    "level": "官方披露",
                    "section": "financing",
                },
                {
                    "title": "未分级公告",
                    "url": "https://example.com/ungraded",
                    "section": "financing",
                },
                {
                    "title": "无链接公告",
                    "level": "官方披露",
                    "section": "financing",
                },
            ],
        }
        sources = agent.extract_sources(
            record,
            limit=10,
            changed_fields=["financing", "sources"],
            dataset="ventureCompany",
            action="updated",
            as_of="2026-01-03T00:00:00+00:00",
        )
        by_title = {source["title"]: source for source in sources}
        self.assertEqual(by_title["公司融资公告"]["supportStatus"], "supports")
        self.assertIn("future_published_at", by_title["未来公告"]["qualityIssues"])
        self.assertIn("missing_title", by_title[""]["qualityIssues"])
        self.assertIn("missing_published_at", by_title[""]["qualityIssues"])
        self.assertIn("ungraded", by_title["未分级公告"]["qualityIssues"])
        self.assertIn("missing_or_invalid_url", by_title["无链接公告"]["qualityIssues"])

        change = {
            "id": "chg-financing",
            "dataset": "ventureCompany",
            "entityType": "创业公司",
            "entityId": "demo",
            "entityName": "示例公司",
            "action": "updated",
            "changedFields": ["financing", "sources"],
            "summary": "示例公司融资变化。",
            "importance": 88,
            "before": {"financing": []},
            "after": {"financing": [{"title": "A轮融资"}]},
            "record": record,
            "changeType": "external_event",
        }
        changes, evidence = agent.build_evidence_package(
            [change], as_of="2026-01-03T00:00:00+00:00"
        )
        self.assertTrue(changes[0]["eligibleForKeyDevelopment"])
        self.assertEqual(changes[0]["publicationTier"], "verified_change")
        self.assertEqual(changes[0]["reviewStatus"], "automated_unreviewed")
        self.assertEqual(changes[0]["claimFields"], ["financing"])
        self.assertEqual(changes[0]["claimBindings"][0]["field"], "financing")
        self.assertTrue(any(row["supportStatus"] == "supports" for row in evidence))

    def test_market_news_uses_only_new_entity_matched_rows(self) -> None:
        old = {
            "title": "中科寒武纪科技股份有限公司既有公告",
            "url": "https://news.example.com/old",
            "publishedAt": "2026-08-22T06:00:00Z",
            "level": "媒体报道",
        }
        unrelated = {
            "title": "章建平夫妇现身亨通光电",
            "url": "https://news.example.com/unrelated",
            "publishedAt": "2026-08-24T06:00:00Z",
            "level": "媒体报道",
        }
        relevant = {
            "title": "寒武纪发布新一代云端芯片",
            "url": "https://news.example.com/relevant?utm_source=test",
            "publishedAt": "2026-08-24T07:00:00Z",
            "level": "媒体报道",
        }
        before_record = {
            "company": {"name": "中科寒武纪科技股份有限公司"},
            "ticker": "688256",
            "news": [old],
        }
        after_record = {
            **before_record,
            "news": [old, unrelated, relevant],
        }
        change = {
            "id": "chg-market-news",
            "dataset": "marketCompany",
            "entityType": "上市公司",
            "entityId": "cambricon",
            "entityName": "中科寒武纪科技股份有限公司",
            "action": "updated",
            "changedFields": ["news"],
            "summary": "寒武纪新闻变化。",
            "importance": 48,
            "before": {"news": [old]},
            "after": {"news": [old, unrelated, relevant]},
            "_beforeRecord": before_record,
            "record": after_record,
            "changeType": "external_event",
        }

        changes, evidence = agent.build_evidence_package(
            [change], as_of="2026-08-24T08:00:00+00:00"
        )

        self.assertNotIn("https://news.example.com/old", {row["url"] for row in evidence})
        by_url = {row["url"].split("?")[0]: row for row in evidence}
        self.assertEqual(
            by_url["https://news.example.com/relevant"]["entityMatchStatus"],
            "matched",
        )
        self.assertEqual(
            by_url["https://news.example.com/relevant"]["supportStatus"],
            "supports",
        )
        self.assertEqual(
            by_url["https://news.example.com/unrelated"]["entityMatchStatus"],
            "mismatched",
        )
        self.assertIn(
            "entity_mismatch",
            by_url["https://news.example.com/unrelated"]["qualityIssues"],
        )
        self.assertEqual(changes[0]["publicationTier"], "candidate")
        self.assertTrue(changes[0]["eligibleForKeyDevelopment"])

    def test_market_news_url_rotation_is_not_a_new_item(self) -> None:
        before_news = [
            {
                "title": "宁德时代发布电池新品",
                "source": "示例媒体",
                "url": "https://old.example.com/story?id=1&utm_source=feed",
                "publishedAt": "2026-08-24T06:00:00Z",
            }
        ]
        after_news = [
            {
                "title": "宁德时代发布电池新品",
                "source": "示例媒体",
                "url": "https://new.example.com/rehosted/story?id=1&token=rotated",
                "publishedAt": "2026-08-24T06:00:00Z",
            }
        ]
        change = {
            "id": "chg-market-url-rotation",
            "dataset": "marketCompany",
            "entityType": "上市公司",
            "entityId": "catl",
            "entityName": "宁德时代",
            "action": "updated",
            "changedFields": ["news"],
            "summary": "宁德时代新闻变化。",
            "importance": 48,
            "before": {"news": before_news},
            "after": {"news": after_news},
            "_beforeRecord": {"news": before_news},
            "record": {"company": {"name": "宁德时代"}, "news": after_news},
            "changeType": "external_event",
        }

        changes, evidence = agent.build_evidence_package(
            [change], as_of="2026-08-24T08:00:00+00:00"
        )

        self.assertFalse(changes[0]["eligibleForKeyDevelopment"])
        self.assertEqual(changes[0]["publicationTier"], "rejected")
        self.assertEqual(evidence[0]["qualityIssues"], ["no_external_evidence"])

    def test_discovery_only_evidence_cannot_enter_formal_tier(self) -> None:
        change = {
            "id": "chg-discovery",
            "dataset": "listedDisclosure",
            "entityType": "上市公司公告",
            "entityId": "d-discovery",
            "entityName": "示例公司",
            "action": "added",
            "changedFields": ["title"],
            "summary": "新增公告。",
            "importance": 96,
            "before": None,
            "after": {"title": "示例公司公告"},
            "record": {
                "title": "示例公司公告",
                "publishedAt": "2026-08-24T06:00:00Z",
                "source": {
                    "name": "搜索发现",
                    "url": "https://example.com/discovery",
                    "level": "D级线索",
                    "sourceRole": "discovery",
                },
            },
            "changeType": "external_event",
        }

        changes, evidence = agent.build_evidence_package(
            [change], as_of="2026-08-24T08:00:00+00:00"
        )

        self.assertFalse(changes[0]["eligibleForKeyDevelopment"])
        self.assertEqual(changes[0]["publicationTier"], "rejected")
        self.assertEqual(evidence[0]["publicationTier"], "rejected")
        self.assertIn("discovery_only", evidence[0]["qualityIssues"])

    def test_core_media_only_change_remains_candidate(self) -> None:
        change = {
            "id": "chg-core-media",
            "dataset": "ventureCompany",
            "entityType": "创业公司",
            "entityId": "demo",
            "entityName": "示例公司",
            "action": "updated",
            "changedFields": ["financing"],
            "summary": "示例公司融资变化。",
            "importance": 88,
            "before": {"financing": []},
            "after": {"financing": [{"round": "A"}]},
            "record": {
                "financing": [{"round": "A"}],
                "sources": [
                    {
                        "title": "示例公司完成融资",
                        "url": "https://media.example.com/financing",
                        "publishedAt": "2026-08-24T06:00:00Z",
                        "level": "C",
                        "section": "financing",
                    }
                ],
            },
            "changeType": "external_event",
        }

        changes, _ = agent.build_evidence_package(
            [change], as_of="2026-08-24T08:00:00+00:00"
        )

        self.assertTrue(changes[0]["eligibleForKeyDevelopment"])
        self.assertEqual(changes[0]["publicationTier"], "candidate")

    def test_intelligence_events_are_external_clues(self) -> None:
        change = {
            "id": "chg-clue",
            "dataset": "intelligenceEvent",
            "entityType": "高价值情报事件",
            "entityId": "event",
            "entityName": "示例公司",
            "action": "added",
            "changedFields": ["summary"],
            "summary": "示例公司发布产品。",
            "importance": 88,
            "before": None,
            "after": {"summary": "示例公司发布产品。"},
            "record": {
                "summary": "示例公司发布产品。",
                "sources": [
                    {
                        "title": "示例公司发布产品",
                        "url": "https://example.com/clue",
                        "publishedAt": "2026-08-24T06:00:00Z",
                        "level": "媒体报道",
                        "section": "summary",
                    }
                ],
            },
            "changeType": "external_event",
        }

        changes, evidence = agent.build_evidence_package(
            [change], as_of="2026-08-24T08:00:00+00:00"
        )

        self.assertEqual(changes[0]["publicationTier"], "external_clue")
        self.assertEqual(evidence[0]["publicationTier"], "external_clue")

    def test_same_company_disclosures_are_aggregated(self) -> None:
        changes = []
        for index, document_type in enumerate(("定期报告", "定期报告", "重大经营"), 1):
            changes.append(
                {
                    "id": f"chg-{index}",
                    "dataset": "listedDisclosure",
                    "entityType": "上市公司公告",
                    "entityId": f"d-{index}",
                    "entityName": "华大基因",
                    "action": "added",
                    "changedFields": ["title", "documentType", "publishedAt", "source"],
                    "summary": "新增上市公司公告记录：华大基因。",
                    "importance": 96,
                    "before": None,
                    "after": {"title": f"公告 {index}"},
                    "record": {
                        "companySlug": "bgi-genomics",
                        "companyName": "华大基因",
                        "publishedAt": "2026-08-21",
                        "title": f"公告 {index}",
                        "documentType": document_type,
                        "source": {
                            "name": "交易所",
                            "url": f"https://example.com/{index}.pdf",
                            "level": "监管文件",
                        },
                    },
                    "changeType": "external_event",
                    "isResearchCandidate": True,
                }
            )
        aggregated = agent.aggregate_external_changes(changes)
        self.assertEqual(len(aggregated), 1)
        self.assertEqual(aggregated[0]["groupSize"], 3)
        self.assertIn("3 份", aggregated[0]["summary"])

        public_changes, evidence = agent.build_evidence_package(
            aggregated, as_of="2026-08-23T00:00:00+00:00"
        )
        self.assertEqual(len(public_changes), 1)
        self.assertEqual(len(public_changes[0]["supportingEvidenceIds"]), 3)
        self.assertEqual(len(evidence), 3)
        self.assertEqual(public_changes[0]["publicationTier"], "candidate")

    def test_model_analysis_drops_unknown_evidence_references(self) -> None:
        raw = {
            "executiveSummary": "摘要",
            "keyDevelopments": [
                {"title": "有效", "assessment": "A", "evidenceIds": ["E001"]},
                {"title": "无效", "assessment": "B", "evidenceIds": ["E999"]},
            ],
        }
        cleaned = agent.sanitize_analysis(raw, {"E001"})
        self.assertEqual(len(cleaned["keyDevelopments"]), 1)
        self.assertEqual(cleaned["keyDevelopments"][0]["title"], "有效")

    def test_generation_excludes_maintenance_and_rejected_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed_data(root, product="A", disclosure=False)
            previous_snapshot = agent.build_snapshot(
                agent.load_input_payloads(root), "2026-01-02T00:00:00+00:00"
            )
            # A product-field change with a source missing its title is an
            # external candidate, but it must fail the evidence quality gate.
            seed_data(root, product="B", disclosure=False)
            snapshot_path = root / "public/data/research_agent_snapshot.json"
            output_path = root / "public/data/research_agent_daily.json"
            write_json(snapshot_path, previous_snapshot)
            report, _ = agent.generate_report(
                root=root,
                output_path=output_path,
                snapshot_path=snapshot_path,
                now=datetime(2026, 1, 3, tzinfo=timezone.utc),
                bootstrap_git_ref="HEAD^",
                offline=True,
                max_changes=36,
            )
            self.assertEqual(report["changeSummary"]["total"], 0)
            self.assertEqual(report["changeSummary"]["qualityRejected"], 1)
            self.assertEqual(report["changeSummary"]["rejectedTotal"], 1)
            self.assertEqual(report["changeSummary"]["verifiedChangeTotal"], 0)
            self.assertEqual(report["changeSummary"]["candidateTotal"], 0)
            self.assertEqual(report["changeSummary"]["auxiliaryLeadTotal"], 0)
            self.assertFalse(report["analysis"]["keyDevelopments"])

            # A newly ingested person profile is data maintenance, not a real-
            # world event, and therefore never enters key developments either.
            current_snapshot = agent.build_snapshot(
                agent.load_input_payloads(root), "2026-01-03T00:00:00+00:00"
            )
            current_snapshot["datasets"]["ventureCompany"] = previous_snapshot[
                "datasets"
            ]["ventureCompany"]
            current_snapshot["datasets"]["person"] = {}
            write_json(snapshot_path, current_snapshot)
            seed_data(root, product="A", disclosure=False)
            report, _ = agent.generate_report(
                root=root,
                output_path=output_path,
                snapshot_path=snapshot_path,
                now=datetime(2026, 1, 3, tzinfo=timezone.utc),
                bootstrap_git_ref="HEAD^",
                offline=True,
                max_changes=36,
            )
            self.assertEqual(report["changeSummary"]["total"], 0)
            self.assertGreaterEqual(report["changeSummary"]["maintenanceExcluded"], 1)
            self.assertFalse(report["analysis"]["keyDevelopments"])

    def test_offline_generation_writes_valid_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed_data(root, product="A", disclosure=False)
            previous_snapshot = agent.build_snapshot(
                agent.load_input_payloads(root), "2026-01-02T00:00:00+00:00"
            )
            seed_data(root, product="B", disclosure=True)
            snapshot_path = root / "public/data/research_agent_snapshot.json"
            output_path = root / "public/data/research_agent_daily.json"
            write_json(snapshot_path, previous_snapshot)
            report, snapshot = agent.generate_report(
                root=root,
                output_path=output_path,
                snapshot_path=snapshot_path,
                now=datetime(2026, 1, 3, tzinfo=timezone.utc),
                bootstrap_git_ref="HEAD^",
                offline=True,
                max_changes=36,
            )
            self.assertEqual(report["runStatus"], "offline-fallback")
            self.assertEqual(report["reviewStatus"], "automated_unreviewed")
            self.assertGreater(report["changeSummary"]["total"], 0)
            self.assertEqual(report["changeSummary"]["verifiedChangeTotal"], 0)
            self.assertGreater(report["changeSummary"]["candidateTotal"], 0)
            self.assertEqual(report["analysis"]["mode"], "structured-change-only")
            self.assertFalse(report["analysis"]["isResearchJudgment"])
            self.assertIn("不提供模型研判", report["analysis"]["executiveSummary"])
            self.assertFalse(agent.validate_report(report))
            self.assertIn("contentHash", snapshot)


if __name__ == "__main__":
    unittest.main()
