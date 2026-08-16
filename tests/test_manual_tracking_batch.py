from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools import manual_tracking as manual
from tools import manual_tracking_batch as batch


class ManualTrackingBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.paths = {
            "tracking": root / "user_tracking.json",
            "inbox": root / "tracking_capture_inbox.json",
            "intents": root / "tracking_intents.json",
            "admins": root / "tracking_admins.json",
        }
        self.original_paths = (
            manual.TRACKING_PATH,
            manual.INBOX_PATH,
            manual.INTENTS_PATH,
            manual.ADMINS_PATH,
        )
        manual.TRACKING_PATH = self.paths["tracking"]
        manual.INBOX_PATH = self.paths["inbox"]
        manual.INTENTS_PATH = self.paths["intents"]
        manual.ADMINS_PATH = self.paths["admins"]
        self._write(
            "tracking",
            {
                "schemaVersion": 1,
                "tracks": [
                    {
                        "slug": "ai",
                        "name": "AI / AGI",
                        "enabled": True,
                        "custom": False,
                        "keywords": ["大语言模型"],
                        "people": [],
                        "sampleCompanies": [],
                    }
                ],
                "listedCompanies": [],
                "sources": [],
            },
        )
        self._write("inbox", {"schemaVersion": 1, "generatedAt": "", "records": []})
        self._write(
            "intents",
            {"schemaVersion": 1, "updatedAt": "", "entities": [], "memberships": []},
        )
        self._write("admins", {"schemaVersion": 1, "actors": ["IamVC"]})

    def tearDown(self) -> None:
        (
            manual.TRACKING_PATH,
            manual.INBOX_PATH,
            manual.INTENTS_PATH,
            manual.ADMINS_PATH,
        ) = self.original_paths
        self.tmp.cleanup()

    def _write(self, key: str, payload: dict) -> None:
        self.paths[key].write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _read(self, key: str) -> dict:
        return json.loads(self.paths[key].read_text(encoding="utf-8"))

    def _run(
        self,
        rows: list[dict],
        mode: str,
        expected: int = 0,
        invalid_policy: str = "strict",
    ) -> dict:
        output = io.StringIO()
        argv = [
            "--mode",
            mode,
            "--invalid-policy",
            invalid_policy,
            "--batch-json",
            json.dumps(rows, ensure_ascii=False),
            "--actor",
            "IamVC",
            "--triggering-actor",
            "IamVC",
            "--now",
            "2026-08-11T08:00:00+00:00",
        ]
        with contextlib.redirect_stdout(output):
            code = batch.main(argv)
        self.assertEqual(code, expected, output.getvalue())
        return json.loads(output.getvalue().splitlines()[-1])

    @staticmethod
    def technology(
        name: str,
        tracks: list[str],
        origin: str = "manual",
    ) -> dict:
        return {
            "objectType": "technology",
            "name": name,
            "targetTracks": tracks,
            "keywords": [name],
            "sourceUrl": "https://example.com/article",
            "sourceCategory": "media",
            "region": "全球",
            "reasons": ["技术突破"],
            "note": "batch test",
            "origin": origin,
        }

    @staticmethod
    def company(
        name: str,
        tracks: list[str] | None = None,
        origin: str = "manual",
    ) -> dict:
        return {
            "objectType": "company",
            "name": name,
            "targetTracks": tracks or ["ai"],
            "keywords": [name],
            "sourceUrl": "https://example.com/company-evidence",
            "sourceCategory": "media",
            "region": "中国",
            "reasons": ["个人研究兴趣"],
            "note": "原文明确描述该公司参与项目。",
            "origin": origin,
        }

    @staticmethod
    def invalid_person(
        name: str = "stdrc",
        origin: str = "automatic",
    ) -> dict:
        return {
            "objectType": "person",
            "name": name,
            "targetTracks": ["ai"],
            "keywords": ["Richard Qian"],
            "sourceUrl": "https://example.com/article",
            "sourceCategory": "media",
            "region": "全球",
            "reasons": ["个人研究兴趣"],
            "note": "machine candidate",
            "origin": origin,
        }

    def test_validate_is_read_only_and_supports_cross_item_new_track_reference(self) -> None:
        new_track_name = "具身智能基础设施"
        new_track_slug = manual.slugify_track(new_track_name)
        rows = [
            {
                "objectType": "track",
                "name": new_track_name,
                "targetTracks": [],
                "keywords": ["具身智能基础设施"],
                "sourceUrl": "https://example.com/article",
                "sourceCategory": "media",
                "region": "全球",
                "reasons": ["技术突破"],
                "note": "batch test",
                "origin": "manual",
            },
            self.technology("视觉语言动作模型", [new_track_slug]),
        ]
        before = {key: path.read_bytes() for key, path in self.paths.items()}
        report = self._run(rows, "validate")
        self.assertTrue(report["ok"])
        self.assertEqual(report["count"], 2)
        self.assertEqual(report["acceptedCount"], 2)
        self.assertEqual(report["skippedCount"], 0)
        self.assertEqual(report["appliedCount"], 0)
        self.assertEqual(report["reviewQueuedCount"], 0)
        self.assertEqual(report["recordedCount"], 0)
        self.assertEqual(report["unchangedCount"], 0)
        self.assertEqual(report["outcomes"], [])
        self.assertFalse(report["changed"])
        self.assertTrue(report["items"][0]["preview"]["changed"])
        self.assertTrue(report["items"][1]["preview"]["changed"])
        self.assertEqual(report["items"][0]["request"]["origin"], "manual")
        self.assertEqual(before, {key: path.read_bytes() for key, path in self.paths.items()})

    def test_apply_writes_multiple_objects_once_as_one_transaction(self) -> None:
        rows = [
            self.technology("端侧多模态", ["ai"]),
            self.technology("视觉语言动作模型", ["ai"]),
        ]
        report = self._run(rows, "apply")
        self.assertTrue(report["changed"])
        self.assertTrue(report["configChanged"])
        self.assertTrue(report["intentsChanged"])
        self.assertEqual(report["acceptedCount"], 2)
        self.assertEqual(report["skippedCount"], 0)
        self.assertEqual(report["appliedCount"], 2)
        self.assertEqual(report["reviewQueuedCount"], 0)
        self.assertEqual(report["recordedCount"], 0)
        self.assertEqual(report["unchangedCount"], 0)
        self.assertEqual([item["outcome"] for item in report["outcomes"]], ["applied", "applied"])
        self.assertEqual([item["name"] for item in report["outcomes"]], ["端侧多模态", "视觉语言动作模型"])
        keywords = self._read("tracking")["tracks"][0]["keywords"]
        self.assertIn("端侧多模态", keywords)
        self.assertIn("视觉语言动作模型", keywords)
        intents = self._read("intents")
        self.assertEqual(len(intents["entities"]), 2)
        self.assertEqual(len(intents["memberships"]), 2)

    def test_apply_reports_review_queue_separately_from_formal_config(self) -> None:
        report = self._run([self.company("星河智算科技有限公司")], "apply")

        self.assertTrue(report["ok"])
        self.assertEqual(report["acceptedCount"], 1)
        self.assertEqual(report["appliedCount"], 0)
        self.assertEqual(report["reviewQueuedCount"], 1)
        self.assertEqual(report["recordedCount"], 0)
        self.assertEqual(report["unchangedCount"], 0)
        self.assertEqual(report["outcomes"][0]["outcome"], "review")
        self.assertTrue(report["outcomes"][0]["reviewQueued"])
        self.assertFalse(report["outcomes"][0]["configChanged"])
        self.assertIn("审核", report["outcomes"][0]["reason"])
        self.assertNotIn("星河智算科技有限公司", self._read("tracking")["tracks"][0]["sampleCompanies"])

    def test_apply_distinguishes_recorded_from_unchanged(self) -> None:
        row = self.technology("端侧多模态", ["ai"])
        first = self._run([row], "apply")
        self.assertEqual(first["appliedCount"], 1)

        row["note"] = "补充第二条人工来源说明"
        recorded = self._run([row], "apply")
        self.assertEqual(recorded["appliedCount"], 0)
        self.assertEqual(recorded["recordedCount"], 1)
        self.assertEqual(recorded["unchangedCount"], 0)
        self.assertEqual(recorded["outcomes"][0]["outcome"], "recorded")
        self.assertFalse(recorded["outcomes"][0]["configChanged"])
        self.assertTrue(recorded["outcomes"][0]["intentsChanged"])

        unchanged = self._run([row], "apply")
        self.assertEqual(unchanged["appliedCount"], 0)
        self.assertEqual(unchanged["recordedCount"], 0)
        self.assertEqual(unchanged["unchangedCount"], 1)
        self.assertEqual(unchanged["outcomes"][0]["outcome"], "unchanged")
        self.assertFalse(unchanged["outcomes"][0]["configChanged"])
        self.assertFalse(unchanged["outcomes"][0]["intentsChanged"])

    def test_apply_is_all_or_nothing_when_later_item_is_invalid(self) -> None:
        rows = [
            self.technology("端侧多模态", ["ai"]),
            self.technology("视觉语言动作模型", ["missing-track"]),
        ]
        before = {key: path.read_bytes() for key, path in self.paths.items()}
        report = self._run(rows, "apply", expected=2)
        self.assertFalse(report["ok"])
        self.assertIn("第 2 个对象", report["error"])
        self.assertEqual(before, {key: path.read_bytes() for key, path in self.paths.items()})

    def test_skip_policy_validate_omits_invalid_automatic_candidate(self) -> None:
        rows = [
            self.technology("端侧多模态", ["ai"], origin="automatic"),
            self.invalid_person(),
            self.technology("视觉语言动作模型", ["ai"], origin="automatic"),
        ]
        before = {key: path.read_bytes() for key, path in self.paths.items()}
        report = self._run(rows, "validate", invalid_policy="skip")
        self.assertTrue(report["ok"])
        self.assertEqual(report["count"], 3)
        self.assertEqual(report["acceptedCount"], 2)
        self.assertEqual(report["skippedCount"], 1)
        self.assertEqual(report["skipped"][0]["index"], 2)
        self.assertEqual(report["skipped"][0]["name"], "stdrc")
        self.assertEqual(report["skipped"][0]["origin"], "automatic")
        self.assertIn("完整姓名", report["skipped"][0]["error"])
        self.assertEqual(report["items"][0]["request"]["origin"], "automatic")
        self.assertEqual(before, {key: path.read_bytes() for key, path in self.paths.items()})

    def test_skip_policy_apply_writes_valid_automatic_subset(self) -> None:
        rows = [
            self.technology("端侧多模态", ["ai"], origin="automatic"),
            self.invalid_person(),
            self.technology("视觉语言动作模型", ["ai"], origin="automatic"),
        ]
        report = self._run(rows, "apply", invalid_policy="skip")
        self.assertTrue(report["ok"])
        self.assertTrue(report["changed"])
        self.assertEqual(report["acceptedCount"], 2)
        self.assertEqual(report["skippedCount"], 1)
        self.assertEqual(report["appliedCount"], 2)
        self.assertEqual(report["reviewQueuedCount"], 0)
        self.assertEqual(report["recordedCount"], 0)
        self.assertEqual(report["unchangedCount"], 0)
        self.assertEqual(
            [item["outcome"] for item in report["outcomes"]],
            ["applied", "skipped", "applied"],
        )
        self.assertIn("完整姓名", report["outcomes"][1]["reason"])
        keywords = self._read("tracking")["tracks"][0]["keywords"]
        self.assertIn("端侧多模态", keywords)
        self.assertIn("视觉语言动作模型", keywords)
        self.assertNotIn("stdrc", self._read("tracking")["tracks"][0]["people"])
        intent_names = [row.get("name") for row in self._read("intents")["entities"]]
        self.assertNotIn("stdrc", intent_names)

    def test_skip_policy_all_invalid_automatic_candidates_is_successful_noop(self) -> None:
        before = {key: path.read_bytes() for key, path in self.paths.items()}
        report = self._run([self.invalid_person()], "apply", invalid_policy="skip")

        self.assertTrue(report["ok"])
        self.assertFalse(report["changed"])
        self.assertFalse(report["configChanged"])
        self.assertFalse(report["inboxChanged"])
        self.assertFalse(report["intentsChanged"])
        self.assertEqual(report["acceptedCount"], 0)
        self.assertEqual(report["skippedCount"], 1)
        self.assertEqual(report["appliedCount"], 0)
        self.assertEqual(report["reviewQueuedCount"], 0)
        self.assertEqual(report["recordedCount"], 0)
        self.assertEqual(report["unchangedCount"], 0)
        self.assertEqual(len(report["outcomes"]), 1)
        self.assertEqual(report["outcomes"][0]["outcome"], "skipped")
        self.assertEqual(report["outcomes"][0]["origin"], "automatic")
        self.assertIn("完整姓名", report["outcomes"][0]["reason"])
        self.assertEqual(before, {key: path.read_bytes() for key, path in self.paths.items()})

    def test_skip_policy_repairs_low_signal_automatic_keyword(self) -> None:
        row = self.technology("端侧多模态", ["ai"], origin="automatic")
        row["keywords"] = ["端侧多模态", "平台", "视觉语言动作模型"]
        before = {key: path.read_bytes() for key, path in self.paths.items()}

        report = self._run([row], "validate", invalid_policy="skip")

        self.assertTrue(report["ok"])
        self.assertEqual(report["acceptedCount"], 1)
        self.assertEqual(report["skippedCount"], 0)
        self.assertEqual(report["repairedCount"], 1)
        self.assertEqual(report["removedKeywordCount"], 1)
        self.assertEqual(report["repaired"][0]["origin"], "automatic")
        self.assertEqual(report["repaired"][0]["removedKeywords"][0]["value"], "平台")
        self.assertEqual(
            report["items"][0]["request"]["keywords"],
            ["端侧多模态", "视觉语言动作模型"],
        )
        self.assertEqual(before, {key: path.read_bytes() for key, path in self.paths.items()})

    def test_skip_policy_apply_persists_candidate_but_not_low_signal_keyword(self) -> None:
        row = self.technology("端侧多模态", ["ai"], origin="automatic")
        row["keywords"] = ["端侧多模态", "平台", "视觉语言动作模型"]

        report = self._run([row], "apply", invalid_policy="skip")

        self.assertTrue(report["ok"])
        self.assertEqual(report["acceptedCount"], 1)
        self.assertEqual(report["skippedCount"], 0)
        self.assertEqual(report["repairedCount"], 1)
        self.assertEqual(report["appliedCount"], 1)
        self.assertEqual(
            report["items"][0]["request"]["keywords"],
            ["端侧多模态", "视觉语言动作模型"],
        )
        keywords = self._read("tracking")["tracks"][0]["keywords"]
        self.assertIn("端侧多模态", keywords)
        self.assertNotIn("平台", keywords)

    def test_skip_policy_never_rewrites_direct_manual_keywords(self) -> None:
        row = self.technology("端侧多模态", ["ai"], origin="manual")
        row["keywords"] = ["端侧多模态", "平台", "视觉语言动作模型"]

        prepared, repair = batch.prepared_row(1, row, "skip")

        self.assertEqual(prepared["keywords"], row["keywords"])
        self.assertEqual(prepared["origin"], "manual")
        self.assertIsNone(repair)

    def test_skip_policy_fails_closed_for_invalid_direct_manual_input(self) -> None:
        rows = [
            self.technology("端侧多模态", ["ai"], origin="automatic"),
            self.invalid_person(origin="manual"),
            self.technology("视觉语言动作模型", ["ai"], origin="automatic"),
        ]
        before = {key: path.read_bytes() for key, path in self.paths.items()}

        report = self._run(rows, "apply", expected=2, invalid_policy="skip")

        self.assertFalse(report["ok"])
        self.assertIn("人工输入", report["error"])
        self.assertIn("第 2 个对象", report["error"])
        self.assertEqual(before, {key: path.read_bytes() for key, path in self.paths.items()})

    def test_skip_policy_repairs_manual_confirmed_keywords_but_does_not_skip_entity(self) -> None:
        row = self.technology("端侧多模态", ["ai"], origin="manual-confirmed")
        row["keywords"] = ["端侧多模态", "平台", "视觉语言动作模型"]

        report = self._run([row], "validate", invalid_policy="skip")

        self.assertTrue(report["ok"])
        self.assertEqual(report["repairedCount"], 1)
        self.assertEqual(report["repaired"][0]["origin"], "manual-confirmed")
        self.assertEqual(report["items"][0]["request"]["origin"], "manual-confirmed")

        before = {key: path.read_bytes() for key, path in self.paths.items()}
        invalid = self._run(
            [self.invalid_person(origin="manual-confirmed")],
            "apply",
            expected=2,
            invalid_policy="skip",
        )
        self.assertFalse(invalid["ok"])
        self.assertIn("人工确认候选", invalid["error"])
        self.assertNotIn("均未通过验证", invalid["error"])
        self.assertEqual(before, {key: path.read_bytes() for key, path in self.paths.items()})

    def test_skip_policy_requires_origin_for_every_row(self) -> None:
        row = self.technology("端侧多模态", ["ai"])
        row.pop("origin")
        before = {key: path.read_bytes() for key, path in self.paths.items()}

        report = self._run([row], "validate", expected=2, invalid_policy="skip")

        self.assertFalse(report["ok"])
        self.assertIn("缺少 origin", report["error"])
        self.assertIn("刷新追踪管理页面", report["error"])
        self.assertEqual(before, {key: path.read_bytes() for key, path in self.paths.items()})

    def test_strict_policy_keeps_legacy_missing_origin_fail_closed(self) -> None:
        row = self.technology("端侧多模态", ["ai"])
        row.pop("origin")

        report = self._run([row], "validate", invalid_policy="strict")

        self.assertTrue(report["ok"])
        self.assertEqual(report["items"][0]["request"]["origin"], "manual")

    def test_strict_policy_still_rejects_same_low_signal_keyword(self) -> None:
        row = self.technology("端侧多模态", ["ai"])
        row["keywords"] = ["端侧多模态", "平台", "视觉语言动作模型"]
        before = {key: path.read_bytes() for key, path in self.paths.items()}

        report = self._run([row], "apply", expected=2, invalid_policy="strict")

        self.assertFalse(report["ok"])
        self.assertIn("平台", report["error"])
        self.assertEqual(before, {key: path.read_bytes() for key, path in self.paths.items()})


if __name__ == "__main__":
    unittest.main()
