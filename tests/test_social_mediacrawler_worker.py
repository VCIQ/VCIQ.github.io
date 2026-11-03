"""No real worker/browser is launched; injected process and Git responses only."""
import contextlib
import io
import json
import os
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from workers.mediacrawler.bootstrap import safe_settings
from workers.mediacrawler.upstream import PIN, UpstreamError, load_lock, verify_checkout
from tools.social import worker
from tools.social.contracts import ContractError
from tools.social.policy import load_policy
from tests.test_social_contracts import fixture
from tests.test_social_xhs import inputs, PATCHES


class WorkerTests(unittest.TestCase):
    def test_flags_require_runtime_and_live_before_git_or_state(self):
        runtime = fixture("runtime_config")
        for enabled, live in ((False, True), (True, False), (False, False)):
            runtime["enabled"] = enabled
            runtime["platforms"]["xhs"]["enabled"] = True
            with patch.object(worker, "verify_checkout", side_effect=AssertionError("git called")):
                with self.assertRaisesRegex(ContractError, "live_activation_required"):
                    worker.preflight(runtime, load_policy(), live=live, runtime_file=Path("/missing"))

    def test_manual_session_is_explicit_and_never_a_query(self):
        runtime = fixture("runtime_config")
        with patch.object(worker, "preflight", side_effect=AssertionError("started")):
            with self.assertRaisesRegex(ContractError, "interactive_auth_opt_in_required"):
                worker.bootstrap_session(runtime=runtime, policy=load_policy(), runtime_file=Path("/missing"))

    def test_safe_settings_disable_browser_reuse_comments_and_proxy(self):
        config = SimpleNamespace(ENABLE_CDP_MODE=True, CDP_CONNECT_EXISTING=True, COOKIES="SYNTHETIC")
        safe_settings(config)
        for field in ("ENABLE_CDP_MODE", "CDP_CONNECT_EXISTING", "ENABLE_IP_PROXY", "ENABLE_GET_COMMENTS", "ENABLE_GET_SUB_COMMENTS", "ENABLE_GET_MEDIA", "DISABLE_SSL_VERIFY"):
            self.assertFalse(getattr(config, field))
        self.assertEqual(config.COOKIES, "")
        self.assertEqual(config.MAX_CONCURRENCY_NUM, 1)

    def test_environment_does_not_forward_credentials_or_pythonpath(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "PRIVATE", "HTTP_PROXY": "PRIVATE", "PYTHONPATH": "PRIVATE", "OPENAI_API_KEY": "PRIVATE"}):
            env = worker.child_environment(Path("/state"))
        self.assertFalse(set(env) & {"GITHUB_TOKEN", "HTTP_PROXY", "PYTHONPATH", "OPENAI_API_KEY"})
        self.assertEqual(env["HOME"], "/state/home")

    def test_process_group_is_terminated_on_timeout(self):
        calls = []
        class Process:
            pid = 777
            returncode = None
            def wait(self, timeout):
                calls.append(("wait", timeout))
                if timeout == 180: raise subprocess.TimeoutExpired("worker", 180)
                self.returncode = -15
        def factory(command, **kwargs):
            self.assertEqual(command[1:3], ["-I", "-B"])
            self.assertFalse(kwargs["shell"])
            self.assertTrue(kwargs["start_new_session"])
            self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
            return Process()
        timed_out, _ = worker.run_child(Path("/python"), Path("/request"), state=Path("/state"), timeout=180,
            popen=factory, kill_group=lambda pid, sig: calls.append((pid, sig)))
        self.assertTrue(timed_out)
        self.assertIn((777, signal.SIGTERM), calls)
        self.assertIn((777, signal.SIGKILL), calls)

    def test_zero_exit_without_receipt_is_not_empty_or_ok(self):
        job, context, _ = inputs()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            upstream = Path(directory) / "upstream"
            state.mkdir(mode=0o700)
            upstream.mkdir()
            (state / "profiles/xhs").mkdir(parents=True)
            lock = {"commit": PIN, "patchsetHash": PATCHES}
            with patch.object(worker, "preflight", return_value=(state, upstream, Path("/python"), lock)), patch.object(worker, "run_child", return_value=(False, 0)):
                result = worker.execute_job(job, context, runtime={}, policy={}, runtime_file=state / "runtime.json", live=True)
            self.assertEqual(result["receipt"]["status"], "schema_error")
            self.assertEqual(result["receipt"]["errorCode"], "WORKER_NO_RECEIPT")

    def test_profile_lock_prevents_two_browsers(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            state.mkdir(mode=0o700)
            with worker.profile_lock(state, (worker.ROOT,)):
                with self.assertRaisesRegex(ContractError, "profile_busy"):
                    with worker.profile_lock(state, (worker.ROOT,)): pass

    def test_upstream_pin_and_dirty_tree_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "config").mkdir()
            (root / "media_platform/xhs").mkdir(parents=True)
            (root / "config/__init__.py").write_text("")
            (root / "media_platform/xhs/core.py").write_text("")
            def good(command, **kwargs):
                value = PIN if command[-2:] == ["rev-parse", "HEAD"] else str(root) if command[-1] == "--show-toplevel" else ""
                self.assertFalse(kwargs["check"])
                self.assertNotIn("shell", kwargs)
                return SimpleNamespace(returncode=0, stdout=value)
            verify_checkout(root, {"commit": PIN, "patches": []}, runner=good)
            with self.assertRaises(UpstreamError):
                verify_checkout(root, {"commit": "a" * 40, "patches": []}, runner=good)
            def dirty(command, **kwargs):
                return SimpleNamespace(returncode=1, stdout="PRIVATE") if "diff" in command else good(command, **kwargs)
            with self.assertRaises(UpstreamError) as error:
                verify_checkout(root, {"commit": PIN, "patches": []}, runner=dirty)
            self.assertNotIn("PRIVATE", str(error.exception))
            (root / ".env").write_text("SYNTHETIC")
            with self.assertRaisesRegex(UpstreamError, "ENV_FILE"):
                verify_checkout(root, {"commit": PIN, "patches": []}, runner=good)

    def test_lock_patch_hash_is_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lock.json"
            value = {"schemaVersion": 1, "repository": "NanmiCoder/MediaCrawler", "commit": PIN, "patches": [], "patchsetHash": PATCHES}
            path.write_text(json.dumps(value))
            self.assertEqual(load_lock(path)["commit"], PIN)
            value["patchsetHash"] = "b" * 64
            path.write_text(json.dumps(value))
            with self.assertRaises(UpstreamError): load_lock(path)


if __name__ == "__main__": unittest.main()
