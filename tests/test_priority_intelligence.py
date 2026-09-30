from datetime import datetime, timezone, timedelta
from pathlib import Path
import unittest
from tools.priority_intelligence import source_specs, config_hash, finalize, wire_item, SOURCES

NOW = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)


def item(source="amd-newsroom"):
    host, level = SOURCES[source][1:]
    return {"id": source + "-example", "sourceId": source, "title": "AMD acquisition agreement",
            "summary": "Completion is subject to approvals", "publishedAt": "2026-09-28", "type": "并购", "region": "美国",
            "sector": "半导体", "company": "AMD", "importance": 90,
            "source": {"name": source, "level": level,
                       "platform": "官方网站" if level == "官方披露" else "媒体", "url": "https://" + host + "/news/test"}}


def scan(specs):
    return {"schemaVersion": 1, "policyVersion": "priority-publisher-v1", "configHash": config_hash(specs), "checkedAt": NOW.isoformat(),
            "sources": [{"sourceId": s["id"], "status": "ok", "items": [item(s["id"])]} for s in specs]}


class PriorityIntelligenceTests(unittest.TestCase):
    def test_complete_scan_produces_bounded_public_snapshot(self):
        specs = source_specs(); result = finalize({}, scan(specs), specs, NOW)
        self.assertEqual(len(result["items"]), len(SOURCES)); self.assertEqual(result["sourceState"], "healthy")
        self.assertEqual(len(result["contentHash"]), 64)

    def test_partial_failures_retain_last_good_source_not_false_healthy(self):
        specs = source_specs(); previous = finalize({}, scan(specs), specs, NOW); failed = scan(specs)
        failed["sources"][0].update(status="error", items=[])
        result = finalize(previous, failed, specs, NOW)
        self.assertEqual(len(result["items"]), len(SOURCES)); self.assertEqual(result["sourceState"], "degraded")

    def test_all_failed_does_not_advance_last_good(self):
        specs = source_specs(); value = scan(specs)
        for row in value["sources"]: row.update(status="error", items=[])
        with self.assertRaises(ValueError): finalize({}, value, specs, NOW)

    def test_old_clock_and_config_race_are_rejected(self):
        specs = source_specs(); value = scan(specs); value["checkedAt"] = (NOW-timedelta(hours=2)).isoformat()
        with self.assertRaises(ValueError): finalize({}, value, specs, NOW)
        value = scan(specs); value["configHash"] = "wrong"
        with self.assertRaises(ValueError): finalize({}, value, specs, NOW)

    def test_no_private_profile_fields_are_published(self):
        value = item(); value.update(preferences="private", actor="private", reasons=["private"])
        self.assertNotIn("private", str(wire_item(value, value["sourceId"])))
        value["source"]["url"] = "https://127.0.0.1/private"
        with self.assertRaises(ValueError): wire_item(value, value["sourceId"])

    def test_workflow_is_main_only_and_does_not_start_pages(self):
        workflow = (Path(__file__).resolve().parents[1]/".github/workflows/priority-intelligence-refresh.yml").read_text()
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("workflow_run", workflow)
        self.assertNotIn("gh workflow run pages", workflow)
        self.assertIn('cron: "*/5 * * * *"', workflow)


if __name__ == "__main__": unittest.main()
