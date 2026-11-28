import unittest

from tools.prelisting_event_dedupe import (
    cluster_candidates,
    extract_amount,
    extract_round,
)


class PrelistingEventDedupeTests(unittest.TestCase):
    def test_extract_round_and_amount(self):
        self.assertEqual(extract_round("杉数科技完成D轮融资，金额数亿元"), "D轮")
        self.assertEqual(extract_amount("完成融资，金额3.5亿元"), "3.5亿元")

    def test_same_round_same_month_cluster(self):
        rows = [
            {"company": "杉数科技", "title": "杉数科技完成D轮融资", "publishedAt": "2026-11-22", "subjectRole": "funding_subject"},
            {"company": "杉数科技", "title": "杉数科技获D轮融资，多家机构参与", "publishedAt": "2026-11-25", "subjectRole": "funding_subject"},
        ]
        groups = cluster_candidates(rows)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["candidateCount"], 2)
        self.assertEqual(groups[0]["eventStatus"], "DISCOVERED")

    def test_different_rounds_do_not_merge(self):
        rows = [
            {"company": "诺顶智能", "title": "诺顶智能完成B轮融资", "publishedAt": "2026-11-02", "subjectRole": "funding_subject"},
            {"company": "诺顶智能", "title": "诺顶智能完成C轮融资", "publishedAt": "2026-11-20", "subjectRole": "funding_subject"},
        ]
        self.assertEqual(len(cluster_candidates(rows)), 2)

    def test_investor_story_is_not_clustered_as_company_funding(self):
        rows = [
            {"company": "DeepSeek", "title": "知乎回应间接投资DeepSeek", "publishedAt": "2026-11-20", "subjectRole": "investee"},
        ]
        groups = cluster_candidates(rows)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["eventType"], "unclassified")
        self.assertEqual(groups[0]["dedupeConfidence"], "singleton-unverified")

    def test_undated_items_remain_singletons(self):
        rows = [
            {"company": "企业甲", "title": "企业甲完成A轮融资", "subjectRole": "funding_subject"},
            {"company": "企业甲", "title": "企业甲获A轮融资", "subjectRole": "funding_subject"},
        ]
        self.assertEqual(len(cluster_candidates(rows)), 2)


if __name__ == "__main__":
    unittest.main()
