"""Contract integration for synthetic XHS records; no live platform traffic."""
import copy
import unittest
from datetime import UTC, datetime
from tests.test_social_contracts import fixture
from tools.social.adapters.xhs import normalize_record, finalize, metric
from tools.social.contracts import ContractError
from workers.mediacrawler.observer import select_record

STAMP = "2026-10-23T12:00:00+00:00"
ID = "0" * 23 + "1"
PATCHES = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"


def inputs():
    job = fixture("crawl_job", "xhs")
    context = {"terms": [{"text": job["query"]["text"]}]}
    row = {"note_id": ID, "title": "合成测试机器人产品发布", "desc": "合成测试机器人：仅为测试数据。",
        "time": 0, "last_update_time": 0, "nickname": "合成名字", "creator_hash": "a" * 64,
        "liked_count": "1.2万", "comment_count": "--", "share_count": "7"}
    return job, context, row


def captured(job, row):
    return {"version": 1, "attemptId": job["attemptId"], "queryId": job["queryId"],
        "startedAt": STAMP, "completedAt": STAMP,
        "pages": [{"pageIndex": 1, "schemaValid": True, "contentItems": 1, "processed": True, "hasMore": False}],
        "records": [select_record(row, original_title=True, observed_at=STAMP)],
        "detailFailures": 0, "searchDuplicates": 0, "detailsNotRequested": 0,
        "status": "ok", "stopReason": "exhausted", "errorCode": None, "retryAfter": None}


class XhsNormalizerTests(unittest.TestCase):
    def normalize(self, row=None, *, title=True):
        job, context, original = inputs()
        return normalize_record(original if row is None else row, job, context, observed_at=STAMP, original_title=title)

    def test_unknown_date_is_not_observation_time(self):
        result = self.normalize()
        self.assertIsNone(result["publishedAt"])
        self.assertEqual(result["publishedPrecision"], "unknown")
        self.assertEqual(result["observedAt"], STAMP)

    def test_millisecond_time_only_no_unit_guessing(self):
        _, _, row = inputs()
        row["time"] = 1792670400000
        self.assertEqual(self.normalize(row)["publishedAt"], "2026-10-22T12:00:00+00:00")
        for value in (1792670400, True, 999999999999999):
            row["time"] = value
            with self.assertRaises(ContractError): self.normalize(row)

    def test_update_cannot_precede_publication(self):
        _, _, row = inputs()
        row.update(time=1792670400000, last_update_time=1792584000000)
        with self.assertRaisesRegex(ContractError, "xhs_update_before_publication"):
            self.normalize(row)

    def test_title_provenance_is_not_invented(self):
        self.assertEqual(self.normalize(title=False)["titleOrigin"], "derived")
        _, _, row = inputs()
        row["title"] = ""
        self.assertEqual(self.normalize(row)["titleOrigin"], "derived")
        row["desc"] = ""
        self.assertEqual(self.normalize(row)["titleOrigin"], "missing")

    def test_token_and_original_profile_do_not_escape(self):
        _, _, row = inputs()
        row.update(xsec_token="SYNTHETIC_PRIVATE", note_url="https://www.xiaohongshu.com/explore/" + ID + "?xsec_token=SYNTHETIC_PRIVATE", user_id="SYNTHETIC_USER", avatar="private")
        result = self.normalize(row)
        self.assertNotIn("SYNTHETIC_PRIVATE", repr(result))
        self.assertNotIn("SYNTHETIC_USER", repr(result))
        self.assertNotIn("?", result["canonicalUrl"])
        self.assertEqual(result["author"]["displayName"], "合***")
        self.assertEqual(result["entityCandidates"], [])
        self.assertEqual(result["evidence"]["role"], "discovery")
        self.assertEqual(result["accessStatus"], "unverified")

    def test_secrets_embedded_in_text_rejected(self):
        _, _, row = inputs()
        row["desc"] = "cookie=SYNTHETIC_PRIVATE"
        with self.assertRaises(ContractError) as error: self.normalize(row)
        self.assertNotIn("SYNTHETIC_PRIVATE", str(error.exception))

    def test_unknown_creator_identity_not_confirmed(self):
        _, _, row = inputs()
        row["creator_hash"] = "not a hash"
        self.assertIsNone(self.normalize(row)["author"]["creatorKey"])

    def test_metrics_approximate_and_unknown_are_distinct(self):
        self.assertEqual(metric("1.2万"), {"value": 12000, "approximate": True})
        self.assertEqual(metric("1,234"), {"value": 1234, "approximate": False})
        self.assertEqual(metric("--"), {"value": None, "approximate": False})
        with self.assertRaises(ContractError): metric(True)

    def test_content_identity_ignores_metrics_and_query_tokens(self):
        _, _, row = inputs()
        before = self.normalize(row)
        row["liked_count"] = "300"
        row["xsec_token"] = "SYNTHETIC_OTHER"
        after = self.normalize(row)
        self.assertEqual(before["signalId"], after["signalId"])
        self.assertEqual(before["contentHash"], after["contentHash"])

    def test_match_terms_require_visible_evidence(self):
        _, _, row = inputs()
        row.update(title="无关内容", desc="无关摘要")
        result = self.normalize(row)
        self.assertEqual(result["matchedTerms"], [])
        self.assertNotEqual(result["queryTerms"], [])

    def test_finalize_counts_and_real_page_proof(self):
        job, context, row = inputs()
        result = finalize(job, captured(job, row), context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "ok")
        self.assertEqual(result["receipt"]["counts"]["rawRows"], 1)
        self.assertEqual(result["receipt"]["counts"]["emittedRows"], 1)
        self.assertFalse(result["diagnostics"]["batchIntegrityChecked"])

    def test_good_record_and_later_failure_become_partial(self):
        job, context, row = inputs()
        value = captured(job, row)
        value.update(status="network_error", stopReason="network", errorCode="DETAIL_FAILED", detailFailures=1)
        result = finalize(job, value, context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "partial")
        self.assertEqual(len(result["observations"]), 1)

    def test_auth_after_data_still_pauses_instead_of_partial(self):
        job, context, row = inputs()
        value = captured(job, row)
        value.update(status="auth_required", stopReason="auth", errorCode="AUTH")
        self.assertEqual(finalize(job, value, context, patchset_hash=PATCHES)["receipt"]["status"], "auth_required")

    def test_corrupt_identity_and_missing_pages_rejected(self):
        job, context, row = inputs()
        for change in ("attempt", "pages", "oversized"):
            value = captured(job, row)
            if change == "attempt": value["attemptId"] = "bad"
            if change == "pages": value["pages"] = []
            if change == "oversized": value["records"] *= 21
            with self.assertRaises(ContractError): finalize(job, value, context, patchset_hash=PATCHES)

    def test_sensitive_row_rejected_without_disclosure_or_success(self):
        job, context, row = inputs()
        row["desc"] = "authorization=PRIVATE_SYNTHETIC"
        result = finalize(job, captured(job, row), context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "schema_error")
        self.assertEqual(result["receipt"]["counts"]["rejectedRows"], 1)
        self.assertNotIn("PRIVATE_SYNTHETIC", repr(result))

    def test_post_filter_unknown_date_does_not_invent_one(self):
        job, context, row = inputs()
        job["window"] = {"from": "2026-10-01", "to": None, "filterMode": "post_filter"}
        result = finalize(job, captured(job, row), context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "ok")
        self.assertEqual(result["observations"], [])
        self.assertEqual(result["receipt"]["counts"]["rejectedRows"], 1)


if __name__ == "__main__": unittest.main()
