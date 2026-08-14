from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from tools import finalize_frequent_refresh as finalize
from tools import prepare_frequent_refresh as prepare


class FrequentRefreshAuditTests(unittest.TestCase):
    def test_prepare_and_finalize_publish_incremental_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            articles_path = root / "articles.json"
            baseline_path = root / "baseline.json"
            local_date = datetime.now(finalize.TAIPEI).date().isoformat()
            previous_full = "2026-08-14T00:30:00+00:00"
            payload = {
                "schemaVersion": 3,
                "generatedAt": "2026-07-29T00:00:00+00:00",
                "articleCount": 1,
                "articles": [
                    {
                        "id": "existing",
                        "publishedAt": local_date,
                        "sourceId": "source-a",
                        "source": {"name": "A", "url": "https://example.com/a"},
                    }
                ],
                "sourceStatus": [
                    {"id": "source-a", "status": "ok", "scanned": 1, "accepted": 1}
                ],
                "refreshAudit": {
                    "mode": "full",
                    "pipelineCompleted": True,
                    "completedAt": previous_full,
                    "lastNewsCrawlAt": previous_full,
                },
            }
            articles_path.write_text(json.dumps(payload), encoding="utf-8")

            old_prepare_articles = prepare.ARTICLES_PATH
            old_prepare_baseline = prepare.BASELINE_PATH
            old_finalize_articles = finalize.ARTICLES_PATH
            old_finalize_baseline = finalize.BASELINE_PATH
            try:
                prepare.ARTICLES_PATH = articles_path
                prepare.BASELINE_PATH = baseline_path
                finalize.ARTICLES_PATH = articles_path
                finalize.BASELINE_PATH = baseline_path
                self.assertEqual(prepare.main(), 0)

                payload["articles"].append(
                    {
                        "id": "new",
                        "publishedAt": local_date,
                        "sourceId": "source-b",
                        "source": {"name": "B", "url": "https://example.com/b"},
                    }
                )
                payload["articleCount"] = 2
                articles_path.write_text(json.dumps(payload), encoding="utf-8")

                self.assertEqual(finalize.main(), 0)
                result = json.loads(articles_path.read_text(encoding="utf-8"))
                audit = result["refreshAudit"]
                self.assertEqual(audit["mode"], "frequent")
                self.assertTrue(audit["pipelineCompleted"])
                self.assertEqual(audit["lastNewsCrawlAt"], audit["completedAt"])
                self.assertEqual(audit["lastFullRefreshAt"], previous_full)
                self.assertEqual(audit["previousArticleCount"], 1)
                self.assertEqual(audit["newArticleCount"], 1)
                self.assertEqual(audit["todayArticleCount"], 2)
                self.assertEqual(audit["todaySourceCount"], 2)
                self.assertNotIn("lastAttemptAt", result["sourceStatus"][0])
                self.assertFalse(baseline_path.exists())
            finally:
                prepare.ARTICLES_PATH = old_prepare_articles
                prepare.BASELINE_PATH = old_prepare_baseline
                finalize.ARTICLES_PATH = old_finalize_articles
                finalize.BASELINE_PATH = old_finalize_baseline


if __name__ == "__main__":
    unittest.main()
