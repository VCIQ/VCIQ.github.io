from __future__ import annotations

import unittest
from contextlib import ExitStack
from unittest.mock import patch

from tools import crawl_with_wechat_registry as target


class CrawlWithWechatRegistryIntegrationTests(unittest.TestCase):
    def test_main_installs_wechat_and_toutiao_routes_before_base_crawl(self) -> None:
        with ExitStack() as stack:
            search_redirects = stack.enter_context(
                patch.object(target.search_index_feed_redirects, "install")
            )
            stack.enter_context(patch.object(target.wechat_fetch_compat, "install"))
            stack.enter_context(patch.object(target.wechat_registry_bridge, "install"))
            original_redirect = stack.enter_context(
                patch.object(target.wechat_original_redirect_bridge, "install")
            )
            stack.enter_context(
                patch.object(target.wechat_index_context_guard, "install")
            )
            stack.enter_context(
                patch.object(target.wechat_index_record_fallback, "install")
            )
            sogou_redirect = stack.enter_context(
                patch.object(target.wechat_sogou_redirect_compat, "install")
            )
            stack.enter_context(
                patch.object(target.wechat_sogou_link_compat, "install")
            )
            title_fallback = stack.enter_context(
                patch.object(target.wechat_public_index_title_fallback, "install")
            )
            public_aggregator = stack.enter_context(
                patch.object(target.wechat_public_aggregator, "install")
            )
            stack.enter_context(patch.object(target.wechat_sogou_bridge, "install"))
            toutiao_feed = stack.enter_context(
                patch.object(target.toutiao_public_feed, "install")
            )
            stack.enter_context(patch.object(target, "_install_professional_media"))
            stack.enter_context(patch.object(target, "_install_source_governance"))
            stack.enter_context(patch.object(target, "_install_snapshot_quality"))
            base_main = stack.enter_context(
                patch.object(target.base, "main", return_value=23)
            )

            result = target.main()

        self.assertEqual(result, 23)
        search_redirects.assert_called_once_with(target.base.tracking.crawler)
        original_redirect.assert_called_once_with(
            target.wechat_public_sources,
            target.wechat_registry_bridge,
        )
        sogou_redirect.assert_called_once_with(target.wechat_sogou_index)
        title_fallback.assert_called_once_with(
            target.wechat_registry_bridge,
            target.wechat_sogou_index,
        )
        public_aggregator.assert_called_once_with(target.wechat_sogou_index)
        toutiao_feed.assert_called_once_with(target.base.tracking)
        base_main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
