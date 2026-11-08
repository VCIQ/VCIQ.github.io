"""Synthetic GitHub and isolated temporary local Git tests; no network/PR writes."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.company_profile_writer_pr_handoff import (
    RESERVATION, DetachedWorkspace, GitHubCli, HandoffError, Snapshot, submit,
)
from tools.company_profile_writer_pr_handoff import SMOKE_RESERVATION
from tools.company_profile_writer_pr_gate import SMOKE_BASE_BRANCH, SMOKE_BRANCH_PREFIX

BASE = "a" * 40
OTHER = "b" * 40
COMMIT = "c" * 40
BRANCH = "automation/company-profile-refresh/run-12345-attempt-1"
FILES = {"public/data/company_profile_refresh_queue.json": '{"processedEvents":{}}'}


class Prepared:
    def __init__(self, files=None):
        self.source = Snapshot(BASE, dict(FILES if files is None else files))
        self.reads = 0

    def snapshot(self):
        self.reads += 1
        return self.source


class FakeGithub:
    token_kind = "GITHUB_TOKEN"

    def __init__(self, *, base_branch="main", main_shas=(), open_second=(), open_after=2, fail_at=""):
        self.base_branch = base_branch
        self.branch_prefix = ("automation/company-profile-refresh/" if base_branch == "main"
                              else SMOKE_BRANCH_PREFIX)
        self.reservation_ref = RESERVATION if base_branch == "main" else SMOKE_RESERVATION
        self.main_shas = list(main_shas) or [BASE] * 5
        self.open_second = list(open_second)
        self.open_after = open_after
        self.fail_at = fail_at
        self.calls = []
        self.branches = []
        self.pr = None
        self.main_reads = 0
        self.open_reads = 0

    def _step(self, name):
        self.calls.append(name)
        if name == self.fail_at:
            raise HandoffError("SYNTHETIC_UPSTREAM_FAILURE")

    def base_sha(self):
        self._step("base")
        index = min(self.main_reads, len(self.main_shas) - 1)
        self.main_reads += 1
        return self.main_shas[index]

    def open_proposals(self):
        self._step("open")
        self.open_reads += 1
        return list(self.open_second) if self.open_reads >= self.open_after else []

    def candidate_branches(self):
        self._step("branches")
        return sorted(self.branches)

    def create_ref(self, name, sha):
        self._step("ref:" + name)
        if name in self.branches:
            raise HandoffError("SYNTHETIC_REF_CONFLICT")
        self.branches.append(name)

    def create_commit(self, base, files, run_id, attempt):
        self._step("commit")
        if base != BASE or files != FILES or run_id != "12345" or attempt != 1:
            raise AssertionError("unexpected mutation")
        return COMMIT

    def create_draft_pr(self, branch, commit, run_id):
        self._step("pr")
        self.pr = {"branch": branch, "sha": commit, "run_id": run_id,
                   "draft": True, "base": self.base_branch}
        return 6650

    def verify_pr(self, number, branch, commit):
        self._step("verify")
        expected = self.branch_prefix + "run-12345-attempt-1"
        if (number, branch, commit) != (6650, expected, COMMIT):
            raise AssertionError("wrong PR")


def run(gh, prepared=None, *, authorized=True):
    return submit(prepared or Prepared(), gh, run_id="12345", attempt=1,
                  authorized=authorized)


class HandoffOrchestrationTests(unittest.TestCase):
    def test_root_owned_connector_cannot_run_live_adapter(self):
        with patch.dict(os.environ, {"GH_TOKEN": "SYNTHETIC-SECRET"}, clear=False):
            adapter = GitHubCli()
            with patch("tools.company_profile_writer_pr_handoff.os.geteuid", return_value=0):
                with self.assertRaisesRegex(HandoffError, "UNPRIVILEGED_OPERATOR_REQUIRED"):
                    run(adapter)

    def test_default_requires_explicit_operator_approval(self):
        gh, prepared = FakeGithub(), Prepared()
        with self.assertRaisesRegex(HandoffError, "EXPLICIT_APPROVAL_REQUIRED"):
            run(gh, prepared, authorized=False)
        self.assertEqual(prepared.reads, 0)
        self.assertEqual(gh.calls, [])

    def test_success_creates_only_new_refs_commit_and_draft_pr(self):
        gh = FakeGithub()
        result = run(gh)
        self.assertEqual(result["decision"], "draft_pr_opened")
        self.assertEqual(result["candidateBranch"], BRANCH)
        self.assertEqual(result["candidateSha"], COMMIT)
        self.assertEqual(result["prNumber"], 6650)
        self.assertEqual(gh.branches, [RESERVATION, BRANCH])
        self.assertTrue(gh.pr["draft"])
        self.assertTrue(result["humanReviewRequired"])
        self.assertTrue(result["reservationCleanupRequiresHuman"])
        self.assertFalse(result["ciChecksVerified"])
        self.assertFalse(result["merged"])
        self.assertFalse(result["published"])
        self.assertEqual(gh.calls.count("commit"), 1)
        self.assertEqual(gh.calls.count("pr"), 1)

    def test_sandbox_base_creates_only_sandbox_namespaced_refs_and_pr(self):
        gh = FakeGithub(base_branch=SMOKE_BASE_BRANCH)
        result = run(gh)
        self.assertEqual(result["decision"], "draft_pr_opened")
        self.assertEqual(result["baseBranch"], SMOKE_BASE_BRANCH)
        self.assertEqual(result["candidateBranch"],
                         SMOKE_BRANCH_PREFIX + "run-12345-attempt-1")
        self.assertEqual(gh.branches, [SMOKE_RESERVATION,
                         SMOKE_BRANCH_PREFIX + "run-12345-attempt-1"])

    def test_prior_reservation_prevents_duplicate_run_before_writes(self):
        gh = FakeGithub()
        gh.branches = [RESERVATION]
        result = run(gh)
        self.assertEqual(result["decision"], "blocked_existing_branch")
        self.assertFalse(result["remoteWritesAttempted"])
        self.assertNotIn("commit", gh.calls)

    def test_stale_main_prevents_any_mutation(self):
        gh = FakeGithub(main_shas=[OTHER])
        result = run(gh)
        self.assertEqual(result["decision"], "blocked_stale_main")
        self.assertFalse(result["remoteWritesAttempted"])

    def test_preflight_error_exposes_only_fixed_safe_error_code(self):
        gh = FakeGithub(fail_at="base")
        result = run(gh)
        self.assertEqual(result["stage"], "preflight")
        self.assertEqual(result["errorCode"], "SYNTHETIC_UPSTREAM_FAILURE")
        self.assertFalse(result["remoteWritesAttempted"])

    def test_no_data_changes_is_noop_without_github_io(self):
        gh = FakeGithub()
        result = submit(SimpleNamespace(snapshot=lambda: None), gh,
                        run_id="12345", attempt=1, authorized=True)
        self.assertEqual(result["decision"], "no_changes")
        self.assertEqual(gh.calls, [])

    def test_ambiguous_reservation_failure_is_not_retried(self):
        gh = FakeGithub(fail_at="ref:" + RESERVATION)
        result = run(gh)
        self.assertEqual(result["stage"], "reserve")
        self.assertTrue(result["manualTriageRequired"])
        self.assertEqual(gh.calls.count("ref:" + RESERVATION), 1)

    def test_main_advanced_after_reservation_stops_before_commit(self):
        gh = FakeGithub(main_shas=[BASE, OTHER])
        result = run(gh)
        self.assertEqual(result["stage"], "recheck")
        self.assertTrue(result["manualTriageRequired"])
        self.assertNotIn("commit", gh.calls)

    def test_open_pr_race_after_reservation_fails_closed(self):
        gh = FakeGithub(open_second=["automation/company-profile-refresh/run-2-attempt-1"])
        result = run(gh)
        self.assertEqual(result["stage"], "recheck")
        self.assertNotIn("commit", gh.calls)

    def test_commit_api_failure_preserves_reservation_for_triage(self):
        gh = FakeGithub(fail_at="commit")
        result = run(gh)
        self.assertEqual(result["stage"], "commit")
        self.assertEqual(gh.branches, [RESERVATION])
        self.assertTrue(result["manualTriageRequired"])

    def test_candidate_ref_conflict_does_not_open_pr(self):
        gh = FakeGithub(fail_at="ref:" + BRANCH)
        result = run(gh)
        self.assertEqual(result["stage"], "candidate")
        self.assertNotIn("pr", gh.calls)
        self.assertTrue(result["manualTriageRequired"])

    def test_uncertain_pr_response_is_not_retried(self):
        gh = FakeGithub(fail_at="pr")
        result = run(gh)
        self.assertEqual(result["stage"], "proposal")
        self.assertEqual(gh.calls.count("pr"), 1)
        self.assertTrue(result["manualTriageRequired"])

    def test_verify_failure_is_a_manual_triage_not_success(self):
        gh = FakeGithub(fail_at="verify")
        result = run(gh)
        self.assertEqual(result["stage"], "verify")
        self.assertEqual(result["decision"], "blocked")
        self.assertNotEqual(result.get("prNumber"), 6650)

    def test_main_advances_after_draft_creation_requires_reconciliation(self):
        gh = FakeGithub(main_shas=[BASE, BASE, BASE, BASE, OTHER])
        result = run(gh)
        self.assertEqual(result["decision"], "draft_pr_opened_main_advanced")
        self.assertFalse(result["ciChecksVerified"])

    def test_main_advances_before_proposal_no_pr_is_created(self):
        gh = FakeGithub(main_shas=[BASE, BASE, BASE, OTHER])
        result = run(gh)
        self.assertEqual(result["stage"], "preproposal")
        self.assertTrue(result["manualTriageRequired"])
        self.assertNotIn("pr", gh.calls)

    def test_concurrent_pr_appears_after_candidate_creation(self):
        gh = FakeGithub(open_second=[BRANCH], open_after=3)
        result = run(gh)
        self.assertEqual(result["stage"], "preproposal")
        self.assertTrue(result["manualTriageRequired"])
        self.assertNotIn("pr", gh.calls)

    def test_duplicate_json_key_is_rejected_before_remote_write(self):
        with self.assertRaisesRegex(HandoffError, "DUPLICATE_JSON_KEYS"):
            Snapshot(BASE, {
                "public/data/venture_profiles.json": '{"companies":{},"companies":{}}',
            })

    def test_json_array_and_nonfinite_values_rejected(self):
        for value in ('[1,2]', '{"score":NaN}', '{"score":Infinity}'):
            with self.subTest(value=value), self.assertRaises(HandoffError):
                Snapshot(BASE, {"public/data/venture_profiles.json": value})


class GithubAdapterContractTests(unittest.TestCase):
    def test_pagination_uses_ampersand_for_existing_query(self):
        gh = object.__new__(GitHubCli)
        calls = []
        def fake_api(path, payload=None):
            calls.append(path)
            return []
        gh._api = fake_api
        self.assertEqual(gh.open_proposals(), [])
        self.assertEqual(calls, [
            "repos/VCIQ/VCIQ.github.io/pulls?state=open&per_page=100&page=1",
        ])

    def test_incomplete_pagination_fails_closed(self):
        gh = object.__new__(GitHubCli)
        gh.branch_prefix = "automation/company-profile-refresh/"
        gh._api = lambda path, payload=None: [{"name": "main"}] * 100
        with patch("tools.company_profile_writer_pr_handoff.MAX_PAGE", 2):
            with self.assertRaisesRegex(HandoffError, "INCOMPLETE"):
                gh.candidate_branches()

    def test_post_uses_json_stdin_and_never_prints_secret(self):
        with patch.dict(os.environ, {"GH_TOKEN": "SYNTHETIC-SECRET"}, clear=False):
            gh = GitHubCli()
            def fake_run(args, **kw):
                self.assertEqual(args[:2], ["gh", "api"])
                self.assertFalse(any("SYNTHETIC-SECRET" in token for token in args))
                self.assertNotIn("shell", kw)
                self.assertEqual(kw["stderr"], subprocess.DEVNULL)
                self.assertEqual(json.loads(kw["input"])["ref"],
                                 "refs/heads/" + RESERVATION)
                return SimpleNamespace(returncode=0, stdout=json.dumps({
                    "ref": "refs/heads/" + RESERVATION,
                    "object": {"sha": BASE},
                }))
            with patch("subprocess.run", side_effect=fake_run):
                gh.create_ref(RESERVATION, BASE)

    def test_failed_api_does_not_surface_sensitive_response(self):
        with patch.dict(os.environ, {"GH_TOKEN": "SYNTHETIC-SECRET"}, clear=False):
            gh = GitHubCli()
            with patch("subprocess.run", return_value=SimpleNamespace(
                returncode=1, stdout="PRIVATE-RESPONSE", stderr="PRIVATE-ERROR",
            )):
                with self.assertRaises(HandoffError) as caught:
                    gh.base_sha()
        self.assertNotIn("PRIVATE", str(caught.exception))
        self.assertNotIn("SYNTHETIC-SECRET", str(caught.exception))

    def test_pr_requires_draft_correct_branch_and_exact_commit(self):
        gh = object.__new__(GitHubCli)
        gh.base_branch = "main"
        good = {"draft": True, "state": "open", "merged_at": None,
                "head": {"ref": BRANCH, "sha": COMMIT,
                         "repo": {"full_name": "VCIQ/VCIQ.github.io"}},
                "base": {"ref": "main", "repo": {"full_name": "VCIQ/VCIQ.github.io"}}}
        gh._assert_pr(good, BRANCH, COMMIT)
        for change in ({"draft": False}, {"state": "closed"},
                       {"head": {"ref": BRANCH, "sha": OTHER}},
                       {"base": {"ref": "staging"}},
                       {"head": {"ref": BRANCH, "sha": COMMIT,
                                 "repo": {"full_name": "untrusted/fork"}}}):
            with self.subTest(change=change):
                with self.assertRaisesRegex(HandoffError, "UNCONFIRMED"):
                    gh._assert_pr({**good, **change}, BRANCH, COMMIT)


class DetachedWorkspaceTests(unittest.TestCase):
    def _repo(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        def git(*args):
            subprocess.run(["git", *args], cwd=root, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        git("init", "-q")
        git("config", "user.email", "synthetic@example.invalid")
        git("config", "user.name", "Synthetic Test")
        git("remote", "add", "origin", "https://github.com/VCIQ/VCIQ.github.io.git")
        directory = root / "public" / "data"
        directory.mkdir(parents=True)
        path = directory / "company_profile_refresh_queue.json"
        path.write_text('{"processedEvents":{}}', encoding="utf-8")
        git("add", "--", "public/data/company_profile_refresh_queue.json")
        git("commit", "-qm", "synthetic initial")
        git("checkout", "--detach", "HEAD")
        return root, path, git

    def test_reads_only_allowlisted_changed_json_from_detached_git(self):
        root, path, _ = self._repo()
        path.write_text('{"processedEvents":{"abc":{}}}', encoding="utf-8")
        snapshot = DetachedWorkspace(root).snapshot()
        self.assertEqual(set(snapshot.files),
                         {"public/data/company_profile_refresh_queue.json"})
        self.assertTrue(snapshot.base_sha)

    def test_unexpected_untracked_file_is_rejected(self):
        root, path, _ = self._repo()
        path.write_text('{"processedEvents":{"abc":{}}}', encoding="utf-8")
        (root / "secret.txt").write_text("SYNTHETIC")
        with self.assertRaisesRegex(HandoffError, "DIFF_UNEXPECTED"):
            DetachedWorkspace(root).snapshot()

    def test_attached_branch_is_rejected(self):
        root, path, git = self._repo()
        git("switch", "-c", "temporary-branch")
        path.write_text('{"processedEvents":{"abc":{}}}', encoding="utf-8")
        with self.assertRaisesRegex(HandoffError, "DETACHED_HEAD_REQUIRED"):
            DetachedWorkspace(root).snapshot()


if __name__ == "__main__":
    unittest.main()
