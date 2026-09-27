import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.native_event_research import SECTIONS, generate, resolve_event
from tools.native_event_research_archive import archived_event

ROOT = Path(__file__).resolve().parents[1]
EVENT = "official-xtalpi-451071ace85fb99c"
REQUEST = "b83e3fa3-1863-4389-83e4-b8b2603f4cd7"


class ArchivedResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = json.loads((ROOT / "config/native_research_event_archives.json").read_text())
        self.write("config/native_research_event_archives.json", self.archive)
        self.write("public/data/articles.json", {"articles": []})
        self.write("public/data/ranked-intelligence.json", {"items": []})

    def write(self, path, payload):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(payload, ensure_ascii=False))

    def test_exact_historical_event_is_restored(self):
        event = resolve_event(self.root, EVENT)
        self.assertEqual(event["id"], EVENT)
        self.assertIn("超衍智能", event["title"])
        self.assertEqual(event["publishedAt"], "2026-09-16")
        self.assertEqual(event["archiveProvenance"]["sourceCommit"], "5e5a3ab9e6bc3ac8a61c507f375df70ceb9e669e")
        self.assertIsNone(archived_event(self.root, "official-xtalpi-unrelated"))

    def test_current_snapshot_wins_over_history(self):
        current = copy.deepcopy(self.archive["records"][0]["event"])
        current["summary"] = "A corrected current statement"
        self.write("public/data/articles.json", {"articles": [current]})
        event = resolve_event(self.root, EVENT)
        self.assertEqual(event["summary"], current["summary"])
        self.assertNotIn("archiveProvenance", event)

    def test_current_rejection_cannot_resurrect_archived_material(self):
        current = copy.deepcopy(self.archive["records"][0]["event"])
        current["qualityStatus"] = "rejected"
        self.write("public/data/articles.json", {"articles": [current]})
        with self.assertRaises(ValueError):
            resolve_event(self.root, EVENT)

    def test_mismatched_or_unverifiable_archive_fails_closed(self):
        for field, value in [("sourceCommit", "invalid"), ("sourcePath", "private/notes.json")]:
            data = copy.deepcopy(self.archive)
            data["records"][0][field] = value
            self.write("config/native_research_event_archives.json", data)
            with self.assertRaises(ValueError):
                archived_event(self.root, EVENT)
        data = copy.deepcopy(self.archive)
        data["records"][0]["event"]["id"] = "different-event"
        self.write("config/native_research_event_archives.json", data)
        with self.assertRaises(ValueError):
            archived_event(self.root, EVENT)

    def test_generated_draft_and_prompt_disclose_historical_scope(self):
        prompts = []
        def model(prompt):
            prompts.append(json.loads(prompt))
            return {
                "executiveSummary": {"text": "历史来源陈述的有限分析", "kind": "inference", "evidenceIds": ["N001"]},
                "sections": {key: [{"text": "待进一步核验", "kind": "source_statement" if key == "facts" else "unknown", "evidenceIds": ["N001"]}] for key in SECTIONS},
            }
        with patch.dict("os.environ", {"SILICONFLOW_API_KEY": ""}):
            result = generate(self.root, EVENT, REQUEST, model_call=model)
        self.assertEqual(result["status"], "completed-draft")
        self.assertIn("历史公开快照", result["methodology"])
        self.assertEqual(result["reviewStatus"], "automated_unreviewed")
        self.assertEqual(prompts[0]["event"]["archiveProvenance"]["sourceBlob"], self.archive["records"][0]["sourceBlob"])
        self.assertEqual(result["evidence"][0]["publishedAt"], "2026-09-16")


if __name__ == "__main__":
    unittest.main()
