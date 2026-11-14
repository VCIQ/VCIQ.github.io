"""Weibo normalization and receipt regressions, all data synthetic."""
import copy
import unittest
from datetime import UTC, datetime

from tests.test_social_contracts import fixture
from tools.social.adapters import weibo
from tools.social.contracts import ContractError, validate
from workers.mediacrawler.observer import envelope

NOW = "2026-10-23T12:00:00+00:00"
ID = "9007199254740993123"
PATCHES = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"


def inputs():
    job = fixture("crawl_job", "wb")
    context = {"terms": [{"text": "机器人"}, {"text": "AI"}]}
    row = {"note_id": ID, "content": "<p>机器人 &amp; AI 发布合成测试产品</p>",
        "raw_created_at": "Thu Oct 22 12:00:00 +0800 2026", "create_time": 1792641600,
        "create_date_time": "2026-10-22 12:00:00+08:00", "liked_count": "1.2万",
        "comments_count": None, "shared_count": "0", "nickname": "合成作者", "creator_hash": "a" * 32}
    # Derive the fixture timestamp, rather than embedding a guessed epoch.
    row["create_time"] = int(datetime(2026, 10, 22, 4, tzinfo=UTC).timestamp())
    return job, context, row


def captured(job, row):
    result = envelope(job, clock=lambda: NOW)
    result.update(completedAt=NOW, status="ok", stopReason="page_limit")
    result["pages"] = [{"pageIndex": 1, "schemaValid": True, "contentItems": 1, "processed": True, "hasMore": None}]
    result["records"] = [{"record": row, "originalTitle": False, "observedAt": NOW}]
    return result


