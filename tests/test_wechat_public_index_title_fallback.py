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
    def test_paraphrased_title_with_long_unique_segment_scores_safely(self) -> None:
        expected = "半导体全链聚合，IICIE国际集成电路创新博览会9月深圳举办"
        candidate = (
            "重磅嘉宾官宣！IICIE国际集成电路创新博览会开幕式暨"
            "集成电路创新高峰论坛，9月9日深圳启幕"
        )
        unrelated = "英伟达发布新一代Rubin架构与人工智能计算平台"

        self.assertGreaterEqual(
            fallback._title_score(expected, candidate, expected),
            fallback.MIN_TITLE_SCORE,
        )
        self.assertLess(
            fallback._title_score(expected, unrelated, expected),
            fallback.MIN_TITLE_SCORE,
        )

    def test_explicit_wrong_sogou_account_is_rejected_before_redirect(self) -> None:
        title = "中芯国际发布先进封装芯片量产进展"
        rows = [
            {
                "url": "https://weixin.sogou.com/link?wrong",
                "title": title,
                "account": "转载观察",
                "publishedAt": "",
            },
            {
                "url": "https://weixin.sogou.com/link?right",
                "title": title,
                "account": "半导体技术",
                "publishedAt": "",
            },
        ]
        spec = {"expectedAccounts": ["半导体技术"]}

        ranked = fallback._ranked_rows(
            rows,
            title,
            title,
            spec,
            _Crawler(),
        )

        self.assertEqual([row["account"] for row in ranked], ["半导体技术"])
        self.assertEqual(spec["_publicIndexTitleAccountMismatches"], 1)

    def test_missing_sogou_account_defers_identity_check_to_original_page(self) -> None:
        title = "中芯国际发布先进封装芯片量产进展"
        rows = [{
            "url": "https://weixin.sogou.com/link?unknown",
            "title": title,
            "account": "",
            "publishedAt": "",
        }]

        ranked = fallback._ranked_rows(
            rows,
            title,
            title,
            {"expectedAccounts": ["半导体技术"]},
            _Crawler(),
        )

        self.assertEqual(ranked, rows)

    def test_short_variant_is_distinct_when_full_title_fits_query_limit(self) -> None:
        title = "半导体全链聚合，IICIE国际集成电路创新博览会9月深圳举办"
        variants = fallback._query_variants(title)

        self.assertEqual(len(variants), 2)
        self.assertNotEqual(
            fallback._normalize_title(variants[0]),
            fallback._normalize_title(variants[1]),
        )
        self.assertIn("IICIE", variants[1])

    def test_acronym_fragment_keeps_high_signal_terms(self) -> None:
        title = "WAIC 2026释放强烈信号，HDD迎来“第二春”"

        self.assertEqual(
            fallback._query_variants(title)[1],
            "WAIC 2026 HDD",
        )

    def test_entity_prefix_stays_in_acronym_heavy_fragment(self) -> None:
        title = "澜起科技：净利增长超60%，DDR5 RCD芯片出货量显著增加"

        fragment = fallback._query_variants(title)[1]

        self.assertIn("澜起科技", fragment)
        self.assertIn("DDR5", fragment)
        self.assertNotEqual(fragment, "60 DDR5 RCD")

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

    def test_title_only_discovery_hint_enters_bounded_lookup(self) -> None:
        row = {
            "kind": "title",
            "url": "https://www.jintiankansha.com/column/test",
            "title": "澜起科技DDR5芯片出货量显著增加",
            "date": "",
        }
        bridge = SimpleNamespace(_resolve_detail_row=lambda value, *_args: [value])
        with patch.object(
            fallback,
            "_resolve_by_title",
            return_value=[{"kind": "wechat", "url": "https://mp.weixin.qq.com/s/direct"}],
        ) as title_lookup:
            fallback.install(bridge, SimpleNamespace())
            resolved = bridge._resolve_detail_row(row, {}, "ua", _Crawler())

        self.assertEqual(resolved[0]["kind"], "wechat")
        title_lookup.assert_called_once()

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

        self.assertEqual(index.queries, [
            fallback._query_variants(titles[0])[0],
            fallback._query_variants(titles[1])[-1],
        ])
        self.assertEqual(
            spec["_publicIndexTitleSearchQueries"],
            fallback.MAX_SEARCH_QUERIES_PER_SOURCE,
        )
        self.assertEqual(spec["_publicIndexTitleLookupTitles"], list(titles[:2]))

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
        self.assertEqual(len(first["_publicIndexTitleLookupTitles"]), 2)
        self.assertEqual(len(second["_publicIndexTitleLookupTitles"]), 2)

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

        self.assertEqual(index.queries, [fallback._query_variants(title)[0]])
        self.assertEqual(spec["_publicIndexTitleSearchQueries"], 1)
        self.assertEqual(spec["_publicIndexTitleLookupTitles"], [title])

    def test_next_title_short_fragment_resolves_after_exact_redirect_fails(self) -> None:
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
                        "title": (
                            "腾讯芯片一号位离职创业投身AI CPU"
                            if len(self.queries) == 1
                            else "具身机器人制造基地正式落地常州"
                        ),
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

        exact = bridge._resolve_detail_row(
            {
                "kind": "detail",
                "title": title,
                "date": "",
            },
            spec,
            "ua",
            _Crawler(),
        )
        next_title = "重磅丨具身机器人制造基地正式落地常州"
        resolved = bridge._resolve_detail_row(
            {"kind": "detail", "title": next_title, "date": ""},
            spec,
            "ua",
            _Crawler(),
        )

        self.assertEqual(exact, [])
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["kind"], "wechat")
        self.assertEqual(
            resolved[0]["url"],
            "https://mp.weixin.qq.com/s/resolved-fragment",
        )
        self.assertEqual(index.queries, [
            fallback._query_variants(title)[0],
            fallback._query_variants(next_title)[-1],
        ])
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

    def test_two_equal_headlines_preserve_second_redirect_for_identity_gate(self) -> None:
        class SyndicatedIndex(_EmptyIndex):
            @staticmethod
            def _normalized_url(value: str) -> str:
                return value

            def _request(self, url: str, *, referer: str = "") -> str:
                return url if referer else "search"

            @staticmethod
            def parse_search_results(_body: str, _search_url: str) -> list[dict]:
                title = "宁德时代钠电储能项目正式落地"
                return [
                    {"url": "https://example.com/copied", "title": title, "account": "", "publishedAt": ""},
                    {"url": "https://example.com/original", "title": title, "account": "", "publishedAt": ""},
                ]

            @staticmethod
            def resolve_script_url(body: str) -> str:
                suffix = "copied" if body.endswith("/copied") else "original"
                return f"https://mp.weixin.qq.com/s/{suffix}"

        index = SyndicatedIndex()
        bridge = SimpleNamespace(_resolve_detail_row=lambda *_args: [])
        fallback.install(bridge, index)
        spec = {"expectedAccounts": ["电池中国"]}

        resolved = bridge._resolve_detail_row(
            {"kind": "detail", "title": "宁德时代钠电储能项目正式落地", "date": ""},
            spec,
            "ua",
            _Crawler(),
        )

        self.assertEqual([row["titleLookupRank"] for row in resolved], ["1", "2"])
        self.assertEqual(spec["_publicIndexTitleSearchQueries"], 1)
        self.assertEqual(spec["_publicIndexTitleRedirectAttempts"], 2)

    def test_first_direct_resolution_stops_later_title_lookups(self) -> None:
        class ExactIndex(_EmptyIndex):
            @staticmethod
            def _normalized_url(value: str) -> str:
                return value

            @staticmethod
            def _request(_url: str, *, referer: str = "") -> str:
                return "jump" if referer else "search"

            @staticmethod
            def parse_search_results(_body: str, _search_url: str) -> list[dict]:
                return [{
                    "url": "https://example.com/exact",
                    "title": "腾讯芯片一号位离职创业投身AI CPU",
                    "publishedAt": "",
                }]

            @staticmethod
            def resolve_script_url(_body: str) -> str:
                return "https://mp.weixin.qq.com/s/resolved-exact"

        index = ExactIndex()
        bridge = SimpleNamespace(_resolve_detail_row=lambda *_args: [])
        fallback.install(bridge, index)
        spec: dict = {}

        first = bridge._resolve_detail_row(
            {"kind": "detail", "title": "腾讯芯片一号位离职创业投身AI CPU", "date": ""},
            spec,
            "ua",
            _Crawler(),
        )
        second = bridge._resolve_detail_row(
            {"kind": "detail", "title": "具身机器人制造基地正式落地常州", "date": ""},
            spec,
            "ua",
            _Crawler(),
        )

        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(len(index.queries), 1)
        self.assertEqual(spec["_publicIndexTitleLookupTitles"], [
            "腾讯芯片一号位离职创业投身AI CPU"
        ])

    def test_stale_exact_match_preserves_short_query_for_next_title(self) -> None:
        class StaleThenFreshIndex(_EmptyIndex):
            @staticmethod
            def _normalized_url(value: str) -> str:
                return value

            def _request(self, url: str, *, referer: str = "") -> str:
                return "jump" if referer else f"search-{len(self.queries)}"

            def parse_search_results(self, _body: str, _search_url: str) -> list[dict]:
                if len(self.queries) == 1:
                    return [{
                        "url": "https://example.com/stale",
                        "title": "英伟达Rubin GPU芯片正式发布3360亿晶体管",
                        "publishedAt": "2026-03-17",
                    }]
                return [{
                    "url": "https://example.com/fresh",
                    "title": "WAIC 2026释放强烈信号 HDD迎来第二春",
                    "publishedAt": "2026-08-24",
                }]

            @staticmethod
            def resolve_script_url(_body: str) -> str:
                return "https://mp.weixin.qq.com/s/resolved-fresh"

        index = StaleThenFreshIndex()
        bridge = SimpleNamespace(_resolve_detail_row=lambda *_args: [])
        fallback.install(bridge, index)
        spec = {"maxArticleAgeDays": 45}
        stale_title = "3360亿晶体管！英伟达Rubin GPU细节首曝：智能体AI性能提升10倍"
        fresh_title = "WAIC 2026释放强烈信号，HDD迎来“第二春”"

        stale = bridge._resolve_detail_row(
            {"kind": "detail", "title": stale_title, "date": ""},
            spec,
            "ua",
            _Crawler(),
        )
        fresh = bridge._resolve_detail_row(
            {"kind": "detail", "title": fresh_title, "date": ""},
            spec,
            "ua",
            _Crawler(),
        )

        self.assertEqual(stale, [])
        self.assertEqual(len(fresh), 1)
        self.assertEqual(index.queries[0], fallback._query_variants(stale_title)[0])
        self.assertEqual(index.queries[1], fallback._query_variants(fresh_title)[-1])
        self.assertEqual(spec["_publicIndexTitleSearchQueries"], 2)
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
