from __future__ import annotations

import unittest
from unittest import mock

from tools import wechat_sogou_index as sogou


SEARCH_RESULT_BODY = """
<ul class="news-list">
  <li>
    <div class="txt-box">
      <h3>
        <a target="_blank"
           id="sogou_vr_11002601_title_0"
           href="/link?url=abc&amp;type=2&amp;query=%E9%AB%98%E5%B7%A5%E6%9C%BA%E5%99%A8%E4%BA%BA">
          人形机器人进入量产阶段
        </a>
      </h3>
      <p class="txt-info">高工机器人报道产业链量产进展。</p>
      <div class="s-p">
        <a class="account" uigs="article_account_0">高工机器人</a>
        <span t="1784937600"></span>
      </div>
    </div>
  </li>
</ul>
"""


class WeChatSogouIndexTest(unittest.TestCase):
    def test_builds_account_and_topic_search_query(self) -> None:
        spec = {
            "name": "量子位",
            "expectedAccounts": ["量子位", "qbitai"],
            "sector": "AI / AGI",
            "keywords": ["推理模型", "大模型"],
        }
        url = sogou.build_search_url(spec)
        self.assertIn("weixin.sogou.com/weixin", url)
        self.assertIn("type=2", url)
        self.assertIn("s_from=input", url)
        self.assertIn("%E9%87%8F%E5%AD%90%E4%BD%8D", url)
        self.assertIn("%E6%8E%A8%E7%90%86%E6%A8%A1%E5%9E%8B", url)

    def test_account_query_has_sector_and_identity_only_fallbacks(self) -> None:
        spec = {
            "name": "高工机器人",
            "expectedAccounts": ["高工机器人"],
            "sector": "机器人",
            "keywords": ["人形机器人", "具身智能"],
        }
        self.assertEqual(
            sogou._query_terms(spec),
            ["高工机器人 人形机器人", "高工机器人 机器人", "高工机器人"],
        )

    def test_generic_track_query_uses_sector_not_display_prefix(self) -> None:
        spec = {
            "name": "微信公众号 · 商业航天",
            "sector": "商业航天",
            "queryIdentity": "商业航天",
            "genericDiscovery": True,
            "keywords": ["商业航天", "可复用火箭"],
        }
        query = sogou._query_term(spec)
        self.assertTrue(query.startswith("商业航天"))
        self.assertIn("可复用火箭", query)
        self.assertNotIn("微信公众号", query)
        self.assertEqual(sogou._query_terms(spec), [query])

    def test_discover_retries_broader_account_query_only_after_zero_results(self) -> None:
        spec = {
            "name": "高工机器人",
            "expectedAccounts": ["高工机器人"],
            "sector": "机器人",
            "keywords": ["人形机器人", "具身智能"],
        }
        with (
            mock.patch.object(sogou, "_request", side_effect=["<html></html>", SEARCH_RESULT_BODY]) as request,
            mock.patch.object(
                sogou,
                "resolve_result_url",
                return_value="https://mp.weixin.qq.com/s?__biz=test&mid=1&idx=1&sn=abc",
            ),
        ):
            rows, meta = sogou.discover(spec)

        self.assertEqual(request.call_count, 2)
        self.assertEqual(len(rows), 1)
        self.assertEqual(meta["query"], "高工机器人 机器人")
        self.assertTrue(meta["queryFallbackUsed"])
        self.assertEqual(
            meta["queryAttempts"],
            [
                {"query": "高工机器人 人形机器人", "scanned": 0},
                {"query": "高工机器人 机器人", "scanned": 1},
            ],
        )

    def test_discover_does_not_issue_broader_query_after_first_hit(self) -> None:
        spec = {
            "name": "高工机器人",
            "expectedAccounts": ["高工机器人"],
            "sector": "机器人",
            "keywords": ["人形机器人", "具身智能"],
        }
        with (
            mock.patch.object(sogou, "_request", return_value=SEARCH_RESULT_BODY) as request,
            mock.patch.object(
                sogou,
                "resolve_result_url",
                return_value="https://mp.weixin.qq.com/s?__biz=test&mid=1&idx=1&sn=abc",
            ),
        ):
            rows, meta = sogou.discover(spec)

        self.assertEqual(request.call_count, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(meta["query"], "高工机器人 人形机器人")
        self.assertFalse(meta["queryFallbackUsed"])

    def test_parses_server_rendered_article_result(self) -> None:
        body = """
        <ul class="news-list">
          <li>
            <div class="txt-box">
              <h3>
                <a target="_blank"
                   id="sogou_vr_11002601_title_0"
                   href="/link?url=abc&amp;type=2&amp;query=%E9%87%8F%E5%AD%90%E4%BD%8D">
                  OpenAI发布新推理模型
                </a>
              </h3>
              <p class="txt-info">OpenAI公布新的推理模型和长期智能体能力。</p>
              <div class="s-p">
                <a class="account" uigs="article_account_0">量子位</a>
                <span t="1784937600"></span>
              </div>
            </div>
          </li>
        </ul>
        """
        search_url = "https://weixin.sogou.com/weixin?type=2&query=test&page=1"
        rows = sogou.parse_search_results(body, search_url)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "OpenAI发布新推理模型")
        self.assertEqual(rows[0]["account"], "量子位")
        self.assertIn("长期智能体", rows[0]["summary"])
        self.assertTrue(rows[0]["url"].startswith("https://weixin.sogou.com/link?"))
        self.assertRegex(rows[0]["publishedAt"], r"^\d{4}-\d{2}-\d{2}$")

    def test_reassembles_split_javascript_wechat_url(self) -> None:
        body = """
        <script>
          var url = '';
          url += 'https://mp.';
          url += 'weixin.qq.c';
          url += 'om/s?src=11';
          url += '&timestamp=1784995758&';
          url += 'ver=6864&signature=abc123&new=1';
          window.location.replace(url);
        </script>
        """
        url = sogou.resolve_script_url(body)
        self.assertEqual(
            url,
            "https://mp.weixin.qq.com/s?src=11&timestamp=1784995758&ver=6864&signature=abc123&new=1",
        )

    def test_rejects_non_wechat_redirect(self) -> None:
        body = "<script>var url=''; url += 'https://example.com/article';</script>"
        self.assertEqual(sogou.resolve_script_url(body), "")


if __name__ == "__main__":
    unittest.main()
