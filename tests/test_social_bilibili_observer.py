"""Bilibili search/detail callbacks are synthetic and never contact a platform."""
import unittest

from workers.mediacrawler import observer as common
from workers.mediacrawler.bilibili_observer import collect_bilibili, aid, bvid
from tests.test_social_bilibili import inputs, NOW, BV


def hit(native="123", bv=BV):
    return {"type": "video", "aid": native, "bvid": bv}


def detail_doc(native="123", bv=BV):
    return {"View": {"aid": native, "bvid": bv, "title": "合成演讲", "desc": "简介"}}


class BilibiliObserverTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, pages, *, max_pages=2, max_records=20, details=None, job=None):
        selected = job or inputs()[0]
        selected["limits"].update(maxSearchPages=max_pages, maxRecords=max_records)
        calls = []
        async def search(keyword, page):
            calls.append(("search", keyword, page))
            response = pages[page - 1]
            if isinstance(response, Exception): raise response
            return response
        async def detail(native):
            calls.append(("detail", native))
            value = details.get(native) if details is not None else detail_doc(native)
            if isinstance(value, Exception): raise value
            return value
        async def project(value):
            view = value["View"]
            return {"video_id": str(view["aid"]), "bvid": view.get("bvid"), "title": view.get("title"), "desc": view.get("desc")}
        result = await collect_bilibili(selected, search, detail, project, observer=common, clock=lambda: NOW)
        return result, calls

    async def test_final_nonempty_page_processed(self):
        result, calls = await self.run_case([{"result": [hit()], "numPages": 1}])
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["stopReason"], "exhausted")
        self.assertTrue(result["pages"][0]["processed"])

    async def test_positive_page_without_end_is_bounded(self):
        result, _ = await self.run_case([{"result": [hit()], "numResults": 1}], max_pages=1)
        self.assertEqual(result["stopReason"], "page_limit")
        self.assertIsNone(result["pages"][0]["hasMore"])

    async def test_explicit_empty_is_not_failure(self):
        result, calls = await self.run_case([{"result": []}])
        self.assertEqual(result["status"], "empty")
        self.assertEqual(len(calls), 1)

    async def test_missing_list_and_login_shapes_not_empty(self):
        for response in ({}, {"result": None}, {"result": {}}, {"message": "login"}):
            result, _ = await self.run_case([response])
            self.assertEqual(result["status"], "schema_error")

    async def test_duplicate_aid_not_refetched(self):
        result, calls = await self.run_case([{"result": [hit(), hit()]}, {"result": []}])
        self.assertEqual(sum(c[0] == "detail" for c in calls), 1)
        self.assertEqual(result["searchDuplicates"], 1)

    async def test_item_budget_counts_unrequested(self):
        result, calls = await self.run_case([{"result": [hit(), hit("124", None)], "numPages": 1}], max_records=1)
        self.assertEqual(result["stopReason"], "item_limit")
        self.assertEqual(result["detailsNotRequested"], 1)
        self.assertEqual(sum(c[0] == "detail" for c in calls), 1)

    async def test_second_page_failure_keeps_record(self):
        error = common.CollectorError("network_error", "REQUEST_FAILED")
        result, _ = await self.run_case([{"result": [hit()]}, error])
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["status"], "network_error")

    async def test_detail_restriction_stops_immediately(self):
        error = common.CollectorError("rate_limited", "HTTP_RATE_LIMIT", 600)
        result, calls = await self.run_case([{"result": [hit(), hit("124", None)]}], details={"123": error})
        self.assertEqual(result["status"], "rate_limited")
        self.assertEqual(result["retryAfter"], 600)
        self.assertEqual(sum(c[0] == "detail" for c in calls), 1)

    async def test_detail_identity_must_match_search(self):
        result, _ = await self.run_case([{"result": [hit()]}], details={"123": detail_doc("124")})
        self.assertEqual(result["status"], "schema_error")
        self.assertEqual(result["records"], [])

    async def test_bvid_conflict_not_guessed(self):
        result, _ = await self.run_case([{"result": [hit()]}], details={"123": detail_doc("123", "BV1d54y1g7dc")})
        self.assertEqual(result["status"], "schema_error")

    async def test_same_title_different_videos_both_retained(self):
        result, _ = await self.run_case([{"result": [hit("123", None), hit("124", None)], "numPages": 1}],
            details={"123": detail_doc("123", None), "124": detail_doc("124", None)})
        self.assertEqual(len(result["records"]), 2)

    async def test_search_bvid_conflict_rejected(self):
        result, _ = await self.run_case([{"result": [hit(), hit("123", "BV1d54y1g7dc")]}])
        self.assertEqual(result["status"], "schema_error")

    async def test_large_ids_exact_and_float_rejected(self):
        self.assertEqual(aid(9007199254740993123), "9007199254740993123")
        for value in (True, 123.0, "00123", "None", -1):
            with self.assertRaises(ValueError): aid(value)

    async def test_conflicting_pagination_not_exhausted(self):
        for response in ({"result": [hit()], "numPages": 0}, {"result": [], "numPages": 3}, {"result": [], "page": 2}, {"result": [], "numPages": True}):
            result, _ = await self.run_case([response])
            self.assertEqual(result["status"], "schema_error")

    async def test_native_filter_and_signature_mutation_refused(self):
        for marker in ("native", "punctuation"):
            job = inputs()[0]
            if marker == "native": job["window"]["filterMode"] = "native"
            else: job["query"]["text"] = "robot's model"
            result, calls = await self.run_case([], job=job)
            self.assertEqual(result["status"], "unsupported")
            self.assertEqual(calls, [])

    async def test_no_raw_error_or_private_fields_exported(self):
        error = RuntimeError("Cookie: PRIVATE")
        result, _ = await self.run_case([error])
        self.assertNotIn("PRIVATE", str(result))


if __name__ == "__main__": unittest.main()
