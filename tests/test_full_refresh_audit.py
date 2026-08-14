from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import finalize_full_refresh
from tools import prepare_full_refresh


def article(article_id: str, published_at: str = "2026-07-28") -> dict:
    return {
        "id": article_id,
        "sourceId": "test-source",
        "title": article_id,
        "summary": article_id,
        "type": "公司动态",
        "region": "全球",
        "sector": "AI / AGI",
        "company": "科技产业",
        "publishedAt": published_at,
        "importance": 70,
        "source": {
            "name": "Test",
            "url": f"https://example.com/{article_id}",
            "level": "媒体报道",
            "platform": "Test",
        },
    }


class FullRefreshAuditTest(unittest.TestCase):
    def test_prepare_and_finalize_publish_new_article_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "articles.json"
            baseline_path = Path(tmp) / "refresh-baseline.json"
            path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 3,
                        "generatedAt": "2026-07-28T00:00:00Z",
                        "articleCount": 2,
                        "articles": [article("existing-a"), article("existing-b")],
                        "sourceStatus": [{"id": "old", "status": "ok"}],
                        "qualityGate": {"passed": True},
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(prepare_full_refresh, "ARTICLES_PATH", path),
                patch.object(prepare_full_refresh, "BASELINE_PATH", baseline_path),
            ):
                self.assertEqual(prepare_full_refresh.main(), 0)

            prepared = json.loads(path.read_text(encoding="utf-8"))
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            self.assertEqual(baseline["articleCount"], 2)
            self.assertNotIn("_refreshBaseline", prepared)
            self.assertEqual(prepared["sourceStatus"], [])

            # Simulate a crawler rebuilding the public payload from its known
            # schema fields. The external baseline must remain available.
            prepared = {
                "schemaVersion": prepared["schemaVersion"],
                "generatedAt": "2026-07-28T01:00:00Z",
                "articleCount": 3,
                "articles": [
                    *prepared["articles"],
                    article("new-c"),
                ],
                "sourceStatus": [],
                "qualityGate": {"passed": True},
            }
            path.write_text(json.dumps(prepared), encoding="utf-8")

            with (
                patch.object(finalize_full_refresh, "ARTICLES_PATH", path),
                patch.object(finalize_full_refresh, "BASELINE_PATH", baseline_path),
            ):
                self.assertEqual(finalize_full_refresh.main(), 0)
                self.assertFalse(baseline_path.exists())
                self.assertEqual(finalize_full_refresh.main(), 0)

            finalized = json.loads(path.read_text(encoding="utf-8"))
            audit = finalized["refreshAudit"]
            self.assertEqual(audit["previousArticleCount"], 2)
            self.assertEqual(audit["newArticleCount"], 1)
            self.assertEqual(audit["articleCount"], 3)
            self.assertTrue(audit["pipelineCompleted"])
            self.assertEqual(audit["lastFullRefreshAt"], audit["completedAt"])


if __name__ == "__main__":
    unittest.main()
