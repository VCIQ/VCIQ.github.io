"""Synthetic Bilibili contracts and identity checks; no platform traffic."""
import copy
import unittest

from tests.test_social_contracts import fixture
from tools.social.adapters.bilibili import normalize_record, finalize, seconds, plain
from tools.social.bilibili_identity import link_identity, reconcile_materials
from tools.social.contracts import ContractError, content_hash, validate
from tools.social.scheduler import instant
from workers.mediacrawler import observer as common

NOW = "2026-11-03T06:00:00+00:00"
BV = "BV1d54y1g7db"
PATCHES = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"


def inputs():
    job = fixture("crawl_job", "bili")
    context = {"terms": [{"text": "合成测试机器人", "kind": "keyword"}]}
    row = {"video_id": "9007199254740993123", "bvid": BV, "title": "合成测试机器人演讲",
           "desc": "测试视频简介，不是视频转录", "create_time": 1760000000,
           "creator_hash": "a" * 64, "nickname": "测***", "liked_count": "1.2万",
           "video_comment": None, "video_share_count": 0, "video_play_count": "1,234"}
    return job, context, row


def document(row=None):
    job, context, default = inputs()
    return normalize_record(row or default, job, context, observed_at=NOW, original_title=True)


def captured(job, row):
    value = common.envelope(job, lambda: NOW)
    value.update(completedAt=NOW, status="ok", stopReason="page_limit",
        pages=[{"pageIndex": 1, "schemaValid": True, "contentItems": 1, "processed": True, "hasMore": None}],
        records=[{"record": row, "originalTitle": True, "observedAt": NOW}])
    return value


class BilibiliNormalizerTests(unittest.TestCase):
    def test_exact_aid_and_detail_alias(self):
        doc = document()
        self.assertEqual(doc["nativeId"], "9007199254740993123")
        self.assertEqual(doc["nativeAliases"], ["bvid:" + BV])
        self.assertTrue(doc["canonicalUrl"].endswith("av9007199254740993123"))
        validate(doc)

    def test_description_never_claims_transcript(self):
        doc = document()
        self.assertEqual(doc["textScope"], "video_description")
        self.assertEqual(doc["entityCandidates"], [])
        self.assertEqual(doc["evidence"]["verification"], "unverified")

    def test_missing_dates_not_collection_time(self):
        _, _, row = inputs()
        row["create_time"] = None
        doc = document(row)
        self.assertIsNone(doc["publishedAt"])
        self.assertEqual(doc["publishedPrecision"], "unknown")

    def test_seconds_not_milliseconds_and_no_future(self):
        for value in (1760000000000, 9999999999, True, 1760000000.0, "yesterday"):
            with self.subTest(value=value), self.assertRaises(ContractError): seconds(value, instant(NOW))
        self.assertEqual(seconds("1760000000", instant(NOW)), seconds(1760000000, instant(NOW)))

    def test_html_highlights_removed_without_script(self):
        self.assertEqual(plain('<em>robot</em><script>hidden</script>&amp; AI', 100), "robot& AI")
        with self.assertRaises(ContractError): plain('access_token=SYNTHETIC', 100)

    def test_title_missing_can_be_derived(self):
        job, context, row = inputs()
        row["title"] = ""
        doc = normalize_record(row, job, context, observed_at=NOW, original_title=False)
        self.assertEqual(doc["titleOrigin"], "derived")
        row["desc"] = None
        doc = normalize_record(row, job, context, observed_at=NOW, original_title=False)
        self.assertEqual(doc["titleOrigin"], "missing")

    def test_metrics_zero_unknown_approximate(self):
        doc = document()
        self.assertEqual(doc["metrics"]["likes"], {"value": 12000, "approximate": True})
        self.assertIsNone(doc["metrics"]["comments"]["value"])
        self.assertEqual(doc["metrics"]["shares"]["value"], 0)
        self.assertEqual(doc["metrics"]["views"]["value"], 1234)

    def test_no_media_person_id_or_access_token_export(self):
        _, _, row = inputs()
        row.update(mid="SECRET_ID", video_url="https://example.invalid/?token=SYNTHETIC", video_cover_url="private")
        doc = document(row)
        self.assertNotIn("SECRET_ID", str(doc))
        self.assertNotIn("SYNTHETIC", str(doc))
        self.assertEqual(doc["author"]["maskStatus"], "masked")

    def test_hash_ignores_metrics_and_alias_enrichment(self):
        _, _, row = inputs()
        original = document(row)
        row.update(bvid=None, liked_count=9000)
        self.assertEqual(document(row)["contentHash"], original["contentHash"])

    def test_match_requires_visible_text(self):
        _, _, row = inputs()
        row.update(title="Unrelated", desc="No matching phrase")
        self.assertEqual(document(row)["matchedTerms"], [])

    def test_float_native_and_invalid_bvid_rejected(self):
        for key, value in (("video_id", 12.0), ("video_id", "None"), ("bvid", "BVbad")):
            _, _, row = inputs()
            row[key] = value
            with self.subTest(key=key), self.assertRaises(ContractError): document(row)

    def test_success_requires_page_evidence(self):
        job, context, row = inputs()
        cap = captured(job, row)
        result = finalize(job, cap, context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "ok")
        self.assertFalse(result["diagnostics"]["transcriptFetched"])
        cap["pages"] = []
        with self.assertRaises(ContractError): finalize(job, cap, context, patchset_hash=PATCHES)

    def test_network_partial_keeps_first_row(self):
        job, context, row = inputs()
        cap = captured(job, row)
        common.fail(cap, common.CollectorError("network_error", "SECOND_PAGE_FAILED"))
        result = finalize(job, cap, context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "partial")
        self.assertEqual(len(result["observations"]), 1)

    def test_auth_and_rate_remain_pause_states(self):
        job, context, row = inputs()
        for status in ("auth_required", "rate_limited", "verification_required"):
            cap = captured(job, row)
            common.fail(cap, common.CollectorError(status, "RESTRICTED", 100))
            self.assertEqual(finalize(job, cap, context, patchset_hash=PATCHES)["receipt"]["status"], status)

    def test_bad_row_is_not_reported_success(self):
        job, context, row = inputs()
        row["create_time"] = True
        result = finalize(job, captured(job, row), context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "schema_error")
        self.assertEqual(result["receipt"]["counts"]["rejectedRows"], 1)

    def test_time_window_unknown_date_rejected_not_invented(self):
        job, context, row = inputs()
        job["window"] = {"from": "2026-01-01", "to": None, "filterMode": "post_filter"}
        row["create_time"] = None
        result = finalize(job, captured(job, row), context, patchset_hash=PATCHES)
        self.assertEqual(result["observations"], [])
        self.assertEqual(result["receipt"]["status"], "ok")


