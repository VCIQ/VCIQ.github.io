"""Synthetic Weibo responses only; no accounts, sockets, or browser required."""
import copy
import unittest

from tests.test_social_contracts import fixture
from workers.mediacrawler.observer import CollectorError
from workers.mediacrawler.weibo_observer import collect_weibo, extract_posts, native_id

NOW = "2026-10-23T12:00:00+00:00"
ID = "9007199254740993123"


def card(identity=ID, **extra):
    return {"card_type": 9, "mblog": {"id": identity, "text": "合成机器人融资", **extra}}


class WeiboObserverTests(unittest.IsolatedAsyncioTestCase):
    async def run_query(self, responses, *, maximum=20, pages=2, project=None, job=None):
        selected = job or fixture("crawl_job", "wb")
        selected["limits"].update(maxSearchPages=pages, maxRecords=maximum)
        requests, projected = [], []
        async def search(keyword, page):
            requests.append((keyword, page))
            value = responses[page - 1]
            if isinstance(value, Exception):
                raise value
            return copy.deepcopy(value)
        async def default_projection(item):
            projected.append(item)
            return {"note_id": item["mblog"]["id"], "content": item["mblog"].get("text")}
        output = await collect_weibo(selected, search, project or default_projection, clock=lambda: NOW)
        return output, requests, projected

    async def test_nested_cards_and_exact_query_pages(self):
        response = {"cards": [{"card_type": 11, "card_group": [card()]}, {"card_type": 1}]}
        result, calls, _ = await self.run_query([response, {"cards": []}])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stopReason"], "exhausted")
        self.assertEqual([page for _, page in calls], [1, 2])
        self.assertTrue(all(term == fixture("crawl_job", "wb")["query"]["text"] for term, _ in calls))
        self.assertEqual(result["records"][0]["record"]["note_id"], ID)

    async def test_large_integer_id_is_exact_string(self):
        result, _, _ = await self.run_query([{"cards": [card(int(ID))]}], pages=1)
        self.assertEqual(result["records"][0]["record"]["note_id"], ID)

    def test_float_bool_and_conflicting_ids_rejected(self):
        for value in (True, 1.0, -1, "", "001", "1e20", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                native_id(value)
        with self.assertRaisesRegex(ValueError, "ID_CONFLICT"):
            extract_posts({"cards": [card(mid="123")]})

    async def test_positive_page_never_infers_exhaustion_from_total(self):
        result, _, _ = await self.run_query([{"cards": [card()], "cardlistInfo": {"total": 1}}], pages=1)
        self.assertEqual(result["stopReason"], "page_limit")
        self.assertIsNone(result["pages"][0]["hasMore"])

    async def test_explicit_empty_success_page(self):
        result, calls, _ = await self.run_query([{"cards": []}])
        self.assertEqual(result["status"], "empty")
        self.assertEqual(len(calls), 1)

    async def test_recommendations_only_are_not_proven_empty(self):
        result, _, _ = await self.run_query([{"cards": [{"card_type": 1}]}], pages=1)
        self.assertEqual(result["errorCode"], "EMPTY_COVERAGE_UNPROVEN")

    async def test_missing_cards_and_unknown_shapes_fail(self):
        for response in ({}, {"cards": None}, {"cards": [None]}, {"cards": [{"card_type": 9}]}, {"cards": [], "cardlistInfo": []}):
            with self.subTest(response=response):
                result, _, _ = await self.run_query([response])
                self.assertEqual(result["status"], "schema_error")

    async def test_duplicate_across_pages_not_projected_twice(self):
        result, _, projected = await self.run_query([{"cards": [card()]}, {"cards": [card()]}])
        self.assertEqual(len(projected), 1)
        self.assertEqual(result["searchDuplicates"], 1)

    async def test_item_budget_is_hard_and_counts_unprojected(self):
        result, calls, projected = await self.run_query([{"cards": [card(), card("123"), card("456")]}], maximum=1)
        self.assertEqual(len(projected), 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["detailsNotRequested"], 2)
        self.assertEqual(result["stopReason"], "item_limit")

    async def test_second_page_failure_retains_first_page(self):
        result, _, _ = await self.run_query([{"cards": [card()]}, CollectorError("network_error", "SEARCH_FAILED")])
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["status"], "network_error")

    async def test_restriction_and_retry_after_not_retried(self):
        for status in ("auth_required", "verification_required", "rate_limited"):
            result, calls, _ = await self.run_query([CollectorError(status, "RESTRICTED", 90000)])
            self.assertEqual(result["status"], status)
            self.assertEqual(result["retryAfter"], 90000)
            self.assertEqual(len(calls), 1)

    async def test_tokens_user_ids_and_nested_repost_not_exported(self):
        async def project(item):
            return {"note_id": ID, "content": "合成", "user_id": "PRIVATE", "note_url": "PRIVATE", "xsec_token": "PRIVATE", "retweeted_status": {"id": "123"}}
        result, _, _ = await self.run_query([{"cards": [card(retweeted_status={"id": "123"})]}], pages=1, project=project)
        self.assertNotIn("PRIVATE", repr(result))
        self.assertNotIn("retweeted_status", result["records"][0]["record"])
        self.assertEqual(len(result["records"]), 1)

    async def test_projection_identity_must_match(self):
        async def project(item): return {"note_id": "123"}
        result, _, _ = await self.run_query([{"cards": [card()]}], project=project)
        self.assertEqual(result["errorCode"], "WEIBO_PROJECTION_ID")

    async def test_projection_fields_are_bounded_scalars(self):
        for value in ({"private": "data"}, "x" * 100001):
            async def project(item): return {"note_id": ID, "content": value}
            result, _, _ = await self.run_query([{"cards": [card()]}], project=project)
            self.assertEqual(result["status"], "schema_error")

    async def test_unknown_exception_is_not_echoed(self):
        result, _, _ = await self.run_query([ValueError("PRIVATE_COOKIE")])
        self.assertNotIn("PRIVATE_COOKIE", repr(result))
        self.assertEqual(result["status"], "schema_error")

    async def test_native_filters_and_query_delimiters_rejected_before_search(self):
        for text in ("a&b", "a=b", "a,b", "a#b", "a?b"):
            job = fixture("crawl_job", "wb")
            job["query"]["text"] = text
            result, calls, _ = await self.run_query([], job=job)
            self.assertEqual(result["status"], "unsupported")
            self.assertEqual(calls, [])
        job = fixture("crawl_job", "wb")
        job["window"]["filterMode"] = "native"
        result, calls, _ = await self.run_query([], job=job)
        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(calls, [])

    def test_deep_or_overlarge_group_rejected(self):
        group = []
        for _ in range(5): group = [{"card_type": 11, "card_group": group}]
        for cards in (group, [{}] * 201):
            with self.assertRaises(ValueError): extract_posts({"cards": cards})


if __name__ == "__main__": unittest.main()
