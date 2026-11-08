"""Synthetic raw search pages; no browser, external API or upstream import."""
import copy
import unittest
from urllib.parse import urlencode

from tests.test_social_contracts import fixture
from workers.mediacrawler import observer as obs
from workers.mediacrawler.zhihu_observer import collect_zhihu, content_identity

NOW = "2026-11-03T08:00:00+00:00"


def obj(kind="answer", native="101", parent="900"):
    value = {"type": kind, "id": native, "title": "合成机器人", "content": "合成内容"}
    if kind == "answer": value["question"] = {"id": parent}
    return value


def page(objects=(), end=True):
    return {"data": [{"type": "search_result", "object": value} for value in objects], "paging": {"is_end": end}}


async def projection(value):
    kind, native, parent = content_identity(value, obs)
    return {"content_type": kind, "content_id": native, "question_id": parent, "title": value.get("title"), "content": value.get("content")}


class ZhihuObserverTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, pages, *, records=20, project=projection, mutate=None):
        job = fixture("crawl_job", "zhihu")
        job["limits"].update(maxSearchPages=len(pages), maxRecords=records)
        if mutate: mutate(job)
        self.calls = []
        async def search(keyword, number):
            self.calls.append((keyword, number))
            result = pages[number - 1]
            if isinstance(result, Exception): raise result
            return copy.deepcopy(result)
        return await collect_zhihu(job, search, project, observer=obs, clock=lambda: NOW)

    async def test_three_types_with_same_id_remain_distinct(self):
        result = await self.run_case([page([obj(kind) for kind in ("answer", "article", "zvideo")])])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["records"]), 3)

    async def test_same_question_different_answers_remain_distinct(self):
        result = await self.run_case([page([obj(native="101"), obj(native="102")])])
        self.assertEqual(len(result["records"]), 2)

    async def test_final_nonempty_page_processed_before_end(self):
        result = await self.run_case([page([obj()], False), page([obj(native="102")])])
        self.assertEqual(result["stopReason"], "exhausted")
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual([number for _, number in self.calls], [1, 2])

    async def test_empty_requires_explicit_end(self):
        self.assertEqual((await self.run_case([page()]))["status"], "empty")
        for end in (None, False):
            self.assertEqual((await self.run_case([page(end=end)]))["status"], "schema_error")

    async def test_positive_unknown_end_is_bounded(self):
        result = await self.run_case([page([obj()], None)])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stopReason"], "page_limit")
        self.assertIsNone(result["pages"][0]["hasMore"])

    async def test_bad_shapes_never_become_empty(self):
        for data in ({}, {"data": [], "paging": []}, page(end=1), {"error": {}, **page()}, {"data": [{"type": "unknown"}], "paging": {"is_end": True}}):
            self.assertEqual((await self.run_case([data]))["status"], "schema_error")

    async def test_mixed_noncontent_cards_do_not_block_valid_answer(self):
        data = page([obj()], end=True)
        data["data"].insert(0, {"type": "search_suggestion", "url": "PRIVATE", "object": {"type": "answer", "id": "999"}})
        data["data"].append({"type": "ad-card", "payload": {"secret": "PRIVATE"}})
        result = await self.run_case([data], records=2)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["excludedItems"], 2)
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["pages"][0]["contentItems"], 1)
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn("PRIVATE", repr(result))

    async def test_all_presentation_cards_never_attest_empty_coverage(self):
        data = {"data": [{"type": "search_suggestion", "title": "PRIVATE"},
                         {"type": "ad-card", "object": {"type": "answer", "id": "999"}}],
                "paging": {"is_end": True}}
        result = await self.run_case([data])
        self.assertEqual(result["status"], "schema_error")
        self.assertEqual(result["errorCode"], "ZHIHU_EMPTY_COVERAGE_UNPROVEN")
        self.assertEqual(result["excludedItems"], 2)
        self.assertEqual(len(result["records"]), 0)
        self.assertNotIn("PRIVATE", repr(result))

    async def test_malformed_untrusted_card_type_is_never_ignored(self):
        for category in (None, 2, True, "", "PRIVATE<script>", "回答", "a" * 49):
            with self.subTest(category=type(category).__name__):
                data = page([obj()], True)
                data["data"].insert(0, {"type": category, "PRIVATE": "SECRET"})
                result = await self.run_case([data])
                self.assertEqual(result["status"], "schema_error")
                self.assertEqual(result["errorCode"], "ZHIHU_SEARCH_CARD_TYPE_INVALID")
                self.assertNotIn("SECRET", repr(result))

    async def test_unknown_content_type_is_not_silently_ignored(self):
        self.assertEqual((await self.run_case([page([obj("new-type")])]))["status"], "schema_error")

    async def test_non_target_results_are_counted_not_claimed_zero(self):
        result = await self.run_case([page([obj("question")])])
        self.assertEqual(result["excludedItems"], 1)
        self.assertEqual(result["errorCode"], "ZHIHU_EMPTY_COVERAGE_UNPROVEN")

    async def test_next_cursor_conflict_or_cross_host_rejected(self):
        job = fixture("crawl_job", "zhihu")
        for url in ("https://evil.example/api/v4/search_v3?offset=20", "https://www.zhihu.com/api/v4/search_v3?offset=0", "https://www.zhihu.com/api/v4/search_v3?offset=20&q=other"):
            data = page([obj()], False); data["paging"]["next"] = url
            self.assertEqual((await self.run_case([data]))["status"], "schema_error")
        data = page([obj()], False)
        data["paging"]["next"] = "https://www.zhihu.com/api/v4/search_v3?" + urlencode({"offset": 20, "q": job["query"]["text"]})
        self.assertEqual((await self.run_case([data]))["status"], "ok")

    async def test_cursor_failure_cause_is_fixed_without_leaking_url(self):
        cases = [
            ("https://evil.example/api/v4/search_v3?offset=20",
             "ZHIHU_PAGING_CURSOR_AUTHORITY"),
            ("http://www.zhihu.com/api/v4/search_v3?offset=20",
             "ZHIHU_PAGING_CURSOR_AUTHORITY"),
            ("https://api.zhihu.com.evil.invalid/api/v4/search_v3?offset=20",
             "ZHIHU_PAGING_CURSOR_AUTHORITY"),
            ("https://www.zhihu.com/api/v4/other?offset=20",
             "ZHIHU_CURSOR_PATH_OTHER_V4"),
            ("https://www.zhihu.com/api/v4/search_v3?offset=10",
             "ZHIHU_PAGING_CURSOR_OFFSET"),
            ("https://www.zhihu.com/api/v4/search_v3?offset=20&q=PRIVATE",
             "ZHIHU_PAGING_CURSOR_KEYWORD"),
            ("https://www.zhihu.com/api/v4/search_v3?offset=20&offset=20",
             "ZHIHU_PAGING_CURSOR_QUERY"),
            ("https://www.zhihu.com/api/v4/search_v3?offset=%XX",
             "ZHIHU_PAGING_CURSOR_OFFSET"),
        ]
        for url, code in cases:
            with self.subTest(code=code):
                data = page([obj()], False)
                data["paging"]["next"] = url
                result = await self.run_case([data])
                self.assertEqual(result["status"], "schema_error")
                self.assertEqual(result["errorCode"], code)
                self.assertNotIn("PRIVATE", repr(result))

    async def test_bounded_official_or_relative_next_cursor_is_metadata_only(self):
        for url in (
            "/api/v4/search_v3?offset=20",
            "https://api.zhihu.com/api/v4/search_v3?offset=20",
            "https://www.zhihu.com/api/v4/search_v3?offset=20",
        ):
            with self.subTest(authority=url.split("/api/v4/")[0]):
                data = page([obj()], False)
                data["paging"]["next"] = url
                result = await self.run_case([data])
                self.assertEqual(result["status"], "ok")
                self.assertEqual(len(result["records"]), 1)
                self.assertEqual(len(self.calls), 1)

    async def test_cursor_diagnostic_classes_never_echo_untrusted_paths(self):
        cases = (
            ("/api/v4/search_v3/", "ZHIHU_CURSOR_PATH_TRAILING_SLASH"),
            ("api/v4/search_v3", "ZHIHU_CURSOR_PATH_RELATIVE_NO_SLASH"),
            ("/api/v4/search_v2", "ZHIHU_CURSOR_PATH_SEARCH_V2"),
            ("/api/v4/search", "ZHIHU_CURSOR_PATH_SEARCH_LEGACY"),
            ("/api/v4/search_v3/next", "ZHIHU_CURSOR_PATH_V3_NESTED"),
            ("/api/v4/search_post", "ZHIHU_CURSOR_PATH_SEARCH_FAMILY"),
            ("/api/v4/PRIVATE", "ZHIHU_CURSOR_PATH_OTHER_V4"),
            ("/api/PRIVATE", "ZHIHU_CURSOR_PATH_OTHER_API"),
            ("/search", "ZHIHU_CURSOR_PATH_WEB_SEARCH"),
            ("/search/PRIVATE", "ZHIHU_CURSOR_PATH_OTHER_WEB_SEARCH"),
            ("/PRIVATE-account-path", "ZHIHU_CURSOR_PATH_UNKNOWN"),
        )
        for path, expected in cases:
            with self.subTest(expected=expected):
                data = page([obj()], False)
                data["paging"]["next"] = (
                    path if not path.startswith("/") else "https://www.zhihu.com" + path
                ) + "?offset=20"
                result = await self.run_case([data])
                if expected == "ZHIHU_CURSOR_PATH_OTHER_WEB_SEARCH":
                    # The one-page-only exception treats this as an ignored
                    # hint, not a trusted pagination cursor.
                    self.assertEqual(result["status"], "ok")
                    self.assertIsNone(result["pages"][0]["hasMore"])
                    self.assertEqual(result["stopReason"], "page_limit")
                else:
                    self.assertEqual(result["status"], "schema_error")
                    self.assertEqual(result["errorCode"], expected)
                self.assertNotIn("PRIVATE", repr(result))

    async def test_observed_web_search_cursor_is_metadata_only_for_one_page(self):
        for url in (
            "https://www.zhihu.com/search/type?offset=20&q=PRIVATE",
            "https://api.zhihu.com/search/something?offset=20",
            "/search/unrecognized?offset=20",
        ):
            data = page([obj()], False)
            data["paging"]["next"] = url
            result = await self.run_case([data], records=2)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["stopReason"], "page_limit")
            self.assertIsNone(result["pages"][0]["hasMore"])
            self.assertEqual(len(result["records"]), 1)
            self.assertEqual(len(self.calls), 1)
            self.assertNotIn("PRIVATE", repr(result))

    async def test_web_search_cursor_not_trusted_for_multi_page_or_empty(self):
        data = page([obj()], False)
        data["paging"]["next"] = "/search/unrecognized?offset=20"
        next_page = page([obj(native="102")], True)
        result = await self.run_case([data, next_page])
        self.assertEqual(result["errorCode"], "ZHIHU_CURSOR_PATH_OTHER_WEB_SEARCH")
        self.assertEqual(result["status"], "schema_error")
        self.assertEqual(len(self.calls), 1)
        no_data = page([], False)
        no_data["paging"]["next"] = "/search/unrecognized?offset=20"
        result = await self.run_case([no_data])
        self.assertEqual(result["status"], "schema_error")
        self.assertEqual(result["errorCode"], "ZHIHU_CURSOR_PATH_OTHER_WEB_SEARCH")

    async def test_official_source_constraint_not_relaxed_for_metadata_hint(self):
        data = page([obj()], False)
        data["paging"]["next"] = "https://evil.example/search/unrecognized?offset=20"
        result = await self.run_case([data])
        self.assertEqual(result["errorCode"], "ZHIHU_PAGING_CURSOR_AUTHORITY")

    async def test_duplicate_across_pages_not_projected_twice(self):
        result = await self.run_case([page([obj()], False), page([obj()])])
        self.assertEqual(result["searchDuplicates"], 1)
        self.assertEqual(len(result["records"]), 1)

    async def test_conflicting_parent_is_rejected(self):
        result = await self.run_case([page([obj(), obj(parent="901")])])
        self.assertEqual(result["errorCode"], "ZHIHU_ANSWER_QUESTION_CONFLICT")
        self.assertEqual(len(result["records"]), 1)

    async def test_large_ids_exact_and_float_bool_rejected(self):
        native = "900719925474099312345"
        result = await self.run_case([page([obj(native=int(native))])])
        self.assertEqual(result["records"][0]["record"]["content_id"], native)
        for value in (1.0, True, "01", "", None):
            self.assertEqual((await self.run_case([page([obj(native=value)])]))["status"], "schema_error")

    async def test_item_budget_counts_unprojected(self):
        result = await self.run_case([page([obj(), obj(native="102")])], records=1)
        self.assertEqual(result["stopReason"], "item_limit")
        self.assertEqual(result["detailsNotRequested"], 1)

    async def test_second_page_failure_keeps_first(self):
        result = await self.run_case([page([obj()], False), obs.CollectorError("network_error", "NETWORK")])
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["status"], "network_error")

    async def test_restriction_stops_without_retry(self):
        result = await self.run_case([obs.CollectorError("rate_limited", "LIMIT", 600), page()])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["retryAfter"], 600)

    async def test_projection_identity_and_types_checked(self):
        async def wrong(value):
            result = await projection(value); result["content_id"] = "999"; return result
        self.assertEqual((await self.run_case([page([obj()])], project=wrong))["errorCode"], "ZHIHU_PROJECTION_ID_CONFLICT")
        async def nested(value): return {**await projection(value), "content": {"bad": 1}}
        self.assertEqual((await self.run_case([page([obj()])], project=nested))["status"], "schema_error")

    async def test_raw_person_media_and_tokens_do_not_cross_boundary(self):
        async def extra(value):
            return {**await projection(value), "user_id": "PRIVATE", "access_token": "PRIVATE", "video_url": "PRIVATE"}
        result = await self.run_case([page([obj()])], project=extra)
        self.assertNotIn("PRIVATE", repr(result))

    async def test_native_filter_rejected_before_search(self):
        result = await self.run_case([page()], mutate=lambda job: job["window"].update(filterMode="native"))
        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(self.calls, [])

    async def test_zvideo_wrapper_must_match_object(self):
        data = page([obj()]); data["data"][0]["type"] = "zvideo"
        self.assertEqual((await self.run_case([data]))["errorCode"], "ZHIHU_WRAPPER_TYPE_CONFLICT")

    async def test_unknown_exception_text_never_exported(self):
        result = await self.run_case([RuntimeError("cookie=PRIVATE")])
        self.assertEqual(result["status"], "schema_error")
        self.assertNotIn("PRIVATE", repr(result))


if __name__ == "__main__": unittest.main()
