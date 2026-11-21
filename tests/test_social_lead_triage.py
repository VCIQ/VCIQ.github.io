"""Explainable background gate: synthetic controls and immutable review history."""
import copy
import unittest
from tests.social_review_fixtures import rows, registry
from tools.social.lead_builder import build_leads
from tools.social.lead_triage import classify_material


class BackgroundGateTests(unittest.TestCase):
    def build(self, title, excerpt="机器人是指能执行任务的系统。简单来说，它与环境交互。", companies=None):
        doc = rows(title=title, excerpt=excerpt)[2][0]
        before = copy.deepcopy(doc)
        result = build_leads(doc, registry() if companies is None else companies)
        self.assertEqual(before, doc)
        return result

    def test_generic_explainer_not_company_discovery(self):
        self.assertEqual(self.build("看懂爆火的机器人"), [])

    def test_education_words_do_not_create_event_candidates(self):
        self.assertEqual(self.build("机器人入门教程：融资、投资、技术、发布与上市是什么"), [])

    def test_known_company_mention_alone_does_not_rescue_primer(self):
        index = registry({"slug":"synthetic", "name":"合成甲公司", "aliases":[]})
        self.assertEqual(self.build("机器人科普", "以合成甲公司为例讲解机器人基本概念。", index), [])

    def test_report_in_explainer_title_remains_unverified(self):
        result = self.build("一文读懂机器人融资：合成甲公司完成A轮融资", "该公司宣布获得新融资。")
        self.assertTrue(result)
        self.assertFalse(result[0]["snapshot"]["factVerified"])
        self.assertIsNone(result[0]["item"]["subject"]["companyId"])

    def test_unknown_company_event_in_body_is_retained(self):
        self.assertTrue(self.build("机器人科普与行业动态", "未登记公司宣布完成B轮融资。"))

    def test_explicit_denial_of_event_remains_reviewable(self):
        self.assertTrue(self.build("机器人科普与辟谣", "合成甲公司否认已完成融资。"))

    def test_hypothetical_example_not_event_evidence(self):
        self.assertEqual(self.build("机器人融资入门", "例如甲公司完成A轮融资，这只是一个假设。"), [])

    def test_conditional_example_not_event_evidence(self):
        self.assertEqual(self.build("机器人融资教程", "如果企业完成亿元融资，就可能扩大规模。"), [])

    def test_mixed_actual_and_hypothetical_sentences_retained(self):
        self.assertTrue(self.build("机器人融资入门", "例如甲公司完成融资。乙公司宣布完成B轮融资。"))

    def test_concrete_product_report_retained(self):
        self.assertTrue(self.build("看懂机器人产品", "合成甲公司正式发布机器人新品。"))

    def test_concrete_technology_report_retained(self):
        self.assertTrue(self.build("机器人技术科普", "合成大学实验室首次开源机器人控制模型。"))

    def test_concrete_listing_report_retained(self):
        self.assertTrue(self.build("机器人上市科普", "合成甲公司递交上市申请。"))

    def test_english_explainer_is_background(self):
        value = classify_material("Robotics explained", "A robot refers to a machine. It is defined as an embodied system.")
        self.assertEqual(value["disposition"], "background")

    def test_english_funding_report_retained(self):
        self.assertEqual(classify_material("Robotics explained", "Synthetic Labs raised five million in funding.")["disposition"], "reviewable")

    def test_english_hypothetical_not_event_evidence(self):
        self.assertEqual(classify_material("Robotics tutorial", "For example, Synthetic Labs raised five million in funding.")["disposition"], "background")

    def test_one_definition_without_title_cue_is_not_overfiltered(self):
        self.assertEqual(classify_material("机器人新闻", "机器人是指一种系统。还有企业动态。")["disposition"], "reviewable")

    def test_two_definition_cues_without_event_is_background(self):
        self.assertEqual(classify_material("机器人概念", "机器人是指一种系统，简单来说可以执行任务。")["disposition"], "background")

    def test_event_not_invented_across_sentences(self):
        self.assertEqual(classify_material("机器人教程", "完成。融资。")["disposition"], "background")

    def test_unicode_normalization_and_case(self):
        self.assertEqual(classify_material("ＲＯＢＯＴＩＣＳ ＥＸＰＬＡＩＮＥＤ", "概念说明")["disposition"], "background")

    def test_concrete_report_is_not_fact_verification(self):
        value = classify_material("科普与新消息", "甲公司宣布完成融资。")
        self.assertFalse(value["factVerified"])
        self.assertEqual(value["reason"], "MIXED_REPORT_REQUIRES_REVIEW")

    def test_existing_plain_event_categories_are_unchanged(self):
        self.assertTrue(self.build("机器人融资", "未核验的具体消息。"))

    def test_unrelated_explainer_not_retained(self):
        self.assertEqual(self.build("无关教程", "与赛道无关。"), [])


if __name__ == "__main__": unittest.main()
