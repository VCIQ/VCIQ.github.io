"""Synthetic async callback tests: no browser, login, network, or real records."""
import asyncio
import copy
import unittest
from workers.mediacrawler.observer import CollectorError, collect_xhs, select_record, classify

ID1, ID2 = "0" * 23 + "1", "0" * 23 + "2"
STAMP = "2026-10-24T12:00:00+00:00"


def job(records=20, pages=1):
    return {"platform": "xhs", "operation": "search", "attemptId": "attempt", "queryId": "query",
        "query": {"text": "合成机器人", "scope": "track", "targetId": None},
        "window": {"filterMode": "none"}, "limits": {"maxSearchPages": pages, "maxRecords": records, "maxWallSeconds": 180}}


def item(native=ID1):
    return {"id": native, "model_type": "note", "xsec_token": "SYNTHETIC_ONLY"}


class ObserverTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, pages, *, selected=None, detail_failure=None):
        seen = {"queries": [], "details": []}
        async def search(term, page):
            seen["queries"].append((term, page))
            response = pages[page - 1]
            if isinstance(response, Exception):
                raise response
            return copy.deepcopy(response)
        async def detail(value):
            seen["details"].append(value["id"])
            if detail_failure and value["id"] in detail_failure:
                raise detail_failure[value["id"]]
            return {"note_id": value["id"], "title": "合成机器人", "desc": "仅测试", "xsec_token": "PRIVATE_ONLY"}
        async def project(value):
            return value
        result = await collect_xhs(selected or job(), search, detail, project, clock=lambda: STAMP)
        return result, seen

    async def test_final_nonempty_page_is_processed(self):
        result, seen = await self.run_case([{"items": [item()], "has_more": False}])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stopReason"], "exhausted")
        self.assertEqual(seen["details"], [ID1])
        self.assertEqual(len(result["records"]), 1)
        self.assertTrue(result["pages"][0]["processed"])

    async def test_explicit_zero_results(self):
        result, _ = await self.run_case([{"items": [], "has_more": False}])
        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["stopReason"], "exhausted")

    async def test_unknown_response_not_empty(self):
        for response in ({}, None, "login page", {"items": "changed"}):
            result, _ = await self.run_case([response])
            self.assertEqual(result["status"], "schema_error")

    async def test_empty_without_exhaustion_not_claimed_successful(self):
        result, _ = await self.run_case([{"items": [], "has_more": None}])
        self.assertEqual(result["errorCode"], "EMPTY_COVERAGE_UNPROVEN")

    async def test_bounded_page_limit(self):
        result, seen = await self.run_case([{"items": [item()], "has_more": True}])
        self.assertEqual(result["stopReason"], "page_limit")
        self.assertEqual(seen["queries"], [("合成机器人", 1)])

    async def test_exact_detail_budget_is_bounded_even_on_final_page(self):
        result, seen = await self.run_case([{"items": [item(), item(ID2)], "has_more": False}], selected=job(records=1))
        self.assertEqual(seen["details"], [ID1])
        self.assertEqual(result["detailsNotRequested"], 1)
        self.assertEqual(result["stopReason"], "item_limit")

    async def test_duplicate_search_hits_do_not_refetch(self):
        result, seen = await self.run_case([{"items": [item(), item()], "has_more": False}])
        self.assertEqual(result["searchDuplicates"], 1)
        self.assertEqual(seen["details"], [ID1])

    async def test_recommendation_cards_not_contents(self):
        result, _ = await self.run_case([{"items": [{"model_type": "hot_query"}, item()], "has_more": False}])
        self.assertEqual(result["pages"][0]["contentItems"], 1)

    async def test_second_page_failure_preserves_observations(self):
        result, seen = await self.run_case([{"items": [item()], "has_more": True}, CollectorError("network_error", "NETWORK")], selected=job(pages=2))
        self.assertEqual(result["status"], "network_error")
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(len(seen["queries"]), 2)

    async def test_rate_limit_stops_without_retry(self):
        result, seen = await self.run_case([CollectorError("rate_limited", "LIMIT", 90000)])
        self.assertEqual(result["retryAfter"], 90000)
        self.assertEqual(len(seen["queries"]), 1)
        self.assertEqual(seen["details"], [])

    async def test_restriction_during_details_stops(self):
        result, seen = await self.run_case([{"items": [item(), item(ID2)], "has_more": False}],
            detail_failure={ID1: CollectorError("verification_required", "VERIFY")})
        self.assertEqual(result["status"], "verification_required")
        self.assertEqual(seen["details"], [ID1])
        self.assertFalse(result["pages"][0]["processed"])

    async def test_failed_detail_does_not_become_empty(self):
        result, _ = await self.run_case([{"items": [item()], "has_more": False}], detail_failure={ID1: CollectorError("network_error", "DETAIL")})
        self.assertEqual(result["status"], "network_error")
        self.assertEqual(result["detailFailures"], 1)

    async def test_token_never_crosses_child_record_boundary(self):
        result, _ = await self.run_case([{"items": [item()], "has_more": False}])
        self.assertNotIn("xsec_token", repr(result))
        self.assertNotIn("PRIVATE_ONLY", repr(result))

    async def test_scope_and_native_filter_rejected_before_search(self):
        for change in ("comma", "account", "native"):
            selected = job()
            if change == "comma": selected["query"]["text"] = "A,B"
            if change == "account": selected["query"]["scope"] = "account"
            if change == "native": selected["window"]["filterMode"] = "native"
            result, seen = await self.run_case([], selected=selected)
            self.assertEqual(result["status"], "unsupported")
            self.assertEqual(seen["queries"], [])

    async def test_malformed_ids_and_has_more_fail_closed(self):
        for response in ({"items": [{"id": "../../../bad"}], "has_more": False}, {"items": [item()], "has_more": "false"}):
            result, _ = await self.run_case([response])
            self.assertEqual(result["status"], "schema_error")

    async def test_detail_identity_mismatch(self):
        async def search(*args): return {"items": [item()], "has_more": False}
        async def detail(*args): return {"note_id": ID2}
        async def project(note): return note
        result = await collect_xhs(job(), search, detail, project, clock=lambda: STAMP)
        self.assertEqual(result["errorCode"], "DETAIL_ID_MISMATCH")

    def test_unknown_exceptions_never_leak_values(self):
        result = classify(ValueError("cookie=SYNTHETIC_PRIVATE"))
        self.assertEqual(str(result), "UNEXPECTED_WORKER_ERROR")

    def test_nested_store_fields_and_large_text_rejected(self):
        for value in ({"desc": {"nested": 1}}, {"desc": "x" * 100001}):
            with self.assertRaises(CollectorError):
                select_record(value, original_title=True, observed_at=STAMP)


if __name__ == "__main__":
    unittest.main()