class WeiboNormalizerTests(unittest.TestCase):
    def norm(self, row=None, job=None, **kwargs):
        j, context, default = inputs()
        return weibo.normalize_record(row or default, job or j, context, observed_at=NOW, **kwargs)

    def test_exact_large_string_identity_and_derived_title(self):
        doc = self.norm()
        self.assertEqual(doc["nativeId"], ID)
        self.assertEqual(doc["canonicalUrl"], "https://m.weibo.cn/detail/" + ID)
        self.assertEqual(doc["titleOrigin"], "derived")
        self.assertNotIn("<p>", doc["excerpt"])
        self.assertIn("& AI", doc["excerpt"])
        self.assertEqual(doc["publishedAt"], "2026-10-22T04:00:00+00:00")
        validate(doc)

    def test_missing_date_does_not_use_collection_time(self):
        _, _, row = inputs()
        for key in ("create_time", "create_date_time", "raw_created_at"): row[key] = None
        row["last_modify_ts"] = 1790000000000
        doc = self.norm(row)
        self.assertIsNone(doc["publishedAt"])
        self.assertIsNone(doc["updatedAt"])
        self.assertEqual(doc["publishedPrecision"], "unknown")

    def test_relative_time_remains_unknown(self):
        _, _, row = inputs()
        row.update(create_time=None, create_date_time=None)
        for value in ("刚刚", "5分钟前", "昨天 12:30", "10-22"):
            row["raw_created_at"] = value
            self.assertIsNone(self.norm(row)["publishedAt"])

    def test_seconds_not_milliseconds_and_no_float_id(self):
        _, _, row = inputs()
        row["create_time"] *= 1000
        with self.assertRaisesRegex(ContractError, "unit_or_future"): self.norm(row)
        _, _, row = inputs()
        row["note_id"] = float(ID)
        with self.assertRaisesRegex(ContractError, "id_string"): self.norm(row)

    def test_date_conflict_and_missing_offset_fail(self):
        _, _, row = inputs()
        row["create_date_time"] = "2026-10-22T12:01:00+08:00"
        with self.assertRaisesRegex(ContractError, "conflict"): self.norm(row)
        row["create_date_time"] = "2026-10-22 12:00:00"
        with self.assertRaisesRegex(ContractError, "offset_required"): self.norm(row)

    def test_source_calendar_invalid_and_future_rejected(self):
        _, _, row = inputs()
        row.update(create_time=None, create_date_time=None, raw_created_at="Thu Feb 30 12:00:00 +0800 2026")
        with self.assertRaisesRegex(ContractError, "date_invalid"): self.norm(row)
        row["raw_created_at"] = "Thu Oct 29 12:00:00 +0800 2026"
        with self.assertRaisesRegex(ContractError, "future"): self.norm(row)

    def test_approximate_zero_and_unknown_metrics_distinct(self):
        doc = self.norm()
        self.assertEqual(doc["metrics"]["likes"], {"value": 12000, "approximate": True})
        self.assertIsNone(doc["metrics"]["comments"]["value"])
        self.assertEqual(doc["metrics"]["shares"]["value"], 0)

    def test_hash_ignores_interactions_and_signed_urls(self):
        _, _, row = inputs()
        first = self.norm(row)
        row.update(liked_count="8888", note_url="https://m.weibo.cn/detail/" + ID + "?token=PRIVATE")
        self.assertEqual(first["contentHash"], self.norm(row)["contentHash"])
        self.assertNotIn("PRIVATE", repr(self.norm(row)))

    def test_repost_and_person_identity_are_not_inferred(self):
        _, _, row = inputs()
        row.update(retweeted_status={"id": "123"}, user_id="PRIVATE", profile_url="PRIVATE")
        doc = self.norm(row)
        self.assertEqual(doc["entityCandidates"], [])
        self.assertEqual(doc["nativeAliases"], [])
        self.assertEqual(doc["author"]["maskStatus"], "masked")
        self.assertNotIn("PRIVATE", repr(doc))

    def test_match_terms_require_visible_excerpt(self):
        _, _, row = inputs()
        row["content"] = "RAIL 合成案例"
        self.assertEqual(self.norm(row)["matchedTerms"], [])
        row["content"] = "AI 机器人案例"
        self.assertEqual(set(self.norm(row)["matchedTerms"]), {"AI", "机器人"})

    def test_script_text_removed_and_secret_text_rejected(self):
        _, _, row = inputs()
        row["content"] = "<script>AI 机器人</script><p>普通内容</p>"
        self.assertEqual(self.norm(row)["matchedTerms"], [])
        row["content"] = "Cookie=PRIVATE"
        with self.assertRaises(ContractError) as error: self.norm(row)
        self.assertNotIn("PRIVATE", str(error.exception))

    def test_no_original_title_claim(self):
        with self.assertRaisesRegex(ContractError, "derived"): self.norm(original_title=True)

    def test_finalize_positive_page_is_bounded(self):
        job, context, row = inputs()
        result = weibo.finalize(job, captured(job, row), context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "ok")
        self.assertEqual(result["receipt"]["completeness"], "bounded")
        self.assertFalse(result["diagnostics"]["fullTextFetched"])

    def test_later_network_failure_becomes_partial_not_complete(self):
        job, context, row = inputs()
        cap = captured(job, row)
        cap.update(status="network_error", stopReason="network", errorCode="SEARCH_FAILED")
        result = weibo.finalize(job, cap, context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "partial")
        self.assertEqual(len(result["observations"]), 1)

    def test_auth_after_data_keeps_pause_status(self):
        job, context, row = inputs()
        cap = captured(job, row)
        cap.update(status="auth_required", stopReason="auth", errorCode="AUTH")
        result = weibo.finalize(job, cap, context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "auth_required")
        self.assertEqual(len(result["observations"]), 1)

    def test_invalid_row_not_silently_counted_success(self):
        job, context, row = inputs()
        row["content"] = "Cookie=PRIVATE"
        result = weibo.finalize(job, captured(job, row), context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "schema_error")
        self.assertEqual(result["receipt"]["counts"]["rejectedRows"], 1)
        self.assertNotIn("PRIVATE", repr(result))

    def test_postfilter_unknown_time_rejected_without_fabrication(self):
        job, context, row = inputs()
        job["window"].update(filterMode="post_filter", **{"from": "2026-10-01", "to": "2026-10-23"})
        row.update(create_time=None, create_date_time=None, raw_created_at=None)
        result = weibo.finalize(job, captured(job, row), context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["counts"]["rejectedRows"], 1)
        self.assertEqual(result["observations"], [])

    def test_wrong_envelope_and_accounting_rejected(self):
        job, context, row = inputs()
        for change in ({"attemptId": "wrong"}, {"searchDuplicates": 1}, {"retryAfter": True}):
            cap = captured(job, row)
            cap.update(change)
            with self.assertRaises(ContractError):
                weibo.finalize(job, cap, context, patchset_hash=PATCHES)


if __name__ == "__main__": unittest.main()
