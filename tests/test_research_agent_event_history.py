from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from tools import research_agent as agent


def packaged_change(
    change_id: str,
    *,
    title: str,
    evidence_id: str,
    dataset: str = "intelligenceEvent",
    entity_id: str = "url-derived-row",
    entity_name: str | None = None,
    field: str = "title",
    before: object = None,
    after: object | None = None,
) -> dict[str, object]:
    after_value = title if after is None else after
    return {
        "id": change_id,
        "dataset": dataset,
        "entityType": "高价值情报事件" if dataset == "intelligenceEvent" else "人物",
        "entityId": entity_id,
        "entityName": entity_name or title,
        "action": "added" if before is None else "updated",
        "changedFields": [field],
        "summary": f"{entity_name or title} 的 {field} 发生变化。",
        "importance": 90,
        "before": {field: before} if before is not None else None,
        "after": {field: after_value},
        "changeType": "external_event",
        "publicationTier": (
            "external_clue" if dataset == "intelligenceEvent" else "candidate"
        ),
        "claimFields": [field],
        "claimBindings": [
            {
                "field": field,
                "before": before,
                "after": after_value,
                "evidenceIds": [evidence_id],
            }
        ],
        "evidenceIds": [evidence_id],
        "supportingEvidenceIds": [evidence_id],
        "evidenceQuality": {"status": "passed", "supporting": 1, "total": 1},
        "eligibleForKeyDevelopment": True,
    }


def evidence(
    evidence_id: str,
    change_id: str,
    *,
    title: str,
    url: str,
    source_name: str = "示例媒体",
    grade: str = "媒体报道",
    published_at: str = "2026-08-29",
) -> dict[str, object]:
    return {
        "id": evidence_id,
        "changeId": change_id,
        "entityName": title,
        "claim": title,
        "sourceName": source_name,
        "title": title,
        "url": url,
        "publishedAt": published_at,
        "evidenceGrade": grade,
        "claimFields": ["title"],
        "qualityIssues": [],
        "qualityStatus": "passed",
        "supportStatus": "supports",
    }


def legacy_report(change: dict[str, object], row: dict[str, object]) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "generatedAt": "2026-08-29T01:00:00+00:00",
        "asOfDate": "2026-08-29",
        "changes": [change],
        "evidence": [row],
        "history": [
            {
                "date": "2026-08-28",
                "generatedAt": "2026-08-28T01:00:00+00:00",
                "changeCount": 20,
                "executiveSummary": "自然语言历史不得被猜测成事件账本。",
            }
        ],
    }


def with_supporting_evidence(
    change: dict[str, object], evidence_ids: list[str]
) -> dict[str, object]:
    result = copy.deepcopy(change)
    result["evidenceIds"] = evidence_ids
    result["supportingEvidenceIds"] = evidence_ids
    bindings = result.get("claimBindings")
    if isinstance(bindings, list):
        for binding in bindings:
            if isinstance(binding, dict):
                binding["evidenceIds"] = evidence_ids
    quality = result.get("evidenceQuality")
    if isinstance(quality, dict):
        quality["supporting"] = len(evidence_ids)
        quality["total"] = len(evidence_ids)
    return result


