from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools import manual_tracking_remove_batch as batch


class ManualTrackingRemovalBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.tracking = root / "user_tracking.json"
        self.intents = root / "tracking_intents.json"
        self.tracking.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "tracks": [
                        {
                            "slug": "robotics",
                            "name": "机器人",
                            "enabled": True,
                            "keywords": [],
                            "people": [],
                            "sampleCompanies": ["宇树科技"],
                        },
                        {
                            "slug": "ai",
                            "name": "AI / AGI",
                            "enabled": True,
                            "keywords": [],
                            "people": [],
                            "sampleCompanies": ["示例AI公司"],
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.intents.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "entities": [
                        {"id": "company:unitree", "kind": "company", "name": "宇树科技", "aliases": []},
                        {"id": "company:demo-ai", "kind": "company", "name": "示例AI公司", "aliases": []},
                    ],
                    "memberships": [
                        {
                            "id": "m1",
                            "entityId": "company:unitree",
                            "trackId": "track:robotics",
                            "state": "active",
                            "origins": [],
                        },
                        {
                            "id": "m2",
                            "entityId": "company:demo-ai",
                            "trackId": "track:ai",
                            "state": "active",
                            "origins": [],
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_batch(self, rows: list[dict], mode: str, expected: int = 0) -> dict:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = batch.main(
                [
                    "--mode",
                    mode,
                    "--batch-json",
                    json.dumps(rows, ensure_ascii=False),
                    "--actor",
                    "VCIQ",
                    "--triggering-actor",
                    "VCIQ",
                    "--tracking",
                    str(self.tracking),
                    "--intents",
                    str(self.intents),
                ]
            )
        self.assertEqual(code, expected, output.getvalue())
        return json.loads(output.getvalue().splitlines()[-1])

    @staticmethod
    def rows() -> list[dict]:
        return [
            {
                "objectType": "company",
                "name": "宇树科技",
                "targetTrack": "机器人",
                "reasons": ["赛道错配"],
                "note": "remove robotics relation",
            },
            {
                "objectType": "company",
                "name": "示例AI公司",
                "targetTrack": "AI / AGI",
                "reasons": ["赛道错配"],
                "note": "remove ai relation",
            },
        ]

    def test_validate_is_read_only_but_reports_preview_changes(self) -> None:
        before_tracking = self.tracking.read_bytes()
        before_intents = self.intents.read_bytes()
        report = self.run_batch(self.rows(), "validate")
        self.assertTrue(report["ok"])
        self.assertFalse(report["changed"])
        self.assertTrue(report["previewChanged"])
        self.assertEqual(report["changedCount"], 2)
        self.assertEqual(before_tracking, self.tracking.read_bytes())
        self.assertEqual(before_intents, self.intents.read_bytes())

    def test_apply_commits_all_removals_in_one_atomic_write(self) -> None:
        report = self.run_batch(self.rows(), "apply")
        self.assertTrue(report["changed"])
        self.assertEqual(report["changedCount"], 2)
        tracking = json.loads(self.tracking.read_text(encoding="utf-8"))
        intents = json.loads(self.intents.read_text(encoding="utf-8"))
        self.assertNotIn("宇树科技", tracking["tracks"][0]["sampleCompanies"])
        self.assertNotIn("示例AI公司", tracking["tracks"][1]["sampleCompanies"])
        self.assertEqual({row["state"] for row in intents["memberships"]}, {"rejected"})
        self.assertTrue(all(row["origins"][-1]["decision"] == "remove-fixed-watch" for row in intents["memberships"]))

    def test_invalid_later_item_does_not_write_earlier_changes(self) -> None:
        rows = self.rows()
        rows[1]["targetTrack"] = "missing-track"
        before_tracking = self.tracking.read_bytes()
        before_intents = self.intents.read_bytes()
        report = self.run_batch(rows, "apply", expected=2)
        self.assertFalse(report["ok"])
        self.assertEqual(before_tracking, self.tracking.read_bytes())
        self.assertEqual(before_intents, self.intents.read_bytes())

    def test_duplicate_relation_is_rejected_before_execution(self) -> None:
        rows = [self.rows()[0], self.rows()[0]]
        report = self.run_batch(rows, "apply", expected=2)
        self.assertFalse(report["ok"])
        self.assertIn("重复", report["error"])

    def test_batch_limit_is_enforced(self) -> None:
        rows = [
            {
                "objectType": "company",
                "name": f"公司{i}",
                "targetTrack": "机器人",
                "reasons": ["赛道错配"],
                "note": "",
            }
            for i in range(21)
        ]
        report = self.run_batch(rows, "validate", expected=2)
        self.assertFalse(report["ok"])
        self.assertIn("最多处理", report["error"])


class ManualTrackingRemovalBatchWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.text = (root / ".github/workflows/manual-tracking-remove-batch.yml").read_text(encoding="utf-8")

    def test_workflow_is_manual_dispatch_and_atomic_batch(self) -> None:
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("schedule:", self.text)
        self.assertIn("options: [validate, apply]", self.text)
        self.assertIn("manual_tracking_remove_batch.py", self.text)
        self.assertIn("Up to 20 removal requests", self.text)

    def test_apply_alone_has_write_permission_and_governance_gates(self) -> None:
        apply_job = self.text.split("  apply:\n", 1)[1]
        validate_job = self.text.split("  validate:\n", 1)[1].split("  apply:\n", 1)[0]
        self.assertIn("permissions:\n      contents: write", apply_job)
        self.assertIn("permissions:\n      contents: read", validate_job)
        self.assertIn("environment: tracking-admin", apply_job)
        self.assertIn("npm run validate:tracking", apply_job)
        self.assertIn("npm run validate:taxonomy", apply_job)
        self.assertIn("tracking_source_governance.py --check", apply_job)
        self.assertIn("config/tracking_intents.json config/user_tracking.json", apply_job)
        self.assertNotIn("git add .", apply_job)
        self.assertIn("refusing to rebase, force, or overwrite", apply_job)


if __name__ == "__main__":
    unittest.main()
