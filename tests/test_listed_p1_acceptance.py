import copy
import unittest
from dataclasses import replace
from tools.article_metadata_reviews import metadata_reviews, apply_article_metadata_review
from tools.crawl_official_companies import _article_from_page, load_registry


class ListedP1Acceptance(unittest.TestCase):
    def fixture(self):
        review = next(row for row in metadata_reviews() if row["id"] == "resonac-sic-not-nvidia")
        return {
            "id": review["articleId"], "sourceId": review["sourceId"],
            "title": review["expectedTitle"], "summary": "Resonac Holdings 开发300毫米SiC衬底",
            "company": "英伟达", "companySlug": "nvidia", "companySlugs": ["nvidia"],
            "companyMatch": {"slug": "nvidia", "method": "structured-company", "confidence": .97},
            "companyMatches": [{"slug": "nvidia", "method": "structured-company", "confidence": .97}],
            "companyCandidateSlugs": ["nvidia"], "mentionedCompanies": ["英伟达"],
            "publishedAt": "2026-09-29", "importance": 82, "qualityScore": 25, "qualityStatus": "低可信",
            "source": {"url": review["sourceUrl"], "level": "媒体报道"},
        }

    def test_correction_is_bounded_idempotent_and_non_promotional(self):
        raw = self.fixture(); before = copy.deepcopy(raw)
        result = apply_article_metadata_review(raw)
        self.assertEqual(raw, before)
        self.assertEqual(result["company"], "Resonac Holdings")
        for key in ["companySlug", "companySlugs", "companyMatch", "companyMatches", "companyCandidateSlugs"]:
            self.assertNotIn(key, result)
        self.assertEqual(result["mentionedCompanies"], ["Resonac Holdings"])
        for key in ["source", "importance", "publishedAt", "qualityScore", "qualityStatus"]:
            self.assertEqual(result[key], raw[key])
        self.assertIs(apply_article_metadata_review(result), result)

    def test_mismatching_or_newer_evidence_is_not_overwritten(self):
        for changes in [{"id": "other"}, {"sourceId": "other"}, {"title": "other"},
                        {"summary": "unrelated"}, {"company": "New reviewed company"},
                        {"source": {"url": "https://example.org/other"}}]:
            raw = {**self.fixture(), **changes}
            self.assertIs(apply_article_metadata_review(raw), raw)

    def test_rejections_distinguish_missing_date_and_entity_evidence(self):
        specs = load_registry()
        if isinstance(specs, tuple):
            specs = specs[0]
        spec = next(item for item in specs if item.slug == "nvidia")
        spec = replace(spec, require_entity_match=True, entity_aliases=("NVIDIA",))
        counts = {}
        self.assertIsNone(_article_from_page(spec, "https://nvidianews.nvidia.com/news/test", "<h1>NVIDIA launches a new system</h1>", counts))
        self.assertEqual(counts, {"missing-or-invalid-publication-date": 1})
        counts = {}
        self.assertIsNone(_article_from_page(spec, "https://nvidianews.nvidia.com/news/test", "<h1>Different company launches a new system</h1>", counts))
        self.assertEqual(counts, {"entity-not-in-title-or-summary": 1})


if __name__ == "__main__":
    unittest.main()
