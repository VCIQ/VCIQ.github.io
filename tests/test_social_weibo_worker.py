"""Exercise shared Worker and real Weibo wiring with injected clients, never live I/O."""
import contextlib
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode

from tests.test_social_contracts import fixture
from tests.test_social_weibo import ID, NOW, PATCHES, captured, inputs
from tests.test_social_weibo_transport import Client, Stream
from tools.social import worker, mediacrawler_cli
from tools.social.adapters.weibo import finalize
from tools.social.contracts import ContractError, digest
from tools.social.policy import load_policy
from tools.social.query_registry import build_query_registry
from tools.social.scheduler import plan_jobs
from workers.mediacrawler import observer
from workers.mediacrawler.bootstrap_weibo import bind_and_collect, project_post
from workers.mediacrawler.upstream import PIN
from workers.mediacrawler.weibo_transport import WeiboGate


class WeiboBindingTests(unittest.IsolatedAsyncioTestCase):
    def dependencies(self, *, auth=True, second=None, retry_wrapper=True):
        self.calls = []
        data = {"cards": [{"card_type": 9, "mblog": {"id": int(ID), "text": "机器人 AI 合成测试", "created_at": "Thu Oct 22 12:00:00 +0800 2026", "user": {"id": 123, "screen_name": "合成作者"}}}]}
        streams = [Stream(body=json.dumps({"ok": 1, "data": {"login": auth}}).encode()), Stream(body=json.dumps({"ok": 1, "data": data}).encode())]
        if second is not None: streams.append(second)
        async def sleep(_): pass
        def gate_class(obs, keyword, pages):
            return WeiboGate(obs, keyword, pages, client_factory=lambda: Client(streams, self.calls), sleep=sleep)
        module = SimpleNamespace()
        async def raw_request(self, method, url, **kwargs):
            async with module.make_async_client(proxy=self.proxy) as client:
                response = await client.request(method, url, **kwargs)
            return response.json()["data"]
        class FakeClient:
            def __init__(self, **kwargs): self.proxy = kwargs["proxy"]; self.headers = kwargs["headers"]
            async def request(self, *args, **kwargs): raise AssertionError("upstream retries invoked")
            async def get(self, uri): return await self.request("GET", "https://m.weibo.cn" + uri, headers=self.headers)
            async def get_note_by_keyword(self, keyword, page):
                uri = "/api/container/getIndex?" + urlencode({"containerid": "100103type=1&q=" + keyword, "page_type": "searchall", "page": page})
                return await self.get(uri)
        if retry_wrapper: FakeClient.request.__wrapped__ = raw_request
        module.WeiboClient = FakeClient
        class Context:
            async def new_page(self):
                class Page:
                    async def goto(self, *args, **kwargs): raise AssertionError("automatic navigation/login")
                return Page()
        async def cookies(context, urls):
            self.assertEqual(urls, ["https://m.weibo.cn"])
            return "PRIVATE_COOKIE", {"private": "PRIVATE_COOKIE"}
        utils = SimpleNamespace(convert_browser_context_cookies=cookies, get_mobile_user_agent=lambda: "synthetic-mobile")
        return {"context": Context(), "observer": observer, "client_module": module, "utils": utils,
            "anonymize": lambda value: "a" * 32, "mask": lambda value: "合***", "gate_class": gate_class}

    async def test_actual_binding_query_url_and_projection(self):
        job, context, _ = inputs()
        result = await bind_and_collect({"job": job}, **self.dependencies())
        normalized = finalize(job, result, context, patchset_hash=PATCHES)
        self.assertEqual(normalized["receipt"]["status"], "ok")
        self.assertEqual(normalized["observations"][0]["nativeId"], ID)
        self.assertEqual(len(self.calls), 2)
        self.assertIn("page_type=searchall", self.calls[1][1])
        self.assertNotIn("PRIVATE_COOKIE", repr(result))
        self.assertNotIn("user_id", repr(result))

    async def test_auth_failure_stops_before_search(self):
        job, _, _ = inputs()
        with self.assertRaises(observer.CollectorError) as error:
            await bind_and_collect({"job": job}, **self.dependencies(auth=False))
        self.assertEqual(error.exception.status, "auth_required")
        self.assertEqual(len(self.calls), 1)

    async def test_second_page_rate_limit_retains_data_and_pause(self):
        job, context, _ = inputs()
        job["limits"]["maxSearchPages"] = 2
        result = await bind_and_collect({"job": job}, **self.dependencies(second=Stream(status=429, headers={"Retry-After": "600"})))
        normalized = finalize(job, result, context, patchset_hash=PATCHES)
        self.assertEqual(normalized["receipt"]["status"], "rate_limited")
        self.assertEqual(len(normalized["observations"]), 1)
        self.assertEqual(len(self.calls), 3)

    async def test_missing_retry_wrapper_fails_before_auth_call(self):
        job, _, _ = inputs()
        with self.assertRaisesRegex(observer.CollectorError, "WRAPPER_CHANGED"):
            await bind_and_collect({"job": job}, **self.dependencies(retry_wrapper=False))
        self.assertEqual(self.calls, [])

    def test_projection_missing_date_metrics_remain_unknown(self):
        result = project_post({"mblog": {"id": ID, "text": "合成"}}, lambda value: "a" * 32, lambda value: "合***")
        self.assertIsNone(result["raw_created_at"])
        self.assertIsNone(result["liked_count"])
        self.assertIsNone(result["create_time"])
        self.assertIsNone(result["creator_hash"])


