"""Stop and private-journal boundaries; all platform network paths are injected."""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_social_contracts import fixture
from tools.social.batch import ROOT
from tools.social.contracts import ContractError
from tools.social.guard import GuardError
from tools.social.shadow_state import save, load, request_stop, clear_stop, stopped, run_lock
from tools.social import worker, wechat_runner
from workers.mediacrawler import observer, request_control
from workers.mediacrawler.weibo_transport import WeiboGate
from tests.test_social_weibo_transport import Client, Stream


class ShadowControlTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve() / "private"; self.root.mkdir(mode=0o700)
        self.roots = (ROOT,)
        self.runtime = fixture("runtime_config")
        self.runtime.update(enabled=True, stateDir=str(self.root), profileRoot=str(self.root / "profiles"), mediacrawlerDir=None)
        self.runtime["platforms"]["wb"]["enabled"] = True
        self.path = self.root / "runtime.json"; self.write_runtime()

    def write_runtime(self):
        self.path.write_text(json.dumps(self.runtime)); self.path.chmod(0o600)

    def check(self):
        request_control.check(observer, platform="wb", state_dir=str(self.root), runtime_file=str(self.path))

    def test_enabled_private_runtime_permits_guard(self): self.check()

    def test_stop_and_clear_are_idempotent(self):
        self.assertTrue(request_stop(self.root, self.roots)); self.assertFalse(request_stop(self.root, self.roots))
        with self.assertRaisesRegex(observer.CollectorError, "STOP_REQUESTED"): self.check()
        self.assertTrue(clear_stop(self.root, self.roots)); self.assertFalse(clear_stop(self.root, self.roots)); self.check()

    def test_runtime_disable_is_seen_without_restarting_worker(self):
        self.check(); self.runtime["enabled"] = False; self.write_runtime()
        with self.assertRaisesRegex(observer.CollectorError, "DISABLED"): self.check()

    def test_platform_disable_independent(self):
        self.runtime["platforms"]["xhs"]["enabled"] = True
        self.runtime["platforms"]["wb"]["enabled"] = False; self.write_runtime()
        with self.assertRaisesRegex(observer.CollectorError, "DISABLED"): self.check()

    def test_linked_stop_marker_stops_without_following(self):
        (self.root / "shadow.stop").symlink_to(self.root / "nonexistent")
        self.assertTrue(stopped(self.root, self.roots))
        with self.assertRaisesRegex(observer.CollectorError, "STOP_REQUESTED"): self.check()
        with self.assertRaises(GuardError): clear_stop(self.root, self.roots)

    def test_missing_runtime_fails_closed_without_echo(self):
        self.path.unlink()
        with self.assertRaisesRegex(observer.CollectorError, "CONTROL_UNAVAILABLE") as caught: self.check()
        self.assertNotIn(str(self.root), str(caught.exception))

    def test_corrupt_duplicate_keys_and_non_object_refused(self):
        for content in ('{"enabled":true,"enabled":false}', '[1]', 'garbage'):
            self.path.write_text(content)
            with self.assertRaises(observer.CollectorError): self.check()

    def test_public_runtime_permission_rejected(self):
        self.path.chmod(0o644)
        with self.assertRaisesRegex(observer.CollectorError, "PERMISSIONS"): self.check()

    def test_runtime_outside_private_root_rejected(self):
        with self.assertRaisesRegex(observer.CollectorError, "CONTROL_PATH"):
            request_control.check(observer, platform="wb", state_dir=str(self.root), runtime_file=str(ROOT / "config/social_discovery.json"))

    def test_runtime_changed_to_production_rejected(self):
        self.runtime["mode"] = "production"; self.write_runtime()
        with self.assertRaisesRegex(observer.CollectorError, "CONTROL_INVALID"): self.check()

    def test_control_is_optional_only_for_non_child_unit_calls(self):
        with patch.dict(os.environ, {}, clear=True): request_control.check(observer, platform="wb")

    def test_child_environment_uses_only_explicit_paths(self):
        calls = []
        class Process:
            pid = 42
            returncode = 0
            def wait(self, timeout): return 0
        def popen(command, **kw): calls.append(kw); return Process()
        with patch.dict(os.environ, {"VCIQ_SHADOW_RUNTIME": "do-not-inherit", "GITHUB_TOKEN": "PRIVATE"}):
            worker.run_child(Path("/python"), Path("/request"), state=self.root, timeout=10,
                platform="wb", runtime_file=self.path, popen=popen, kill_group=lambda *a: None)
        self.assertEqual(calls[0]["env"]["VCIQ_SHADOW_STATE"], str(self.root))
        self.assertEqual(calls[0]["env"]["VCIQ_SHADOW_RUNTIME"], str(self.path))
        self.assertNotIn("GITHUB_TOKEN", calls[0]["env"])

    def test_exclusive_journal_never_overwrites(self):
        save(self.root, "journal.json", {"value": 1}, self.roots, exclusive=True)
        with self.assertRaises(FileExistsError): save(self.root, "journal.json", {"value": 2}, self.roots, exclusive=True)
        self.assertEqual(load(self.root, "journal.json", self.roots), {"value": 1})

    def test_interrupted_exclusive_write_does_not_publish_partial_target(self):
        with patch("tools.social.shadow_state.os.link", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError): save(self.root, "journal.json", {"value": 1}, self.roots, exclusive=True)
        self.assertFalse((self.root / "journal.json").exists())

    def test_journal_checksum_and_size_checked(self):
        save(self.root, "journal.json", {"value": 1}, self.roots)
        path = self.root / "journal.json"; wrapped = json.loads(path.read_text()); wrapped["payload"]["value"] = 2
        path.write_text(json.dumps(wrapped))
        with self.assertRaisesRegex(ContractError, "checksum"): load(self.root, "journal.json", self.roots)
        with patch("tools.social.shadow_state.MAX_JOURNAL", 5):
            with self.assertRaisesRegex(ContractError, "journal_limit"): save(self.root, "other.json", {"long": "1234567"}, self.roots)

    def test_lock_released_after_exception(self):
        with self.assertRaises(RuntimeError):
            with run_lock(self.root, self.roots): raise RuntimeError()
        with run_lock(self.root, self.roots): pass

    def test_wechat_stop_checked_before_quota_and_network(self):
        from tests.social_orchestration_fixtures import result_for, NOW
        from tests.social_storage_fixtures import sample
        from tools.social.adapters.wechat_transport import FetchError
        job = sample("wechat")[0][0]
        request_stop(self.root, self.roots)
        def collect(job, context, transport):
            with self.assertRaisesRegex(FetchError, "STOP_REQUESTED"): transport.before_request()
            return result_for(job, now=NOW, status="cancelled", positive=False)
        with patch("tools.social.adapters.wechat.run_job", collect), patch.object(wechat_runner.SchedulerStore, "consume_request", side_effect=AssertionError("quota should not be used")):
            wechat_runner._child(job, {}, str(self.root), (str(ROOT),), {}, "pending/test.json", str(self.path))


class RequestGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_during_spacing_prevents_request(self):
        calls = []
        async def sleep(_): pass
        gate = WeiboGate(observer, "机器人", 1, client_factory=lambda: Client([], calls), sleep=sleep)
        def stop(): raise observer.CollectorError("cancelled", "SHADOW_STOP_REQUESTED")
        gate.before_request = stop
        with self.assertRaisesRegex(observer.CollectorError, "STOP_REQUESTED"):
            async with gate.factory() as client: await client.request("GET", "https://m.weibo.cn/api/config")
        self.assertEqual(calls, []); self.assertEqual(gate.requests, 0)

    async def test_bilibili_gate_checks_stop_before_auth(self):
        from workers.mediacrawler.bilibili_transport import BilibiliGate
        calls = []
        async def sleep(_): pass
        gate = BilibiliGate(observer, "机器人", 1, 1, client_factory=lambda: Client([], calls), sleep=sleep)
        def stop(): raise observer.CollectorError("cancelled", "SHADOW_STOP_REQUESTED")
        gate.before_request = stop
        with self.assertRaisesRegex(observer.CollectorError, "STOP_REQUESTED"):
            async with gate.factory() as client: await client.request("GET", "https://api.bilibili.com/x/web-interface/nav")
        self.assertEqual(calls, [])

    async def test_zhihu_gate_checks_stop_before_auth(self):
        from workers.mediacrawler.zhihu_transport import ZhihuGate
        calls = []
        async def sleep(_): pass
        gate = ZhihuGate(observer, "机器人", 1, client_factory=lambda: Client([], calls), sleep=sleep)
        def stop(): raise observer.CollectorError("cancelled", "SHADOW_STOP_REQUESTED")
        gate.before_request = stop
        with self.assertRaisesRegex(observer.CollectorError, "STOP_REQUESTED"):
            async with gate.factory() as client: await client.request("GET", "https://www.zhihu.com/api/v4/me")
        self.assertEqual(calls, [])


if __name__ == "__main__": unittest.main()
