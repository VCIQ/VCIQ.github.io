"""PR-03 controller tests: fake worker, no browser and no live platform traffic."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_social_contracts import fixture
from tools.social import worker
from tools.social.contracts import ContractError, digest
from workers.mediacrawler.observer import Observer


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.upstream = self.base / "upstream"
        self.upstream.mkdir()
        self.state = self.base / "state"
        self.state.mkdir(mode=0o700)
        self.job = fixture("crawl_job", "xhs")
        self.runtime = fixture("runtime_config")
        self.runtime.update(enabled=True, stateDir=str(self.state), profileRoot=str(self.state / "profiles"), mediacrawlerDir=str(self.upstream))
        self.runtime["platforms"]["xhs"]["enabled"] = True
        self.checked = {"commit": self.job["upstreamCommit"], "patchsetHash": digest([]), "python": self.upstream / ".venv/bin/python"}

    def test_R01_fresh_interpreter_imports_upstream_not_vciq(self):
        for name in ("config", "tools"):
            path = self.upstream / name
            path.mkdir()
            (path / "__init__.py").write_text("SYNTHETIC=True\n", encoding="utf-8")
        code = "import importlib.util,sys; from pathlib import Path; p=Path(sys.argv[1]); s=importlib.util.spec_from_file_location('bridge',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); c=m.import_isolated(sys.argv[2]); print(Path(c.__file__).resolve())"
        run = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(worker.BRIDGE / "bootstrap.py"), str(self.upstream)], capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), str(self.upstream / "config/__init__.py"))

    def test_R01_upstream_revision_dirty_and_untracked_rejected(self):
        python = self.upstream / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        python.parent.mkdir(parents=True)
        python.write_text("synthetic", encoding="utf-8")
        replies = [SimpleNamespace(returncode=0, stdout=self.job["upstreamCommit"]), SimpleNamespace(returncode=0, stdout=""), SimpleNamespace(returncode=0, stdout="")]
        with patch("subprocess.run", side_effect=replies):
            result = worker.verify_upstream(self.upstream)
        self.assertEqual(result["commit"], self.job["upstreamCommit"])
        with patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="0" * 40)):
            with self.assertRaisesRegex(ContractError, "upstream_revision_mismatch"):
                worker.verify_upstream(self.upstream)
        with patch("subprocess.run", side_effect=[replies[0], SimpleNamespace(returncode=1, stdout="")]):
            with self.assertRaisesRegex(ContractError, "upstream_worktree_modified"):
                worker.verify_upstream(self.upstream)

    def test_R02_child_environment_drops_unrelated_credentials(self):
        env = worker.child_environment(self.state, source={"PATH": "/bin", "GITHUB_TOKEN": "synthetic", "OPENAI_API_KEY": "synthetic", "HTTP_PROXY": "synthetic", "PYTHONPATH": "synthetic"})
        self.assertEqual(env["PATH"], "/bin")
        for key in ("GITHUB_TOKEN", "OPENAI_API_KEY", "HTTP_PROXY", "PYTHONPATH"):
            self.assertNotIn(key, env)
        self.assertEqual(env["HOME"], str(self.state / "worker-home"))

    def test_R03_exit_zero_without_report_is_not_success(self):
        class Process:
            returncode = 0
            def wait(self, timeout): return 0
            def poll(self): return 0
        result = worker.execute_job(self.job, self.runtime, live=True, runner=lambda *a, **k: Process(), upstream_check=lambda _: self.checked)
        self.assertEqual(result["receipt"]["errorCode"], "WORKER_NO_RECEIPT")

    def test_R03_structured_auth_failure_not_exit_code(self):
        job = self.job
        def launch(argv, **kwargs):
            self.assertFalse(kwargs["shell"])
            self.assertNotIn("--cookies", argv)
            envelope = json.loads(Path(argv[-1]).read_text())
            report = Observer(job)
            report.fail("auth_required", "SESSION_NOT_READY")
            Path(envelope["output"]).write_text(json.dumps(report.payload()), encoding="utf-8")
            return SimpleNamespace(returncode=0, wait=lambda timeout: 0, poll=lambda: 0)
        result = worker.execute_job(job, self.runtime, live=True, runner=launch, upstream_check=lambda _: self.checked)
        self.assertEqual(result["receipt"]["status"], "auth_required")

    def test_R04_timeout_terminates_owned_process_and_releases_lock(self):
        class Process:
            returncode = None
            def wait(self, timeout): raise subprocess.TimeoutExpired("fake", timeout)
            def poll(self): return self.returncode
        process = Process()
        def terminate(p): p.returncode = -15
        with patch.object(worker, "stop_process_tree", side_effect=terminate) as stopped:
            result = worker.execute_job(self.job, self.runtime, live=True, runner=lambda *a, **k: process, upstream_check=lambda _: self.checked)
        self.assertEqual(result["receipt"]["status"], "timeout")
        stopped.assert_called_once_with(process)
        with worker.profile_lock(self.state, "xhs", roots=(worker.ROOT, self.upstream)):
            pass

    def test_R04_profile_lock_is_exclusive(self):
        with worker.profile_lock(self.state, "xhs", roots=(worker.ROOT, self.upstream)):
            with self.assertRaisesRegex(ContractError, "profile_busy"):
                with worker.profile_lock(self.state, "xhs", roots=(worker.ROOT, self.upstream)):
                    pass

    def test_disabled_or_missing_live_never_starts_process(self):
        for enabled, live in ((False, True), (True, False)):
            self.runtime["enabled"] = enabled
            with patch("subprocess.Popen", side_effect=AssertionError("launched")):
                with self.assertRaisesRegex(ContractError, "live_activation_required"):
                    worker.execute_job(self.job, self.runtime, live=live)

    def test_native_window_and_comma_never_silently_ignored(self):
        self.job["window"] = {"from": "2026-10-01", "to": "2026-10-23", "filterMode": "native"}
        with self.assertRaisesRegex(ContractError, "worker_operation_unsupported"):
            worker.execute_job(self.job, self.runtime, live=True)

    def test_interactive_login_requires_separate_authorization(self):
        with self.assertRaisesRegex(ContractError, "interactive_auth_not_allowed"):
            worker.execute_job(self.job, self.runtime, live=True, interactive=True)


if __name__ == "__main__":
    unittest.main()
