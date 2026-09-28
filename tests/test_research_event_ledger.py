import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools import research_event_ledger as ledger


class ResearchEventLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "public/data").mkdir(parents=True)

    def write(self, path, payload):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def article(self, event_id="article-event-1", *, status=None):
        row = {
            "id": event_id,
            "title": "Example event",
            "summary": "A bounded public event statement.",
            "type": "公司动态",
            "region": "全球",
            "sector": "AI / AGI",
            "company": "ExampleCo",
            "publishedAt": "2026-09-28T00:00:00Z",
            "importance": 88,
            "source": {"name": "ExampleCo", "url": "https://example.com/event", "level": "官方披露"},
        }
        if status:
            row["qualityStatus"] = status
        return row

    def ranked(self, raw_id="intel-event-abc"):
        return {
            "id": raw_id,
            "title": "Ranked event",
            "summary": "A ranked event that must preserve the homepage ID namespace.",
            "href": "https://news.example.com/ranked",
            "source": "Example News",
            "publishedAt": "2026-09-28T01:00:00Z",
            "priority": "P0",
            "score": 97,
            "eventTypes": ["Funding"],
            "entities": [{"objectType": "company", "name": "RankedCo"}],
            "tracks": ["风险投资"],
            "eventClusterId": raw_id,
            "duplicateCount": 1,
            "relatedSources": [],
        }

    def test_ranked_id_matches_homepage_namespace(self):
        event = ledger.normalize_ranked_event(self.ranked())
        self.assertEqual(event["id"], "ranked-intelligence:intel-event-abc")
        self.assertEqual(event["type"], "融资")
        self.assertEqual(event["company"], "RankedCo")
        self.assertEqual(event["sector"], "风险投资")

    def test_disappeared_event_survives_exactly_without_company_substitution(self):
        self.write("public/data/articles.json", {"generatedAt": "2026-09-28T00:00:00Z", "articles": [self.article()]})
        self.write("public/data/ranked-intelligence.json", {"generatedAt": "2026-09-28T00:00:00Z", "items": []})
        first = ledger.build_ledger(self.root)
        self.write(ledger.LEDGER_PATH, first)

        self.write("public/data/articles.json", {"generatedAt": "2026-09-28T02:00:00Z", "articles": [
            {**self.article("article-event-2"), "company": "ExampleCo", "source": {"name": "ExampleCo", "url": "https://example.com/other", "level": "官方披露"}}
        ]})
        second = ledger.build_ledger(self.root)
        self.write(ledger.LEDGER_PATH, second)

        restored = ledger.retained_event(self.root, "article-event-1")
        self.assertEqual(restored["id"], "article-event-1")
        self.assertIn("A bounded public event statement", restored["summary"])
        self.assertIsNone(ledger.retained_event(self.root, "article-event-missing"))

    def test_current_rejection_overwrites_old_active_record(self):
        self.write("public/data/articles.json", {"generatedAt": "2026-09-28T00:00:00Z", "articles": [self.article()]})
        self.write("public/data/ranked-intelligence.json", {"generatedAt": "2026-09-28T00:00:00Z", "items": []})
        self.write(ledger.LEDGER_PATH, ledger.build_ledger(self.root))
        self.write("public/data/articles.json", {"generatedAt": "2026-09-28T01:00:00Z", "articles": [self.article(status="rejected")]})
        updated = ledger.build_ledger(self.root)
        self.assertEqual(updated["events"]["article-event-1"]["status"], "rejected")
        self.write(ledger.LEDGER_PATH, updated)
        self.assertIsNone(ledger.retained_event(self.root, "article-event-1"))

    def test_pruning_and_byte_contract_are_bounded(self):
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=ledger.RETENTION_DAYS + 2)).isoformat().replace("+00:00", "Z")
        payload = {
            "schemaVersion": 1,
            "generatedAt": old,
            "retentionDays": ledger.RETENTION_DAYS,
            "maxEvents": ledger.MAX_EVENTS,
            "events": {
                "article-old": {
                    "eventId": "article-old",
                    "firstSeenAt": old,
                    "lastSeenAt": old,
                    "sourceDataset": ledger.ARTICLE_PATH,
                    "snapshotGeneratedAt": old,
                    "sourceCommit": "",
                    "sourceBlob": "",
                    "status": "active",
                    "event": self.article("article-old"),
                }
            },
        }
        self.write(ledger.LEDGER_PATH, payload)
        self.write("public/data/articles.json", {"generatedAt": now.isoformat(), "articles": []})
        self.write("public/data/ranked-intelligence.json", {"generatedAt": now.isoformat(), "items": []})
        refreshed = ledger.build_ledger(self.root)
        self.assertNotIn("article-old", refreshed["events"])
        summary = ledger.validate_ledger(refreshed)
        self.assertLessEqual(summary["bytes"], ledger.MAX_BYTES)

    def test_seeded_production_regressions_are_exact(self):
        production = json.loads((Path(__file__).resolve().parents[1] / ledger.LEDGER_PATH).read_text(encoding="utf-8"))
        self.assertIn("official-xtalpi-451071ace85fb99c", production["events"])
        ranked_id = "ranked-intelligence:intel-event-35084a5f95caa665"
        self.assertIn(ranked_id, production["events"])
        self.assertIn("数据中心", production["events"][ranked_id]["event"]["title"])


if __name__ == "__main__":
    unittest.main()
