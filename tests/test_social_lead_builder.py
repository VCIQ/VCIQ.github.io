"""Conservative classifications and stable fingerprints, entirely synthetic."""
import copy
import unittest
from unittest.mock import patch

from tests.social_review_fixtures import rows, registry, request
from tools.social.contracts import ContractError, content_hash
from tools.social.lead_builder import build_leads, company_index, validate_item, mentioned
from tools.social.innovation_bridge import final_decision


class LeadBuilderTests(unittest.TestCase):
    def doc(self, **kwargs): return rows(**kwargs)[2][0]
    def build(self, **kwargs): return build_leads(self.doc(**kwargs), registry())

    def test_all_five_lead_types(self):
        for word, kind in (("融资", "funding"), ("发布", "product"), ("论文", "technology"), ("IPO", "listing"), ("动态", "company_discovery")):
            with self.subTest(kind=kind): self.assertEqual(self.build(title="机器人 " + word)[0]["item"]["leadType"], kind)

    def test_not_every_technology_item_is_listing(self):
        self.assertEqual([p["item"]["leadType"] for p in self.build(title="机器人 技术论文")], ["technology"])

    def test_product_launch_timing_is_not_a_listing(self):
        leads = self.build(title="合成机器人技术进展", excerpt="新机型预计年底正式推出，尚未公布上市日期。")
        self.assertEqual([p["item"]["leadType"] for p in leads], ["technology"])

    def test_product_launch_timing_does_not_hide_separate_listing(self):
        leads = self.build(title="机器人公司计划在交易所上市", excerpt="新机型预计正式推出，暂未确定上市时间。")
        self.assertIn("listing", [p["item"]["leadType"] for p in leads])

    def test_product_launch_timing_does_not_hide_an_explicit_ipo_cue(self):
        leads = self.build(title="机器人公司递交 IPO 申请", excerpt="新机型预计正式推出，暂未确定上市时间。")
        self.assertIn("listing", [p["item"]["leadType"] for p in leads])

    def test_non_product_announcement_preserves_listing_timing(self):
        leads = self.build(title="机器人公司动态", excerpt="公司正式发布经营数据，同时确认上市时间。")
        self.assertIn("listing", [p["item"]["leadType"] for p in leads])

    def test_denial_remains_quoted_not_confirmed(self):
        lead = self.build(title="机器人公司否认融资")[0]
        self.assertIn("否认融资", lead["item"]["claims"][0])
        self.assertFalse(lead["snapshot"]["factVerified"])

    def test_unique_name_is_only_a_suggestion(self):
        index = registry({"slug": "synthetic", "name": "合成甲公司", "aliases": []})
        lead = build_leads(self.doc(title="合成甲公司 机器人发布"), index)[0]
        self.assertIsNone(lead["item"]["subject"]["companyId"])
        self.assertEqual(lead["item"]["subject"]["resolution"], "unresolved")
        self.assertEqual(lead["snapshot"]["companySuggestions"][0]["companyId"], "synthetic")

    def test_same_alias_is_ambiguous(self):
        index = registry(*({"slug": x, "name": x, "aliases": ["同名公司"]} for x in ("one", "two")))
        lead = build_leads(self.doc(title="同名公司机器人融资"), index)[0]
        self.assertEqual(lead["item"]["subject"]["resolution"], "ambiguous")
        self.assertIsNone(lead["item"]["subject"]["companyId"])

    def test_author_name_is_not_entity_evidence(self):
        doc = self.doc(); doc["author"]["displayName"] = "合成甲公司"
        lead = build_leads(doc, registry({"slug": "one", "name": "合成甲公司", "aliases": []}))[0]
        self.assertEqual(lead["snapshot"]["companySuggestions"], [])

    def test_unrelated_material_does_not_enter_queue(self):
        doc = self.doc(title="无关素材", excerpt="一般讨论")
        self.assertEqual(build_leads(doc, registry()), [])

    def test_latin_matching_not_substring(self):
        self.assertFalse(mentioned("AI", "CHAIR"))
        self.assertTrue(mentioned("AI", "AI product"))

    def test_unknown_company_is_retained_unresolved(self):
        lead = self.build(title="未登记的机器人团队融资")[0]
        self.assertIsNone(lead["item"]["subject"]["companyId"])
        self.assertEqual(lead["item"]["subject"]["resolution"], "unresolved")

    def test_engagement_time_and_query_do_not_change_revision(self):
        doc = self.doc(); before = build_leads(doc, registry())[0]["item"]
        doc["metrics"]["likes"]["value"] = 99
        doc["observedAt"] = "2026-10-25T12:00:00Z"
        self.assertEqual(before, build_leads(doc, registry())[0]["item"])

    def test_body_change_requires_new_revision(self):
        first = self.build()[0]["item"]; second = self.build(excerpt="正文内容变化")[0]["item"]
        self.assertEqual(first["leadId"], second["leadId"])
        self.assertNotEqual(first["candidateFingerprint"], second["candidateFingerprint"])

    def test_same_title_different_content_is_not_merged(self):
        one = self.build(platform="xhs")[0]["item"]; two = self.build(platform="wb")[0]["item"]
        self.assertNotEqual(one["leadId"], two["leadId"])

    def test_registry_reorder_is_stable(self):
        companies = [{"slug": "b", "name": "乙公司", "aliases": []}, {"slug": "a", "name": "甲公司", "aliases": []}]
        self.assertEqual(registry(*companies), registry(*reversed(companies)))

    def test_invalid_duplicate_or_sensitive_registry_rejected(self):
        for payload in ({}, {"companies": [{"slug": "x", "name": "甲", "aliases": "bad"}]}, {"companies": [{"slug": "x", "name": "Cookie=PRIVATE"}]}):
            with self.assertRaises(ContractError): company_index(payload)
        with self.assertRaises(ContractError): registry({"slug": "x", "name": "甲"}, {"slug": "x", "name": "乙"})

    def test_inputs_not_mutated(self):
        doc = self.doc(); original = copy.deepcopy(doc)
        lead = build_leads(doc, registry())[0]
        lead["snapshot"]["observation"]["title"] = "mutated"
        self.assertEqual(doc, original)

    def test_fingerprint_tamper_rejected(self):
        item = self.build()[0]["item"]; item["claims"] = ["changed"]
        with self.assertRaisesRegex(ContractError, "review_fingerprint"): validate_item(item)

    def test_listing_uses_existing_pure_function_without_writers(self):
        from tools import innovation_listing_candidate_review as original
        item = self.build(title="机器人 IPO")[0]["item"]
        with patch.object(original, "write_json", side_effect=AssertionError("production write")), patch.object(original, "apply_decision", wraps=original.apply_decision) as called:
            result = final_decision(item, request(item))
        self.assertEqual(called.call_count, 1)
        self.assertEqual(result["promotionStatus"], "awaiting-primary-evidence")
        self.assertFalse(result["productionChanged"])

    def test_other_types_not_disguised_as_listing(self):
        from tools import innovation_listing_candidate_review as original
        item = self.build()[0]["item"]
        with patch.object(original, "apply_decision", side_effect=AssertionError("wrong type")):
            self.assertEqual(final_decision(item, request(item, "rejected"))["promotionStatus"], "rejected")

    def test_bridge_refuses_fingerprint_mismatch(self):
        item = self.build()[0]["item"]; command = request(item); command["candidateFingerprint"] = "a" * 64
        with self.assertRaisesRegex(ContractError, "evidence_changed"): final_decision(item, command)


if __name__ == "__main__": unittest.main()