class WeiboWorkerTests(unittest.TestCase):
    def test_weibo_activation_does_not_use_xhs_toggle(self):
        runtime = fixture("runtime_config")
        runtime["enabled"] = True
        runtime["platforms"]["xhs"]["enabled"] = True
        with patch.object(worker, "verify_checkout", side_effect=AssertionError("git invoked")):
            with self.assertRaisesRegex(ContractError, "live_activation_required"):
                worker.preflight(runtime, load_policy(), live=True, runtime_file=Path("/missing"), platform="wb")

    def test_platform_locks_separate_but_same_platform_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            state.mkdir(mode=0o700)
            with worker.profile_lock(state, (worker.ROOT,), "wb"):
                with worker.profile_lock(state, (worker.ROOT,), "xhs"): pass
                with self.assertRaisesRegex(ContractError, "profile_busy"):
                    with worker.profile_lock(state, (worker.ROOT,), "wb"): pass

    def test_profile_and_entrypoint_are_platform_specific(self):
        job, context, row = inputs()
        with tempfile.TemporaryDirectory() as directory:
            state, upstream = Path(directory) / "state", Path(directory) / "upstream"
            state.mkdir(mode=0o700); upstream.mkdir()
            (state / "profiles/wb").mkdir(parents=True)
            lock = {"commit": PIN, "patchsetHash": PATCHES}
            def child(python, request_path, **kwargs):
                self.assertEqual(kwargs["platform"], "wb")
                request = json.loads(request_path.read_text())
                self.assertEqual(request["profile"], str(state / "profiles/wb"))
                Path(request["output"]).write_text(json.dumps(captured(job, row)))
                return False, 0
            with patch.object(worker, "preflight", return_value=(state, upstream, Path("/python"), lock)), patch.object(worker, "run_child", side_effect=child):
                result = worker.execute_job(job, context, runtime={}, policy={}, runtime_file=state / "runtime.json", live=True)
            self.assertEqual(result["receipt"]["platform"], "wb")
            self.assertEqual(result["receipt"]["status"], "ok")
            self.assertTrue((state / "pending" / (job["attemptId"] + ".json")).exists())
            self.assertFalse((state / "profiles/xhs").exists())

    def test_unknown_platform_rejected_before_subprocess(self):
        # Platforms added by later PRs remain valid; reject genuinely unknown input.
        self.assertEqual(worker.platform_check("bili"), "bili")
        self.assertEqual(worker.platform_check("zhihu"), "zhihu")
        for platform in ("../../bad", "__unsupported_platform__", ""):
            with patch("subprocess.Popen", side_effect=AssertionError("spawned")):
                with self.assertRaisesRegex(ContractError, "not_implemented"):
                    worker.platform_check(platform)

    def test_weibo_delimiter_query_is_excluded_not_truncated(self):
        registry = build_query_registry({"tracks": [{"name": "合成", "keywords": ["A&B", "机器人"]}]}, load_policy(), platforms=("wb",))
        excluded = [entry for entry in registry.entries if entry["excludedReason"]]
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]["excludedReason"], "weibo_query_requires_manual_delimiter")

    def test_cli_runs_weibo_plan_through_shared_checkpoint(self):
        policy = load_policy()
        tracking = {"tracks": [{"name": "合成", "keywords": ["机器人"]}]}
        accounts = {"accounts": []}
        registry = build_query_registry(tracking, policy, platforms=("wb",), accounts=accounts)
        hashed = digest({"tracking": tracking, "policy": policy, "accounts": accounts})
        plan = plan_jobs(registry, {}, datetime.now(UTC), policy, vciq_commit="a" * 40, config_hash=hashed, upstream_commit=PIN)
        with tempfile.TemporaryDirectory() as directory:
            state, upstream = Path(directory) / "state", Path(directory) / "upstream"
            state.mkdir(mode=0o700); upstream.mkdir()
            runtime = fixture("runtime_config")
            runtime.update(enabled=True, stateDir=str(state), profileRoot=str(state / "profiles"), mediacrawlerDir=str(upstream))
            runtime["platforms"]["wb"]["enabled"] = True
            for name, value in (("runtime.json", runtime), ("plan.json", plan)):
                (state / name).write_text(json.dumps(value))
            def collect(job, context, **kwargs):
                _, _, row = inputs()
                return finalize(job, captured(job, row), context, patchset_hash=PATCHES)
            args = ["run-mediacrawler", "--platform", "wb", "--state-dir", str(state), "--plan", str(state / "plan.json"), "--runtime-config", str(state / "runtime.json"), "--vciq-commit", "a" * 40, "--live"]
            with patch.object(mediacrawler_cli, "preflight", return_value=(state, upstream, Path("/python"), {"commit": PIN, "patchsetHash": PATCHES})), patch.object(mediacrawler_cli, "_inputs", return_value=(policy, registry, hashed)), patch.object(mediacrawler_cli, "execute_job", side_effect=collect) as run, contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(mediacrawler_cli.main(args), 0)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(json.loads(output.getvalue())["platform"], "wb")
            self.assertTrue((state / "state.sqlite3").is_file())


if __name__ == "__main__": unittest.main()
