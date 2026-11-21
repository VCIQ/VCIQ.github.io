"""Typed Zhihu observations and receipt regressions, all records synthetic."""
import copy
import unittest
from datetime import UTC, datetime

from tests.test_social_contracts import fixture
from tools.social.adapters.zhihu import finalize, normalize_record
from tools.social.contracts import ContractError, digest
from workers.mediacrawler import observer

NOW = "2026-11-03T08:00:00+00:00"
CREATED = int(datetime(2026, 11, 1, tzinfo=UTC).timestamp())
PATCHES = digest([])


def inputs(kind="answer", native="101"):
    job = fixture("crawl_job", "zhihu")
    context = {"terms": [{"text": "机器人"}, {"text": "AI"}]}
    row = {"content_type": kind, "content_id": native, "question_id": "900" if kind == "answer" else None,
        "title": "合成机器人", "content": "AI 机器人合成正文", "description": "合成简介",
        "created_time": CREATED if kind != "zvideo" else None, "created_at": CREATED if kind == "zvideo" else None,
        "nickname": "合***", "creator_hash": "a" * 32, "voteup_count": 0, "comment_count": None}
    return job, context, row


def captured(job, rows):
    result = observer.envelope(job, lambda: NOW)
    result.update(completedAt=NOW, status="ok", stopReason="exhausted", excludedItems=0,
        pages=[{"pageIndex": 1, "schemaValid": True, "contentItems": len(rows), "processed": True, "hasMore": False}],
        records=[{"record": row, "originalTitle": bool(row.get("title")), "observedAt": NOW} for row in rows])
    return result


def convert(row, *, original_title=True):
    job, context, _ = inputs()
    return normalize_record(row, job, context, observed_at=NOW, original_title=original_title)


