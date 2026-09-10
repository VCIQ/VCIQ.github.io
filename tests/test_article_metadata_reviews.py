import copy
import unittest

from tools.article_metadata_reviews import apply_article_metadata_review, metadata_reviews
from tools.article_publication_gate import filter_publishable_articles


class ArticleMetadataReviewTests(unittest.TestCase):
    def article(self, review):
        return {
            "id": review["articleId"], "sourceId": review["sourceId"], "title": review["expectedTitle"],
            "summary": "archived summary", "sector": "AI / AGI", "type": "公司动态", "importance": 80,
            "publishedAt": "2026-09-07", "company": "company", "qualityStatus": "可用",
            "source": {"url": review["sourceUrl"], "level": "媒体报道", "sourceRole": "corroboration"},
            "trackSlugs": [*review["removeTrackSlugs"], "unrelated-track"],
            **{key: change["from"] for key, change in review["fields"].items()},
        }

    def test_five_bounded_reviews_and_idempotence(self):
        for review in metadata_reviews():
            with self.subTest(review=review["id"]):
                original = self.article(review)
                frozen = copy.deepcopy(original)
                corrected = apply_article_metadata_review(original)
                for key, change in review["fields"].items():
                    self.assertEqual(corrected[key], change["to"])
                for key in ("id", "title", "summary", "importance", "source", "publishedAt", "qualityStatus"):
                    self.assertEqual(corrected[key], original[key])
                self.assertEqual(original, frozen)
                self.assertIs(apply_article_metadata_review(corrected), corrected)
                self.assertIn("unrelated-track", corrected["trackSlugs"])
                for slug in review["removeTrackSlugs"]:
                    self.assertNotIn(slug, corrected["trackSlugs"])

    def test_exact_record_boundary(self):
        for review in metadata_reviews():
            original = self.article(review)
            for field, value in (
                ("id", "different-article-id"),
                ("title", "different event"),
                ("sourceId", "different source"),
            ):
                changed = {**original, field: value}
                self.assertIs(apply_article_metadata_review(changed), changed)
            for url in (
                review["sourceUrl"] + "?article=other",
                "javascript:alert(1)",
                "not-a-url",
                review["sourceUrl"].replace("https://", "https://u:p@"),
            ):
                changed = {**original, "source": {**original["source"], "url": url}}
                self.assertIs(apply_article_metadata_review(changed), changed)

    def test_tracking_suffix_does_not_change_material_identity(self):
        for review in metadata_reviews():
            original = self.article(review)
            original["source"]["url"] += "?utm_source=test&fbclid=tracking#top"
            corrected = apply_article_metadata_review(original)
            for key, change in review["fields"].items():
                self.assertEqual(corrected[key], change["to"])

    def test_newer_different_metadata_is_not_overwritten(self):
        review = metadata_reviews()[0]
        row = {**self.article(review), "sector": "新材料"}
        self.assertIs(apply_article_metadata_review(row), row)

    def test_real_publication_gate_applies_reviews(self):
        original = [self.article(review) for review in metadata_reviews()]
        frozen = copy.deepcopy(original)
        published, report = filter_publishable_articles(original)
        self.assertEqual(len(published), len(original))
        self.assertEqual(report["corroboration"], len(original))
        for row, review in zip(published, metadata_reviews()):
            for key, change in review["fields"].items():
                self.assertEqual(row[key], change["to"])
        self.assertEqual(original, frozen)

    def test_review_does_not_authorize_a_discovery_source(self):
        review = next(r for r in metadata_reviews() if r["id"] == "form-energy-technician-hiring")
        row = self.article(review)
        row["source"]["sourceRole"] = "discovery"
        row["source"]["level"] = "待交叉验证"
        published, report = filter_publishable_articles([row])
        self.assertEqual(published, [])
        self.assertEqual(report["discoveryHeld"], 1)


if __name__ == "__main__":
    unittest.main()
