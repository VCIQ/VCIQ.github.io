"""PR-01 G01/G02: path isolation, default-off operation, safe offline CLI."""
from __future__ import annotations

import contextlib
import copy
import importlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.social import cli, contracts, guard, policy

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/social/contracts"


def runtime_fixture():
    return next(json.loads(line) for line in (FIXTURES / "valid.jsonl").read_text(encoding="utf-8").splitlines() if json.loads(line)["kind"] == "runtime_config")


class SocialGuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.base = Path(self.directory).resolve()
        self.repo = self.base / "vciq"
        self.mc = self.base / "MediaCrawler"
        self.repo.mkdir()
        self.mc.mkdir()
        self.state = self.base / "private-state"
        for target in ("socket.create_connection", "socket.socket.connect", "urllib.request.urlopen", "subprocess.Popen"):
            self.enterContext(patch(target, side_effect=AssertionError("offline guard attempted external work")))

    def assertGuard(self, expected, fn, *args, **kwargs):
        with self.assertRaises(guard.GuardError) as caught:
            fn(*args, **kwargs)
        self.assertEqual(expected, caught.exception.code)

    def test_G01_state_outside_both_worktrees_no_creation(self):
        self.assertEqual(self.state, guard.state_path(self.state, repo_roots=[self.repo, self.mc]))
        self.assertFalse(self.state.exists())
        for path in (self.repo, self.repo / "public/data", self.mc / "data", self.base):
            self.assertGuard("state_overlaps_repository", guard.state_path, path, repo_roots=[self.repo, self.mc])

    def test_G01_relative_and_parent_paths_rejected(self):
        for path in ("relative", "", self.base / "private-state/../elsewhere"):
            self.assertGuard("absolute_path_required", guard.state_path, path, repo_roots=[self.repo])

    def test_G01_symlink_into_repo_dangling_and_nested(self):
        link = self.base / "linked-state"
        link.symlink_to(self.repo, target_is_directory=True)
        self.assertGuard("symlink_forbidden", guard.state_path, link, repo_roots=[self.repo])
        link.unlink()
        link.symlink_to(self.base / "missing", target_is_directory=True)
        self.assertGuard("symlink_forbidden", guard.state_path, link / "child", repo_roots=[self.repo])
        self.state.mkdir()
        (self.state / "reports").symlink_to(self.repo, target_is_directory=True)
        self.assertGuard("symlink_forbidden", guard.output_path, self.state, "reports/result.json", repo_roots=[self.repo])

    def test_G01_invalid_output_components_and_hardlink(self):
        for relative in ("../public/data/x", "/tmp/x", "a//x", "a/./x", "a\\x", "C:/x"):
            self.assertGuard("invalid_relative_path", guard.output_path, self.state, relative, repo_roots=[self.repo])
        self.state.mkdir()
        source = self.repo / "immutable.json"
        source.write_text("production", encoding="utf-8")
        os.link(source, self.state / "hardlink.json")
        self.assertGuard("unsafe_output_target", guard.output_path, self.state, "hardlink.json", repo_roots=[self.repo])
        target = guard.output_path(self.state, "reports/report.json", repo_roots=[self.repo])
        self.assertEqual(target, self.state / "reports/report.json")
        self.assertFalse(target.parent.exists())

    def test_G01_regular_file_cannot_be_state_directory(self):
        self.state.write_text("not a directory", encoding="utf-8")
        self.assertGuard("state_not_directory", guard.state_path, self.state, repo_roots=[self.repo])

    def test_runtime_uses_dedicated_profile_and_external_config(self):
        runtime = runtime_fixture()
        self.state.mkdir()
        config_file = self.state / "runtime.json"
        config_file.write_text("{}", encoding="utf-8")
        runtime.update(stateDir=str(self.state), mediacrawlerDir=str(self.mc), profileRoot=str(self.state / "profiles"))
        self.assertEqual(self.state, guard.runtime_paths(runtime, repo_root=self.repo, runtime_file=config_file))
        runtime["profileRoot"] = str(self.base / "normal-browser")
        self.assertGuard("dedicated_profile_required", guard.runtime_paths, runtime, repo_root=self.repo)
        runtime["profileRoot"] = str(self.state / "profiles")
        repo_config = self.repo / "runtime.json"
        repo_config.write_text("{}", encoding="utf-8")
        self.assertGuard("runtime_outside_state", guard.runtime_paths, runtime, repo_root=self.repo, runtime_file=repo_config)

    def test_production_snapshot_detects_modified_added_and_removed(self):
        (self.repo / "config").mkdir()
        p = self.repo / "config/watchlist.json"
        p.write_text("{}", encoding="utf-8")
        baseline = guard.protected_snapshot(self.repo)
        guard.assert_unchanged(baseline, repo_root=self.repo)
        p.write_text('{"changed":true}', encoding="utf-8")
        self.assertGuard("production_modified", guard.assert_unchanged, baseline, repo_root=self.repo)
        p.write_text("{}", encoding="utf-8")
        new = self.repo / "config/new.json"
        new.write_text("{}", encoding="utf-8")
        self.assertGuard("production_modified", guard.assert_unchanged, baseline, repo_root=self.repo)
        new.unlink()
        p.unlink()
        self.assertGuard("production_modified", guard.assert_unchanged, baseline, repo_root=self.repo)

    def test_snapshot_does_not_dereference_protected_file_symlink(self):
        (self.repo / "config").mkdir()
        secret = self.base / "synthetic-private.txt"
        secret.write_text("SYNTHETIC_SECRET_ONLY", encoding="utf-8")
        (self.repo / "config/link").symlink_to(secret)
        with patch.object(Path, "read_bytes", side_effect=AssertionError("dereferenced link")):
            snapshot = guard.protected_snapshot(self.repo)
        self.assertIn("config/link", snapshot)

    def test_G02_default_disabled_even_if_policy_is_enabled(self):
        p = policy.load_policy()
        self.assertFalse(p["enabled"])
        self.assertTrue(all(not row["enabled"] for row in p["platforms"].values()))
        self.assertEqual(set(policy.activation(p).values()), {"disabled"})
        p["enabled"] = True
        self.assertEqual(set(policy.activation(p, live=True).values()), {"disabled"})

    def test_G02_runtime_requires_live_and_implemented_collector(self):
        p, runtime = policy.load_policy(), runtime_fixture()
        runtime["enabled"] = True
        runtime["platforms"]["xhs"]["enabled"] = True
        self.assertEqual(policy.activation(p, runtime)["xhs"], "live_opt_in_required")
        self.assertEqual(policy.activation(p, runtime, live=True)["xhs"], "not_implemented")
        self.assertEqual(policy.activation(p, runtime, live=True, implemented=frozenset({"xhs"}))["xhs"], "eligible")
        runtime["budget"] = {"recordsPerJob": 1000}
        with self.assertRaises(contracts.ContractError):
            policy.activation(p, runtime, live=True)

    def test_G02_doctor_and_validate_have_no_application_writes(self):
        before = guard.protected_snapshot(ROOT)
        with patch.object(Path, "write_text", side_effect=AssertionError("unexpected write")), patch.object(Path, "mkdir", side_effect=AssertionError("unexpected mkdir")):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(cli.main(["doctor", "--offline"]), 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result["status"], "disabled")
            self.assertFalse(result["writesPerformed"])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["validate", "--fixtures", str(FIXTURES)]), 0)
        guard.assert_unchanged(before, repo_root=ROOT)

    def test_G02_offline_doctor_never_enables_active_runtime(self):
        self.state.mkdir()
        runtime = runtime_fixture()
        runtime.update(enabled=True, stateDir=str(self.state), mediacrawlerDir=str(self.mc), profileRoot=str(self.state / "profiles"))
        runtime["platforms"]["xhs"]["enabled"] = True
        path = self.state / "runtime.json"
        path.write_text(json.dumps(runtime), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(["doctor", "--offline", "--runtime", str(path)]), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "offline_only")
        self.assertEqual(result["platforms"]["xhs"], "live_opt_in_required")
        self.assertFalse(result["liveExecuted"])
        self.assertFalse((self.state / "profiles").exists())

    def test_cli_refuses_publish_production_and_online_doctor(self):
        for args in (["publish"], ["run"], ["doctor"], ["doctor", "--offline", "--mode", "production"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                cli.main(args)
            self.assertEqual(caught.exception.code, 2)

    def test_cli_errors_do_not_echo_payload_or_input_filename(self):
        path = self.base / "SYNTHETIC_SECRET_FILENAME.json"
        doc = {"kind": "crawl_job", "cookie": "SYNTHETIC_SECRET_ONLY"}
        path.write_text(json.dumps(doc), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(cli.main(["validate", "--file", str(path)]), 2)
        self.assertNotIn("SYNTHETIC_SECRET", error.getvalue())
        self.assertEqual(json.loads(error.getvalue())["error"], "sensitive_field")


class SocialImportTests(unittest.TestCase):
    def test_G02_fresh_imports_no_network_subprocess_or_writes(self):
        # The child checks the real package parent in repository CI; -B suppresses
        # interpreter-generated bytecode so only application side effects matter.
        script = r'''
import sys, pathlib, importlib
from unittest.mock import patch

def deny(*args, **kwargs):
    raise AssertionError("import attempted external work")

def audit(event, args):
    if event.startswith(("socket.", "subprocess.")):
        raise AssertionError("import attempted external work")
    if event == "open":
        mode = args[1]
        flags = args[2] if len(args) > 2 else 0
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & (1 | 2 | 64 | 512 | 1024)):
            raise AssertionError("import attempted write")
    if event in {"os.mkdir", "os.rename", "os.remove", "os.rmdir", "os.chmod"}:
        raise AssertionError("import attempted filesystem mutation")

sys.addaudithook(audit)
with patch("urllib.request.urlopen", deny), patch("subprocess.Popen", deny):
    for name in ("tools.social", "tools.social.contracts", "tools.social.policy", "tools.social.guard", "tools.social.cli"):
        importlib.import_module(name)
print("IMPORT_GUARD_OK")
'''
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=25, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "IMPORT_GUARD_OK")


if __name__ == "__main__":
    unittest.main()
