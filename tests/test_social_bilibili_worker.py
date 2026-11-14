"""Actual Bilibili binding/CLI wiring with injected client/process, no real login."""
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

from workers.mediacrawler import observer
from workers.mediacrawler.bootstrap_bilibili import bind_and_collect, project_video, wbi_keys
from workers.mediacrawler.bilibili_observer import collect_bilibili
from workers.mediacrawler.bilibili_transport import BilibiliGate
from workers.mediacrawler.upstream import PIN
from tools.social import worker, mediacrawler_cli, bilibili_reconcile
from tools.social.adapters.bilibili import finalize
from tools.social.contracts import ContractError, digest
from tools.social.policy import load_policy
from tools.social.query_compile import compile_query
from tools.social.query_registry import build_query_registry
from tools.social.scheduler import plan_jobs
from tools.social.scheduler_state import read_state
from tests.test_social_contracts import fixture
from tests.test_social_bilibili import inputs, captured, document, BV, PATCHES
from tests.test_social_bilibili_transport import MemoryClient, MemoryResponse


def auth_data(login=True):
    return {"isLogin": login, "wbi_img": {"img_url": "https://i0.hdslb.com/bfs/wbi/" + "a" * 32 + ".png", "sub_url": "https://i0.hdslb.com/bfs/wbi/" + "b" * 32 + ".png"}}


class BilibiliBindingTests(unittest.IsolatedAsyncioTestCase):
    async def binding(self, responses):
        calls, keys_used = [], []
        module = SimpleNamespace()
        async def sleep(_): pass
        def gate_class(obs, keyword, pages, records):
            return BilibiliGate(obs, keyword, pages, records, client_factory=lambda: MemoryClient(responses, calls), sleep=sleep)
        class Client:
            def __init__(self, **kwargs): self.headers = kwargs["headers"]
            async def get_wbi_keys(self): raise AssertionError("uncached keys path")
            async def get(self, path, params=None, enable_params_sign=True):
                if params is not None and enable_params_sign:
                    keys_used.append(await self.get_wbi_keys())
                    params = {**params, "wts": 1760000000, "w_rid": "c" * 32}
                url = "https://api.bilibili.com" + path + ("?" + urlencode(params) if params is not None else "")
                async with module.make_async_client() as client:
                    response = await client.request("GET", url, headers=self.headers)
                return response.json()["data"]
            async def search_video_by_keyword(self, keyword, page, page_size, pubtime_begin_s, pubtime_end_s):
                return await self.get("/x/web-interface/wbi/search/type", {"search_type": "video", "keyword": keyword, "page": page, "page_size": page_size, "order": "", "pubtime_begin_s": pubtime_begin_s, "pubtime_end_s": pubtime_end_s})
            async def get_video_info(self, aid):
                return await self.get("/x/web-interface/view/detail", {"aid": aid}, enable_params_sign=False)
        module.BilibiliClient = Client
        class Page:
            async def evaluate(self, expression):
                self_expression = expression
                if self_expression != "() => navigator.userAgent": raise AssertionError("unexpected browser evaluation")
                return "SyntheticUserAgent"
        class Context:
            async def new_page(self): return Page()
        async def cookies(context, urls):
            self.assertEqual(urls, ["https://www.bilibili.com"])
            return "SYNTHETIC_PRIVATE", {}
        result = await bind_and_collect({"job": inputs()[0]}, Context(), observer,
            client_module=module, utils=SimpleNamespace(convert_browser_context_cookies=cookies),
            anonymize=lambda value: "a" * 64, mask=lambda value: "测***",
            collector=collect_bilibili, gate_class=gate_class)
        return result, calls, keys_used

    async def test_binding_auth_sign_search_detail_projection(self):
        responses = [MemoryResponse(auth_data()), MemoryResponse({"result": [{"aid": 123, "bvid": BV}], "numPages": 1}),
            MemoryResponse({"View": {"aid": 123, "bvid": BV, "title": "合成", "desc": "简介", "pubdate": 1760000000, "owner": {"mid": "private-user", "name": "Name"}, "stat": {"like": 1}}})]
        result, calls, keys = await self.binding(responses)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(calls), 3)
        self.assertEqual(keys, [("a" * 32, "b" * 32)])
        self.assertEqual(result["records"][0]["record"]["bvid"], BV)
        self.assertNotIn("private-user", str(result))
        self.assertNotIn("SYNTHETIC_PRIVATE", str(result))

    async def test_auth_stops_before_search(self):
        responses = [MemoryResponse(auth_data(False))]
        with self.assertRaises(observer.CollectorError) as error: await self.binding(responses)
        self.assertEqual(error.exception.status, "auth_required")
        self.assertEqual(responses, [])

    async def test_negative_search_does_not_refresh_browser(self):
        result, calls, _ = await self.binding([MemoryResponse(auth_data()), MemoryResponse(status=403)])
        self.assertEqual(result["status"], "verification_required")
        self.assertEqual(len(calls), 2)

    async def test_empty_search_does_not_request_detail(self):
        result, calls, _ = await self.binding([MemoryResponse(auth_data()), MemoryResponse({"result": [], "numPages": 0})])
        self.assertEqual(result["status"], "empty")
        self.assertEqual(len(calls), 2)

    async def test_unknown_keys_not_fabricated(self):
        for value in ({}, {"wbi_img": {"img_url": "private", "sub_url": None}}):
            with self.assertRaises(ValueError): wbi_keys(value)

    async def test_projection_missing_metadata_stays_unknown(self):
        row = project_video({"View": {"aid": 123}}, lambda _: "a" * 64, lambda _: "x")
        self.assertIsNone(row["create_time"])
        self.assertIsNone(row["liked_count"])
        self.assertIsNone(row["bvid"])


