"""Offline safety regressions for historical WeChat link repair review."""
import copy
import unittest

from tools.wechat_historical_link_review import historical_temporary_rows, validate

SIGNED = "https://mp.weixin.qq.com/s?signature=expired&timestamp=1793&src=11&ver=7000&new=1"
SHARE = "https://mp.weixin.qq.com/s/hNvk76l8FzVEhglIQqebJg"


def fixture():
    a = {"id": "wx-old", "sourceId": "user-track-wechat-ai", "title": "测试公众号科技报道",
         "wechatAccount": "示例科技", "publishedAt": "2026-10-21",
         "source": {"platform": "微信", "url": SIGNED}}
    snapshot = {"generatedAt": "2026-11-19T00:00:00Z", "articles": [
        a, {"id": "wx-good", "source": {"platform": "微信", "url": SHARE}},
        {"id": "web", "source": {"platform": "官网", "url": "https://example.org/"}}]}
    row = {"articleId": "wx-old", "sourceId": a["sourceId"], "title": a["title"],
           "wechatAccount": a["wechatAccount"], "publishedAt": a["publishedAt"],
           "originalLinkStatus": "temporary-signed", "priority": "P0",
           "reviewStatus": "pending-original-verification", "reviewDecision": "pending",
           "verifiedOriginalWechatUrl": None, "approvedReplacementUrl": None,
           "appliedToProduction": False, "alternativeCandidates": []}
    q = {"schemaVersion": 1, "mode": "review-only",
         "snapshot": {"generatedAt": snapshot["generatedAt"], "articleCount": 3,
                      "temporaryWechatArticles": 1}, "articles": [row]}
    return snapshot, q


class HistoricalWeChatReviewTests(unittest.TestCase):
    def test_captures_only_temporary_links(self):
        s, q = fixture()
        self.assertEqual(list(historical_temporary_rows(s)), ["wx-old"])
        self.assertEqual(validate(s, q)["status"], "ok")

    def test_snapshot_drift_is_rejected(self):
        s, q = fixture()
        s["generatedAt"] = "2026-11-20T00:00:00Z"
        self.assertEqual(validate(s, q)["status"], "invalid")

    def test_queue_missing_one_article_is_rejected(self):
        s, q = fixture()
        q["articles"].clear()
        self.assertEqual(validate(s, q)["status"], "invalid")

    def test_unapproved_replacement_is_rejected(self):
        s, q = fixture()
        q["articles"][0]["approvedReplacementUrl"] = "https://example.org/"
        self.assertEqual(validate(s, q)["status"], "invalid")

    def test_forged_human_review_is_rejected(self):
        s, q = fixture()
        q["articles"][0]["reviewDecision"] = "approved"
        self.assertEqual(validate(s, q)["status"], "invalid")

    def test_signed_candidate_is_rejected(self):
        s, q = fixture()
        q["articles"][0]["alternativeCandidates"] = [{
            "url": SIGNED, "kind": "non-wechat-alternative", "reviewStatus": "pending",
            "publisher": "第三方", "relationship": "index",
            "verifiedAsOriginalWechat": False, "approvedForReplacement": False}]
        self.assertEqual(validate(s, q)["status"], "invalid")

    def test_official_alternative_still_does_not_count_as_original(self):
        s, q = fixture()
        q["articles"][0]["alternativeCandidates"] = [{
            "url": "https://www.goodix.com/zh/news", "kind": "non-wechat-alternative",
            "reviewStatus": "pending", "publisher": "官网", "relationship": "same-title",
            "verifiedAsOriginalWechat": False, "approvedForReplacement": False}]
        report = validate(s, q)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["alternativeCandidates"], 1)
        self.assertEqual(report["verifiedOriginalWechat"], 0)

    def test_full_wechat_candidate_stays_pending(self):
        s, q = fixture()
        q["articles"][0]["originalWechatCandidates"] = [{
            "url": "https://mp.weixin.qq.com/s?__biz=MzA3&mid=2651072888&idx=3&sn=abcd",
            "accessStatus": "not-verified", "humanReviewStatus": "pending",
            "publisherIdentityConfirmedFromWeChat": False,
            "approvedForReplacement": False,
            "independentEvidenceUrls": [
                "https://robosignal.ai/items/abc",
                "https://www.lininn.cn/page/ai-daily"]
        }]
        result = validate(s, q)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["originalWechatCandidates"], 1)
        self.assertEqual(result["verifiedOriginalWechat"], 0)
        self.assertEqual(result["appliedToProduction"], 0)

    def test_temporary_or_offsite_original_candidate_is_rejected(self):
        s, q = fixture()
        q["articles"][0]["originalWechatCandidates"] = [{
            "url": SIGNED, "accessStatus": "not-verified",
            "humanReviewStatus": "pending",
            "publisherIdentityConfirmedFromWeChat": False,
            "approvedForReplacement": False,
            "independentEvidenceUrls": [
                "https://robosignal.ai/items/abc",
                "https://www.lininn.cn/page/ai-daily"]
        }]
        self.assertEqual(validate(s, q)["status"], "invalid")

    def test_original_candidate_cannot_forge_human_approval(self):
        s, q = fixture()
        q["articles"][0]["originalWechatCandidates"] = [{
            "url": "https://mp.weixin.qq.com/s?__biz=MzA3&mid=2651072888&idx=3&sn=abcd",
            "accessStatus": "verified", "humanReviewStatus": "approved",
            "publisherIdentityConfirmedFromWeChat": True,
            "approvedForReplacement": True,
            "independentEvidenceUrls": [
                "https://robosignal.ai/items/abc",
                "https://www.lininn.cn/page/ai-daily"]
        }]
        self.assertEqual(validate(s, q)["status"], "invalid")

    def test_original_candidate_needs_two_evidence_hosts(self):
        s, q = fixture()
        q["articles"][0]["originalWechatCandidates"] = [{
            "url": "https://mp.weixin.qq.com/s?__biz=MzA3&mid=2651072888&idx=3&sn=abcd",
            "accessStatus": "not-verified", "humanReviewStatus": "pending",
            "publisherIdentityConfirmedFromWeChat": False,
            "approvedForReplacement": False,
            "independentEvidenceUrls": [
                "https://robosignal.ai/items/abc",
                "https://robosignal.ai/items/def"]
        }]
        self.assertEqual(validate(s, q)["status"], "invalid")

    def test_source_identity_mismatch_is_rejected(self):
        s, q = fixture()
        q["articles"][0]["sourceId"] = "different"
        self.assertEqual(validate(s, q)["status"], "invalid")


if __name__ == "__main__":
    unittest.main()
