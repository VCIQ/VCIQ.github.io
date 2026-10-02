"""Exact SMIC publication-field and CXMT entry regressions; no network."""
from contextlib import ExitStack, redirect_stdout
from datetime import UTC, datetime, timedelta
from io import StringIO
import unittest
from unittest.mock import patch

from tools import crawl_official_companies as c
from tools import crawl_official_with_tracking as tracking
from tools import crawl_official_with_source_categories as categories
from tools import eastmoney_transport as entrypoint


class P1RoundFourSourceTests(unittest.TestCase):
    def setUp(self):
        specs = {s.slug: s for s in c.load_registry()}
        self.smic, self.cxmt = specs["smic"], specs["cxmt"]
        self.day = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
        self.url = "https://www.smics.com/site/news_read/3722"
        self.title = "中芯国际发布最新季度经营与制造技术进展"

    def body(self, day, *, extra=""):
        return (f'<h1>{self.title}</h1><div class="container clearfix">'
                f'<div class="date clearfix"><div><p>{day}</p></div>'
                '<ul><li><a>打印</a></li><li><a>返回</a></li></ul></div>'
                '<div class="content">财务期间 2025-06-30，报告日期 '
                f'2025-08-13，点击量 2026。</div></div>{extra}')

    def test_smic_nested_field_not_fiscal_dates_or_clicks(self):
        article = c._article_from_page(self.smic, self.url, self.body(self.day))
        self.assertIsNotNone(article)
        self.assertEqual(article["publishedAt"], self.day)
        self.assertEqual(article["publicationDateEvidence"]["method"], "official-detail-field")
        self.assertEqual(article["publicationDateEvidence"]["sourceUrl"], self.url)

    def test_smic_class_order_and_nested_inline_text(self):
        body = self.body(f"<span>{self.day}</span>").replace('class="date clearfix"', 'class="clearfix date"')
        self.assertEqual(c._article_from_page(self.smic, self.url, body)["publishedAt"], self.day)

    def test_smic_scope_excludes_other_hosts_paths_and_companies(self):
        body = self.body(self.day)
        for url in ("https://www.smics.com/site/news", "https://www.smics.com/site/productdetail/3722",
                    "https://www.smics.com.evil.example/site/news_read/3722",
                    "https://unrelated.example/site/news_read/3722"):
            with self.subTest(url=url):
                self.assertEqual(c._smic_publication_dates(self.smic, url, body), [])
        self.assertEqual(c._smic_publication_dates(self.cxmt, self.url, body), [])

    def test_smic_footer_and_unrelated_date_classes_are_not_fields(self):
        for body in (f'<footer><div class="date clearfix"><div><p>{self.day}</p></div></div></footer>',
                     f'<div class="content"><p>{self.day}</p></div>',
                     f'<div class="date"><div><p>{self.day}</p></div></div>'):
            self.assertEqual(c._smic_publication_dates(self.smic, self.url, body), [])

    def test_smic_invalid_future_and_conflicting_dates_fail_closed(self):
        future = (datetime.now(UTC).date() + timedelta(days=3)).isoformat()
        other = (datetime.now(UTC).date() - timedelta(days=2)).isoformat()
        evidence = [{"title": self.title, "publishedAt": self.day,
                     "sourceUrl": "https://www.smics.com/site/news", "method": "official-index-link"}]
        cases = [self.body(day) for day in ("2026-02-30", "2026", "", "点击量 1234", future)]
        cases += [self.body(self.day, extra=f'<meta name="date" content="{other}">'),
                  self.body(self.day) + self.body(other)]
        for body in cases:
            with self.subTest(body=body[:100]):
                counts = {}
                self.assertIsNone(c._article_from_page(self.smic, self.url, body, counts, evidence))
                self.assertEqual(counts, {"conflicting-or-invalid-detail-publication-date": 1})

    def test_smic_old_detail_cannot_be_refreshed_by_index(self):
        old = (datetime.now(UTC).date() - timedelta(days=self.smic.max_age_days + 1)).isoformat()
        evidence = [{"title": self.title, "publishedAt": self.day,
                     "sourceUrl": self.smic.homepage, "method": "official-index-link"}]
        counts = {}
        self.assertIsNone(c._article_from_page(self.smic, self.url, self.body(old), counts, evidence))
        self.assertEqual(counts, {"outside-age-window": 1})

    def test_smic_date_is_not_attached_to_a_different_canonical_article(self):
        body = self.body(self.day, extra='<meta property="og:url" content="https://www.smics.com/site/news_read/3723">')
        counts = {}
        self.assertIsNone(c._article_from_page(self.smic, self.url, body, counts))
        self.assertEqual(counts, {"canonical-detail-mismatch": 1})

    def test_cxmt_index_date_remains_bound_to_same_detail_title(self):
        self.assertEqual(self.cxmt.news_urls, ("https://www.cxmt.com/news.html",))
        url = "https://www.cxmt.com/news/info_97.html"
        title = "长鑫存储发布新一代技术平台并实现量产"
        index = f'<a href="/news/info_97.html">{title} {self.day}</a>'
        rows = c._index_publication_evidence(self.cxmt.news_urls[0], index, self.cxmt)[url]
        body = f'<h1>{title}</h1><p>历史日期2024-01-01；财务期2025-03-31。</p>'
        # A clean detail title is mandatory; list evidence alone is not enough.
        article = c._article_from_page(self.cxmt, url, body, index_evidence=rows)
        self.assertEqual(article["publishedAt"], self.day)
        self.assertIsNone(c._article_from_page(self.cxmt, url, '<h1>长鑫存储另一项技术发布与量产消息</h1>', index_evidence=rows))

    def test_smic_field_survives_actual_scheduled_adapter_chain(self):
        def assertion():
            counts = {}
            article = c._article_from_page(self.smic, self.url, self.body(self.day), counts, ())
            self.assertEqual(article["publishedAt"], self.day)
            self.assertEqual(article["companySlug"], "smic")
            self.assertEqual(counts, {})
            return 0
        with ExitStack() as stack:
            for module in (c, tracking, categories):
                stack.enter_context(patch.dict(module.__dict__, module.__dict__.copy()))
            writer = stack.enter_context(patch.object(c, "write_if_changed"))
            terminal = stack.enter_context(patch.object(c, "main", side_effect=assertion))
            with redirect_stdout(StringIO()):
                self.assertEqual(entrypoint.main(), 0)
            terminal.assert_called_once()
            writer.assert_not_called()

    def test_source_budgets_and_required_entity_match_are_unchanged(self):
        for spec in (self.smic, self.cxmt):
            self.assertEqual((spec.max_items, spec.max_candidate_links, spec.max_age_days), (4, 10, 90))
            self.assertTrue(spec.require_entity_match)


if __name__ == "__main__":
    unittest.main()
