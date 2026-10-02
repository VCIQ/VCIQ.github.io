import copy
import json
import unittest
from tools.project_article_review_runtime import ROOT, FIELDS, project


class ReviewProjectionTests(unittest.TestCase):
    def test_committed_projection_exactly_matches_authoritative_rules(self):
        manifest = json.loads((ROOT / "config/article_metadata_reviews.json").read_text(encoding="utf-8"))
        runtime = json.loads((ROOT / "config/article_metadata_runtime.json").read_text(encoding="utf-8"))
        before = copy.deepcopy(manifest)
        self.assertEqual(runtime, project(manifest))
        self.assertEqual(manifest, before)
        for row, original in zip(runtime["reviews"], manifest["reviews"]):
            self.assertEqual(row["fields"], original["fields"])
            self.assertFalse(set(row) - set(FIELDS))
        self.assertLess(len(json.dumps(runtime, ensure_ascii=False).encode()),
                        len(json.dumps(manifest, ensure_ascii=False).encode()) - 1000)

    def test_unknown_manifest_schema_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            project({"schemaVersion": 2, "reviews": []})
