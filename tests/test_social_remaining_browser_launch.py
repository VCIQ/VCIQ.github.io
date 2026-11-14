"""Launch boundaries for the remaining platforms; no real account or network."""
import asyncio
import copy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from workers.mediacrawler import bootstrap, bootstrap_bilibili, bootstrap_weibo, bootstrap_zhihu


class LaunchBoundary(Exception):
    pass


ENTRIES = {"bili": bootstrap_bilibili, "wb": bootstrap_weibo, "zhihu": bootstrap_zhihu}


class RemainingBrowserLaunchTests(unittest.TestCase):
    def exercise(self, platform, action="run", *, deny=False, wrong_origin=False):
        entry = ENTRIES[platform]
        root = Path("/synthetic/pinned-source")
        config = types.ModuleType("config"); config.__file__ = str(root / "config/__init__.py")
        tools = types.ModuleType("tools"); tools.__file__ = str(root / "tools/__init__.py")
        tools.utils = types.SimpleNamespace(get_mobile_user_agent=lambda: "synthetic-mobile-ua")
        if wrong_origin:
            tools.__file__ = "/untrusted/tools/__init__.py"
        calls, gates = [], []

        class Browser:
            async def launch_persistent_context(self, *args, **kwargs):
                calls.append((args, kwargs))
                raise LaunchBoundary()

        class Playwright:
            chromium = Browser()
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass

        def check(*args, **kwargs):
            gates.append(kwargs)
            if deny:
                raise PermissionError("synthetic-stop")

        def sibling(name):
            if name == "request_control": return types.SimpleNamespace(check=check)
            if name == "bootstrap": return bootstrap
            raise AssertionError("unexpected dependency")

        api = types.ModuleType("playwright.async_api"); api.async_playwright = Playwright
        request = {"action": action, "upstream": str(root),
                   "profile": "/synthetic/private/profiles/" + platform}
        before = copy.deepcopy(request)
        observer = types.SimpleNamespace(CollectorError=lambda status, code: ValueError(code))
        failure = None
        with patch.object(sys, "path", list(sys.path)), \
             patch.dict(sys.modules, {"config": config, "tools": tools, "playwright.async_api": api}), \
             patch.object(entry, "sibling", side_effect=sibling):
            try:
                asyncio.run(entry.execute(request, observer))
            except (LaunchBoundary, ValueError, PermissionError) as exc:
                failure = exc
        self.assertEqual(request, before)
        return calls, gates, failure, config

    def test_all_collectors_use_bundled_full_chromium_headless(self):
        for platform in ENTRIES:
            with self.subTest(platform=platform):
                calls, gates, failure, _ = self.exercise(platform)
                self.assertIsInstance(failure, LaunchBoundary)
                self.assertEqual(gates, [{"platform": platform}])
                self.assertEqual(calls[0][1]["channel"], "chromium")
                self.assertIs(calls[0][1]["headless"], True)

    def test_sessions_are_headed_with_the_same_binary(self):
        for platform in ENTRIES:
            with self.subTest(platform=platform):
                calls, gates, failure, _ = self.exercise(platform, "session")
                self.assertIsInstance(failure, LaunchBoundary)
                self.assertEqual(gates, [])
                self.assertIs(calls[0][1]["headless"], False)
                self.assertEqual(calls[0][1]["channel"], "chromium")

    def test_exact_platform_profile_is_preserved(self):
        for platform in ENTRIES:
            calls, _, _, _ = self.exercise(platform)
            self.assertEqual(calls[0][0], ("/synthetic/private/profiles/" + platform,))

    def test_stop_guard_runs_before_any_browser_launch(self):
        for platform in ENTRIES:
            calls, gates, failure, _ = self.exercise(platform, deny=True)
            self.assertEqual(calls, [])
            self.assertEqual(gates, [{"platform": platform}])
            self.assertIsInstance(failure, PermissionError)

    def test_upstream_import_origin_is_checked(self):
        for platform in ENTRIES:
            calls, _, failure, _ = self.exercise(platform, wrong_origin=True)
            self.assertEqual(calls, [])
            self.assertEqual(str(failure), "IMPORT_ORIGIN_MISMATCH")

    def test_browser_options_have_no_new_security_or_proxy_overrides(self):
        for platform in ENTRIES:
            calls, _, _, config = self.exercise(platform)
            kwargs = calls[0][1]
            allowed = {"channel", "headless", "accept_downloads", "service_workers", "timeout"}
            if platform == "wb": allowed.add("user_agent")
            self.assertEqual(set(kwargs), allowed)
            self.assertFalse(kwargs["accept_downloads"])
            self.assertEqual(kwargs["service_workers"], "block")
            self.assertEqual(kwargs["timeout"], 30000)
            self.assertFalse(config.DISABLE_SSL_VERIFY)
            self.assertFalse(config.ENABLE_IP_PROXY)
            self.assertFalse(config.ENABLE_CDP_MODE)
            self.assertFalse(config.CDP_CONNECT_EXISTING)
            self.assertEqual(config.COOKIES, "")

    def test_existing_mobile_user_agent_is_not_changed(self):
        calls, _, _, _ = self.exercise("wb")
        self.assertEqual(calls[0][1]["user_agent"], "synthetic-mobile-ua")
        for platform in ("bili", "zhihu"):
            self.assertNotIn("user_agent", self.exercise(platform)[0][0][1])

    def test_platform_configuration_remains_platform_specific(self):
        for platform in ENTRIES:
            _, _, _, config = self.exercise(platform)
            self.assertEqual(config.PLATFORM, platform)
            self.assertFalse(config.ENABLE_GET_COMMENTS)
            self.assertFalse(config.ENABLE_GET_MEDIA)
        self.assertFalse(self.exercise("bili")[3].CREATOR_MODE)
        self.assertEqual(self.exercise("wb")[3].WEIBO_SEARCH_TYPE, "default")


if __name__ == "__main__": unittest.main()
