"""XHS launch contract: no browser, credentials, network or upstream import."""
import asyncio
import copy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from workers.mediacrawler import bootstrap


class LaunchBoundary(Exception):
    pass


class XhsBrowserLaunchTests(unittest.TestCase):
    def exercise(self, action, *, deny_control=False, wrong_origin=False):
        root = Path('/synthetic/pinned-source')
        config = types.ModuleType('config'); config.__file__ = str(root / 'config/__init__.py')
        tools = types.ModuleType('tools'); tools.__file__ = str(root / 'tools/__init__.py')
        if wrong_origin:
            tools.__file__ = '/untrusted/tools/__init__.py'
        launches, gates = [], []
        class Browser:
            async def launch_persistent_context(self, *args, **kwargs):
                launches.append((args, kwargs))
                raise LaunchBoundary()
        class Playwright:
            chromium = Browser()
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
        api = types.ModuleType('playwright.async_api'); api.async_playwright = Playwright
        def check(*args, **kwargs):
            gates.append(kwargs)
            if deny_control:
                raise PermissionError('stopped')
        observer = types.SimpleNamespace(CollectorError=lambda *args: ValueError(args[1]))
        request = {'action': action, 'upstream': str(root), 'profile': '/synthetic/private/profiles/xhs'}
        before = copy.deepcopy(request)
        caught = None
        with patch.object(sys, 'path', list(sys.path)), \
             patch.dict(sys.modules, {'config': config, 'tools': tools, 'playwright.async_api': api}), \
             patch.object(bootstrap, 'sibling', return_value=types.SimpleNamespace(check=check)):
            try:
                asyncio.run(bootstrap.execute(request, observer))
            except (LaunchBoundary, PermissionError, ValueError) as exc:
                caught = exc
        self.assertEqual(request, before)
        return launches, gates, caught, config

    def test_run_uses_bundled_full_chromium_headless(self):
        launches, gates, caught, _ = self.exercise('run')
        self.assertIsInstance(caught, LaunchBoundary)
        self.assertEqual(gates, [{'platform': 'xhs'}])
        self.assertEqual(launches, [(('/synthetic/private/profiles/xhs',), {
            'headless': True, 'accept_downloads': False, 'channel': 'chromium',
            'service_workers': 'block', 'timeout': 30000})])

    def test_session_same_binary_but_headed(self):
        launches, gates, caught, _ = self.exercise('session')
        self.assertIsInstance(caught, LaunchBoundary)
        self.assertEqual(gates, [])
        self.assertFalse(launches[0][1]['headless'])
        self.assertEqual(launches[0][1]['channel'], 'chromium')

    def test_stop_gate_precedes_browser(self):
        launches, gates, caught, _ = self.exercise('run', deny_control=True)
        self.assertIsInstance(caught, PermissionError)
        self.assertEqual(len(gates), 1)
        self.assertEqual(launches, [])

    def test_import_origin_still_checked(self):
        launches, _, caught, _ = self.exercise('run', wrong_origin=True)
        self.assertIsInstance(caught, ValueError)
        self.assertEqual(str(caught), 'IMPORT_ORIGIN_MISMATCH')
        self.assertEqual(launches, [])

    def test_no_proxy_tls_cdp_or_cookie_override(self):
        launches, _, _, config = self.exercise('run')
        self.assertNotIn('ignore_https_errors', launches[0][1])
        self.assertNotIn('executable_path', launches[0][1])
        self.assertNotIn('proxy', launches[0][1])
        self.assertFalse(config.ENABLE_CDP_MODE)
        self.assertFalse(config.CDP_CONNECT_EXISTING)
        self.assertFalse(config.ENABLE_IP_PROXY)
        self.assertFalse(config.DISABLE_SSL_VERIFY)
        self.assertEqual(config.COOKIES, '')


if __name__ == '__main__':
    unittest.main()