class ResearchAgentEventHistoryTest(unittest.TestCase):
    def test_legacy_report_migrates_current_evidence_but_not_history(self) -> None:
        change = packaged_change(
            "chg-old", title="OpenAI 发布管理插件", evidence_id="E001"
        )
        row = evidence(
            "E001",
            "chg-old",
            title="OpenAI 发布管理插件",
            url="https://example.com/openai-admin",
        )

        ledger = agent._legacy_event_ledger(legacy_report(change, row))

        self.assertEqual(len(ledger["events"]), 1)
        entry = next(iter(ledger["events"].values()))
        self.assertTrue(entry["eventId"].startswith("evt-"))
        self.assertEqual(entry["firstSeenAt"], "2026-08-29T01:00:00+00:00")
        self.assertEqual(entry["lastSeenAt"], "2026-08-29T01:00:00+00:00")
        self.assertNotIn("E001", str(entry))

    def test_google_url_token_drift_is_suppressed_as_duplicate(self) -> None:
        title = "OpenAI发布适用于ChatGPT Work和Codex的Admin插件"
        old_change = packaged_change("chg-old", title=title, evidence_id="E001")
        old_row = evidence(
            "E001",
            "chg-old",
            title=title,
            source_name="Google News",
            url="https://news.google.com/rss/articles/TOKEN-A?oc=5",
        )
        current_change = packaged_change(
            "chg-new",
            title=title,
            evidence_id="E999",
            entity_id="different-url-derived-row",
        )
        current_row = evidence(
            "E999",
            "chg-new",
            title=title,
            source_name="Google News",
            url="https://news.google.com/rss/articles/TOKEN-B?oc=5",
        )

        formal, ledger, diagnostics = agent.reconcile_event_ledger(
            legacy_report(old_change, old_row),
            [current_change],
            [current_row],
            generated_at="2026-08-30T01:00:00+00:00",
        )

        self.assertEqual(formal, [])
        self.assertEqual(diagnostics["duplicatesSuppressed"], 1)
        self.assertEqual(diagnostics["newEvents"], 0)
        self.assertEqual(len(ledger["events"]), 1)

    def test_independent_and_stronger_sources_are_reconfirmations(self) -> None:
        title = "示例公司宣布重大技术突破"
        old_change = packaged_change("chg-old", title=title, evidence_id="E001")
        old_row = evidence(
            "E001",
            "chg-old",
            title=title,
            source_name="标题聚合",
            grade="D",
            url="https://aggregator.example/story",
        )
        previous = legacy_report(old_change, old_row)

        media_change = packaged_change("chg-media", title=title, evidence_id="E002")
        media_row = evidence(
            "E002",
            "chg-media",
            title=title,
            source_name="公司官网",
            grade="原始材料",
            url="https://company.example/announcement",
        )
        formal, ledger, diagnostics = agent.reconcile_event_ledger(
            previous,
            [media_change],
            [media_row],
            generated_at="2026-08-30T01:00:00+00:00",
        )

        self.assertEqual(formal, [])
        self.assertEqual(diagnostics["reconfirmations"], 1)
        entry = next(iter(ledger["events"].values()))
        self.assertEqual(entry["observationCount"], 2)
        self.assertEqual(entry["bestEvidenceStrength"], 4)
        self.assertEqual(entry["confirmationCount"], 1)

    def test_same_source_claim_revision_is_published_as_update(self) -> None:
        old_title = "示例公司产品发布日期为九月"
        new_title = "示例公司产品发布日期更改为十月"
        old_change = packaged_change("chg-old", title=old_title, evidence_id="E001")
        old_row = evidence(
            "E001",
            "chg-old",
            title=old_title,
            url="https://company.example/product",
            grade="原始材料",
        )
        current_change = packaged_change(
            "chg-current", title=new_title, evidence_id="E002"
        )
        current_row = evidence(
            "E002",
            "chg-current",
            title=new_title,
            url="https://company.example/product",
            grade="原始材料",
        )

        formal, ledger, diagnostics = agent.reconcile_event_ledger(
            legacy_report(old_change, old_row),
            [current_change],
            [current_row],
            generated_at="2026-08-30T01:00:00+00:00",
        )

        self.assertEqual(len(formal), 1)
        self.assertEqual(formal[0]["lifecycle"], "updated")
        self.assertEqual(diagnostics["updates"], 1)
        self.assertEqual(len(ledger["events"]), 1)

    def test_same_effective_date_scalar_disagreement_is_only_possible_conflict(self) -> None:
        old_change = packaged_change(
            "chg-old",
            title="示例人物任职状态",
            evidence_id="E001",
            dataset="person",
            entity_id="person-1",
            entity_name="示例人物",
            field="role",
            before="研究员",
            after="首席技术官",
        )
        old_row = evidence(
            "E001",
            "chg-old",
            title="示例人物任职状态",
            url="https://example.com/profile",
            grade="官方披露",
        )
        current_change = packaged_change(
            "chg-current",
            title="示例人物任职状态",
            evidence_id="E002",
            dataset="person",
            entity_id="person-1",
            entity_name="示例人物",
            field="role",
            before="首席技术官",
            after="顾问",
        )
        current_row = evidence(
            "E002",
            "chg-current",
            title="示例人物任职状态",
            url="https://example.com/profile",
            grade="媒体报道",
        )

        formal, ledger, diagnostics = agent.reconcile_event_ledger(
            legacy_report(old_change, old_row),
            [current_change],
            [current_row],
            generated_at="2026-08-30T01:00:00+00:00",
        )

        self.assertEqual(formal, [])
        self.assertEqual(diagnostics["possibleConflicts"], 1)
        self.assertEqual(len(diagnostics["reviewQueue"]), 1)
        self.assertTrue(
            any(
                entry["conflictStatus"] == "possible"
                for entry in ledger["events"].values()
            )
        )

        next_day_row = copy.deepcopy(current_row)
        next_day_row["publishedAt"] = "2026-08-30"
        formal, _, diagnostics = agent.reconcile_event_ledger(
            legacy_report(old_change, old_row),
            [current_change],
            [next_day_row],
            generated_at="2026-08-30T02:00:00+00:00",
        )
        self.assertEqual(len(formal), 1)
        self.assertEqual(formal[0]["lifecycle"], "updated")
        self.assertEqual(diagnostics["possibleConflicts"], 0)

    def test_same_day_empty_run_preserves_material_history(self) -> None:
        previous = {
            "history": [
                {
                    "metricsVersion": 2,
                    "date": "2026-08-30",
                    "generatedAt": "2026-08-30T01:00:00+00:00",
                    "runStatus": "model",
                    "changeCount": 3,
                    "executiveSummary": "已有三条正式变化。",
                    "eventIds": ["evt-a", "evt-b", "evt-c"],
                    "eventSummary": {
                        "newEvents": 3,
                        "reconfirmations": 0,
                        "updates": 0,
                        "corrections": 0,
                        "possibleConflicts": 0,
                        "duplicatesSuppressed": 0,
                    },
                }
            ]
        }
        current = {
            "asOfDate": "2026-08-30",
            "generatedAt": "2026-08-30T02:00:00+00:00",
            "runStatus": "no-material-change",
            "changeSummary": {
                "total": 0,
                "reconfirmations": 1,
                "possibleConflicts": 1,
                "duplicatesSuppressed": 2,
            },
            "analysis": {"executiveSummary": "本轮无变化。"},
            "changes": [],
        }

        history = agent._merge_history(previous, current)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["generatedAt"], current["generatedAt"])
        self.assertEqual(history[0]["runStatus"], "no-material-change")
        self.assertEqual(history[0]["changeCount"], 3)
        self.assertEqual(history[0]["executiveSummary"], "已有三条正式变化。")
        self.assertEqual(history[0]["eventIds"], ["evt-a", "evt-b", "evt-c"])
        self.assertEqual(history[0]["eventSummary"]["newEvents"], 3)
        self.assertEqual(history[0]["eventSummary"]["reconfirmations"], 1)
        self.assertEqual(history[0]["eventSummary"]["possibleConflicts"], 1)
        self.assertEqual(history[0]["eventSummary"]["duplicatesSuppressed"], 2)

    def test_same_day_empty_v2_run_does_not_relabel_legacy_count(self) -> None:
        previous = {
            "history": [
                {
                    "date": "2026-08-30",
                    "generatedAt": "2026-08-30T01:00:00+00:00",
                    "runStatus": "model",
                    "changeCount": 10,
                    "executiveSummary": "旧口径十条变化。",
                }
            ]
        }
        current = {
            "asOfDate": "2026-08-30",
            "generatedAt": "2026-08-30T02:00:00+00:00",
            "runStatus": "no-material-change",
            "changeSummary": {
                "total": 0,
                "verifiedChangeTotal": 0,
                "candidateTotal": 0,
                "auxiliaryLeadTotal": 0,
            },
            "analysis": {"executiveSummary": "本轮无变化。"},
            "changes": [],
        }

        row = agent._merge_history(previous, current)[0]

        self.assertNotIn("metricsVersion", row)
        self.assertEqual(row["legacyChangeCount"], 10)
        self.assertEqual(row["changeCount"], 10)
        self.assertNotIn("verifiedChangeTotal", row)

    def test_later_conflict_removes_earlier_same_run_formal_event(self) -> None:
        first = packaged_change(
            "chg-first",
            title="示例人物任职状态",
            evidence_id="E001",
            dataset="person",
            entity_id="person-1",
            entity_name="示例人物",
            field="role",
            before="研究员",
            after="首席技术官",
        )
        second = packaged_change(
            "chg-second",
            title="示例人物任职状态",
            evidence_id="E002",
            dataset="person",
            entity_id="person-1",
            entity_name="示例人物",
            field="role",
            before="首席技术官",
            after="顾问",
        )
        first_evidence = evidence(
            "E001",
            "chg-first",
            title="示例人物任职状态",
            url="https://official.example/profile",
            grade="官方披露",
        )
        second_evidence = evidence(
            "E002",
            "chg-second",
            title="示例人物任职状态",
            url="https://media.example/profile",
            grade="媒体报道",
        )

        formal, ledger, diagnostics = agent.reconcile_event_ledger(
            {},
            [first, second],
            [first_evidence, second_evidence],
            generated_at="2026-08-30T01:00:00+00:00",
        )

        self.assertEqual(formal, [])
        self.assertEqual(diagnostics["possibleConflicts"], 1)
        conflicted = next(iter(ledger["events"].values()))
        self.assertEqual(conflicted["status"], "needs_review")
        self.assertEqual(conflicted["conflictStatus"], "possible")

    def test_entity_compatibility_prevents_generic_title_alias_merge(self) -> None:
        title = "管理层变动公告"
        first = packaged_change(
            "chg-a",
            title=title,
            evidence_id="E001",
            dataset="person",
            entity_id="person-a",
            entity_name="甲公司高管",
        )
        second = packaged_change(
            "chg-b",
            title=title,
            evidence_id="E002",
            dataset="person",
            entity_id="person-b",
            entity_name="乙公司高管",
        )
        rows = [
            evidence(
                "E001",
                "chg-a",
                title=title,
                url="https://example.com/generic-announcement",
            ),
            evidence(
                "E002",
                "chg-b",
                title=title,
                url="https://example.com/generic-announcement",
            ),
        ]

        formal, ledger, diagnostics = agent.reconcile_event_ledger(
            {},
            [first, second],
            rows,
            generated_at="2026-08-30T01:00:00+00:00",
        )

        self.assertEqual(len(formal), 2)
        self.assertEqual(len(ledger["events"]), 2)
        self.assertEqual(diagnostics["newEvents"], 2)

    def test_homonyms_with_distinct_person_ids_do_not_merge(self) -> None:
        title = "王伟出任首席技术官"
        changes = [
            packaged_change(
                f"chg-{suffix}",
                title=title,
                evidence_id=f"E00{index}",
                dataset="person",
                entity_id=f"person-{suffix}",
                entity_name="王伟",
            )
            for index, suffix in enumerate(("a", "b"), 1)
        ]
        rows = [
            evidence(
                f"E00{index}",
                f"chg-{suffix}",
                title=title,
                url="https://example.com/leadership",
            )
            for index, suffix in enumerate(("a", "b"), 1)
        ]

        formal, ledger, diagnostics = agent.reconcile_event_ledger(
            {}, changes, rows, generated_at="2026-08-30T01:00:00+00:00"
        )

        self.assertEqual(len(formal), 2)
        self.assertEqual(len(ledger["events"]), 2)
        self.assertEqual(diagnostics["newEvents"], 2)
        self.assertEqual(diagnostics["updates"], 0)

    def test_corroborating_evidence_is_one_order_invariant_event(self) -> None:
        change = with_supporting_evidence(
            packaged_change(
                "chg-multi",
                title="示例公司发布新产品",
                evidence_id="E001",
                dataset="ventureCompany",
                entity_id="demo",
                entity_name="示例公司",
            ),
            ["E001", "E002"],
        )
        rows = [
            evidence(
                "E001",
                "chg-multi",
                title="示例公司发布新产品",
                source_name="公司官网",
                grade="官方披露",
                url="https://company.example/product",
            ),
            evidence(
                "E002",
                "chg-multi",
                title="新一代产品由示例公司正式推出",
                source_name="交易所",
                grade="监管文件",
                url="https://exchange.example/filing",
            ),
        ]

        formal, ledger, diagnostics = agent.reconcile_event_ledger(
            {}, [change], rows, generated_at="2026-08-30T01:00:00+00:00"
        )
        reversed_formal, reversed_ledger, _ = agent.reconcile_event_ledger(
            {},
            [with_supporting_evidence(change, ["E002", "E001"])],
            list(reversed(rows)),
            generated_at="2026-08-30T01:00:00+00:00",
        )

        self.assertEqual(len(formal), 1)
        self.assertEqual(formal[0]["supportingEvidenceIds"], ["E001", "E002"])
        self.assertEqual(formal[0]["lifecycle"], "first_seen")
        self.assertEqual(diagnostics["newEvents"], 1)
        self.assertEqual(len(ledger["events"]), 1)
        entry = next(iter(ledger["events"].values()))
        self.assertEqual(entry["observationCount"], 2)
        self.assertEqual(set(entry["evidenceFingerprints"]), set(
            next(iter(reversed_ledger["events"].values()))["evidenceFingerprints"]
        ))
        self.assertEqual(formal[0]["eventId"], reversed_formal[0]["eventId"])

        rerun_change = copy.deepcopy(change)
        rerun_change["id"] = "chg-multi-rerun"
        rerun_rows = []
        for index, row in enumerate(rows, 101):
            rerun = copy.deepcopy(row)
            rerun["id"] = f"E{index}"
            rerun["changeId"] = "chg-multi-rerun"
            rerun_rows.append(rerun)
        rerun_change = with_supporting_evidence(
            rerun_change, [str(row["id"]) for row in rerun_rows]
        )
        repeated, _, repeated_diagnostics = agent.reconcile_event_ledger(
            {"eventLedger": ledger},
            [rerun_change],
            rerun_rows,
            generated_at="2026-08-30T02:00:00+00:00",
        )
        self.assertEqual(repeated, [])
        self.assertEqual(repeated_diagnostics["duplicatesSuppressed"], 1)

    def test_legacy_evidence_ids_and_stable_event_id_are_preserved(self) -> None:
        change = packaged_change(
            "chg-legacy", title="旧报告事件", evidence_id="E001"
        )
        change.pop("supportingEvidenceIds")
        change["eventId"] = "evt-existing-stable-id"
        row = evidence(
            "E001",
            "chg-legacy",
            title="旧报告事件",
            url="https://example.com/legacy",
        )

        ledger = agent._legacy_event_ledger(legacy_report(change, row))

        self.assertIn("evt-existing-stable-id", ledger["events"])

    def test_legacy_market_news_preserves_multiple_stable_event_ids(self) -> None:
        change = packaged_change(
            "chg-legacy-news",
            title="市场新闻更新",
            evidence_id="E001",
            dataset="marketCompany",
            entity_id="catl",
            entity_name="宁德时代",
            field="news",
            after=[],
        )
        change["changedFields"] = ["news"]
        change = with_supporting_evidence(change, ["E001", "E002"])
        change["eventIds"] = ["evt-legacy-a", "evt-legacy-b"]
        rows = [
            evidence(
                "E001",
                "chg-legacy-news",
                title="宁德时代签署海外储能订单",
                url="https://example.com/order",
            ),
            evidence(
                "E002",
                "chg-legacy-news",
                title="宁德时代发布新一代电池平台",
                url="https://example.com/platform",
            ),
        ]
        report = {
            "generatedAt": "2026-08-29T01:00:00+00:00",
            "changes": [change],
            "evidence": rows,
        }

        ledger = agent._legacy_event_ledger(report)

        self.assertEqual(
            set(ledger["events"]), {"evt-legacy-a", "evt-legacy-b"}
        )

    def test_corrupt_or_expired_ledger_entries_fail_closed(self) -> None:
        corrupt = {
            "eventLedger": {
                "schemaVersion": agent.EVENT_LEDGER_SCHEMA_VERSION,
                "events": {
                    "evt-key": {
                        "eventId": "evt-other",
                        "lastSeenAt": "2026-08-29T00:00:00+00:00",
                    }
                },
            }
        }
        normalized = agent._load_event_ledger(
            corrupt, "2026-08-30T00:00:00+00:00"
        )
        self.assertEqual(normalized["events"], {})

        incomplete = {
            "eventLedger": {
                "schemaVersion": agent.EVENT_LEDGER_SCHEMA_VERSION,
                "events": {
                    "evt-incomplete": {
                        "eventId": "evt-incomplete",
                        "sourceAliases": ["src-attacker-controlled"],
                    }
                },
            }
        }
        self.assertEqual(
            agent._load_event_ledger(
                incomplete, "2026-08-30T00:00:00+00:00"
            )["events"],
            {},
        )

        old_change = packaged_change(
            "chg-old", title="过期事件", evidence_id="E001"
        )
        old_row = evidence(
            "E001",
            "chg-old",
            title="过期事件",
            url="https://example.com/expired",
            published_at="2025-01-01",
        )
        old_report = legacy_report(old_change, old_row)
        old_report["generatedAt"] = "2025-01-01T00:00:00+00:00"
        expired = agent._load_event_ledger(
            old_report, "2026-08-30T00:00:00+00:00"
        )
        self.assertEqual(expired["events"], {})

    def test_event_dataset_row_id_drift_keeps_stable_semantic_event(self) -> None:
        for dataset in ("institutionEvent", "listedDisclosure"):
            old_change = packaged_change(
                f"chg-old-{dataset}",
                title="示例公司发布重大公告",
                evidence_id="E001",
                dataset=dataset,
                entity_id="url-row-a",
                entity_name="示例公司",
            )
            old_row = evidence(
                "E001",
                f"chg-old-{dataset}",
                title="示例公司发布重大公告",
                url="https://example.com/announcement",
            )
            current_change = copy.deepcopy(old_change)
            current_change["id"] = f"chg-new-{dataset}"
            current_change["entityId"] = "url-row-b"
            current_change = with_supporting_evidence(current_change, ["E101"])
            current_row = copy.deepcopy(old_row)
            current_row["id"] = "E101"
            current_row["changeId"] = f"chg-new-{dataset}"

            formal, ledger, diagnostics = agent.reconcile_event_ledger(
                legacy_report(old_change, old_row),
                [current_change],
                [current_row],
                generated_at="2026-08-30T01:00:00+00:00",
            )

            self.assertEqual(formal, [], dataset)
            self.assertEqual(len(ledger["events"]), 1, dataset)
            self.assertEqual(diagnostics["duplicatesSuppressed"], 1, dataset)

    def test_conflict_does_not_mutate_claim_and_persists_next_run(self) -> None:
        accepted = packaged_change(
            "chg-accepted",
            title="示例人物任职状态",
            evidence_id="E001",
            dataset="person",
            entity_id="person-1",
            entity_name="示例人物",
            field="role",
            before="研究员",
            after="首席技术官",
        )
        accepted_evidence = evidence(
            "E001",
            "chg-accepted",
            title="示例人物任职状态",
            url="https://example.com/profile",
            grade="官方披露",
        )
        disputed = packaged_change(
            "chg-disputed",
            title="示例人物任职状态",
            evidence_id="E002",
            dataset="person",
            entity_id="person-1",
            entity_name="示例人物",
            field="role",
            before="首席技术官",
            after="顾问",
        )
        disputed_evidence = evidence(
            "E002",
            "chg-disputed",
            title="示例人物任职状态",
            url="https://example.com/profile",
            grade="媒体报道",
        )

        formal, ledger, diagnostics = agent.reconcile_event_ledger(
            legacy_report(accepted, accepted_evidence),
            [disputed],
            [disputed_evidence],
            generated_at="2026-08-30T01:00:00+00:00",
        )
        entry = next(iter(ledger["events"].values()))
        self.assertEqual(formal, [])
        self.assertEqual(diagnostics["possibleConflicts"], 1)
        self.assertEqual(
            next(iter(entry["scalarClaims"].values())), "首席技术官"
        )
        queued_event = diagnostics["reviewQueue"][0]["events"][0]
        self.assertEqual(queued_event["evidenceIds"], ["E002"])
        self.assertEqual(queued_event["evidence"][0]["id"], "E002")
        historical_urls = {
            item.get("url") for item in queued_event["historicalEvidence"]
        }
        self.assertIn("https://example.com/profile", historical_urls)

        repeated, repeated_ledger, repeated_diagnostics = agent.reconcile_event_ledger(
            {"eventLedger": ledger},
            [disputed],
            [disputed_evidence],
            generated_at="2026-08-30T02:00:00+00:00",
        )
        repeated_entry = next(iter(repeated_ledger["events"].values()))
        self.assertEqual(repeated, [])
        self.assertEqual(repeated_diagnostics["possibleConflicts"], 1)
        self.assertEqual(repeated_diagnostics["duplicatesSuppressed"], 0)
        self.assertEqual(
            next(iter(repeated_entry["scalarClaims"].values())), "首席技术官"
        )

    def test_related_ipo_conflicts_are_isolated_in_either_order(self) -> None:
        listed = packaged_change(
            "chg-listed",
            title="示例公司完成上市并挂牌交易",
            evidence_id="E001",
            dataset="ventureCompany",
            entity_id="demo",
            entity_name="示例公司",
        )
        withdrawn = packaged_change(
            "chg-withdrawn",
            title="示例公司撤回IPO申请",
            evidence_id="E002",
            dataset="ventureCompany",
            entity_id="demo",
            entity_name="示例公司",
        )
        rows = {
            "chg-listed": evidence(
                "E001",
                "chg-listed",
                title="示例公司完成上市并挂牌交易",
                url="https://example.com/listed",
            ),
            "chg-withdrawn": evidence(
                "E002",
                "chg-withdrawn",
                title="示例公司撤回IPO申请",
                url="https://example.com/withdrawn",
            ),
        }

        for candidates in ([listed, withdrawn], [withdrawn, listed]):
            formal, ledger, diagnostics = agent.reconcile_event_ledger(
                {},
                list(candidates),
                [rows[str(change["id"])] for change in candidates],
                generated_at="2026-08-30T01:00:00+00:00",
            )
            self.assertEqual(formal, [])
            self.assertEqual(diagnostics["possibleConflicts"], 2)
            self.assertTrue(
                all(
                    entry["status"] == "needs_review"
                    and entry["conflictStatus"] == "possible"
                    for entry in ledger["events"].values()
                )
            )

    def test_legacy_ipo_conflicts_are_isolated_in_either_order(self) -> None:
        listed = packaged_change(
            "chg-listed-legacy",
            title="示例公司完成上市并挂牌交易",
            evidence_id="E001",
            dataset="ventureCompany",
            entity_id="demo",
            entity_name="示例公司",
        )
        withdrawn = packaged_change(
            "chg-withdrawn-legacy",
            title="示例公司撤回IPO申请",
            evidence_id="E002",
            dataset="ventureCompany",
            entity_id="demo",
            entity_name="示例公司",
        )
        evidence_by_id = {
            "chg-listed-legacy": evidence(
                "E001",
                "chg-listed-legacy",
                title="示例公司完成上市并挂牌交易",
                url="https://example.com/listed-legacy",
            ),
            "chg-withdrawn-legacy": evidence(
                "E002",
                "chg-withdrawn-legacy",
                title="示例公司撤回IPO申请",
                url="https://example.com/withdrawn-legacy",
            ),
        }
        for changes in ([listed, withdrawn], [withdrawn, listed]):
            ledger = agent._legacy_event_ledger(
                {
                    "generatedAt": "2026-08-30T01:00:00+00:00",
                    "changes": list(changes),
                    "evidence": [
                        evidence_by_id[str(change["id"])] for change in changes
                    ],
                }
            )
            self.assertEqual(len(ledger["events"]), 2)
            self.assertTrue(
                all(
                    entry["conflictStatus"] == "possible"
                    and entry["status"] == "needs_review"
                    for entry in ledger["events"].values()
                )
            )

    def test_correction_does_not_supersede_unrelated_same_entity_event(self) -> None:
        financing = packaged_change(
            "chg-financing",
            title="示例公司完成A轮融资",
            evidence_id="E001",
            dataset="ventureCompany",
            entity_id="demo",
            entity_name="示例公司",
        )
        financing_evidence = evidence(
            "E001",
            "chg-financing",
            title="示例公司完成A轮融资",
            url="https://example.com/financing",
            grade="官方披露",
        )
        correction = packaged_change(
            "chg-correction",
            title="更正：示例公司首席技术官任命",
            evidence_id="E002",
            dataset="ventureCompany",
            entity_id="demo",
            entity_name="示例公司",
        )
        correction_evidence = evidence(
            "E002",
            "chg-correction",
            title="更正：示例公司首席技术官任命",
            url="https://example.com/cto-correction",
            grade="官方披露",
        )

        formal, ledger, _ = agent.reconcile_event_ledger(
            legacy_report(financing, financing_evidence),
            [correction],
            [correction_evidence],
            generated_at="2026-08-30T01:00:00+00:00",
        )

        self.assertEqual(len(formal), 1)
        self.assertEqual(formal[0]["lifecycle"], "first_seen")
        self.assertEqual(len(ledger["events"]), 2)
        self.assertFalse(
            any(entry.get("supersedesEventId") for entry in ledger["events"].values())
        )

    def test_official_correction_can_target_semantic_event_after_45_days(self) -> None:
        original = packaged_change(
            "chg-original-date",
            title="示例公司产品发布日期为九月",
            evidence_id="E001",
            dataset="ventureCompany",
            entity_id="demo",
            entity_name="示例公司",
        )
        original_evidence = evidence(
            "E001",
            "chg-original-date",
            title="示例公司产品发布日期为九月",
            url="https://example.com/original-date",
            grade="官方披露",
            published_at="2026-06-01",
        )
        correction = packaged_change(
            "chg-corrected-date",
            title="更正：示例公司产品发布日期为十月",
            evidence_id="E002",
            dataset="ventureCompany",
            entity_id="demo",
            entity_name="示例公司",
        )
        correction_evidence = evidence(
            "E002",
            "chg-corrected-date",
            title="更正：示例公司产品发布日期为十月",
            url="https://example.com/corrected-date",
            grade="官方披露",
            published_at="2026-07-16",
        )

        formal, ledger, diagnostics = agent.reconcile_event_ledger(
            legacy_report(original, original_evidence),
            [correction],
            [correction_evidence],
            generated_at="2026-07-16T01:00:00+00:00",
        )

        self.assertEqual(len(formal), 1)
        self.assertEqual(formal[0]["lifecycle"], "correction")
        self.assertEqual(diagnostics["corrections"], 1)
        corrected_entry = ledger["events"][formal[0]["eventId"]]
        self.assertTrue(corrected_entry.get("supersedesEventId"))

    def test_low_grade_correction_cannot_borrow_other_source_strength(self) -> None:
        change = with_supporting_evidence(
            packaged_change(
                "chg-mixed-correction",
                title="示例公司更正产品发布日期",
                evidence_id="E001",
                dataset="ventureCompany",
                entity_id="demo",
                entity_name="示例公司",
            ),
            ["E001", "E002"],
        )
        rows = [
            evidence(
                "E001",
                "chg-mixed-correction",
                title="更正：示例公司发布日期",
                url="https://media.example.com/correction",
                grade="媒体报道",
            ),
            evidence(
                "E002",
                "chg-mixed-correction",
                title="示例公司产品页面",
                url="https://company.example.com/product",
                grade="监管文件",
            ),
        ]

        formal, _, diagnostics = agent.reconcile_event_ledger(
            {}, [change], rows, generated_at="2026-08-30T01:00:00+00:00"
        )

        self.assertEqual(formal, [])
        self.assertEqual(diagnostics["possibleConflicts"], 1)

    def test_market_news_keeps_distinct_headlines_and_suppresses_old_items(self) -> None:
        first = packaged_change(
            "chg-news-1",
            title="市场新闻更新",
            evidence_id="E001",
            dataset="marketCompany",
            entity_id="catl",
            entity_name="宁德时代",
            field="news",
            after=[
                {"title": "宁德时代签署海外储能订单"},
                {"title": "宁德时代发布新一代电池平台"},
            ],
        )
        first["changedFields"] = ["news"]
        first = with_supporting_evidence(first, ["E001", "E002"])
        first_rows = [
            evidence(
                "E001",
                "chg-news-1",
                title="宁德时代签署海外储能订单",
                url="https://example.com/storage-order",
            ),
            evidence(
                "E002",
                "chg-news-1",
                title="宁德时代发布新一代电池平台",
                url="https://example.com/battery-platform",
            ),
        ]
        for row in first_rows:
            row["claimFields"] = ["news"]
        formal, ledger, diagnostics = agent.reconcile_event_ledger(
            {}, [first], first_rows, generated_at="2026-08-30T01:00:00+00:00"
        )
        self.assertEqual(len(formal), 1)
        self.assertEqual(len(formal[0]["eventIds"]), 2)
        self.assertEqual(diagnostics["newEvents"], 2)

        second = copy.deepcopy(first)
        second["id"] = "chg-news-2"
        second["after"]["news"].append(
            {"title": "宁德时代获批建设回收基地"}
        )
        second["claimBindings"][0]["after"] = copy.deepcopy(
            second["after"]["news"]
        )
        second = with_supporting_evidence(second, ["E101", "E102", "E103"])
        second_rows = []
        for evidence_id, title, url in (
            ("E101", "宁德时代签署海外储能订单", "https://example.com/storage-order"),
            ("E102", "宁德时代发布新一代电池平台", "https://example.com/battery-platform"),
            ("E103", "宁德时代获批建设回收基地", "https://example.com/recycling"),
        ):
            second_rows.append(
                evidence(
                    evidence_id,
                    "chg-news-2",
                    title=title,
                    url=url,
                )
            )
        next_formal, _, next_diagnostics = agent.reconcile_event_ledger(
            {"eventLedger": ledger},
            [second],
            second_rows,
            generated_at="2026-08-30T02:00:00+00:00",
        )
        self.assertEqual(len(next_formal), 1)
        self.assertEqual(len(next_formal[0]["eventIds"]), 1)
        self.assertEqual(next_formal[0]["supportingEvidenceIds"], ["E103"])
        self.assertEqual(
            next_formal[0]["after"]["news"],
            [{"title": "宁德时代获批建设回收基地"}],
        )
        self.assertEqual(next_diagnostics["newEvents"], 1)
        self.assertEqual(next_diagnostics["duplicatesSuppressed"], 2)

    def test_market_news_shared_url_does_not_merge_distinct_headlines(self) -> None:
        change = packaged_change(
            "chg-news-alias",
            title="市场新闻更新",
            evidence_id="E001",
            dataset="marketCompany",
            entity_id="catl",
            entity_name="宁德时代",
            field="news",
            after=[],
        )
        change["changedFields"] = ["news"]
        change = with_supporting_evidence(change, ["E001", "E002", "E003"])
        rows = [
            evidence(
                "E001",
                "chg-news-alias",
                title="宁德时代发布新一代电池平台",
                url="https://example.com/company-news",
            ),
            evidence(
                "E002",
                "chg-news-alias",
                title="宁德时代签署海外储能订单",
                url="https://example.com/company-news",
            ),
            evidence(
                "E003",
                "chg-news-alias",
                title="宁德时代发布全新一代电池平台",
                url="https://media.example.com/battery-platform",
            ),
        ]

        formal, ledger, diagnostics = agent.reconcile_event_ledger(
            {}, [change], rows, generated_at="2026-08-30T01:00:00+00:00"
        )

        self.assertEqual(len(formal), 1)
        self.assertEqual(len(formal[0]["eventIds"]), 2)
        self.assertEqual(set(formal[0]["supportingEvidenceIds"]), {"E001", "E002", "E003"})
        self.assertEqual(len(ledger["events"]), 2)
        self.assertEqual(diagnostics["newEvents"], 2)

    def test_partial_market_news_conflict_keeps_benign_event_pending(self) -> None:
        change = packaged_change(
            "chg-partial-conflict",
            title="市场新闻更新",
            evidence_id="E001",
            dataset="marketCompany",
            entity_id="catl",
            entity_name="宁德时代",
            field="news",
            after=[],
        )
        change["changedFields"] = ["news"]
        change = with_supporting_evidence(change, ["E001", "E002"])
        rows = [
            evidence(
                "E001",
                "chg-partial-conflict",
                title="宁德时代发布新一代电池平台",
                url="https://example.com/benign",
            ),
            evidence(
                "E002",
                "chg-partial-conflict",
                title="撤回：宁德时代未经证实的项目消息",
                url="https://example.com/disputed",
                grade="媒体报道",
            ),
        ]
        for row in rows:
            row["claimFields"] = ["news"]
        formal, ledger, diagnostics = agent.reconcile_event_ledger(
            {}, [change], rows, generated_at="2026-08-30T01:00:00+00:00"
        )
        self.assertEqual(formal, [])
        self.assertEqual(diagnostics["newEvents"], 0)
        self.assertEqual(diagnostics["possibleConflicts"], 1)
        benign_entry = next(
            entry
            for entry in ledger["events"].values()
            if entry["title"] == "宁德时代发布新一代电池平台"
        )
        self.assertEqual(benign_entry["pendingLifecycle"], "first_seen")
        self.assertEqual(len(ledger["pendingPublications"]), 1)

        replay_evidence: list[dict[str, object]] = []
        next_formal, next_ledger, next_diagnostics = agent.reconcile_event_ledger(
            {"eventLedger": ledger},
            [],
            replay_evidence,
            generated_at="2026-08-30T02:00:00+00:00",
        )
        self.assertEqual(len(next_formal), 1)
        self.assertEqual(next_formal[0]["lifecycle"], "first_seen")
        self.assertTrue(next_formal[0]["replayedFromPending"])
        self.assertEqual(next_diagnostics["newEvents"], 1)
        self.assertEqual(len(replay_evidence), 1)
        self.assertEqual(next_ledger["pendingPublications"], [])

    def test_market_pending_atoms_survive_a_sibling_conflict(self) -> None:
        news = [
            {"title": "宁德时代发布新品"},
            {"title": "宁德时代正式上市并挂牌交易"},
        ]
        change = packaged_change(
            "chg-market-pending",
            title="市场新闻更新",
            evidence_id="E001",
            dataset="marketCompany",
            entity_id="catl",
            entity_name="宁德时代",
            field="news",
            after=news,
        )
        change["changedFields"] = ["news"]
        change = with_supporting_evidence(change, ["E001", "E002"])
        rows = [
            evidence(
                "E001",
                "chg-market-pending",
                title="宁德时代发布新品",
                url="https://example.com/product",
            ),
            evidence(
                "E002",
                "chg-market-pending",
                title="宁德时代正式上市并挂牌交易",
                url="https://example.com/listing",
            ),
        ]
        for row in rows:
            row["claimFields"] = ["news"]

        _, first_ledger, _ = agent.reconcile_event_ledger(
            {},
            [change],
            rows,
            generated_at="2026-08-29T01:00:00+00:00",
            publish_limit=0,
        )

        self.assertEqual(len(first_ledger["pendingPublications"]), 2)
        for item in first_ledger["pendingPublications"]:
            pending_change = item["change"]
            self.assertEqual(len(pending_change["eventIds"]), 1)
            self.assertEqual(len(pending_change["evidenceIds"]), 1)
            self.assertEqual(len(item["evidence"]), 1)
            self.assertEqual(len(pending_change["after"]["news"]), 1)
            self.assertEqual(
                pending_change["after"]["news"],
                pending_change["claimBindings"][0]["after"],
            )

        conflict = packaged_change(
            "chg-withdrawn",
            title="市场新闻更新",
            evidence_id="E003",
            dataset="marketCompany",
            entity_id="catl",
            entity_name="宁德时代",
            field="news",
            after=[{"title": "宁德时代撤回IPO上市申请"}],
        )
        conflict["changedFields"] = ["news"]
        conflict_row = evidence(
            "E003",
            "chg-withdrawn",
            title="宁德时代撤回IPO上市申请",
            url="https://example.com/withdrawn",
        )
        conflict_row["claimFields"] = ["news"]
        second_evidence = [conflict_row]
        second_formal, second_ledger, second_diagnostics = (
            agent.reconcile_event_ledger(
                {"eventLedger": first_ledger},
                [conflict],
                second_evidence,
                generated_at="2026-08-30T01:00:00+00:00",
                publish_limit=0,
            )
        )

        self.assertEqual(second_formal, [])
        self.assertEqual(second_diagnostics["possibleConflicts"], 2)
        self.assertEqual(len(second_ledger["pendingPublications"]), 1)
        survivor = second_ledger["pendingPublications"][0]
        self.assertEqual(survivor["queuedAt"], "2026-08-29T01:00:00+00:00")
        self.assertEqual(survivor["evidence"][0]["title"], "宁德时代发布新品")

        replay_evidence: list[dict[str, object]] = []
        third_formal, third_ledger, _ = agent.reconcile_event_ledger(
            {"eventLedger": second_ledger},
            [],
            replay_evidence,
            generated_at="2026-08-31T01:00:00+00:00",
        )
        self.assertEqual(len(third_formal), 1)
        self.assertTrue(third_formal[0]["replayedFromPending"])
        self.assertEqual(third_formal[0]["after"]["news"], [news[0]])
        self.assertEqual(replay_evidence[0]["title"], "宁德时代发布新品")
        self.assertEqual(third_ledger["pendingPublications"], [])

    def test_market_public_payload_projects_out_unbound_fields(self) -> None:
        news = [
            {"title": "宁德时代发布新电池"},
            {"title": "宁德时代签署储能订单"},
        ]
        change = packaged_change(
            "chg-market-projection",
            title="市场新闻更新",
            evidence_id="E001",
            dataset="marketCompany",
            entity_id="catl",
            entity_name="宁德时代",
            field="news",
            after=news,
        )
        change["changedFields"] = ["news", "valuation"]
        change["after"]["valuation"] = "100亿元"
        change["unsupportedClaimFields"] = ["valuation"]
        change = with_supporting_evidence(change, ["E001", "E002"])
        rows = [
            evidence(
                "E001",
                "chg-market-projection",
                title="宁德时代发布新电池",
                url="https://example.com/battery",
            ),
            evidence(
                "E002",
                "chg-market-projection",
                title="宁德时代签署储能订单",
                url="https://example.com/storage",
            ),
        ]
        for row in rows:
            row["claimFields"] = ["news"]

        formal, ledger, _ = agent.reconcile_event_ledger(
            {},
            [copy.deepcopy(change)],
            copy.deepcopy(rows),
            generated_at="2026-08-30T01:00:00+00:00",
        )
        self.assertEqual(len(formal), 1)
        self.assertEqual(formal[0]["changedFields"], ["news"])
        self.assertEqual(set(formal[0]["after"]), {"news"})
        self.assertNotIn("unsupportedClaimFields", formal[0])
        immediate_report = {
            "schemaVersion": 1,
            "generatedAt": "2026-08-30T01:00:00+00:00",
            "analysis": {
                "keyDevelopments": [],
                "thesisUpdates": [],
                "watchlist": [],
                "risks": [],
            },
            "changes": formal,
            "evidence": rows,
            "eventLedger": ledger,
        }
        self.assertEqual(agent.validate_report(immediate_report), [])

        _, pending_ledger, _ = agent.reconcile_event_ledger(
            {},
            [copy.deepcopy(change)],
            copy.deepcopy(rows),
            generated_at="2026-08-30T01:00:00+00:00",
            publish_limit=0,
        )
        self.assertEqual(len(pending_ledger["pendingPublications"]), 2)
        self.assertTrue(
            all(
                item["change"]["changedFields"] == ["news"]
                and set(item["change"]["after"]) == {"news"}
                for item in pending_ledger["pendingPublications"]
            )
        )
        replay_evidence: list[dict[str, object]] = []
        replay, _, _ = agent.reconcile_event_ledger(
            {"eventLedger": pending_ledger},
            [],
            replay_evidence,
            generated_at="2026-08-30T02:00:00+00:00",
        )
        self.assertEqual(len(replay), 2)
        self.assertTrue(
            all(
                item["changedFields"] == ["news"]
                and set(item["after"]) == {"news"}
                for item in replay
            )
        )

        corrupted_report = copy.deepcopy(immediate_report)
        corrupted_report["changes"][0]["changedFields"].append("valuation")
        corrupted_report["changes"][0]["after"]["valuation"] = "100亿元"
        errors = agent.validate_report(corrupted_report)
        self.assertTrue(
            any("invalid claim projection" in error for error in errors), errors
        )

    def test_listed_disclosure_sources_remain_one_pending_event(self) -> None:
        change = with_supporting_evidence(
            packaged_change(
                "chg-disclosure",
                title="公司发布年度报告",
                evidence_id="E001",
                dataset="listedDisclosure",
                entity_id="demo",
                entity_name="示例公司",
            ),
            ["E001", "E002"],
        )
        rows = [
            evidence(
                "E001",
                "chg-disclosure",
                title="公司发布年度报告",
                url="https://exchange.example/annual-report",
                grade="监管文件",
            ),
            evidence(
                "E002",
                "chg-disclosure",
                title="示例公司年度报告全文",
                url="https://company.example/annual-report",
                grade="官方披露",
            ),
        ]

        formal, ledger, _ = agent.reconcile_event_ledger(
            {},
            [change],
            rows,
            generated_at="2026-08-30T01:00:00+00:00",
            publish_limit=0,
        )

        self.assertEqual(formal, [])
        self.assertEqual(len(ledger["events"]), 1)
        self.assertEqual(len(ledger["pendingPublications"]), 1)
        self.assertEqual(
            set(ledger["pendingPublications"][0]["change"]["evidenceIds"]),
            {"E001", "E002"},
        )

    def test_current_correction_replaces_same_event_pending_replay(self) -> None:
        old_change = packaged_change(
            "chg-old", title="示例公司产品发布日期为九月", evidence_id="E001"
        )
        old_row = evidence(
            "E001",
            "chg-old",
            title="示例公司产品发布日期为九月",
            url="https://company.example/product",
            grade="原始材料",
        )
        _, first_ledger, _ = agent.reconcile_event_ledger(
            {},
            [old_change],
            [old_row],
            generated_at="2026-08-29T01:00:00+00:00",
            publish_limit=0,
        )
        update = packaged_change(
            "chg-update",
            title="示例公司产品发布日期改为十一月",
            evidence_id="E002",
        )
        update_row = evidence(
            "E002",
            "chg-update",
            title="示例公司产品发布日期改为十一月",
            url="https://company.example/product",
            grade="原始材料",
        )
        correction = packaged_change(
            "chg-correction",
            title="更正：示例公司产品发布日期改为十月",
            evidence_id="E003",
        )
        correction_row = evidence(
            "E003",
            "chg-correction",
            title="更正：示例公司产品发布日期改为十月",
            url="https://company.example/product",
            grade="原始材料",
        )
        expected_fingerprint = agent._event_observations(
            correction, [correction_row]
        )[0]["claimFingerprint"]

        for label, changes, rows in (
            (
                "update-then-correction",
                [update, correction],
                [update_row, correction_row],
            ),
            (
                "correction-then-update",
                [correction, update],
                [correction_row, update_row],
            ),
        ):
            with self.subTest(order=label):
                formal, ledger, diagnostics = agent.reconcile_event_ledger(
                    {"eventLedger": first_ledger},
                    copy.deepcopy(changes),
                    copy.deepcopy(rows),
                    generated_at="2026-08-30T01:00:00+00:00",
                )

                self.assertEqual(
                    [change["id"] for change in formal], ["chg-correction"]
                )
                self.assertEqual(formal[0]["lifecycle"], "correction")
                self.assertNotIn("replayedFromPending", formal[0])
                self.assertEqual(diagnostics["corrections"], 1)
                self.assertEqual(ledger["pendingPublications"], [])
                entry = ledger["events"][formal[0]["eventId"]]
                self.assertEqual(
                    entry["title"], "更正：示例公司产品发布日期改为十月"
                )
                self.assertEqual(entry["lastLifecycle"], "correction")
                self.assertEqual(entry["claimFingerprint"], expected_fingerprint)

    def test_correction_superseding_pending_event_filters_old_replay(self) -> None:
        old_change = packaged_change(
            "chg-old",
            title="示例公司产品发布日期为九月",
            evidence_id="E001",
            dataset="ventureCompany",
            entity_id="demo",
            entity_name="示例公司",
        )
        old_row = evidence(
            "E001",
            "chg-old",
            title="示例公司产品发布日期为九月",
            url="https://company.example/old-notice",
            grade="原始材料",
            published_at="2026-01-01",
        )
        _, first_ledger, _ = agent.reconcile_event_ledger(
            {},
            [old_change],
            [old_row],
            generated_at="2026-01-01T01:00:00+00:00",
            publish_limit=0,
        )
        old_event_id = next(iter(first_ledger["events"]))
        correction = packaged_change(
            "chg-correction",
            title="更正：示例公司产品发布日期为十月",
            evidence_id="E002",
            dataset="ventureCompany",
            entity_id="demo",
            entity_name="示例公司",
        )
        correction_row = evidence(
            "E002",
            "chg-correction",
            title="更正：示例公司产品发布日期为十月",
            url="https://company.example/new-notice",
            grade="原始材料",
            published_at="2026-03-01",
        )

        formal, ledger, _ = agent.reconcile_event_ledger(
            {"eventLedger": first_ledger},
            [correction],
            [correction_row],
            generated_at="2026-03-01T01:00:00+00:00",
        )

        self.assertEqual(len(formal), 1)
        self.assertEqual(formal[0]["id"], "chg-correction")
        self.assertEqual(formal[0]["lifecycle"], "correction")
        self.assertNotEqual(formal[0]["eventId"], old_event_id)
        self.assertEqual(ledger["events"][old_event_id]["status"], "superseded")
        self.assertEqual(ledger["pendingPublications"], [])

    def test_publish_limit_keeps_tail_event_pending_for_next_run(self) -> None:
        changes = [
            packaged_change(
                f"chg-{suffix}", title=title, evidence_id=f"E00{index}"
            )
            for index, (suffix, title) in enumerate(
                (("first", "第一条新事件"), ("second", "第二条新事件")), 1
            )
        ]
        rows = [
            evidence(
                f"E00{index}",
                f"chg-{suffix}",
                title=title,
                url=f"https://example.com/{suffix}",
            )
            for index, (suffix, title) in enumerate(
                (("first", "第一条新事件"), ("second", "第二条新事件")), 1
            )
        ]
        first_formal, first_ledger, first_diagnostics = agent.reconcile_event_ledger(
            {},
            changes,
            rows,
            generated_at="2026-08-30T01:00:00+00:00",
            publish_limit=1,
        )
        pending_entries = [
            entry
            for entry in first_ledger["events"].values()
            if entry.get("pendingLifecycle")
        ]
        self.assertEqual([change["id"] for change in first_formal], ["chg-first"])
        self.assertEqual(first_diagnostics["newEvents"], 1)
        self.assertEqual(len(pending_entries), 1)
        self.assertEqual(pending_entries[0]["lastPublishedAt"], "")

        self.assertEqual(len(first_ledger["pendingPublications"]), 1)
        replay_evidence: list[dict[str, object]] = []
        second_formal, second_ledger, diagnostics = agent.reconcile_event_ledger(
            {"eventLedger": first_ledger},
            [],
            replay_evidence,
            generated_at="2026-08-30T02:00:00+00:00",
            publish_limit=1,
        )
        self.assertEqual(len(second_formal), 1)
        self.assertTrue(second_formal[0]["id"].startswith("pending-"))
        self.assertEqual(second_formal[0]["sourceChangeId"], "chg-second")
        self.assertTrue(second_formal[0]["replayedFromPending"])
        self.assertEqual(diagnostics["duplicatesSuppressed"], 0)
        self.assertEqual(diagnostics["newEvents"], 1)
        self.assertEqual(len(replay_evidence), 1)
        published_second = next(
            entry
            for entry in second_ledger["events"].values()
            if entry["title"] == "第二条新事件"
        )
        self.assertNotIn("pendingLifecycle", published_second)
        self.assertEqual(
            published_second["lastPublishedAt"], "2026-08-30T02:00:00+00:00"
        )
        self.assertEqual(second_ledger["pendingPublications"], [])
        replay_report = {
            "schemaVersion": 1,
            "generatedAt": "2026-08-30T02:00:00+00:00",
            "analysis": {
                "keyDevelopments": [],
                "thesisUpdates": [],
                "watchlist": [],
                "risks": [],
            },
            "changes": second_formal,
            "evidence": replay_evidence,
            "eventLedger": second_ledger,
        }
        self.assertEqual(agent.validate_report(replay_report), [])

    def test_pending_publication_queue_is_bounded_and_expires(self) -> None:
        events: dict[str, dict[str, object]] = {}
        pending = []
        for index in range(agent.MAX_PENDING_PUBLICATIONS + 3):
            event_id = f"evt-{index}"
            change_id = f"chg-{index}"
            evidence_id = f"E{index:03d}"
            change = packaged_change(
                change_id, title=f"待发布事件 {index}", evidence_id=evidence_id
            )
            change["eventIds"] = [event_id]
            change["eventId"] = event_id
            change["eventLifecycles"] = {event_id: "first_seen"}
            change["lifecycle"] = "first_seen"
            row = evidence(
                evidence_id,
                change_id,
                title=f"待发布事件 {index}",
                url=f"https://example.com/pending/{index}",
            )
            observation = agent._event_observations(change, [row])[0]
            events[event_id] = agent._new_ledger_entry(
                event_id, observation, "2026-08-29T01:00:00+00:00"
            )
            pending.append(
                {
                    "queuedAt": "2026-08-29T01:00:00+00:00",
                    "change": change,
                    "evidence": [row],
                }
            )
        expired = copy.deepcopy(pending[0])
        expired["change"]["eventIds"] = ["evt-expired"]
        expired["change"]["eventId"] = "evt-expired"
        expired["change"]["eventLifecycles"] = {
            "evt-expired": "first_seen"
        }
        expired["queuedAt"] = "2025-01-01T01:00:00+00:00"
        expired_observation = agent._event_observations(
            expired["change"], expired["evidence"]
        )[0]
        events["evt-expired"] = agent._new_ledger_entry(
            "evt-expired", expired_observation, "2025-01-01T01:00:00+00:00"
        )
        pending.append(expired)

        normalized = agent._normalize_pending_publications(
            pending, events, "2026-08-30T01:00:00+00:00"
        )

        self.assertEqual(len(normalized), agent.MAX_PENDING_PUBLICATIONS)
        self.assertTrue(
            all(item["queuedAt"] != "2025-01-01T01:00:00+00:00" for item in normalized)
        )

    def test_pending_identity_and_semantics_corruption_fail_closed(self) -> None:
        change = packaged_change(
            "chg-pending", title="待发布事件", evidence_id="E001"
        )
        row = evidence(
            "E001",
            "chg-pending",
            title="待发布事件",
            url="https://example.com/pending",
        )
        _, ledger, _ = agent.reconcile_event_ledger(
            {},
            [change],
            [row],
            generated_at="2026-08-30T01:00:00+00:00",
            publish_limit=0,
        )
        pending = ledger["pendingPublications"][0]
        event_id = pending["change"]["eventId"]

        ghost = copy.deepcopy(pending)
        ghost["change"]["eventId"] = "evt-ghost"
        ghost["change"]["eventLifecycles"]["evt-ghost"] = "first_seen"
        self.assertEqual(
            agent._normalize_pending_publications(
                [ghost], ledger["events"], "2026-08-30T02:00:00+00:00"
            ),
            [],
        )

        rejected = copy.deepcopy(pending)
        rejected["change"]["eligibleForKeyDevelopment"] = False
        rejected["change"]["changeType"] = "source_refresh"
        rejected["change"]["publicationTier"] = "rejected"
        self.assertEqual(
            agent._normalize_pending_publications(
                [rejected], ledger["events"], "2026-08-30T02:00:00+00:00"
            ),
            [],
        )

        raw_orphan = copy.deepcopy(pending)
        raw_orphan_row = copy.deepcopy(raw_orphan["evidence"][0])
        raw_orphan_row["id"] = "E999"
        raw_orphan["evidence"].append(raw_orphan_row)
        self.assertEqual(
            agent._normalize_pending_publications(
                [raw_orphan], ledger["events"], "2026-08-30T02:00:00+00:00"
            ),
            [],
        )

        orphan = copy.deepcopy(pending)
        orphan_row = copy.deepcopy(orphan["evidence"][0])
        orphan_row["id"] = "E002"
        orphan["evidence"].append(orphan_row)
        orphan["change"]["evidenceIds"].append("E002")
        orphan["change"]["supportingEvidenceIds"].append("E002")
        orphan["change"]["evidenceQuality"] = {
            "status": "passed",
            "supporting": 2,
            "total": 2,
        }
        self.assertEqual(
            agent._normalize_pending_publications(
                [orphan], ledger["events"], "2026-08-30T02:00:00+00:00"
            ),
            [],
        )

        duplicate_binding = copy.deepcopy(pending)
        duplicate_binding["change"]["claimBindings"][0]["evidenceIds"].append(
            "E001"
        )
        duplicate_supporting = copy.deepcopy(pending)
        duplicate_supporting["change"]["supportingEvidenceIds"].append("E001")
        for corrupted in (duplicate_binding, duplicate_supporting):
            self.assertEqual(
                agent._normalize_pending_publications(
                    [corrupted], ledger["events"], "2026-08-30T02:00:00+00:00"
                ),
                [],
            )
            corrupt_ledger = copy.deepcopy(ledger)
            corrupt_ledger["pendingPublications"] = [corrupted]
            replay_evidence: list[dict[str, object]] = []
            replay, normalized_ledger, _ = agent.reconcile_event_ledger(
                {"eventLedger": corrupt_ledger},
                [],
                replay_evidence,
                generated_at="2026-08-30T02:00:00+00:00",
            )
            self.assertEqual(replay, [])
            self.assertEqual(replay_evidence, [])
            self.assertEqual(normalized_ledger["pendingPublications"], [])

        report = {
            "schemaVersion": 1,
            "generatedAt": "2026-08-30T02:00:00+00:00",
            "analysis": {
                "keyDevelopments": [],
                "thesisUpdates": [],
                "watchlist": [],
                "risks": [],
            },
            "changes": [ghost["change"]],
            "evidence": ghost["evidence"],
            "eventLedger": ledger,
        }
        errors = agent.validate_report(report)
        self.assertTrue(
            any("eventLifecycles keys do not match eventIds" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("eventId does not match eventIds" in error for error in errors),
            errors,
        )
        self.assertEqual(event_id, pending["change"]["eventIds"][0])

    def test_real_event_id_cross_binding_fails_semantic_validation(self) -> None:
        changes = [
            packaged_change(
                "chg-a", title="甲公司发布新产品", evidence_id="E001"
            ),
            packaged_change(
                "chg-b", title="乙公司完成融资", evidence_id="E002"
            ),
        ]
        rows = [
            evidence(
                "E001",
                "chg-a",
                title="甲公司发布新产品",
                url="https://example.com/company-a",
            ),
            evidence(
                "E002",
                "chg-b",
                title="乙公司完成融资",
                url="https://example.com/company-b",
            ),
        ]
        _, pending_ledger, _ = agent.reconcile_event_ledger(
            {},
            changes,
            rows,
            generated_at="2026-08-30T01:00:00+00:00",
            publish_limit=0,
        )
        pending_a = next(
            item
            for item in pending_ledger["pendingPublications"]
            if item["change"]["id"] == "chg-a"
        )
        pending_b = next(
            item
            for item in pending_ledger["pendingPublications"]
            if item["change"]["id"] == "chg-b"
        )
        event_b = pending_b["change"]["eventId"]
        cross_bound = copy.deepcopy(pending_a)
        cross_bound["change"]["eventIds"] = [event_b]
        cross_bound["change"]["eventId"] = event_b
        cross_bound["change"]["eventLifecycles"] = {event_b: "first_seen"}

        self.assertEqual(
            agent._normalize_pending_publications(
                [cross_bound],
                pending_ledger["events"],
                "2026-08-30T02:00:00+00:00",
            ),
            [],
        )
        corrupted_ledger = copy.deepcopy(pending_ledger)
        corrupted_ledger["pendingPublications"] = [cross_bound]
        replay_evidence: list[dict[str, object]] = []
        replay, next_ledger, _ = agent.reconcile_event_ledger(
            {"eventLedger": corrupted_ledger},
            [],
            replay_evidence,
            generated_at="2026-08-30T02:00:00+00:00",
        )
        self.assertEqual(replay, [])
        self.assertEqual(replay_evidence, [])
        self.assertEqual(next_ledger["pendingPublications"], [])

        formal, formal_ledger, _ = agent.reconcile_event_ledger(
            {},
            copy.deepcopy(changes),
            copy.deepcopy(rows),
            generated_at="2026-08-30T01:00:00+00:00",
        )
        formal_a = next(change for change in formal if change["id"] == "chg-a")
        formal_b = next(change for change in formal if change["id"] == "chg-b")
        formal_a["eventIds"] = [formal_b["eventId"]]
        formal_a["eventId"] = formal_b["eventId"]
        formal_a["eventLifecycles"] = {formal_b["eventId"]: "first_seen"}
        report = {
            "schemaVersion": 1,
            "generatedAt": "2026-08-30T01:00:00+00:00",
            "analysis": {
                "keyDevelopments": [],
                "thesisUpdates": [],
                "watchlist": [],
                "risks": [],
            },
            "changes": formal,
            "evidence": rows,
            "eventLedger": formal_ledger,
        }
        errors = agent.validate_report(report)
        self.assertTrue(
            any("event semantic mismatch" in error for error in errors), errors
        )

        pending_report = {
            "schemaVersion": 1,
            "generatedAt": "2026-08-30T02:00:00+00:00",
            "analysis": {
                "keyDevelopments": [],
                "thesisUpdates": [],
                "watchlist": [],
                "risks": [],
            },
            "changes": [],
            "evidence": [],
            "eventLedger": corrupted_ledger,
        }
        pending_errors = agent.validate_report(pending_report)
        self.assertTrue(
            any("pendingPublications contains invalid" in error for error in pending_errors),
            pending_errors,
        )

    def test_validator_rejects_formal_change_for_superseded_event(self) -> None:
        change = packaged_change(
            "chg-formal", title="已过时事件", evidence_id="E001"
        )
        row = evidence(
            "E001",
            "chg-formal",
            title="已过时事件",
            url="https://example.com/stale",
        )
        formal, ledger, _ = agent.reconcile_event_ledger(
            {},
            [change],
            [row],
            generated_at="2026-08-30T01:00:00+00:00",
        )
        ledger["events"][formal[0]["eventId"]]["status"] = "superseded"
        report = {
            "schemaVersion": 1,
            "generatedAt": "2026-08-30T01:00:00+00:00",
            "analysis": {
                "keyDevelopments": [],
                "thesisUpdates": [],
                "watchlist": [],
                "risks": [],
            },
            "changes": formal,
            "evidence": [row],
            "eventLedger": ledger,
        }

        errors = agent.validate_report(report)

        self.assertTrue(
            any("publishes superseded event" in error for error in errors), errors
        )

    def test_history_normalizes_date_and_keeps_legacy_nonempty_separate(self) -> None:
        previous = {
            "history": [
                {
                    "generatedAt": "2026-08-30T01:00:00+00:00",
                    "changeCount": 7,
                    "executiveSummary": "旧口径。",
                }
            ]
        }
        current = {
            "asOfDate": "2026-08-30",
            "generatedAt": "2026-08-30T02:00:00+00:00",
            "runStatus": "offline-fallback",
            "changeSummary": {
                "total": 1,
                "verifiedChangeTotal": 1,
                "newEvents": 1,
            },
            "analysis": {"executiveSummary": "新口径。"},
            "changes": [
                {
                    "eventId": "evt-current",
                    "lifecycle": "first_seen",
                }
            ],
        }

        history = agent._merge_history(previous, current)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["date"], "2026-08-30")
        self.assertEqual(history[0]["metricsVersion"], 2)
        self.assertEqual(history[0]["changeCount"], 1)
        self.assertEqual(history[0]["legacyChangeCount"], 7)
        self.assertEqual(history[0]["verifiedChangeTotal"], 1)

    def test_same_day_v2_without_event_states_keeps_typed_totals(self) -> None:
        previous = {
            "history": [
                {
                    "metricsVersion": 2,
                    "date": "2026-08-30",
                    "generatedAt": "2026-08-30T01:00:00+00:00",
                    "changeCount": 3,
                    "verifiedChangeTotal": 2,
                    "candidateTotal": 1,
                    "eventSummary": {
                        "newEvents": 3,
                        "reconfirmations": 0,
                        "updates": 0,
                        "corrections": 0,
                        "possibleConflicts": 0,
                        "duplicatesSuppressed": 0,
                    },
                }
            ]
        }
        current = {
            "asOfDate": "2026-08-30",
            "generatedAt": "2026-08-30T02:00:00+00:00",
            "runStatus": "offline-fallback",
            "changeSummary": {
                "total": 1,
                "verifiedChangeTotal": 1,
                "newEvents": 1,
            },
            "analysis": {"executiveSummary": "新增一条。"},
            "changes": [
                {"eventId": "evt-new", "lifecycle": "first_seen"}
            ],
        }

        row = agent._merge_history(previous, current)[0]

        self.assertEqual(row["changeCount"], 4)
        self.assertEqual(row["unidentifiedChangeCount"], 3)
        self.assertEqual(row["verifiedChangeTotal"], 3)
        self.assertEqual(row["candidateTotal"], 1)
        self.assertEqual(row["eventSummary"]["newEvents"], 4)
        self.assertEqual(row["eventIds"], ["evt-new"])

    def test_generate_reconciles_before_applying_max_changes(self) -> None:
        duplicate = packaged_change(
            "chg-duplicate", title="历史重复事件", evidence_id="E001"
        )
        duplicate_row = evidence(
            "E001",
            "chg-duplicate",
            title="历史重复事件",
            url="https://example.com/duplicate",
        )
        _, old_ledger, _ = agent.reconcile_event_ledger(
            {},
            [duplicate],
            [duplicate_row],
            generated_at="2026-08-29T01:00:00+00:00",
        )
        new_change = packaged_change(
            "chg-new", title="真正的新事件", evidence_id="E002"
        )
        new_row = evidence(
            "E002",
            "chg-new",
            title="真正的新事件",
            url="https://example.com/new",
        )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output_path = root / "public/data/research_agent_daily.json"
            snapshot_path = root / "public/data/research_agent_snapshot.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps({"eventLedger": old_ledger}), encoding="utf-8"
            )
            snapshot_path.write_text(
                json.dumps({"datasets": {"seed": {"row": {}}}}),
                encoding="utf-8",
            )
            current_snapshot = {
                "schemaVersion": 1,
                "generatedAt": "2026-08-30T01:00:00+00:00",
                "datasets": {},
                "stats": {},
                "contentHash": "current",
            }
            raw_changes = [
                {"changeType": "external_event", "id": "raw-1"},
                {"changeType": "external_event", "id": "raw-2"},
            ]
            with mock.patch.object(agent, "load_input_payloads", return_value={}), mock.patch.object(
                agent, "build_snapshot", return_value=current_snapshot
            ), mock.patch.object(
                agent, "diff_snapshots", return_value=raw_changes
            ), mock.patch.object(
                agent, "aggregate_external_changes", return_value=raw_changes
            ), mock.patch.object(
                agent,
                "build_evidence_package",
                return_value=([duplicate, new_change], [duplicate_row, new_row]),
            ):
                report, _ = agent.generate_report(
                    root=root,
                    output_path=output_path,
                    snapshot_path=snapshot_path,
                    now=datetime(2026, 8, 30, 1, tzinfo=timezone.utc),
                    bootstrap_git_ref="HEAD^",
                    offline=True,
                    max_changes=1,
                )

        self.assertEqual([change["id"] for change in report["changes"]], ["chg-new"])
        self.assertEqual(report["changeSummary"]["duplicatesSuppressed"], 1)

    def test_generate_report_replays_pending_on_empty_snapshot_delta(self) -> None:
        changes = [
            packaged_change(
                f"chg-{suffix}", title=title, evidence_id=f"E00{index}"
            )
            for index, (suffix, title) in enumerate(
                (("first", "第一条生成事件"), ("second", "第二条生成事件")), 1
            )
        ]
        rows = [
            evidence(
                f"E00{index}",
                f"chg-{suffix}",
                title=title,
                url=f"https://example.com/generate/{suffix}",
            )
            for index, (suffix, title) in enumerate(
                (("first", "第一条生成事件"), ("second", "第二条生成事件")), 1
            )
        ]
        _, ledger, _ = agent.reconcile_event_ledger(
            {},
            changes,
            rows,
            generated_at="2026-08-29T01:00:00+00:00",
            publish_limit=1,
        )
        self.assertEqual(len(ledger["pendingPublications"]), 1)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output_path = root / "public/data/research_agent_daily.json"
            snapshot_path = root / "public/data/research_agent_snapshot.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps({"eventLedger": ledger}), encoding="utf-8"
            )
            snapshot_path.write_text(
                json.dumps({"datasets": {"seed": {"row": {}}}}),
                encoding="utf-8",
            )
            current_snapshot = {
                "schemaVersion": 1,
                "generatedAt": "2026-08-30T01:00:00+00:00",
                "datasets": {},
                "stats": {},
                "contentHash": "unchanged",
            }
            with mock.patch.object(
                agent, "load_input_payloads", return_value={}
            ), mock.patch.object(
                agent, "build_snapshot", return_value=current_snapshot
            ), mock.patch.object(agent, "diff_snapshots", return_value=[]):
                report, _ = agent.generate_report(
                    root=root,
                    output_path=output_path,
                    snapshot_path=snapshot_path,
                    now=datetime(2026, 8, 30, 1, tzinfo=timezone.utc),
                    bootstrap_git_ref="HEAD^",
                    offline=True,
                    max_changes=1,
                )

        self.assertEqual(len(report["changes"]), 1)
        self.assertEqual(report["changes"][0]["sourceChangeId"], "chg-second")
        self.assertTrue(report["changes"][0]["replayedFromPending"])
        self.assertEqual(len(report["evidence"]), 1)
        self.assertEqual(report["changeSummary"]["newEvents"], 1)
        self.assertEqual(report["eventLedger"]["pendingPublications"], [])
        self.assertEqual(agent.validate_report(report), [])

    def test_validator_rejects_publishing_an_unresolved_conflict(self) -> None:
        report = {
            "schemaVersion": 1,
            "analysis": {
                "keyDevelopments": [],
                "thesisUpdates": [],
                "watchlist": [],
                "risks": [],
            },
            "changes": [
                {
                    "id": "chg-conflict",
                    "changeType": "external_event",
                    "eventIds": ["evt-conflict"],
                    "evidenceIds": ["E001"],
                    "eligibleForKeyDevelopment": True,
                    "claimBindings": [
                        {"field": "role", "evidenceIds": ["E001"]}
                    ],
                }
            ],
            "evidence": [
                {
                    "id": "E001",
                    "qualityStatus": "passed",
                    "supportStatus": "supports",
                }
            ],
            "eventLedger": {
                "schemaVersion": 1,
                "events": {
                    "evt-conflict": {
                        "eventId": "evt-conflict",
                        "status": "needs_review",
                        "conflictStatus": "possible",
                    }
                },
            },
        }

        errors = agent.validate_report(report)

        self.assertTrue(
            any("publishes unresolved conflict" in error for error in errors),
            errors,
        )

    def test_validator_rejects_duplicate_and_cross_bound_evidence(self) -> None:
        report = {
            "schemaVersion": 1,
            "analysis": {
                "keyDevelopments": [],
                "thesisUpdates": [],
                "watchlist": [],
                "risks": [],
            },
            "changes": [
                {
                    "id": "chg-one",
                    "changeType": "external_event",
                    "eventIds": ["evt-one"],
                    "evidenceIds": ["E001"],
                    "eligibleForKeyDevelopment": True,
                    "claimBindings": [
                        {"field": "role", "evidenceIds": ["E001", "E999"]}
                    ],
                }
            ],
            "evidence": [
                {
                    "id": "E001",
                    "changeId": "chg-other",
                    "claimFields": ["title"],
                    "qualityStatus": "passed",
                    "supportStatus": "supports",
                },
                {
                    "id": "E001",
                    "changeId": "chg-one",
                    "claimFields": ["role"],
                    "qualityStatus": "passed",
                    "supportStatus": "supports",
                },
            ],
            "eventLedger": {
                "schemaVersion": agent.EVENT_LEDGER_SCHEMA_VERSION,
                "events": {
                    "evt-one": {
                        "eventId": "evt-one",
                        "status": "active",
                        "conflictStatus": "none",
                    }
                },
            },
        }

        errors = agent.validate_report(report)

        self.assertTrue(any("duplicate evidence id E001" in error for error in errors))
        self.assertTrue(any("owned by another change" in error for error in errors))
        self.assertTrue(any("escapes change evidenceIds" in error for error in errors))
        self.assertTrue(any("unsupported by evidence E001" in error for error in errors))

    def test_validator_rejects_incomplete_or_duplicate_formal_evidence(self) -> None:
        change = with_supporting_evidence(
            packaged_change(
                "chg-formal-integrity",
                title="示例公司发布年度报告",
                evidence_id="E001",
                dataset="listedDisclosure",
                entity_id="demo",
                entity_name="示例公司",
            ),
            ["E001", "E002"],
        )
        rows = [
            evidence(
                "E001",
                "chg-formal-integrity",
                title="示例公司发布年度报告",
                url="https://exchange.example/report",
                grade="监管文件",
            ),
            evidence(
                "E002",
                "chg-formal-integrity",
                title="示例公司年度报告全文",
                url="https://company.example/report",
                grade="官方披露",
            ),
        ]
        formal, ledger, _ = agent.reconcile_event_ledger(
            {}, [change], rows, generated_at="2026-08-30T01:00:00+00:00"
        )
        base_report = {
            "schemaVersion": 1,
            "generatedAt": "2026-08-30T01:00:00+00:00",
            "analysis": {
                "keyDevelopments": [],
                "thesisUpdates": [],
                "watchlist": [],
                "risks": [],
            },
            "changes": formal,
            "evidence": rows,
            "eventLedger": ledger,
        }
        self.assertEqual(agent.validate_report(base_report), [])

        unbound = copy.deepcopy(base_report)
        unbound["changes"][0]["claimBindings"][0]["evidenceIds"] = ["E001"]
        unbound_errors = agent.validate_report(unbound)
        self.assertTrue(
            any("do not exactly cover evidenceIds" in error for error in unbound_errors),
            unbound_errors,
        )

        duplicate_binding = copy.deepcopy(base_report)
        duplicate_binding["changes"][0]["claimBindings"][0]["evidenceIds"] = [
            "E001",
            "E001",
            "E002",
        ]
        binding_errors = agent.validate_report(duplicate_binding)
        self.assertTrue(
            any("duplicate claim binding evidenceIds" in error for error in binding_errors),
            binding_errors,
        )

        duplicate_change = copy.deepcopy(base_report)
        duplicate_change["changes"][0]["evidenceIds"] = [
            "E001",
            "E001",
            "E002",
        ]
        duplicate_change["changes"][0]["supportingEvidenceIds"] = [
            "E001",
            "E001",
            "E002",
        ]
        duplicate_change["changes"][0]["evidenceQuality"] = {
            "status": "passed",
            "supporting": 3,
            "total": 3,
        }
        change_errors = agent.validate_report(duplicate_change)
        self.assertTrue(
            any("duplicate evidenceIds" in error for error in change_errors),
            change_errors,
        )
        self.assertTrue(
            any("duplicate supportingEvidenceIds" in error for error in change_errors),
            change_errors,
        )
        self.assertTrue(
            any("inconsistent evidenceQuality" in error for error in change_errors),
            change_errors,
        )

        rejected = copy.deepcopy(base_report)
        rejected["changes"][0]["eligibleForKeyDevelopment"] = False
        rejected["changes"][0]["changeType"] = "source_refresh"
        rejected["changes"][0]["publicationTier"] = "rejected"
        rejected_errors = agent.validate_report(rejected)
        self.assertTrue(
            any("not eligible for formal publication" in error for error in rejected_errors),
            rejected_errors,
        )
        self.assertTrue(
            any("not an external event" in error for error in rejected_errors),
            rejected_errors,
        )
        self.assertTrue(
            any("invalid publicationTier" in error for error in rejected_errors),
            rejected_errors,
        )

        wrong_tier = copy.deepcopy(base_report)
        wrong_tier["changes"][0]["publicationTier"] = "external_clue"
        tier_errors = agent.validate_report(wrong_tier)
        self.assertTrue(
            any("does not match dataset and evidence" in error for error in tier_errors),
            tier_errors,
        )

    def test_validator_rejects_structurally_incomplete_ledger_entry(self) -> None:
        report = {
            "schemaVersion": 1,
            "analysis": {
                "keyDevelopments": [],
                "thesisUpdates": [],
                "watchlist": [],
                "risks": [],
            },
            "changes": [],
            "evidence": [],
            "eventLedger": {
                "schemaVersion": agent.EVENT_LEDGER_SCHEMA_VERSION,
                "events": {
                    "evt-incomplete": {
                        "eventId": "evt-incomplete",
                        "sourceAliases": ["src-only"],
                    }
                },
            },
        }

        errors = agent.validate_report(report)

        self.assertTrue(any("invalid firstSeenAt" in error for error in errors))
        self.assertTrue(any("missing claimFingerprint" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
