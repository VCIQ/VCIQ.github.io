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

    def test_search_budget_is_shared_across_rows_and_capped_at_two(self) -> None:
        index = _EmptyIndex()
        bridge = SimpleNamespace(_resolve_detail_row=lambda *_args: [])
        fallback.install(bridge, index)
        spec: dict = {}
        titles = (
            "独家丨腾讯芯片一号位，离职创业，投身AI CPU",
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

        self.assertEqual(len(index.queries), 2)
        self.assertEqual(
            spec["_publicIndexTitleSearchQueries"],
            fallback.MAX_SEARCH_QUERIES_PER_SOURCE,
        )

    def test_budget_is_isolated_between_sources(self) -> None:
        index = _EmptyIndex()
        bridge = SimpleNamespace(_resolve_detail_row=lambda *_args: [])
        fallback.install(bridge, index)
        title = "独家丨腾讯芯片一号位，离职创业，投身AI CPU"
        first: dict = {}
        second: dict = {}

        for spec in (first, second):
            bridge._resolve_detail_row(
                {"kind": "detail", "title": title, "date": ""},
                spec,
                "ua",
                _Crawler(),
            )

        self.assertEqual(len(index.queries), 4)
        self.assertEqual(first["_publicIndexTitleSearchQueries"], 2)
        self.assertEqual(second["_publicIndexTitleSearchQueries"], 2)


if __name__ == "__main__":
    unittest.main()
