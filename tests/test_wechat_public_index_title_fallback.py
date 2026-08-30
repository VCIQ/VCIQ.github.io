from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import wechat_public_index_title_fallback as fallback


class _Crawler:
    @staticmethod
    def normalize_date(value):
        return str(value or "") or None


class _EmptyIndex:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def build_search_url(self, _spec, *, query: str) -> str:
        self.queries.append(query)
        return f"https://weixin.sogou.com/weixin?query={len(self.queries)}"

    @staticmethod
    def _request(_url: str, *, referer: str = "") -> str:
        return ""

    @staticmethod
    def parse_search_results(_body: str, _search_url: str) -> list[dict]:
        return []


class WeChatPublicIndexTitleFallbackTests(unittest.TestCase):
    def test_original_detail_resolution_runs_before_title_lookup(self) -> None:
        events: list[str] = []

        def original(*_args):
            events.append("original")
            return []

        bridge = SimpleNamespace(_resolve_detail_row=original)
        with patch.object(
            fallback,
            "_resolve_by_title",
            side_effect=lambda *_args: events.append("title") or [{"url": "direct"}],
        ):
            fallback.install(bridge, SimpleNamespace())
            resolved = bridge._resolve_detail_row(
                {"kind": "detail", "title": "足够长的测试文章标题"},
                {},
                "ua",
                _Crawler(),
            )

        self.assertEqual(events, ["original", "title"])
        self.assertEqual(resolved, [{"url": "direct"}])

    def test_successful_original_resolution_skips_title_lookup(self) -> None:
        expected = [{"kind": "wechat", "url": "https://mp.weixin.qq.com/s/direct"}]
        bridge = SimpleNamespace(_resolve_detail_row=lambda *_args: expected)
        with patch.object(fallback, "_resolve_by_title") as title_lookup:
            fallback.install(bridge, SimpleNamespace())
            resolved = bridge._resolve_detail_row(
                {"kind": "detail", "title": "足够长的测试文章标题"},
                {},
                "ua",
                _Crawler(),
            )

        self.assertIs(resolved, expected)
        title_lookup.assert_not_called()

    def test_non_detail_rows_never_enter_title_lookup(self) -> None:
        row = {"kind": "wechat", "url": "https://mp.weixin.qq.com/s/direct"}
        bridge = SimpleNamespace(_resolve_detail_row=lambda value, *_args: [value])
        with patch.object(fallback, "_resolve_by_title") as title_lookup:
            fallback.install(bridge, SimpleNamespace())
            resolved = bridge._resolve_detail_row(row, {}, "ua", _Crawler())

        self.assertEqual(resolved, [row])
        title_lookup.assert_not_called()

    def test_exact_then_fragment_budget_is_shared_across_rows(self) -> None:
        index = _EmptyIndex()
        bridge = SimpleNamespace(_resolve_detail_row=lambda *_args: [])
        fallback.install(bridge, index)
        spec: dict = {}
        first_title = "独家丨腾讯芯片一号位，离职创业，投身AI CPU"
        titles = (
            first_title,
            "重磅丨具身机器人制造基地正式落地常州",
            "观察丨动力电池产业迎来新一轮技术迭代",
        )
        for title in titles:
            bridge._resolve_detail_row(
                {"kind": "detail", "title": title, "date": ""},
                spec,
                "ua",
                _Crawler(),
            )

        self.assertEqual(index.queries, fallback._query_variants(first_title))
        self.assertEqual(
            spec["_publicIndexTitleSearchQueries"],
            fallback.MAX_SEARCH_QUERIES_PER_SOURCE,
        )
        self.assertEqual(spec["_publicIndexTitleLookupTitles"], [first_title])

    def test_budget_is_isolated_between_sources(self) -> None:
        index = _EmptyIndex()
        bridge = SimpleNamespace(_resolve_detail_row=lambda *_args: [])
        fallback.install(bridge, index)
        titles = (
            "独家丨腾讯芯片一号位，离职创业，投身AI CPU",
            "重磅丨具身机器人制造基地正式落地常州",
        )
        first: dict = {}
        second: dict = {}

        for spec in (first, second):
            for title in titles:
                bridge._resolve_detail_row(
                    {"kind": "detail", "title": title, "date": ""},
                    spec,
                    "ua",
                    _Crawler(),
                )

        self.assertEqual(len(index.queries), 4)
        self.assertEqual(first["_publicIndexTitleSearchQueries"], 2)
        self.assertEqual(second["_publicIndexTitleSearchQueries"], 2)
        self.assertEqual(len(first["_publicIndexTitleLookupTitles"]), 1)
        self.assertEqual(len(second["_publicIndexTitleLookupTitles"]), 1)

    def test_duplicate_title_does_not_repeat_exact_or_fragment_lookup(self) -> None:
        index = _EmptyIndex()
        bridge = SimpleNamespace(_resolve_detail_row=lambda *_args: [])
        fallback.install(bridge, index)
        spec: dict = {}
        title = "独家丨腾讯芯片一号位，离职创业，投身AI CPU"

        for _ in range(2):
            bridge._resolve_detail_row(
                {"kind": "detail", "title": title, "date": ""},
                spec,
                "ua",
                _Crawler(),
            )

        self.assertEqual(index.queries, fallback._query_variants(title))
        self.assertEqual(spec["_publicIndexTitleSearchQueries"], 2)
        self.assertEqual(spec["_publicIndexTitleLookupTitles"], [title])

    def test_short_fragment_resolves_after_exact_candidate_redirect_fails(self) -> None:
        class FragmentIndex(_EmptyIndex):
            def __init__(self) -> None:
                super().__init__()
                self.redirects: list[str] = []

            @staticmethod
            def _normalized_url(value: str) -> str:
                return value

            def _request(self, url: str, *, referer: str = "") -> str:
                if referer:
                    self.redirects.append(url)
                    return url
                return f"search-{len(self.queries)}"

            def parse_search_results(
                self,
                _body: str,
                _search_url: str,
            ) -> list[dict]:
                return [
                    {
                        "url": (
                            "https://example.com/exact"
                            if len(self.queries) == 1
                            else "https://example.com/fragment"
                        ),
                        "title": "腾讯芯片一号位离职创业投身AI CPU",
                        "publishedAt": "",
                    }
                ]

            @staticmethod
            def resolve_script_url(body: str) -> str:
                if body.endswith("/fragment"):
                    return "https://mp.weixin.qq.com/s/resolved-fragment"
                return ""

        index = FragmentIndex()
        bridge = SimpleNamespace(_resolve_detail_row=lambda *_args: [])
        fallback.install(bridge, index)
        spec: dict = {}
        title = "独家丨腾讯芯片一号位，离职创业，投身AI CPU"

        resolved = bridge._resolve_detail_row(
            {
                "kind": "detail",
                "title": title,
                "date": "",
            },
            spec,
            "ua",
            _Crawler(),
        )

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["kind"], "wechat")
        self.assertEqual(
            resolved[0]["url"],
            "https://mp.weixin.qq.com/s/resolved-fragment",
        )
        self.assertEqual(index.queries, fallback._query_variants(title))
        self.assertEqual(
            index.redirects,
            ["https://example.com/exact", "https://example.com/fragment"],
        )
        self.assertEqual(spec["_publicIndexTitleSearchQueries"], 2)
        self.assertEqual(spec["_publicIndexTitleRedirectAttempts"], 2)

    def test_successful_exact_query_does_not_spend_fragment_budget(self) -> None:
        class ExactIndex(_EmptyIndex):
            @staticmethod
            def _normalized_url(value: str) -> str:
                return value

            def _request(self, url: str, *, referer: str = "") -> str:
                return "jump" if referer else "search"

            def parse_search_results(
                self,
                _body: str,
                _search_url: str,
            ) -> list[dict]:
                return [
                    {
                        "url": "https://example.com/exact",
                        "title": "腾讯芯片一号位离职创业投身AI CPU",
                        "publishedAt": "",
                    }
                ]

            @staticmethod
            def resolve_script_url(_body: str) -> str:
                return "https://mp.weixin.qq.com/s/resolved-exact"

        index = ExactIndex()
        bridge = SimpleNamespace(_resolve_detail_row=lambda *_args: [])
        fallback.install(bridge, index)
        spec: dict = {}
        title = "独家丨腾讯芯片一号位，离职创业，投身AI CPU"

        resolved = bridge._resolve_detail_row(
            {
                "kind": "detail",
                "title": title,
                "date": "",
            },
            spec,
            "ua",
            _Crawler(),
        )

        self.assertEqual(len(resolved), 1)
        self.assertEqual(index.queries, [fallback._query_variants(title)[0]])
        self.assertEqual(spec["_publicIndexTitleSearchQueries"], 1)
        self.assertEqual(spec["_publicIndexTitleRedirectAttempts"], 1)

    def test_circuit_open_is_recorded_without_leaking_request_details(self) -> None:
        class CircuitIndex(_EmptyIndex):
            @staticmethod
            def _request(_url: str, *, referer: str = "") -> str:
                raise RuntimeError("Sogou CAPTCHA cooldown is active")

        index = CircuitIndex()
        bridge = SimpleNamespace(_resolve_detail_row=lambda *_args: [])
        fallback.install(bridge, index)
        spec: dict = {}

        resolved = bridge._resolve_detail_row(
            {
                "kind": "detail",
                "title": "具身机器人制造基地正式落地常州并公布量产计划",
                "date": "",
            },
            spec,
            "ua",
            _Crawler(),
        )

        self.assertEqual(resolved, [])
        self.assertEqual(
            spec["_publicIndexTitleFailureKinds"],
            ["sogou-circuit-open"],
        )


if __name__ == "__main__":
    unittest.main()