class ZhihuNormalizerTests(unittest.TestCase):
    def test_types_with_same_numeric_id_do_not_collide(self):
        docs = [convert(inputs(kind)[2]) for kind in ("answer", "article", "zvideo")]
        self.assertEqual(len({doc["signalId"] for doc in docs}), 3)
        self.assertEqual([doc["textScope"] for doc in docs], ["answer_excerpt", "article_excerpt", "video_description"])

    def test_question_id_is_not_an_answer_alias(self):
        first = convert(inputs()[2]); second = convert(inputs(native="102")[2])
        self.assertNotEqual(first["signalId"], second["signalId"])
        self.assertEqual(first["nativeAliases"], [])
        self.assertTrue(first["canonicalUrl"].endswith("/question/900/answer/101"))

    def test_missing_question_keeps_unknown_url(self):
        row = inputs()[2]; row["question_id"] = None
        self.assertIsNone(convert(row)["canonicalUrl"])
        self.assertEqual(convert(row)["nativeId"], "101")

    def test_video_empty_text_is_metadata_not_transcript(self):
        row = inputs("zvideo")[2]
        row.update(content="THIS IS NOT A TRANSCRIPT", description=None, excerpt=None, title=None)
        doc = convert(row, original_title=False)
        self.assertEqual(doc["excerpt"], "")
        self.assertEqual(doc["textScope"], "video_description")
        self.assertEqual(doc["titleOrigin"], "missing")

    def test_title_fallback_from_question_is_derived(self):
        row = inputs()[2]; row.update(title=None, question_title="合成问题")
        doc = convert(row, original_title=False)
        self.assertEqual(doc["titleOrigin"], "derived")
        self.assertEqual(doc["title"], "合成问题")

    def test_article_url_and_original_title(self):
        doc = convert(inputs("article")[2])
        self.assertEqual(doc["canonicalUrl"], "https://zhuanlan.zhihu.com/p/101")
        self.assertEqual(doc["titleOrigin"], "upstream")

    def test_creation_and_update_are_distinct(self):
        row = inputs()[2]; row["updated_time"] = CREATED + 3600
        doc = convert(row)
        self.assertNotEqual(doc["publishedAt"], doc["updatedAt"])
        row["updated_time"] = CREATED - 1
        with self.assertRaisesRegex(ContractError, "update_before"): convert(row)

    def test_article_timestamp_alias_conflict_rejected(self):
        row = inputs("article")[2]; row["created"] = CREATED + 1
        with self.assertRaisesRegex(ContractError, "timestamp_conflict"): convert(row)
        row["created"] = CREATED
        self.assertIsNotNone(convert(row)["publishedAt"])

    def test_video_publication_does_not_claim_upload_time(self):
        row = inputs("zvideo")[2]; row["published_at"] = CREATED + 3600
        self.assertEqual(convert(row)["publishedAt"], datetime.fromtimestamp(CREATED + 3600, UTC).isoformat(timespec="seconds"))

    def test_unknown_date_not_observation_time(self):
        row = inputs()[2]; row["created_time"] = None
        doc = convert(row)
        self.assertIsNone(doc["publishedAt"])
        self.assertEqual(doc["publishedPrecision"], "unknown")

    def test_millisecond_future_relative_boolean_dates_rejected(self):
        for value in (CREATED * 1000, 9999999999, "昨天", True, 1.2):
            row = inputs()[2]; row["created_time"] = value
            with self.assertRaises(ContractError): convert(row)

    def test_large_string_id_exact_float_and_boolean_rejected(self):
        row = inputs(native="900719925474099312345")[2]
        self.assertEqual(convert(row)["nativeId"], row["content_id"])
        for value in (1.0, True, "01", None):
            row["content_id"] = value
            with self.assertRaises(ContractError): convert(row)

    def test_missing_metrics_not_zero_and_approximation_explicit(self):
        row = inputs()[2]; row["voteup_count"] = "1.2万+"
        doc = convert(row)
        self.assertEqual(doc["metrics"]["likes"], {"value": 12000, "approximate": True})
        self.assertIsNone(doc["metrics"]["comments"]["value"])
        self.assertIsNone(doc["metrics"]["shares"]["value"])

    def test_hash_ignores_engagement_and_observation_time(self):
        row = inputs()[2]; before = convert(row)
        row["voteup_count"] = 999
        self.assertEqual(convert(row)["contentHash"], before["contentHash"])

    def test_match_requires_visible_excerpt_or_title(self):
        row = inputs()[2]; row.update(title="其他", description=None, content="x" * 501 + "AI 机器人")
        self.assertEqual(convert(row)["matchedTerms"], [])

    def test_html_removed_and_sensitive_text_rejected_before_truncation(self):
        row = inputs()[2]; row["content"] = "<p>AI</p><script>PRIVATE</script><em>机器人</em>"
        self.assertNotIn("PRIVATE", convert(row)["excerpt"])
        row["content"] = "x" * 600 + " access_token=PRIVATE"
        with self.assertRaises(ContractError) as error: convert(row)
        self.assertNotIn("PRIVATE", str(error.exception))

    def test_original_person_id_and_media_not_exported(self):
        row = inputs()[2]; row.update(user_id="PRIVATE", video_url="PRIVATE", access_token="PRIVATE")
        doc = convert(row)
        self.assertNotIn("PRIVATE", repr(doc))
        self.assertEqual(doc["entityCandidates"], [])
        self.assertEqual(doc["evidence"]["role"], "discovery")

    def test_finalizer_mixed_types_and_shared_question(self):
        job, context, row = inputs()
        rows = [row, inputs(native="102")[2], inputs("article")[2], inputs("zvideo")[2]]
        result = finalize(job, captured(job, rows), context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["counts"]["emittedRows"], 4)
        self.assertFalse(result["diagnostics"]["fullTextFetched"])

    def test_network_partial_preserves_rows(self):
        job, context, row = inputs(); data = captured(job, [row])
        data.update(status="network_error", stopReason="network", errorCode="NETWORK")
        result = finalize(job, data, context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "partial")
        self.assertEqual(len(result["observations"]), 1)

    def test_auth_rate_and_verification_keep_platform_pause(self):
        job, context, row = inputs()
        for status, reason in (("auth_required", "auth"), ("rate_limited", "rate_limit"), ("verification_required", "verification")):
            data = captured(job, [row]); data.update(status=status, stopReason=reason, errorCode="RESTRICTED")
            self.assertEqual(finalize(job, data, context, patchset_hash=PATCHES)["receipt"]["status"], status)

    def test_postfilter_missing_date_does_not_fabricate(self):
        job, context, row = inputs(); job["window"].update(filterMode="post_filter", **{"from": "2026-11-01", "to": "2026-11-03"})
        row["created_time"] = None
        result = finalize(job, captured(job, [row]), context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["counts"]["rejectedRows"], 1)
        self.assertEqual(result["observations"], [])

    def test_bad_row_is_not_success(self):
        job, context, row = inputs(); row["content_type"] = "unknown"
        result = finalize(job, captured(job, [row]), context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "schema_error")

    def test_corrupt_envelope_counts_and_pages_rejected(self):
        job, context, row = inputs()
        for mutate in (lambda d: d.update(attemptId="wrong"), lambda d: d.update(searchDuplicates=1), lambda d: d["pages"][0].update(pageIndex=2)):
            data = captured(job, [row]); mutate(data)
            with self.assertRaises(ContractError): finalize(job, data, context, patchset_hash=PATCHES)

    def test_conflicting_answer_parent_not_deduplicated(self):
        job, context, row = inputs(); other = copy.deepcopy(row); other["question_id"] = "901"
        result = finalize(job, captured(job, [row, other]), context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "partial")
        self.assertEqual(result["receipt"]["counts"]["rejectedRows"], 1)


if __name__ == "__main__": unittest.main()
