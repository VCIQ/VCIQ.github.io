"""Runtime wiring and private worker lifecycle; no real login or JS execution."""
import contextlib
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode, urlsplit

from tests.test_social_contracts import fixture
from tests.test_social_weibo_transport import Client, Stream
from tests.test_social_zhihu import inputs, captured, PATCHES
from tests.test_social_zhihu_observer import obj, page
from tests.test_social_zhihu_transport import AUTH, search_url
from tools.social import worker, mediacrawler_cli
from tools.social.adapters.zhihu import finalize
from tools.social.contracts import ContractError, digest
from tools.social.policy import load_policy
from tools.social.query_registry import build_query_registry
from tools.social.scheduler import plan_jobs
from workers.mediacrawler import observer
from workers.mediacrawler.bootstrap_zhihu import bind_and_collect, prepare_signer, project_content
from workers.mediacrawler.upstream import PIN
from workers.mediacrawler.zhihu_transport import ZhihuGate


class ZhihuBindingTests(unittest.IsolatedAsyncioTestCase):
    def dependencies(self, *, auth=True, cookie=True, second=None, wrapper=True):
        self.calls, self.sign_calls = [], []
        streams = [Stream(body=json.dumps({"uid": "PRIVATE_UID", "name": "PRIVATE_NAME"} if auth else {}).encode()),
                   Stream(body=json.dumps(page([obj("answer"), obj("article"), obj("zvideo")], end=second is None)).encode())]
        if second is not None: streams.append(second)
        async def sleep(_): pass
        def gate_class(obs, keyword, pages):
            return ZhihuGate(obs, keyword, pages, client_factory=lambda: Client(streams, self.calls), sleep=sleep)
        module = SimpleNamespace()
        sign_calls = self.sign_calls
        async def raw_request(client, method, url, **options):
            async with module.make_async_client(proxy=client.proxy) as transport:
                return (await transport.request(method, url, **options)).json()
        class FakeClient:
            def __init__(self, **kwargs):
                self.proxy, self.default_headers = kwargs["proxy"], kwargs["headers"]
                self._extractor = None
            async def request(self, *args, **kwargs): raise AssertionError("automatic retry")
            async def get(self, uri, params=None):
                suffix = uri + ("?" + urlencode(params) if params is not None else "")
                sign_calls.append(suffix)
                return await self.request("GET", "https://www.zhihu.com" + suffix, headers=self.default_headers)
            async def get_note_by_keyword(self, keyword, page=1, page_size=20):
                uri = urlsplit(search_url(keyword, page)).path + "?" + urlsplit(search_url(keyword, page)).query
                payload = await self.get(uri)
                return self._extractor.extract_contents_from_search(payload)
        if wrapper: FakeClient.request.__wrapped__ = raw_request
        module.ZhiHuClient = FakeClient
        class Context:
            async def new_page(self):
                class Page:
                    async def goto(self, *args, **kwargs): raise AssertionError("automatic browser navigation")
                return Page()
        async def cookies(context, urls):
            self.assertEqual(urls, ["https://www.zhihu.com"])
            return "PRIVATE_COOKIE", {"d_c0": "PRIVATE_COOKIE"} if cookie else {}
        return {"context": Context(), "observer": observer, "client_module": module,
            "utils": SimpleNamespace(convert_browser_context_cookies=cookies, get_user_agent=lambda: "synthetic"),
            "anonymize": lambda value: "a" * 32, "mask": lambda value: "合***", "gate_class": gate_class}

    async def test_native_client_binding_retains_raw_paging_and_three_types(self):
        job, context, _ = inputs()
        result = await bind_and_collect({"job": job}, **self.dependencies())
        normalized = finalize(job, result, context, patchset_hash=PATCHES)
        self.assertEqual(normalized["receipt"]["status"], "ok")
        self.assertEqual(normalized["receipt"]["completeness"], "exhausted")
        self.assertEqual({d["contentType"] for d in normalized["observations"]}, {"answer", "article", "zvideo"})
        self.assertEqual(self.calls[0][1], AUTH)
        self.assertNotIn("include", self.calls[0][1])
        self.assertEqual(self.sign_calls[0], "/api/v4/me")
        self.assertNotIn("PRIVATE", repr(result))

    async def test_authentication_failure_stops_before_search(self):
        job, _, _ = inputs()
        with self.assertRaises(observer.CollectorError) as caught:
            await bind_and_collect({"job": job}, **self.dependencies(auth=False))
        self.assertEqual(caught.exception.status, "auth_required")
        self.assertEqual(len(self.calls), 1)

    async def test_missing_cookie_stops_before_any_request(self):
        job, _, _ = inputs()
        with self.assertRaisesRegex(observer.CollectorError, "COOKIE_MISSING"):
            await bind_and_collect({"job": job}, **self.dependencies(cookie=False))
        self.assertEqual(self.calls, [])

    async def test_missing_upstream_retry_wrapper_is_detected(self):
        job, _, _ = inputs()
        with self.assertRaisesRegex(observer.CollectorError, "WRAPPER_CHANGED"):
            await bind_and_collect({"job": job}, **self.dependencies(wrapper=False))
        self.assertEqual(self.calls, [])

    async def test_second_page_limit_preserves_content_and_pause(self):
        job, context, _ = inputs(); job["limits"]["maxSearchPages"] = 2
        result = await bind_and_collect({"job": job}, **self.dependencies(second=Stream(status=429, headers={"Retry-After": "600"})))
        normalized = finalize(job, result, context, patchset_hash=PATCHES)
        self.assertEqual(normalized["receipt"]["status"], "rate_limited")
        self.assertEqual(len(normalized["observations"]), 3)
        self.assertEqual(normalized["diagnostics"]["retryAfterSeconds"], 600)
        self.assertEqual(len(self.calls), 3)

    def test_projection_preserves_missing_metrics_and_masks_identity(self):
        value = obj(); value["author"] = {"id": "PRIVATE", "name": "PRIVATE"}
        row = project_content(value, lambda identity: "a" * 32, lambda name: "合***", observer)
        self.assertIsNone(row["voteup_count"])
        self.assertIsNone(row["created_time"])
        self.assertNotIn("PRIVATE", repr(row))
        video = project_content(obj("zvideo"), lambda value: "a" * 32, lambda value: "合***", observer)
        self.assertIsNone(video["content"])

    def test_signer_uses_absolute_pinned_resource_without_chdir(self):
        with tempfile.TemporaryDirectory() as directory:
            upstream = Path(directory) / "upstream"; (upstream / "libs").mkdir(parents=True)
            (upstream / "libs/zhihu.js").write_text("\ufefffunction synthetic() {}", encoding="utf-8")
            helper, compiled = SimpleNamespace(), []
            before = Path.cwd()
            def compiler(code): compiled.append(code); return "COMPILED_SYNTHETIC"
            prepare_signer(upstream, helper=helper, compiler=compiler)
            self.assertEqual(helper.ZHIHU_SGIN_JS, "COMPILED_SYNTHETIC")
            self.assertEqual(compiled, ["function synthetic() {}"])
            self.assertEqual(Path.cwd(), before)

    def test_missing_or_symlink_signer_resource_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "libs").mkdir()
            with self.assertRaisesRegex(ValueError, "RESOURCE_INVALID"):
                prepare_signer(root, helper=SimpleNamespace(), compiler=lambda value: value)
            other = root / "outside.js"; other.write_text("synthetic")
            (root / "libs/zhihu.js").symlink_to(other)
            with self.assertRaisesRegex(ValueError, "RESOURCE_INVALID"):
                prepare_signer(root, helper=SimpleNamespace(), compiler=lambda value: value)


