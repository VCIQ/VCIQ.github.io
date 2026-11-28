import json
import unittest
from pathlib import Path

from tools.prelisting_event_dedupe import (
    cluster_candidates,
    extract_amount,
    extract_round,
)


class PrelistingEventDedupeTests(unittest.TestCase):
    def test_source_retains_investor_extraction_provenance(self):
        rows = [
            {"company": "杉数科技", "title": "杉数科技完成D轮融资，红杉中国领投", "publishedAt": "2026-11-22", "subjectRole": "funding_subject", "publisherUrl": "https://news.example/a"},
        ]
        source = cluster_candidates(rows)[0]["sources"][0]
        self.assertEqual(source["investorsExtracted"], ["红杉中国"])
        self.assertEqual(source["investorExtractionMethod"], "title_explicit_pattern")
        self.assertEqual(source["investorEvidenceStatus"], "DISCOVERED")

    def test_investor_role_extraction_rejects_generic_and_unrelated_phrases(self):
        from tools.prelisting_event_dedupe import extract_investor_mentions
        text = "九大券商集体参投DeepSeek。还可能通过另类投资子公司参与IPO。红杉中国领投，深创投跟投。"
        mentions = extract_investor_mentions(text)
        pairs = {(item["name"], item["role"]) for item in mentions}
        self.assertIn(("红杉中国", "lead"), pairs)
        self.assertIn(("深创投", "follow"), pairs)
        self.assertNotIn(("九大券商集体", "participant"), pairs)
        self.assertNotIn(("还可能通过另类投资子公司参与IPO", "follow"), pairs)
        self.assertTrue(all(item.get("evidenceText") for item in mentions))

    def test_extract_explicit_investor_list_without_splitting_legal_name(self):
        from tools.prelisting_event_dedupe import extract_investor_mentions
        text = "本轮融资由亦庄国投屹唐盛和基金、启明创投、朝晖资本联合领投。"
        mentions = extract_investor_mentions(text)
        pairs = {(item["name"], item["role"]) for item in mentions}
        self.assertIn(("亦庄国投屹唐盛和基金", "lead"), pairs)
        self.assertIn(("启明创投", "lead"), pairs)
        self.assertIn(("朝晖资本", "lead"), pairs)
        self.assertNotIn(("基金", "lead"), pairs)

    def test_source_backed_annotation_candidate_extracts_investor_list(self):
        from tools.prelisting_event_dedupe import extract_investor_mentions
        fixture_path = Path(__file__).parent / "fixtures" / "prelisting_investor_annotation_candidates.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        record = fixture["records"][0]
        self.assertEqual(record["annotationStatus"], "pending_human_confirmation")
        self.assertIsNone(record["eventDate"])
        self.assertEqual(record["candidatePublishedAt"], "2026-11-17")
        self.assertEqual(record["bodyDisplayedPublicationTime"], "2026-11-18 22:58")
        self.assertTrue(record["publicationDateConflict"])
        mentions = extract_investor_mentions(record["evidenceText"])
        self.assertEqual(
            {item["name"] for item in mentions},
            set(record["investors"]),
        )
        self.assertTrue(all(item["role"] == "investor_label" for item in mentions))

    def test_extract_investor_list_including_plain_investor_field(self):
        from tools.prelisting_event_dedupe import extract_investor_mentions
        text = "本轮投资方包括洪泰基金、弘毅投资、中关村科学城、浙创投。"
        mentions = extract_investor_mentions(text)
        names = {item["name"] for item in mentions}
        self.assertEqual(names, {"洪泰基金", "弘毅投资", "中关村科学城", "浙创投"})

    def test_extract_investor_roles_from_body(self):
        from tools.prelisting_event_dedupe import extract_investor_mentions
        mentions = extract_investor_mentions("红杉中国领投，深创投跟投，腾讯投资参与投资。")
        roles = {(item["name"], item["role"]) for item in mentions}
        self.assertIn(("红杉中国", "lead"), roles)
        self.assertIn(("深创投", "follow"), roles)
        self.assertIn(("腾讯投资", "participant"), roles)

    def test_extract_explicit_lead_investor(self):
        from tools.prelisting_event_dedupe import extract_investors
        self.assertIn("红杉中国", extract_investors("杉数科技完成D轮融资，红杉中国领投"))

    def test_do_not_infer_investor_from_company_mention(self):
        from tools.prelisting_event_dedupe import extract_investors
        self.assertEqual(extract_investors("知乎回应间接投资DeepSeek"), [])

    def test_equivalent_rmb_amount_units_normalize(self):
        from tools.prelisting_event_dedupe import normalize_amount
        self.assertEqual(normalize_amount("20亿元"), normalize_amount("20亿人民币"))
        self.assertNotEqual(normalize_amount("20亿元"), normalize_amount("20亿美元"))

    def test_extract_round_and_amount(self):
        self.assertEqual(extract_round("杉数科技完成D轮融资，金额数亿元"), "D轮")
        self.assertEqual(extract_amount("完成融资，金额3.5亿元"), "3.5亿元")

    def test_same_round_same_month_cluster(self):
        rows = [
            {"company": "杉数科技", "title": "杉数科技完成D轮融资", "publishedAt": "2026-11-22", "eventDate": "2026-11-22", "subjectRole": "funding_subject"},
            {"company": "杉数科技", "title": "杉数科技获D轮融资，多家机构参与", "publishedAt": "2026-11-25", "eventDate": "2026-11-22", "subjectRole": "funding_subject"},
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
        self.assertEqual(groups[0]["eventType"], "investment_received")
        self.assertEqual(groups[0]["dedupeConfidence"], "singleton-unverified")

    def test_event_id_is_stable_across_headline_variants(self):
        from tools.prelisting_event_dedupe import event_fingerprint
        first = event_fingerprint("杉数科技", "financing", "D轮", None, "2026-11-22", "杉数科技完成D轮融资")
        second = event_fingerprint("杉数科技", "financing", "D轮", None, "2026-11-25", "杉数科技获D轮融资，多家机构参与")
        self.assertEqual(first, second)

    def test_conflicting_amounts_do_not_merge(self):
        rows = [
            {"company": "某科技", "title": "某科技完成B轮融资3亿元", "publishedAt": "2026-11-03", "subjectRole": "funding_subject"},
            {"company": "某科技", "title": "某科技完成B轮融资5亿元", "publishedAt": "2026-11-03", "subjectRole": "funding_subject"},
        ]
        self.assertEqual(len(cluster_candidates(rows)), 2)

    def test_plus_round_is_preserved(self):
        self.assertEqual(extract_round("某科技完成C+轮融资"), "C轮+")

    def test_distinct_same_month_events_get_unique_ids(self):
        rows = [
            {"company": "某科技", "title": "某科技完成B轮融资", "publishedAt": "2026-11-03", "subjectRole": "funding_subject", "investors": ["甲资本"], "publisherUrl": "https://a.example/news/1"},
            {"company": "某科技", "title": "某科技B轮融资落地", "publishedAt": "2026-11-03", "subjectRole": "funding_subject", "investors": ["乙资本"], "publisherUrl": "https://b.example/news/2"},
        ]
        groups = cluster_candidates(rows)
        self.assertEqual(len(groups), 2)
        self.assertEqual(len({g["eventId"] for g in groups}), 2)

    def test_duplicate_feed_rows_are_deduplicated(self):
        row = {"company": "开源中国", "title": "超智算科技携手共绩科技、开源中国达成战略合作", "publishedAt": "2026-08-22", "subjectRole": "partner", "publisherUrl": "https://news.example/item/1"}
        groups = cluster_candidates([row, dict(row)])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["candidateCount"], 1)
        self.assertEqual(len(groups[0]["sources"]), 1)

    def test_mentions_do_not_extract_financing_amount(self):
        rows = [
            {"company": "DeepSeek", "title": "95亿元！九大券商集体参投DeepSeek", "publishedAt": "2026-11-27", "subjectRole": "mentioned"},
        ]
        groups = cluster_candidates(rows)
        self.assertIsNone(groups[0]["amount"])

    def test_event_group_keeps_event_date_null_and_publication_date_separate(self):
        rows = [
            {"company": "某科技", "title": "某科技完成B轮融资", "publishedAt": "2026-11-25", "subjectRole": "funding_subject"},
        ]
        group = cluster_candidates(rows)[0]
        self.assertIsNone(group["eventDate"])
        self.assertEqual(group["publishedAt"], "2026-11-25")

    def test_published_at_is_not_assumed_to_be_event_date(self):
        rows = [
            {"company": "杉数科技", "title": "杉数科技完成D轮融资", "publishedAt": "2026-11-22", "subjectRole": "funding_subject"},
            {"company": "杉数科技", "title": "杉数科技获D轮融资，多家机构参与", "publishedAt": "2026-11-25", "subjectRole": "funding_subject"},
        ]
        groups = cluster_candidates(rows)
        self.assertEqual(len(groups), 2)
        self.assertTrue(all(g["dedupeConfidence"] == "singleton-unverified" for g in groups))

    def test_undated_items_remain_singletons(self):
        rows = [
            {"company": "企业甲", "title": "企业甲完成A轮融资", "subjectRole": "funding_subject"},
            {"company": "企业甲", "title": "企业甲获A轮融资", "subjectRole": "funding_subject"},
        ]
        self.assertEqual(len(cluster_candidates(rows)), 2)


if __name__ == "__main__":
    unittest.main()
