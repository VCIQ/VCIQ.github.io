"""Additional PR-02 edge cases: no live HTTP, no real browser or worker process."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.social.adapters.wechat_transport import FetchError, PublicTransport
from tools.social.contracts import digest
from tools.social.planning_cli import main
from tools.social.policy import load_policy
from tools.social.query_registry import build_query_registry
from tools.social.scheduler import plan_jobs
from tools.social.wechat_runner import execute_job
from tests.test_social_wechat import FakeTransport, NOW, ROOT, make_job
from tools.social.adapters.wechat import run_job


class HttpResponse:
    def __init__(self, status=200, headers=None, body=b"synthetic"):
        self.status = status
        self.headers = headers or {}
        self.stream = io.BytesIO(body)

    def getheader(self, key, default=None):
        return self.headers.get(key, default)

    def read(self, size):
        return self.stream.read(size)


class Connection:
    def __init__(self, response):
        self.response, self.sock = response, None

    def request(self, *args, **kwargs):
        pass

    def getresponse(self):
        return self.response

    def close(self):
        pass


def transport(responses, debits):
    iterator = iter(responses)
    return PublicTransport(before_request=lambda: debits.append(True), deadline=100,
                           monotonic=lambda: 0, sleep=lambda _: None,
                           connection_factory=lambda *a, **k: Connection(next(iterator)))


class ExecutionGuards(unittest.TestCase):
    def test_long_sensitive_term_stays_redacted_not_overwritten_by_length_error(self):
        raw = "cookie=" + "SYNTHETIC" * 100
        registry = build_query_registry({"tracks": [{"name": "合成", "keywords": [raw]}]}, load_policy())
        entry = registry.entries[0]
        self.assertEqual(entry["excludedReason"], "sensitive_term")
        self.assertNotIn("SYNTHETIC", json.dumps([*registry.entries, *registry.terms]))

    def test_deleted_original_does_not_pause_platform_as_captcha(self):
        job, context = make_job()
        result = run_job(job, context, FakeTransport(article="该内容已被发布者删除"), now=lambda: NOW)
        self.assertEqual(result["receipt"]["status"], "network_error")
        self.assertEqual(result["receipt"]["errorCode"], "ORIGINAL_UNAVAILABLE")
        self.assertEqual(result["observations"], [])

    def test_transport_debits_each_redirect_and_uses_known_hosts(self):
        debits = []
        client = transport([HttpResponse(302, {"Location": "https://mp.weixin.qq.com/s/SYNTHETIC"}), HttpResponse()], debits)
        result = client.get("https://weixin.sogou.com/link?url=SYNTHETIC")
        self.assertEqual(result.url, "https://mp.weixin.qq.com/s/SYNTHETIC")
        self.assertEqual(len(debits), 2)
        self.assertEqual(client.requests, 2)

    def test_transport_rejects_unexpected_cross_provider_redirect(self):
        debits = []
        client = transport([HttpResponse(302, {"Location": "https://www.bing.com/search?q=other"})], debits)
        with self.assertRaisesRegex(FetchError, "CROSS_PROVIDER_REDIRECT"):
            client.get("https://mp.weixin.qq.com/s/SYNTHETIC")
        self.assertEqual(len(debits), 1)

    def test_transport_retry_after_and_size_cap(self):
        debits = []
        client = transport([HttpResponse(429, {"Retry-After": "120000"})], debits)
        with self.assertRaises(FetchError) as caught:
            client.get("https://www.bing.com/search?q=synthetic")
        self.assertEqual(caught.exception.retry_after, 120000)
        client = transport([HttpResponse(body=b"x" * (2 * 1024 * 1024 + 1))], debits)
        with self.assertRaisesRegex(FetchError, "RESPONSE_TOO_LARGE"):
            client.get("https://mp.weixin.qq.com/s/SYNTHETIC")

    def test_timeout_controller_terminates_child_and_never_claims_success(self):
        job, context = make_job()
        events = []
        class Process:
            exitcode = None
            alive = True
            def start(self): events.append("start")
            def join(self, seconds): events.append(("join", seconds))
            def is_alive(self): return self.alive
            def terminate(self): events.append("terminate"); self.alive = False
            def kill(self): events.append("kill"); self.alive = False
            def close(self): events.append("close")
        class Context:
            def Process(self, **kwargs): return Process()
        with tempfile.TemporaryDirectory() as directory, patch("multiprocessing.get_context", return_value=Context()):
            result = execute_job(job, context, state_dir=Path(directory), roots=(ROOT,), grant={})
        self.assertEqual(result["receipt"]["status"], "timeout")
        self.assertEqual(result["receipt"]["counts"]["searchItems"], 0)
        self.assertIn(("join", job["limits"]["maxWallSeconds"]), events)
        self.assertIn("terminate", events)

    def test_live_requires_both_runtime_and_flag_before_worker_or_state_write(self):
        policy = load_policy()
        tracking = {"tracks": [{"name": "机器人", "slug": "robot", "keywords": ["人形机器人"]}]}
        accounts = {"accounts": []}
        registry = build_query_registry(tracking, policy)
        plan = plan_jobs(registry, {}, NOW, policy, vciq_commit="a" * 40,
                         config_hash=digest({"tracking": tracking, "policy": policy, "accounts": accounts}), upstream_commit="b" * 40)
        fixture_rows = [json.loads(line) for line in (ROOT / "tests/fixtures/social/contracts/valid.jsonl").read_text().splitlines()]
        runtime = next(row for row in fixture_rows if row["kind"] == "runtime_config")
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            runtime.update(stateDir=str(state), profileRoot=str(state / "profiles"), mediacrawlerDir=None)
            runtime["platforms"]["wechat"]["enabled"] = True
            for name, value in (("plan.json", plan), ("tracking.json", tracking), ("accounts.json", accounts), ("budget.json", {})):
                (state / name).write_text(json.dumps(value), encoding="utf-8")
            for enabled, live in ((False, True), (True, False), (False, False)):
                runtime["enabled"] = enabled
                (state / "runtime.json").write_text(json.dumps(runtime), encoding="utf-8")
                args = ["run-wechat", "--state-dir", str(state), "--plan", str(state / "plan.json"),
                        "--runtime-config", str(state / "runtime.json"), "--budget-file", str(state / "budget.json"),
                        "--config", str(state / "tracking.json"), "--accounts", str(state / "accounts.json"),
                        "--vciq-commit", "a" * 40] + (["--live"] if live else [])
                with patch("tools.social.wechat_runner.execute_job", side_effect=AssertionError("worker launched")), contextlib.redirect_stderr(io.StringIO()) as errors:
                    self.assertEqual(main(args), 2)
                self.assertEqual(json.loads(errors.getvalue())["error"], "live_activation_required")
                self.assertFalse((state / "state.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