class ZhihuWorkerTests(unittest.TestCase):
    def test_platform_activation_is_independent(self):
        runtime = fixture("runtime_config"); runtime["enabled"] = True
        runtime["platforms"]["xhs"]["enabled"] = True
        with patch.object(worker, "verify_checkout", side_effect=AssertionError("git called")):
            with self.assertRaisesRegex(ContractError, "live_activation_required"):
                worker.preflight(runtime, load_policy(), live=True, runtime_file=Path("/missing"), platform="zhihu")

    def test_platform_profile_lock_is_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"; state.mkdir(mode=0o700)
            with worker.profile_lock(state, (worker.ROOT,), "zhihu"):
                with worker.profile_lock(state, (worker.ROOT,), "bili"): pass
                with self.assertRaisesRegex(ContractError, "profile_busy"):
                    with worker.profile_lock(state, (worker.ROOT,), "zhihu"): pass

    def test_child_dispatch_and_private_pending_result(self):
        job, context, row = inputs()
        with tempfile.TemporaryDirectory() as directory:
            state, upstream = Path(directory) / "state", Path(directory) / "upstream"
            state.mkdir(mode=0o700); upstream.mkdir(); (state / "profiles/zhihu").mkdir(parents=True)
            lock = {"commit": PIN, "patchsetHash": PATCHES}
            def child(python, path, **kwargs):
                self.assertEqual(kwargs["platform"], "zhihu")
                request = json.loads(path.read_text())
                self.assertEqual(request["profile"], str(state / "profiles/zhihu"))
                Path(request["output"]).write_text(json.dumps(captured(job, [row])))
                return False, 0
            with patch.object(worker, "preflight", return_value=(state, upstream, Path("/python"), lock)), patch.object(worker, "run_child", side_effect=child):
                result = worker.execute_job(job, context, runtime={}, policy={}, runtime_file=state / "runtime.json", live=True)
            self.assertEqual(result["receipt"]["platform"], "zhihu")
            self.assertEqual(result["receipt"]["status"], "ok")
            self.assertTrue((state / "pending" / (job["attemptId"] + ".json")).is_file())
            self.assertEqual(worker.ENTRYPOINTS["zhihu"], "bootstrap_zhihu.py")

    def test_exit_zero_without_receipt_does_not_claim_empty(self):
        job, context, _ = inputs()
        with tempfile.TemporaryDirectory() as directory:
            state, upstream = Path(directory) / "state", Path(directory) / "upstream"
            state.mkdir(mode=0o700); upstream.mkdir(); (state / "profiles/zhihu").mkdir(parents=True)
            with patch.object(worker, "preflight", return_value=(state, upstream, Path("/python"), {"commit": PIN, "patchsetHash": PATCHES})), patch.object(worker, "run_child", return_value=(False, 0)):
                result = worker.execute_job(job, context, runtime={}, policy={}, runtime_file=state / "runtime.json", live=True)
            self.assertEqual(result["receipt"]["errorCode"], "WORKER_NO_RECEIPT")

    def test_cli_plan_reaches_transaction_checkpoint(self):
        policy = load_policy(); tracking = {"tracks": [{"name": "合成", "keywords": ["机器人"]}]}; accounts = {"accounts": []}
        registry = build_query_registry(tracking, policy, platforms=("zhihu",), accounts=accounts)
        hashed = digest({"tracking": tracking, "policy": policy, "accounts": accounts})
        plan = plan_jobs(registry, {}, datetime.now(UTC), policy, vciq_commit="a" * 40, config_hash=hashed, upstream_commit=PIN)
        with tempfile.TemporaryDirectory() as directory:
            state, upstream = Path(directory) / "state", Path(directory) / "upstream"
            state.mkdir(mode=0o700); upstream.mkdir()
            runtime = fixture("runtime_config")
            runtime.update(enabled=True, stateDir=str(state), profileRoot=str(state / "profiles"), mediacrawlerDir=str(upstream))
            runtime["platforms"]["zhihu"]["enabled"] = True
            for name, value in (("runtime.json", runtime), ("plan.json", plan)):
                (state / name).write_text(json.dumps(value))
            def collect(job, context, **kwargs): return finalize(job, captured(job, [inputs()[2]]), context, patchset_hash=PATCHES)
            args = ["run-mediacrawler", "--platform", "zhihu", "--state-dir", str(state), "--plan", str(state / "plan.json"), "--runtime-config", str(state / "runtime.json"), "--vciq-commit", "a" * 40, "--live"]
            with patch.object(mediacrawler_cli, "preflight", return_value=(state, upstream, Path("/python"), {"commit": PIN, "patchsetHash": PATCHES})), patch.object(mediacrawler_cli, "_inputs", return_value=(policy, registry, hashed)), patch.object(mediacrawler_cli, "execute_job", side_effect=collect) as run, contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(mediacrawler_cli.main(args), 0)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(json.loads(output.getvalue())["platform"], "zhihu")
            self.assertTrue((state / "state.sqlite3").is_file())


if __name__ == "__main__": unittest.main()
