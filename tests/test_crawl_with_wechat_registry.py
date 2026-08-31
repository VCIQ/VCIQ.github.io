from __future__ import annotations

import json
import re
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from tools import crawl_with_wechat_registry as target


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "wechat_sources.json"
PUBLIC_INDEX_PATH = ROOT / "config" / "wechat_public_indexes.json"


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


class WeChatSourceConfigurationContractTests(unittest.TestCase):
    def test_sohu_profile_requires_official_crosspost_contract(self) -> None:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        public_indexes = json.loads(PUBLIC_INDEX_PATH.read_text(encoding="utf-8"))
        accounts = {
            str(account.get("id")): account
            for account in registry.get("accounts", [])
            if isinstance(account, dict) and account.get("id")
        }

        checked = 0
        for account_id, urls in public_indexes.get("accounts", {}).items():
            if not isinstance(urls, list):
                continue
            for url in urls:
                parts = urlsplit(str(url))
                host = (parts.hostname or "").casefold().removeprefix("www.")
                if (
                    host not in {"sohu.com", "m.sohu.com"}
                    or re.fullmatch(r"/media/\d+", parts.path.rstrip("/")) is None
                ):
                    continue

                checked += 1
                spec = accounts.get(str(account_id))
                self.assertIsNotNone(
                    spec,
                    f"{account_id}: Sohu publisher profile has no registry account",
                )
                assert spec is not None
                self.assertTrue(
                    str(spec.get("publisherEntity", "")).strip(),
                    f"{account_id}: Sohu publisher profile requires publisherEntity",
                )
                self.assertIn(
                    "official-crosspost",
                    spec.get("acceptedSourceKinds", []),
                    f"{account_id}: Sohu publisher profile requires official-crosspost acceptance",
                )
                allowed_hosts = {
                    str(value).casefold().removeprefix("www.")
                    for value in spec.get("officialCrosspostHosts", [])
                    if str(value).strip()
                }
                self.assertIn(
                    host,
                    allowed_hosts,
                    f"{account_id}: Sohu publisher profile host {host} must be whitelisted",
                )

        self.assertGreater(checked, 0, "expected at least one configured Sohu publisher profile")


if __name__ == "__main__":
    unittest.main()
