"""Real local subprocesses in disposable repos; never invoke a real crawler.

The origin URL is deliberately synthetic Git configuration, not provenance
evidence. The committed fixture program uses no HTTP or other network API.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from tools.company_profile_writer_crawl_observer import (
    crawl_argv, observe_selected_company_crawls,
)
from tools.company_profile_writer_crawl_runner import (
    BoundedCrawlRunner, CrawlRunnerError,
)

FIXTURE_PROGRAM = '''from datetime import UTC, datetime
import json, os
from pathlib import Path
path = Path("public/data/venture_profiles.json")
profile = {
    "slug": "alpha", "name": "Alpha", "status": "ok",
    "updatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
    "background": "Offline fixture", "technology": "Synthetic only",
    "products": ["fixture"], "warnings": [], "evidenceScore": 80,
    "sources": [{"url":"https://alpha.example/about"},
                {"url":"https://alpha.example/research"}],
}
status = {"kind":"company", "slug":"alpha", "name":"Alpha", "status":"ok",
          "fetchedPages":2, "acceptedSections":5, "retainedPrevious":False,
          "elapsedSeconds":0.01}
payload = {"companies":{"alpha":profile}, "sourceStatus":[status],
           "qualityGate":{"passed":True},
           "unexpectedEnv":[k for k in ("GH_TOKEN", "HTTP_PROXY", "PYTHONPATH",
                                        "AWS_SECRET_ACCESS_KEY") if k in os.environ]}
path.write_text(json.dumps(payload))
'''


class OfflineRepo:
    def __init__(self, program=FIXTURE_PROGRAM):
        self.temp = tempfile.TemporaryDirectory(prefix="crawl-runner-fixture-")
        self.root = Path(self.temp.name).resolve()
        (self.root / "tools").mkdir()
        (self.root / "tools/__init__.py").write_text("")
        (self.root / "tools/crawl_venture_profiles.py").write_text(program)
        (self.root / "public/data").mkdir(parents=True)
        self.profile_path = self.root / "public/data/venture_profiles.json"
        self.queue_path = self.root / "public/data/company_profile_refresh_queue.json"
        self.profile_path.write_text(json.dumps({
            "companies": {"alpha": {"slug":"alpha", "updatedAt":"2000-01-01T00:00:00Z"}},
            "sourceStatus": [], "qualityGate": {"passed":True},
        }))
        self.queue_path.write_text("{}\n")
        self.git("init", "-q")
        self.git("config", "user.email", "offline@example.invalid")
        self.git("config", "user.name", "Offline Fixture")
        self.git("remote", "add", "origin", "https://github.com/VCIQ/VCIQ.github.io.git")
        self.commit()
        self.git("checkout", "--detach", "-q")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=10).stdout.decode().strip()

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "offline fixture")
        self.sha = self.git("rev-parse", "HEAD")

    def runner(self, **overrides):
        kw = dict(checkout_root=self.root, base_sha=self.sha,
                  selected_slugs=["alpha"], authorized=True)
        kw.update(overrides)
        return BoundedCrawlRunner(**kw)

    def close(self):
        self.temp.cleanup()


@unittest.skipUnless(os.name == "posix", "POSIX process group contract")
class BoundedCrawlRunnerTests(unittest.TestCase):
    def setUp(self):
        self.repo = OfflineRepo()

    def tearDown(self):
        self.repo.close()

    def execute(self, runner=None, timeout=5):
        return (runner or self.repo.runner())(
            crawl_argv("alpha"), cwd=self.repo.root, timeout=timeout,
        )

    def replace_program(self, body):
        (self.repo.root / "tools/crawl_venture_profiles.py").write_text(body)
        self.repo.commit()

    def test_real_offline_subprocess_writes_only_allowed_output(self):
        result = self.execute()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.args, crawl_argv("alpha"))
        self.assertEqual(self.repo.git("status", "--porcelain"),
                         "M public/data/venture_profiles.json")

    def test_observer_and_runner_integration_uses_real_fixture_subprocess(self):
        started = (datetime.now(UTC) - timedelta(seconds=1)).isoformat(timespec="seconds")
        result = observe_selected_company_crawls(
            checkout_root=self.repo.root,
            pre_crawl_selection={"generatedAt":started, "selectedCount":1,
                                 "selectedSlugs":["alpha"]},
            pinned_official_urls={"alpha":"https://alpha.example/"},
            base_sha=self.repo.sha, run_id="offline-integration",
            run_started_at=started, run_command=self.repo.runner(),
            clock=lambda: datetime.now(UTC), authorized=True,
        )
        self.assertEqual(result["verifiedCompanyCount"], 1)
        self.assertFalse(result["markProcessedAuthorized"])
        self.assertFalse(result["publicationAuthorized"])
        self.assertFalse(result["sourceFetchCryptographicallyAttested"])

    def test_secrets_proxy_and_pythonpath_are_not_inherited(self):
        with patch.dict(os.environ, {"GH_TOKEN":"synthetic-secret",
                                     "HTTP_PROXY":"http://invalid.example/",
                                     "PYTHONPATH":"/invalid-path",
                                     "AWS_SECRET_ACCESS_KEY":"synthetic-secret"}):
            self.execute()
        self.assertEqual(json.loads(self.repo.profile_path.read_text())["unexpectedEnv"], [])

    def test_unauthorized_runner_cannot_be_constructed(self):
        with self.assertRaisesRegex(CrawlRunnerError, "NOT_AUTHORIZED"):
            self.repo.runner(authorized=False)

    def test_wrong_sha_blocks_before_fixture(self):
        with self.assertRaisesRegex(CrawlRunnerError, "BASE_MOVED"):
            self.execute(self.repo.runner(base_sha="a" * 40))

    def test_attached_head_is_rejected(self):
        self.repo.git("checkout", "-qb", "not-detached")
        with self.assertRaisesRegex(CrawlRunnerError, "GIT_FAILED"):
            self.execute()

    def test_unexpected_origin_is_rejected(self):
        self.repo.git("remote", "set-url", "origin", "https://invalid.example/repo.git")
        with self.assertRaisesRegex(CrawlRunnerError, "ORIGIN_INVALID"):
            self.execute()

    def test_uncommitted_code_is_rejected(self):
        (self.repo.root / "tools/crawl_venture_profiles.py").write_text("raise Exception()")
        with self.assertRaisesRegex(CrawlRunnerError, "UNEXPECTED_CHANGE"):
            self.execute()

    def test_ignored_module_is_not_silently_imported(self):
        (self.repo.root / ".gitignore").write_text("tools/hidden.py\n")
        self.repo.commit()
        (self.repo.root / "tools/hidden.py").write_text("# ignored but unsafe\n")
        with self.assertRaisesRegex(CrawlRunnerError, "UNEXPECTED_CHANGE"):
            self.execute()

    def test_untracked_file_is_rejected(self):
        (self.repo.root / "unexpected.txt").write_text("untracked")
        with self.assertRaisesRegex(CrawlRunnerError, "UNEXPECTED_CHANGE"):
            self.execute()

    def test_staged_data_changes_are_rejected(self):
        self.repo.queue_path.write_text('{"changed":true}')
        self.repo.git("add", str(self.repo.queue_path))
        with self.assertRaisesRegex(CrawlRunnerError, "UNEXPECTED_CHANGE"):
            self.execute()

    def test_permitted_unstaged_data_changes_are_preserved(self):
        self.repo.queue_path.write_text('{"selected":true}')
        self.execute()
        self.assertEqual(json.loads(self.repo.queue_path.read_text()), {"selected":True})

    def test_command_cannot_choose_a_shell_or_another_slug(self):
        with self.assertRaisesRegex(CrawlRunnerError, "COMMAND_INVALID"):
            self.repo.runner()(["sh", "-c", "true"], cwd=self.repo.root, timeout=5)
        with self.assertRaisesRegex(CrawlRunnerError, "COMMAND_INVALID"):
            self.repo.runner()(crawl_argv("other"), cwd=self.repo.root, timeout=5)

    def test_cwd_cannot_switch_to_another_repository(self):
        with self.assertRaisesRegex(CrawlRunnerError, "CWD_INVALID"):
            self.repo.runner()(crawl_argv("alpha"), cwd=self.repo.root.parent, timeout=5)

    def test_timeout_kills_process_and_disallows_retry(self):
        self.replace_program("import time\ntime.sleep(30)\n")
        runner = self.repo.runner()
        started = time.monotonic()
        with self.assertRaisesRegex(CrawlRunnerError, "PROCESS_TIMEOUT"):
            self.execute(runner, timeout=1)
        self.assertLess(time.monotonic() - started, 15)
        with self.assertRaisesRegex(CrawlRunnerError, "ALREADY_CONSUMED"):
            self.execute(runner)

    def test_nonzero_exit_has_no_success_receipt(self):
        self.replace_program("raise SystemExit(3)\n")
        with self.assertRaisesRegex(CrawlRunnerError, "NONZERO_EXIT"):
            self.execute()

    def test_postprocess_code_mutation_is_detected(self):
        self.replace_program('from pathlib import Path\nPath("tools/__init__.py").write_text("# changed")\n')
        with self.assertRaisesRegex(CrawlRunnerError, "UNEXPECTED_CHANGE"):
            self.execute()

    def test_duplicate_execution_is_rejected(self):
        runner = self.repo.runner()
        self.execute(runner)
        with self.assertRaisesRegex(CrawlRunnerError, "ALREADY_CONSUMED"):
            self.execute(runner)

    def test_expired_runner_deadline_blocks_before_process(self):
        runner = self.repo.runner()
        runner.deadline = time.monotonic() - 1
        with self.assertRaisesRegex(CrawlRunnerError, "DEADLINE_EXCEEDED"):
            self.execute(runner)

    def test_child_must_not_mark_or_change_queue(self):
        self.replace_program('from pathlib import Path\nPath("public/data/company_profile_refresh_queue.json").write_text("changed")\n')
        with self.assertRaisesRegex(CrawlRunnerError, "QUEUE_CHANGED"):
            self.execute()

    def test_deadline_is_rechecked_after_checkout_validation(self):
        runner = self.repo.runner()
        def expired(_):
            runner.deadline = time.monotonic() - 1
        with patch.object(runner, "_verify_checkout", side_effect=expired):
            with self.assertRaisesRegex(CrawlRunnerError, "DEADLINE_EXCEEDED"):
                self.execute(runner)


if __name__ == "__main__":
    unittest.main()
