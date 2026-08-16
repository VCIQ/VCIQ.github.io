from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest import mock

from tools import manual_tracking_batch_entrypoint as entrypoint


class ManualTrackingBatchEntrypointTests(unittest.TestCase):
    @staticmethod
    def automatic_source(name: str = "TNW | Government-policy") -> dict:
        return {
            "objectType": "source",
            "name": name,
            "targetTracks": ["semiconductor", "robotics"],
            "keywords": [],
            "sourceUrl": "https://thenextweb.com/",
            "sourceCategory": "media",
            "region": "全球",
            "reasons": ["个人研究兴趣"],
            "note": "",
            "origin": "automatic",
        }

    def argv(self, rows: list[dict]) -> list[str]:
        return [
            "--mode",
            "apply",
            "--invalid-policy",
            "skip",
            "--batch-json",
            json.dumps(rows, ensure_ascii=False),
            "--actor",
            "IamVC",
            "--triggering-actor",
            "IamVC",
        ]

    @staticmethod
    def rejected_report() -> dict:
        return {
            "ok": False,
            "changed": False,
            "error": (
                "整批对象均未通过验证，没有可安全写入的对象。"
                "（第 1 个对象 TNW | Government-policy："
                "名称必须是单一、完整的对象，不能粘贴列表或残缺括号。）"
            ),
        }

    def test_all_invalid_automatic_batch_becomes_audited_noop(self) -> None:
        report = entrypoint._automatic_noop_report(
            self.argv([self.automatic_source()]),
            2,
            self.rejected_report(),
        )

        self.assertIsNotNone(report)
        assert report is not None
        self.assertTrue(report["ok"])
        self.assertFalse(report["changed"])
        self.assertEqual(report["acceptedCount"], 0)
        self.assertEqual(report["skippedCount"], 1)
        self.assertEqual(report["outcomes"][0]["outcome"], "skipped")
        self.assertEqual(report["outcomes"][0]["origin"], "automatic")
        self.assertIn("名称必须是单一", report["skipped"][0]["error"])
        self.assertIn("没有写入任何状态", report["detail"])

    def test_human_confirmed_failure_remains_fail_closed(self) -> None:
        row = self.automatic_source()
        row["origin"] = "manual-confirmed"

        report = entrypoint._automatic_noop_report(
            self.argv([row]),
            2,
            self.rejected_report(),
        )

        self.assertIsNone(report)

    def test_entrypoint_emits_one_success_json_for_automatic_noop(self) -> None:
        output = io.StringIO()

        def rejected_main(_argv: list[str]) -> int:
            print(json.dumps(self.rejected_report(), ensure_ascii=False))
            return 2

        with mock.patch.object(entrypoint.batch, "main", side_effect=rejected_main):
            with contextlib.redirect_stdout(output):
                code = entrypoint.main(self.argv([self.automatic_source()]))

        self.assertEqual(code, 0)
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        report = json.loads(lines[0])
        self.assertTrue(report["ok"])
        self.assertEqual(report["skippedCount"], 1)


if __name__ == "__main__":
    unittest.main()
