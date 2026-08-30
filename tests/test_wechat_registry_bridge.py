from __future__ import annotations

import unittest
from datetime import UTC, datetime

from tools import crawl_articles
from tools import wechat_public_sources as wechat
from tools import wechat_registry_bridge as bridge


class WeChatRegistryBridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # ``install`` permanently patches the shared module, so snapshot the
        # originals and restore them to keep other test files order-independent.
        cls._original_wechat_attrs = (
            wechat.generated_wechat_sources,
            wechat.parse_wechat_article,
            wechat.crawl_wechat_source,
        )
        bridge.install(wechat)

    @classmethod
    def tearDownClass(cls) -> None:
        (
            wechat.generated_wechat_sources,
            wechat.parse_wechat_article,
            wechat.crawl_wechat_source,
        ) = cls._original_wechat_attrs
        bridge._INDEX_CACHE.clear()

    def test_bridge_keeps_generic_discovery_and_adds_registry_accounts(self) -> None:
        tracks = [
            {
                "slug": "ai",
                "name": "AI / AGI",
                "keywords": ["大模型", "推理模型"],
                "people": ["何恺明"],
                "sampleCompanies": ["OpenAI", "DeepSeek"],
            }
        ]
        sources = wechat.generated_wechat_sources(tracks, object())
        names = {item["name"] for item in sources}
        self.assertIn("量子位", names)
        self.assertIn("机器之心", names)
        generic = [item for item in sources if item.get("genericDiscovery")]
        self.assertEqual(len(generic), 1)
        self.assertFalse(generic[0].get("expectedAccounts"))
        account_scoped = [
            item for item in sources if not item.get("genericDiscovery")
        ]
        self.assertTrue(account_scoped)
        self.assertTrue(
            all(item.get("expectedAccounts") for item in account_scoped)
        )

    def test_bridge_rejects_wrong_account_before_entity_parsing(self) -> None:
        spec = {
            "id": "user-track-wechat-qbitai-ai",
            "name": "量子位",
            "sector": "AI / AGI",
            "region": "中国",
            "sourceLevel": "媒体报道",
            "keywords": ["大模型"],
            "trackedCompanies": ["OpenAI"],
            "trackedPeople": [],
            "expectedAccounts": ["量子位", "qbitai"],
            "accountConfigId": "qbitai",
        }
        body = """
        <html><head>
          <meta property="og:title" content="OpenAI发布新大模型" />
          <meta name="description" content="OpenAI发布新大模型并公布技术进展。" />
          <meta property="article:published_time" content="2026-07-25" />
        </head><body>
          <a id="js_name">无关公众号</a>
          <div id="js_content">OpenAI发布新大模型。</div>
        </body></html>
        """
        article = wechat.parse_wechat_article(
            spec,
            "https://mp.weixin.qq.com/s/wrong-account",
            body,
            crawl_articles,
        )
        self.assertIsNone(article)
        self.assertEqual(
            spec["_publicIndexArticleRejectKinds"],
            ["original-account-mismatch"],
        )
        self.assertEqual(spec["_publicIndexObservedAccounts"], ["无关公众号"])

    def test_verified_account_keeps_media_level_and_entity_links(self) -> None:
        today = datetime.now(UTC).date().isoformat()
        spec = {
            "id": "user-track-wechat-qbitai-ai",
            "name": "量子位",
            "sector": "AI / AGI",
            "region": "中国",
            "sourceLevel": "媒体报道",
            "keywords": ["大模型", "推理模型"],
            "trackedCompanies": ["OpenAI"],
            "trackedPeople": ["Sam Altman"],
            "expectedAccounts": ["量子位", "qbitai"],
            "accountConfigId": "qbitai",
        }
        body = f"""
        <html><head>
          <meta property="og:title" content="OpenAI发布新推理模型" />
          <meta name="description" content="OpenAI发布新推理模型，Sam Altman介绍后续方向。" />
          <meta property="article:published_time" content="{today}" />
        </head><body>
          <a id="js_name">量子位</a>
          <div id="js_content">OpenAI发布新推理模型，Sam Altman介绍后续方向。</div>
        </body></html>
        """
        article = wechat.parse_wechat_article(
            spec,
            "https://mp.weixin.qq.com/s/verified-account",
            body,
            crawl_articles,
        )
        self.assertIsNotNone(article)
        assert article is not None
        self.assertEqual(article["source"]["level"], "媒体报道")
        self.assertEqual(article["wechatAccountConfigId"], "qbitai")
        self.assertIn("OpenAI", article["mentionedCompanies"])
        self.assertIn("Sam Altman", article["mentionedPeople"])

    def test_nested_sohu_detail_can_expose_original_wechat_link(self) -> None:
        spec = {
            "expectedAccounts": ["半导体技术"],
            "keywords": ["半导体", "芯片", "封装"],
            "trackedCompanies": ["中芯国际"],
            "trackedPeople": [],
        }
        body = """
        <html><body>
          <a href="https://mp.weixin.qq.com/s?__biz=abc&mid=1&idx=1&sn=good">
            中芯国际发布半导体芯片封装测试进展
          </a>
        </body></html>
        """

        rows = bridge._extract_index_rows(
            body,
            "https://m.sohu.com/a/1065611950_120498874",
            spec,
            crawl_articles,
            require_account_context=False,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "wechat")

    def test_configured_account_rejects_discovery_date_without_original_date(self) -> None:
        spec = {
            "id": "user-track-wechat-qbitai-ai",
            "name": "量子位",
            "sector": "AI / AGI",
            "keywords": ["大模型", "推理模型"],
            "trackedCompanies": ["OpenAI"],
            "trackedPeople": [],
            "expectedAccounts": ["量子位", "qbitai"],
        }
        body = """
        <html><head>
          <meta property="og:title" content="OpenAI发布新推理模型" />
          <meta name="description" content="OpenAI发布新推理模型并公布重要技术进展。" />
        </head><body>
          <a id="js_name">量子位</a>
          <div id="js_content">OpenAI发布新推理模型并公布重要技术进展。</div>
        </body></html>
        """

        article = wechat.parse_wechat_article(
            spec,
            "https://mp.weixin.qq.com/s/missing-original-date",
            body,
            crawl_articles,
            fallback_date="2026-08-29",
        )

        self.assertIsNone(article)

    def test_configured_account_rejects_stale_original_date(self) -> None:
        spec = {
            "id": "user-track-wechat-qbitai-ai",
            "name": "量子位",
            "sector": "AI / AGI",
            "keywords": ["大模型", "推理模型"],
            "trackedCompanies": ["OpenAI"],
            "trackedPeople": [],
            "expectedAccounts": ["量子位", "qbitai"],
            "maxArticleAgeDays": 45,
        }
        body = """
        <html><head>
          <meta property="og:title" content="OpenAI发布新推理模型" />
          <meta name="description" content="OpenAI发布新推理模型并公布重要技术进展。" />
          <meta property="article:published_time" content="2020-01-01" />
        </head><body>
          <a id="js_name">量子位</a>
          <div id="js_content">OpenAI发布新推理模型并公布重要技术进展。</div>
        </body></html>
        """

        article = wechat.parse_wechat_article(
            spec,
            "https://mp.weixin.qq.com/s/stale-original-date",
            body,
            crawl_articles,
        )

        self.assertIsNone(article)

    def test_account_scoped_sohu_profile_discovers_only_its_article_titles(self) -> None:
        spec = {
            "expectedAccounts": ["半导体技术"],
            "keywords": ["半导体", "芯片", "封装"],
            "trackedCompanies": ["中芯国际"],
            "trackedPeople": [],
        }
        body = """
        <html><body>
          <h1>半导体技术</h1>
          <a href="https://m.sohu.com/a/1065611950_120498874">
            中芯国际发布半导体芯片封装测试进展
          </a>
          <div>昨天12:17 · 17阅读</div>
          <a href="https://m.sohu.com/a/999999999_999999999">
            其他作者的半导体热门文章
          </a>
        </body></html>
        """

        rows = bridge._extract_index_rows(
            body,
            "https://m.sohu.com/media/120498874",
            spec,
            crawl_articles,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "detail")
        self.assertEqual(
            rows[0]["url"],
            "https://m.sohu.com/a/1065611950_120498874",
        )

    def test_sohu_profile_account_survives_large_leading_script(self) -> None:
        spec = {
            "expectedAccounts": ["半导体技术"],
            "keywords": ["半导体", "芯片", "封装"],
            "trackedCompanies": ["长江存储"],
            "trackedPeople": [],
        }
        body = """
        <html><head><script>{script}</script><title>半导体技术的个人主页</title></head>
        <body>
          <div class="author-name">半导体技术</div>
          <a href="https://m.sohu.com/a/1069311167_120498874">
            长江存储发布芯片良率技术进展
          </a>
        </body></html>
        """.format(script="x" * 600)

        rows = bridge._extract_index_rows(
            body,
            "https://m.sohu.com/media/120498874",
            spec,
            crawl_articles,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "detail")

    def test_sohu_profile_title_is_bounded_account_evidence(self) -> None:
        spec = {
            "expectedAccounts": ["半导体技术"],
            "keywords": ["半导体", "芯片", "封装"],
            "trackedCompanies": ["长江存储"],
            "trackedPeople": [],
        }
        leading = "".join(f"<p>导航节点{index}</p>" for index in range(140))
        body = f"""
        <html><head><title>半导体技术的个人主页</title></head><body>
          {leading}
          <a href="https://m.sohu.com/a/1069311167_120498874">
            长江存储发布芯片良率技术进展
          </a>
        </body></html>
        """

        rows = bridge._extract_index_rows(
            body,
            "https://m.sohu.com/media/120498874",
            spec,
            crawl_articles,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "detail")

    def test_eet_account_context_discovers_chiptrend_title(self) -> None:
        spec = {
            "expectedAccounts": ["芯潮IC"],
            "keywords": ["半导体", "芯片", "集成电路"],
            "trackedCompanies": [],
            "trackedPeople": [],
        }
        body = """
        <html><body>
          <div>532296</div>
          <a href="https://www.eet-china.com/mp/a520001.html">
            <img src="cover.jpg" />
          </a>
          <a href="https://www.eet-china.com/mp/a520001.html">
            半导体全链聚合，国际集成电路创新博览会举办
          </a>
          <a href="https://www.eet-china.com/mp/u4006642">芯潮IC</a>
          <div>2026-08-07</div>
          <a href="https://www.eet-china.com/mp/a510000.html">电子技术普及</a>
        </body></html>
        """

        rows = bridge._extract_index_rows(
            body,
            "https://www.eet-china.com/mp/u4006642",
            spec,
            crawl_articles,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "detail")
        self.assertEqual(rows[0]["date"], "2026-08-07")
        self.assertEqual(
            rows[0]["title"],
            "半导体全链聚合，国际集成电路创新博览会举办",
        )

    def test_hidden_title_isolated_from_previous_index_item(self) -> None:
        spec = {
            "expectedAccounts": ["与非网"],
            "keywords": ["芯片", "DDR5"],
            "trackedCompanies": [],
            "trackedPeople": [],
        }
        body = """
        <html><body>
          <div class="cell item">
            <span class="item_title">
              <a href="https://www.jintiankansha.com/t/linked">
                WAIC释放强烈信号，HDD迎来第二春
              </a>
            </span>
            <span>与非网eefocus · 公众号 · 1 月前</span>
          </div>
          <div class="cell item">
            <span class="item_title">
              <span class="hide-content">
                澜起科技：DDR5 RCD芯片出货量显著增加
              </span>
            </span>
            <span class="hide-content">与非网eefocus</span>
            <span>公众号 · 1 月前</span>
          </div>
        </body></html>
        """

        rows = bridge._extract_index_rows(
            body,
            "https://www.jintiankansha.com/column/FoMbC3nnRr",
            spec,
            crawl_articles,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "title")
        self.assertIn("澜起科技", rows[0]["title"])


if __name__ == "__main__":
    unittest.main()
