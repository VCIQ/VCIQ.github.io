"""Exercise the real workflow publication shell against disposable git repos.

Only domain commands / the control-plane finalizer / gh are test doubles. Git
staging, commits, pushes, failed pushes and replay resets execute for real.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/tracking-discovery.yml"


def step(name: str) -> str:
    return WORKFLOW.read_text(encoding="utf-8").split(f"- name: {name}\n", 1)[1].split("\n      - ", 1)[0]


def shell(name: str) -> str:
    return textwrap.dedent(step(name).split("run: |\n", 1)[1])


@unittest.skipUnless(shutil.which("git") and shutil.which("bash"), "requires git and bash")
class TrackingDiscoveryPublicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / "origin.git"
        self.work = self.root / "work"
        self.bin = self.root / "bin"
        self.work.mkdir()
        self.bin.mkdir()
        self.output = self.root / "outputs"
        self.log = self.root / "commands"
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GITHUB_OUTPUT": str(self.output),
            "GITHUB_REPOSITORY": "example/test",
            "EVENT_NAME": "schedule",
            "EXPAND_MODE": "full",
            "TEST_LOG": str(self.log),
        }
        self.git("init", "--bare", "--initial-branch=main", str(self.remote))
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("remote", "add", "origin", str(self.remote))
        for name in ["config/user_tracking.json", "config/tracking_auto_discovery.json", "public/data/source_health.json", "public/data/data_lineage.json", "public/data/pipeline_health.json"]:
            path = self.work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"baseline":true}\n', encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "baseline")
        self.git("push", "origin", "HEAD:main")
        self.baseline = self.git("rev-parse", "HEAD")
        self.stub("python", f"#!{sys.executable}\n" + textwrap.dedent('''\
            import json, os, pathlib, sys
            with open(os.environ['TEST_LOG'], 'a') as log:
                log.write('python ' + ' '.join(sys.argv[1:]) + '\\n')
            if sys.argv[1:3] == ['tools/run_pipeline.py', 'finalize']:
                if os.environ.get('FAIL_FINALIZE') == '1':
                    sys.exit(23)
                for path in ['public/data/data_lineage.json', 'public/data/pipeline_health.json']:
                    pathlib.Path(path).write_text(json.dumps({'testHeartbeat': sys.argv[3]}) + '\\n')
            print('{}')
        '''))
        for command in ["node", "npm", "gh"]:
            self.stub(command, '#!/bin/bash\nprintf "%s\\n" "' + command + ' $*" >> "$TEST_LOG"\nprintf "{}\\n"\n')

    def stub(self, name: str, content: str) -> None:
        path = self.bin / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def git(self, *args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=self.work, env=self.env, text=True, stderr=subprocess.DEVNULL).strip()

    def publish(self, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["bash", "-c", shell("Commit expanded tracking config")], cwd=self.work, env={**self.env, **env}, text=True, capture_output=True, timeout=30)

    def outputs(self) -> dict[str, str]:
        return dict(line.split("=", 1) for line in self.output.read_text().splitlines()) if self.output.exists() else {}

    def logs(self) -> str:
        return self.log.read_text() if self.log.exists() else ""

    def remote_head(self) -> str:
        return self.git("--git-dir", str(self.remote), "rev-parse", "refs/heads/main")

    def change_config(self) -> None:
        (self.work / "config/user_tracking.json").write_text('{"newConfig":true}\n')

    def test_full_noop_publishes_only_genuine_completion_not_business_freshness(self) -> None:
        before = (self.work / "public/data/source_health.json").read_bytes()
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.outputs(), {"published": "true", "config_changed": "false"})
        self.assertNotEqual(self.remote_head(), self.baseline)
        changed = self.git("diff", "--name-only", self.baseline, "HEAD").splitlines()
        self.assertEqual(changed, ["public/data/data_lineage.json", "public/data/pipeline_health.json"])
        self.assertEqual((self.work / "public/data/source_health.json").read_bytes(), before)
        self.assertIn("finalize tracking-entity-discovery --quality-gate passed", self.logs())

    def test_full_config_change_requests_downstream_refresh(self) -> None:
        self.change_config()
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.outputs(), {"published": "true", "config_changed": "true"})
        self.assertIn("config/user_tracking.json", self.git("diff", "--name-only", self.baseline, "HEAD"))

    def test_governance_noop_does_not_manufacture_full_discovery_heartbeat(self) -> None:
        result = self.publish(EVENT_NAME="push", EXPAND_MODE="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.outputs(), {"published": "false"})
        self.assertEqual(self.remote_head(), self.baseline)
        self.assertNotIn("finalize", self.logs())

    def test_governance_change_publishes_config_without_full_heartbeat(self) -> None:
        self.change_config()
        result = self.publish(EVENT_NAME="push", EXPAND_MODE="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.outputs(), {"published": "true", "config_changed": "true"})
        self.assertEqual(self.git("diff", "--name-only", self.baseline, "HEAD"), "config/user_tracking.json")
        self.assertNotIn("finalize", self.logs())

    def test_seed_only_change_is_not_a_full_discovery_heartbeat(self) -> None:
        self.change_config()
        result = self.publish(EVENT_NAME="workflow_dispatch", EXPAND_MODE="seed-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.outputs()["config_changed"], "true")
        self.assertNotIn("finalize", self.logs())

    def test_failed_finalizer_cannot_publish_success(self) -> None:
        self.change_config()
        result = self.publish(FAIL_FINALIZE="1")
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(self.outputs(), {"published": "false"})
        self.assertEqual(self.remote_head(), self.baseline)

    def test_failed_commit_cannot_publish_success(self) -> None:
        hook = self.work / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\nexit 24\n")
        hook.chmod(0o755)
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.outputs(), {"published": "false"})
        self.assertEqual(self.remote_head(), self.baseline)

    def test_failed_push_replays_before_recording_a_new_completion(self) -> None:
        rejected = self.root / "rejected-once"
        hook = self.remote / "hooks/pre-receive"
        hook.write_text(f'#!/bin/sh\nif [ ! -f "{rejected}" ]; then touch "{rejected}"; exit 1; fi\n')
        hook.chmod(0o755)
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.outputs(), {"published": "true", "config_changed": "false"})
        self.assertEqual(self.logs().count("finalize tracking-entity-discovery"), 2)
        self.assertIn("expand_tracking_entities.py --max-tracks 12 --max-requests 240", self.logs())
        self.assertIn("validate-new-tracking-entities.ts --base-ref HEAD", self.logs())

    def test_exhausted_push_retries_never_emit_success(self) -> None:
        hook = self.remote / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.outputs(), {"published": "false"})
        self.assertEqual(self.remote_head(), self.baseline)
        self.assertEqual(self.logs().count("finalize tracking-entity-discovery"), 3)

    def test_handoff_distinguishes_changed_crawler_inputs_from_heartbeat_only(self) -> None:
        for changed, workflow in [("true", "scheduled-sync.yml"), ("false", "pages.yml")]:
            with self.subTest(changed=changed):
                self.log.write_text("")
                result = subprocess.run(["bash", "-c", shell("Hand off the committed discovery result")], cwd=self.work, env={**self.env, "CONFIG_CHANGED": changed}, text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.logs().strip(), f"gh workflow run {workflow} --ref main --repo example/test")
        self.assertIn("if: steps.publish.outputs.published == 'true'", step("Hand off the committed discovery result"))

    def test_final_validation_is_not_skipped_for_noop_and_checkout_is_current_main(self) -> None:
        self.assertNotIn("if:", step("Validate the expanded config before committing"))
        self.assertNotIn("if:", step("Commit expanded tracking config").split("run: |", 1)[0])
        text = WORKFLOW.read_text()
        self.assertIn("ref: main\n", text)
        self.assertIn("queue: max", text)
        self.assertLess(text.index("- name: Validate the expanded config"), text.index("- name: Commit expanded tracking config"))
        # Standalone function calls preserve bash errexit; 'if ! function' would
        # suppress failures inside the function and can falsely mark completion.
        self.assertNotIn("if ! commit_current_config", text)


if __name__ == "__main__":
    unittest.main()