class BilibiliWorkerTests(unittest.TestCase):
    def test_platform_toggle_independent(self):
        runtime = fixture("runtime_config")
        runtime["enabled"] = True
        runtime["platforms"]["xhs"]["enabled"] = True
        with patch.object(worker, "verify_checkout", side_effect=AssertionError("git called")):
            with self.assertRaisesRegex(ContractError, "live_activation_required"):
                worker.preflight(runtime, load_policy(), live=True, runtime_file=Path("/missing"), platform="bili")

    def test_profile_locks_are_platform_specific(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            with worker.profile_lock(state, (worker.ROOT,), "bili"):
                with worker.profile_lock(state, (worker.ROOT,), "wb"): pass
                with self.assertRaisesRegex(ContractError, "profile_busy"):
                    with worker.profile_lock(state, (worker.ROOT,), "bili"): pass

    def test_bili_child_dispatch_and_missing_receipt(self):
        job, context, _ = inputs()
        with tempfile.TemporaryDirectory() as directory:
            state, upstream = Path(directory) / "state", Path(directory) / "upstream"
            state.mkdir(mode=0o700)
            upstream.mkdir()
            (state / "profiles/bili").mkdir(parents=True)
            lock = {"commit": PIN, "patchsetHash": PATCHES}
            with patch.object(worker, "preflight", return_value=(state, upstream, Path("/python"), lock)), patch.object(worker, "run_child", return_value=(False, 0)) as child:
                result = worker.execute_job(job, context, runtime={}, policy={}, runtime_file=state / "runtime.json", live=True)
            self.assertEqual(child.call_args.kwargs["platform"], "bili")
            self.assertEqual(result["receipt"]["errorCode"], "WORKER_NO_RECEIPT")
            self.assertEqual(worker.ENTRYPOINTS["bili"], "bootstrap_bilibili.py")

    def test_signer_characters_excluded_not_mutated(self):
        for value in ("robot's", "robot!", "(robot)", "robot*"):
            with self.assertRaisesRegex(ContractError, "bilibili_query_requires_manual_signature_chars"):
                compile_query("bili", "mediacrawler", value)
        self.assertEqual(compile_query("bili", "mediacrawler", "robot & AI"), "robot & AI")

    def test_cli_plan_checkpoint_without_production_write(self):
        policy = load_policy()
        tracking, accounts = {"tracks": [{"name": "合成", "keywords": ["合成测试机器人"]}]}, {"accounts": []}
        registry = build_query_registry(tracking, policy, platforms=("bili",))
        plan = plan_jobs(registry, {}, datetime.now(UTC), policy, vciq_commit="a" * 40,
            config_hash=digest({"tracking": tracking, "policy": policy, "accounts": accounts}), upstream_commit=PIN)
        with tempfile.TemporaryDirectory() as directory:
            state, upstream = Path(directory) / "state", Path(directory) / "upstream"
            state.mkdir(mode=0o700)
            upstream.mkdir()
            runtime = fixture("runtime_config")
            runtime.update(enabled=True, stateDir=str(state), profileRoot=str(state / "profiles"), mediacrawlerDir=str(upstream))
            runtime["platforms"]["bili"]["enabled"] = True
            for filename, value in (("runtime.json", runtime), ("plan.json", plan), ("tracking.json", tracking), ("accounts.json", accounts)):
                (state / filename).write_text(json.dumps(value), encoding="utf-8")
            def execution(job, context, **kwargs):
                return finalize(job, captured(job, inputs()[2]), context, patchset_hash=PATCHES)
            args = ["run-mediacrawler", "--platform", "bili", "--state-dir", str(state), "--runtime-config", str(state / "runtime.json"), "--plan", str(state / "plan.json"), "--config", str(state / "tracking.json"), "--accounts", str(state / "accounts.json"), "--vciq-commit", "a" * 40, "--live"]
            output = io.StringIO()
            with patch.object(mediacrawler_cli, "preflight", return_value=(state, upstream, Path("/python"), {"commit": PIN})), patch.object(mediacrawler_cli, "execute_job", side_effect=execution), contextlib.redirect_stdout(output):
                self.assertEqual(mediacrawler_cli.main(args), 0)
            self.assertEqual(json.loads(output.getvalue())["platform"], "bili")
            snapshot = read_state(state, repo_roots=(worker.ROOT, upstream))
            self.assertTrue(snapshot["queries"][plan["jobs"][0]["queryId"]]["lastCoveredAt"])

    def test_reconciliation_cli_is_readonly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            result, materials = path / "result.json", path / "materials.json"
            result.write_text(json.dumps({"observations": [document()]}), encoding="utf-8")
            materials.write_text(json.dumps([{"url": "https://www.bilibili.com/video/" + BV}]), encoding="utf-8")
            before = {p.name: p.read_bytes() for p in path.iterdir()}
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(bilibili_reconcile.main(["--observations", str(result), "--materials", str(materials)]), 0)
            self.assertEqual(len(json.loads(output.getvalue())["matches"]), 1)
            self.assertEqual(before, {p.name: p.read_bytes() for p in path.iterdir()})


if __name__ == "__main__": unittest.main()
