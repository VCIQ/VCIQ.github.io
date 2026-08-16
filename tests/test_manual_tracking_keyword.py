from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools import manual_tracking as manual
from tools import manual_tracking_batch_entrypoint as batch_entrypoint
from tools import manual_tracking_entrypoint as single_entrypoint
from tools.manual_tracking_keyword_support import enable_keyword_tracking


class FirstClassManualTrackingKeywordTests(unittest.TestCase):
    def setUp(self) -> None:
        enable_keyword_tracking(manual)
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

    def _run_single(self, name: str, *, expected: int = 0, kind: str = "keyword") -> dict:
        output = io.StringIO()
        argv = [
            "--mode",
            "apply",
            "--kind",
            kind,
            "--name",
            name,
            "--tracks",
            "ai",
            "--source-url",
            "https://example.com/article",
            "--reasons",
            "个人研究兴趣",
            "--actor",
            "IamVC",
            "--triggering-actor",
            "IamVC",
            "--now",
            "2026-08-15T12:00:00+00:00",
        ]
        with contextlib.redirect_stdout(output):
            code = single_entrypoint.main(argv)
        self.assertEqual(code, expected, output.getvalue())
        return json.loads(output.getvalue().splitlines()[-1])

    def _run_batch(self, row: dict, *, expected: int = 0) -> dict:
        output = io.StringIO()
        argv = [
            "--mode",
            "apply",
            "--invalid-policy",
            "skip",
            "--batch-json",
            json.dumps([row], ensure_ascii=False),
            "--actor",
            "IamVC",
            "--triggering-actor",
            "IamVC",
            "--now",
            "2026-08-15T12:00:00+00:00",
        ]
        with contextlib.redirect_stdout(output):
            code = batch_entrypoint.main(argv)
        self.assertEqual(code, expected, output.getvalue())
        return json.loads(output.getvalue().splitlines()[-1])

    def test_single_keyword_updates_search_seeds_without_creating_technology_capture(self) -> None:
        first = self._run_single("IPO")
        second = self._run_single("IPO")

        self.assertTrue(first["configChanged"])
        self.assertTrue(first["intentsChanged"])
        self.assertFalse(first["inboxChanged"])
        self.assertFalse(second["changed"])
        self.assertEqual(first["resolution"]["entityType"], "keyword")
        self.assertIn("IPO", self._read("tracking")["tracks"][0]["keywords"])

        intents = self._read("intents")
        self.assertEqual(len(intents["entities"]), 1)
        self.assertEqual(intents["entities"][0]["kind"], "keyword")
        self.assertEqual(intents["entities"][0]["name"], "IPO")
        self.assertEqual(intents["entities"][0]["keywords"], [])
        self.assertEqual(intents["memberships"][0]["role"], "keyword")
        self.assertTrue(intents["memberships"][0]["pinned"])
        self.assertEqual(self._read("inbox")["records"], [])

        feedback = manual.build_manual_feedback(
            self._read("inbox"),
            intents,
            self._read("tracking"),
        )
        track_feedback = feedback["tracks"]["ai"]
        self.assertIn("IPO", track_feedback["approved"]["keywords"])
        self.assertIn(
            "IPO",
            [row["value"] for row in track_feedback["seedTerms"]],
        )

    def test_keyword_and_technology_keep_separate_intent_entities(self) -> None:
        keyword_report = self._run_single("世界模型", kind="keyword")
        technology_report = self._run_single("世界模型", kind="technology")

        self.assertEqual(keyword_report["resolution"]["entityType"], "keyword")
        self.assertEqual(technology_report["resolution"]["entityType"], "topic")
        self.assertNotEqual(
            keyword_report["resolution"]["targetId"],
            technology_report["resolution"]["targetId"],
        )

        entities = self._read("intents")["entities"]
        self.assertEqual({row["kind"] for row in entities}, {"keyword", "technology"})
        self.assertEqual(len({row["id"] for row in entities}), 2)
        records = self._read("inbox")["records"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["entityType"], "topic")
        self.assertEqual(records[0]["canonicalName"], "世界模型")

    def test_low_signal_keyword_fails_closed(self) -> None:
        before = {key: path.read_bytes() for key, path in self.paths.items()}
        report = self._run_single("融资", expected=2)

        self.assertFalse(report["ok"])
        self.assertIn("关键词", report["error"])
        self.assertEqual(before, {key: path.read_bytes() for key, path in self.paths.items()})

    def test_batch_keyword_reports_keyword_outcome_and_never_sanitizes_manual_name(self) -> None:
        row = {
            "objectType": "keyword",
            "name": "国产替代",
            "targetTracks": ["ai"],
            "keywords": [],
            "sourceUrl": "https://example.com/article",
            "sourceCategory": "media",
            "region": "全球",
            "reasons": ["个人研究兴趣"],
            "note": "人工补充追踪关键词；来源文章：测试",
            "origin": "manual",
        }
        report = self._run_batch(row)

        self.assertEqual(report["acceptedCount"], 1)
        self.assertEqual(report["appliedCount"], 1)
        self.assertEqual(report["repairedCount"], 0)
        self.assertEqual(report["items"][0]["request"]["kind"], "keyword")
        self.assertEqual(report["items"][0]["request"]["keywords"], [])
        self.assertEqual(report["outcomes"][0]["objectType"], "keyword")
        self.assertIn("国产替代", self._read("tracking")["tracks"][0]["keywords"])


class FirstClassKeywordWorkflowContractTests(unittest.TestCase):
    def test_workflows_route_through_keyword_enabled_entrypoints(self) -> None:
        root = Path(__file__).resolve().parents[1]
        single = (root / ".github/workflows/manual-tracking.yml").read_text(encoding="utf-8")
        batch = (root / ".github/workflows/manual-tracking-batch.yml").read_text(encoding="utf-8")

        self.assertIn("options: [keyword, technology, track, company, person, source]", single)
        self.assertIn("python tools/manual_tracking_entrypoint.py", single)
        self.assertIn("python tools/manual_tracking_batch_entrypoint.py", batch)
        self.assertIn("tests.test_manual_tracking_keyword", batch)
        self.assertIn("manual_tracking_keyword_support.py", single)
        self.assertIn("manual_tracking_keyword_support.py", batch)


if __name__ == "__main__":
    unittest.main()