class BilibiliIdentityTests(unittest.TestCase):
    def test_explicit_pair_matches_existing_person_material(self):
        doc = document()
        result = reconcile_materials([doc], [{"url": "https://www.bilibili.com/video/" + BV + "/?p=2", "title": "different title"}])
        self.assertEqual(result["matches"][0]["signalId"], doc["signalId"])
        self.assertFalse(result["productionWrites"])
        self.assertFalse(result["personIdentityInferred"])

    def test_aid_direct_match_does_not_need_bvid(self):
        _, _, row = inputs()
        row["bvid"] = None
        doc = document(row)
        result = reconcile_materials([doc], [{"url": doc["canonicalUrl"]}])
        self.assertEqual(result["matches"][0]["basis"], "exact_aid")

    def test_same_title_different_ids_not_merged(self):
        doc = document()
        result = reconcile_materials([doc], [{"url": "https://www.bilibili.com/video/av999", "title": doc["title"]}])
        self.assertEqual(result["matches"], [])
        self.assertEqual(result["unmatchedMaterialIndices"], [0])

    def test_no_mapping_only_manual_candidate(self):
        _, _, row = inputs()
        row["bvid"] = None
        doc = document(row)
        result = reconcile_materials([doc], [{"url": "https://www.bilibili.com/video/" + BV, "title": doc["title"]}])
        self.assertEqual(result["matches"], [])
        self.assertEqual(result["possibleDuplicates"][0]["basis"], "title_only_not_merged")

    def test_conflicting_bvid_pair_rejected(self):
        first = document()
        _, _, row = inputs()
        row["video_id"] = "99"
        with self.assertRaisesRegex(ContractError, "bili_alias_conflict"):
            reconcile_materials([first, document(row)], [])

    def test_one_aid_cannot_claim_two_bvids(self):
        first = document()
        _, _, row = inputs()
        row["bvid"] = "BV1d54y1g7dc"
        with self.assertRaises(ContractError): reconcile_materials([first, document(row)], [])

    def test_urls_not_resolved_and_hosts_exact(self):
        for url in ("https://b23.tv/example", "https://www.bilibili.com.evil/video/av123", "https://x@www.bilibili.com/video/av123", "https://www.bilibili.com/video/%61v123"):
            self.assertIsNone(link_identity(url))
        self.assertEqual(link_identity("https://bilibili.com/video/" + BV), "bvid:" + BV)
        self.assertIsNone(link_identity("https://bilibili.com/video/" + BV.lower()))

    def test_input_not_mutated_and_observations_retained(self):
        docs = [document()]
        materials = [{"url": docs[0]["canonicalUrl"], "title": "original"}]
        before = copy.deepcopy((docs, materials))
        report = reconcile_materials(docs, materials)
        self.assertEqual(before, (docs, materials))
        self.assertEqual(report["observationsRemoved"], 0)


if __name__ == "__main__": unittest.main()
