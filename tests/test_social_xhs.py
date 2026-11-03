"""PR-03: deterministic XHS replay; not evidence of a live platform query."""
from __future__ import annotations

import asyncio
import copy
import unittest
from types import SimpleNamespace

from tests.test_social_contracts import fixture
from tools.social.adapters.common import epoch
from tools.social.adapters.xhs import normalize_record
from tools.social.contracts import ContractError, assert_safe
from tools.social.worker import normalize_execution
from workers.mediacrawler.observer import Halt, Observer, apply_safe_config, xhs_search

TIME = "2026-10-23T12:00:00+00:00"
ID = "000000000000000000000001"


def raw_note():
    return {"note_id": ID, "title": "合成测试机器人", "desc": "合成测试机器人发布产品，仅用于测试。", "time": 0,
            "last_modify_ts": 1792756800, "nickname": "测***", "creator_hash": "a" * 64,
            "liked_count": "1.2万", "comment_count": "--", "share_count": "3", "xsec_token": "SYNTHETIC_ONLY"}


async def no_sleep(_):
    pass


class XhsTests(unittest.TestCase):
    def setUp(self):
        self.job = fixture("crawl_job", "xhs")

    def replay(self, pages, details=None):
        observer = Observer(self.job, clock=lambda: TIME)
        class Client:
            async def get_note_by_keyword(self, **kwargs):
                return pages[kwargs["page"] - 1]
            async def get_note_by_id(self, identifier, source, locator):
                return (details or {}).get(identifier, {**raw_note(), "note_id": identifier})
        class Store:
            async def update_xhs_note(self, row):
                observer.capture(row)
        asyncio.run(xhs_search(Client(), Store(), observer, sleep=no_sleep))
        return observer

    def test_X01_nonempty_final_page_is_processed_once(self):
        response = {"items": [{"id": ID, "model_type": "note", "xsec_token": "SYNTHETIC_ONLY"}], "has_more": False}
        self.assertTrue(not response or not response.get("has_more", False))  # pinned old early-exit condition
        observer = self.replay([response])
        self.assertEqual(len(observer.rows), 1)
        result = normalize_execution(observer.payload(), self.job)
        self.assertEqual(result["receipt"]["status"], "ok")
        self.assertEqual(result["receipt"]["completeness"], "exhausted")

    def test_X02_missing_has_more_is_schema_error(self):
        with self.assertRaisesRegex(Halt, "XHS_SEARCH_SHAPE"):
            self.replay([{"items": []}])

    def test_X02_wrong_items_type_rejected(self):
        with self.assertRaises(Halt):
            self.replay([{"items": {}, "has_more": False}])

    def test_X02_explicit_empty_success(self):
        result = normalize_execution(self.replay([{"items": [], "has_more": False}]).payload(), self.job)
        self.assertEqual(result["receipt"]["status"], "empty")

    def test_X02_no_rows_no_response_is_not_empty(self):
        result = normalize_execution(Observer(self.job, clock=lambda: TIME).payload(), self.job)
        self.assertEqual(result["receipt"]["status"], "schema_error")

    def test_X02_detail_identity_must_match(self):
        with self.assertRaisesRegex(Halt, "XHS_DETAIL_SHAPE"):
            self.replay([{"items": [{"id": ID, "xsec_token": "test"}], "has_more": False}], {ID: {"note_id": "other", "desc": "test"}})

    def test_X03_access_parameters_do_not_change_identity(self):
        raw = raw_note()
        first = normalize_record(raw, self.job, observed_at=TIME)
        raw["xsec_token"] = "SECOND_SYNTHETIC"
        raw["note_url"] = "https://www.xiaohongshu.com/explore/" + ID + "?xsec_token=SECOND_SYNTHETIC"
        second = normalize_record(raw, self.job, observed_at=TIME)
        self.assertEqual(first["signalId"], second["signalId"])
        self.assertEqual(first["contentHash"], second["contentHash"])
        self.assertNotIn("?", second["canonicalUrl"])
        self.assertEqual(second["accessStatus"], "unverified")
        assert_safe(second)

    def test_X04_missing_time_is_not_collection_time(self):
        row = normalize_record(raw_note(), self.job, observed_at=TIME)
        self.assertIsNone(row["publishedAt"])
        self.assertEqual(row["publishedPrecision"], "unknown")

    def test_X04_explicit_units_never_guessed(self):
        self.assertEqual(epoch(1700000000), epoch(1700000000000, unit="milliseconds"))
        with self.assertRaises(ContractError):
            epoch(1700000000, unit="milliseconds")
        raw = raw_note()
        raw["time"] = 1700000000000
        self.assertTrue(normalize_record(raw, self.job, observed_at=TIME)["publishedAt"].startswith("2023-"))

    def test_X04_future_date_is_not_changed_to_today(self):
        raw = raw_note()
        raw["time"] = 4102444800000
        with self.assertRaises(ContractError):
            normalize_record(raw, self.job, observed_at=TIME)

    def test_X05_masked_author_does_not_confirm_identity(self):
        row = normalize_record(raw_note(), self.job, observed_at=TIME)
        self.assertEqual(row["author"]["maskStatus"], "masked")
        self.assertEqual(row["entityCandidates"], [])
        self.assertEqual(row["evidence"]["verification"], "unverified")
        self.assertEqual(row["metrics"]["likes"], {"value": 12000, "approximate": True})
        self.assertIsNone(row["metrics"]["comments"]["value"])

    def test_X05_sensitive_text_rejected_not_logged(self):
        raw = raw_note()
        raw["desc"] = "Cookie: SYNTHETIC_SECRET"
        with self.assertRaises(ContractError) as caught:
            normalize_record(raw, self.job, observed_at=TIME)
        self.assertNotIn("SYNTHETIC_SECRET", str(caught.exception))

    def test_R02_safe_overrides_after_cli_defaults(self):
        config = SimpleNamespace(ENABLE_CDP_MODE=True, ENABLE_GET_COMMENTS=True)
        apply_safe_config(config, platform="xhs", profile="/private/profiles/xhs", output="/private/raw")
        for name in ("ENABLE_CDP_MODE", "CDP_CONNECT_EXISTING", "ENABLE_IP_PROXY", "ENABLE_GET_COMMENTS", "ENABLE_GET_SUB_COMMENTS", "ENABLE_GET_MEDIA", "DISABLE_SSL_VERIFY"):
            self.assertFalse(getattr(config, name))
        self.assertEqual(config.MAX_CONCURRENCY_NUM, 1)

    def test_R03_authentication_error_survives_exit_zero_payload(self):
        observer = Observer(self.job, clock=lambda: TIME)
        observer.fail("auth_required", "SESSION_NOT_READY")
        result = normalize_execution(observer.payload(), self.job)
        self.assertEqual(result["receipt"]["status"], "auth_required")

    def test_partial_failure_keeps_previous_valid_content(self):
        observer = self.replay([{"items": [{"id": ID, "xsec_token": "test"}], "has_more": True}])
        observer.fail("verification_required", "HTTP_VERIFICATION")
        result = normalize_execution(observer.payload(), self.job)
        self.assertEqual(result["receipt"]["status"], "partial")
        self.assertEqual(result["receipt"]["stopReason"], "verification")
        self.assertEqual(len(result["observations"]), 1)

    def test_result_bounds_and_duplicate_rows(self):
        observer = self.replay([{"items": [{"id": ID, "xsec_token": "test"}], "has_more": False}])
        observer.rows.append(copy.deepcopy(observer.rows[0]))
        result = normalize_execution(observer.payload(), self.job)
        self.assertEqual(result["receipt"]["counts"]["duplicateRows"], 1)
        self.assertEqual(len(result["observations"]), 1)


if __name__ == "__main__":
    unittest.main()
