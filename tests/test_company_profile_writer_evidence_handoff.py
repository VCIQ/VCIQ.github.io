"""Synthetic end-to-end composition; no remote GitHub calls or real collection."""
from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.company_profile_writer_evidence_handoff import (
    ARTICLES, CATALOG, EvidenceBoundWorkspace, EvidenceError, PROFILES, QUEUE,
)
from tools.company_profile_writer_pr_handoff import (
    DetachedWorkspace, Snapshot, submit,
)
from tests.test_company_profile_writer_transition_gate import NOW, ARTICLES as ARTICLE_FIXTURE, sample


SHA = "a" * 40
NEW_SHA = "b" * 40
CATALOG_FIXTURE = """export const companies: Company[] = [
  { slug:"openai", name:"OpenAI", source:official("OpenAI","https://example.org/openai") },
  { slug:"anthropic", name:"Anthropic", source:official("Anthropic","https://example.org/anthropic") },
];
export type Institution = {
"""


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"


class StubCheckout:
    def __init__(self, *, selected=None, after=None, baseline=None,
                 profile_before=None, profile_after=None, changed=None):
        original, intent, final, profiles_old, profiles_new = sample()
        self.base = {
            QUEUE: original if baseline is None else baseline,
            PROFILES: profiles_old if profile_before is None else profile_before,
        }
        self.sources = {
            ARTICLES: copy.deepcopy(ARTICLE_FIXTURE),
            CATALOG: CATALOG_FIXTURE,
        }
        self.selection = intent if selected is None else selected
        self.after = {
            QUEUE: final if after is None else after,
            PROFILES: profiles_new if profile_after is None else profile_after,
        }
        self.changed = [QUEUE, PROFILES] if changed is None else changed
        self.calls = []
        self.mode = b"100644"
        self.current_sha = SHA

    def _git(self, *args):
        self.calls.append(args)
        if args == ("rev-parse", "HEAD"):
            return (self.current_sha + "\n").encode()
        if args[:2] == ("ls-tree", "-z"):
            path = args[-1]
            return self.mode + b" blob " + b"0" * 40 + b"\t" + path.encode() + b"\0"
        if args[0] == "show" and ":" in args[1]:
            name = args[1].split(":", 1)[1]
            if name in self.base:
                return encoded(self.base[name]).encode()
            if name == ARTICLES:
                return encoded(self.sources[ARTICLES]).encode()
            if name == CATALOG:
                return self.sources[CATALOG].encode()
            raise AssertionError("unexpected base source")
        raise AssertionError("unexpected Git operation")

    def snapshot(self):
        if not self.changed:
            return None
        return Snapshot(SHA, {name: encoded(self.after[name]) for name in self.changed})


class FakeGitHub:
    base_branch = "main"
    token_kind = "GITHUB_TOKEN"
    branch_prefix = "automation/company-profile-refresh/"
    reservation_ref = "automation/company-profile-refresh/reservation"

    def __init__(self, base_sha=SHA):
        self.head = base_sha
        self.calls = []
        self.refs = []

    def base_sha(self):
        self.calls.append("base_sha")
        return self.head

    def open_proposals(self):
        self.calls.append("open_proposals")
        return []

    def candidate_branches(self):
        self.calls.append("candidate_branches")
        return sorted(self.refs)

    def create_ref(self, branch, sha):
        self.calls.append("create_ref")
        if branch in self.refs:
            raise AssertionError("reference overwritten")
        self.refs.append(branch)

    def create_commit(self, base_sha, files, run_id, attempt):
        self.calls.append("create_commit")
        assert base_sha == SHA
        assert run_id == "12345" and attempt == 1
        assert set(files) == {QUEUE, PROFILES}
        return NEW_SHA

    def create_draft_pr(self, branch, commit, run_id):
        self.calls.append("create_draft_pr")
        assert commit == NEW_SHA
        return 123

    def verify_pr(self, number, branch, commit):
        self.calls.append("verify_pr")
        assert number == 123 and commit == NEW_SHA


def bound(workspace, selected=None, started=None, completed=None):
    return EvidenceBoundWorkspace(
        workspace,
        copy.deepcopy(workspace.selection if selected is None else selected),
        NOW.isoformat() if started is None else started,
        NOW.isoformat() if completed is None else completed,
    )


class EvidenceHandoffTests(unittest.TestCase):
    def test_valid_candidate_binds_both_json_files_to_actual_base(self):
        checkout = StubCheckout()
        snapshot = bound(checkout).snapshot()
        self.assertEqual(snapshot.base_sha, SHA)
        self.assertEqual(set(snapshot.files), {QUEUE, PROFILES})
        self.assertEqual(sum(x[0] == "show" for x in checkout.calls), 4)

    def test_combination_can_open_only_a_draft_using_injected_api(self):
        github = FakeGitHub()
        result = submit(bound(StubCheckout()), github,
                        run_id="12345", attempt=1, authorized=True)
        self.assertEqual(result["decision"], "draft_pr_opened")
        self.assertEqual(result["prNumber"], 123)
        self.assertEqual(github.calls.count("create_ref"), 2)
        self.assertEqual(github.calls.count("create_commit"), 1)
        self.assertEqual(github.calls.count("create_draft_pr"), 1)
        self.assertFalse(result["merged"])
        self.assertFalse(result["published"])
        self.assertFalse(result["ciChecksVerified"])

    def test_transition_mismatch_blocks_before_any_gitHub_mutation(self):
        original, intent, final, old_profiles, new_profiles = sample()
        final["processedEvents"] = {}
        checkout = StubCheckout(after=final)
        github = FakeGitHub()
        result = submit(bound(checkout), github, run_id="12345",
                        attempt=1, authorized=True)
        self.assertEqual(result["stage"], "preflight")
        self.assertEqual(result["errorCode"], "WRITER_TRANSITION_PROCESSED_MISMATCH")
        self.assertFalse(result["remoteWritesAttempted"])
        self.assertEqual(github.calls, [])

    def test_unselected_company_change_is_rejected_before_remote_write(self):
        checkout = StubCheckout()
        checkout.after[PROFILES]["companies"]["anthropic"]["name"] = "Unauthorized"
        github = FakeGitHub()
        result = submit(bound(checkout), github, run_id="12345",
                        attempt=1, authorized=True)
        self.assertEqual(result["errorCode"], "WRITER_TRANSITION_UNRELATED_COMPANY_CHANGED")
        self.assertEqual(github.calls, [])

    def test_stale_remote_main_blocks_after_validated_transition(self):
        github = FakeGitHub(base_sha="c" * 40)
        result = submit(bound(StubCheckout()), github, run_id="12345",
                        attempt=1, authorized=True)
        self.assertEqual(result["decision"], "blocked_stale_main")
        self.assertNotIn("create_ref", github.calls)

    def test_selected_items_with_no_local_change_fail_closed(self):
        checkout = StubCheckout(changed=[])
        with self.assertRaisesRegex(EvidenceError, "PROCESSED_MISMATCH"):
            bound(checkout).snapshot()

    def test_no_selection_no_change_is_no_op(self):
        checkout = StubCheckout(changed=[])
        checkout.selection = copy.deepcopy(checkout.base[QUEUE])
        checkout.sources[ARTICLES]["articles"] = []
        self.assertIsNone(bound(checkout).snapshot())
        github = FakeGitHub()
        result = submit(bound(checkout), github, run_id="12345",
                        attempt=1, authorized=True)
        self.assertEqual(result["decision"], "no_changes")
        self.assertEqual(github.calls, [])

    def test_malformed_or_duplicate_base_json_fails_closed(self):
        checkout = StubCheckout()
        original = checkout._git
        def malformed(*args):
            if args == ("show", SHA + ":" + QUEUE):
                return b'{"schemaVersion":1,"schemaVersion":1}'
            return original(*args)
        checkout._git = malformed
        with self.assertRaisesRegex(EvidenceError, "DUPLICATE_KEY"):
            bound(checkout).snapshot()

    def test_symlinked_base_git_blob_rejected(self):
        checkout = StubCheckout()
        checkout.mode = b"120000"
        with self.assertRaisesRegex(EvidenceError, "BASE_BLOB_INVALID"):
            bound(checkout).snapshot()

    def test_head_moved_after_staging_is_refused(self):
        checkout = StubCheckout()
        checkout.current_sha = "f" * 40
        with self.assertRaisesRegex(EvidenceError, "BASE_MOVED"):
            bound(checkout).snapshot()

    def test_baseline_git_reads_use_immutable_sha_not_moving_head(self):
        checkout = StubCheckout()
        bound(checkout).snapshot()
        self.assertIn(("ls-tree", "-z", SHA, "--", QUEUE), checkout.calls)
        self.assertIn(("show", SHA + ":" + PROFILES), checkout.calls)
        self.assertIn(("show", SHA + ":" + ARTICLES), checkout.calls)
        self.assertIn(("show", SHA + ":" + CATALOG), checkout.calls)

    def test_forged_pre_crawl_selection_not_derived_from_articles_is_rejected(self):
        checkout = StubCheckout()
        checkout.sources[ARTICLES]["articles"] = []
        github = FakeGitHub()
        result = submit(bound(checkout), github, run_id="12345",
                        attempt=1, authorized=True)
        self.assertEqual(result["errorCode"], "EVIDENCE_SELECTION_SOURCE_MISMATCH")
        self.assertEqual(github.calls, [])

    def test_replayed_selection_timestamp_outside_run_is_rejected(self):
        checkout = StubCheckout()
        with self.assertRaisesRegex(EvidenceError, "SELECTION_OUTSIDE_RUN"):
            bound(checkout, started="2026-11-08T11:00:00+00:00",
                  completed="2026-11-08T11:05:00+00:00").snapshot()

    def test_stale_article_snapshot_does_not_reject_new_selection(self):
        checkout = StubCheckout()
        checkout.sources[ARTICLES]["generatedAt"] = "2026-11-03T10:00:00+00:00"
        self.assertEqual(bound(checkout).snapshot().base_sha, SHA)

    def test_unapproved_catalog_change_is_rejected_before_remote_access(self):
        checkout = StubCheckout()
        checkout.sources[CATALOG] = "export const companies: Company[] = [];\n"
        with self.assertRaisesRegex(EvidenceError, "CATALOG_INVALID"):
            bound(checkout).snapshot()

    def test_malformed_catalog_does_not_fall_back_to_ambient_registry(self):
        checkout = StubCheckout()
        checkout.sources[CATALOG] = (
            'export const companies: Company[] = [\n'
            '  { slug:"openai", name:"OpenAI", source:official("OpenAI","ftp://unsafe") },\n'
            '];\nexport type Institution = {\n'
        )
        with self.assertRaisesRegex(EvidenceError, "CATALOG_INVALID"):
            bound(checkout).snapshot()

    def test_bad_evidence_window_rejected(self):
        checkout = StubCheckout()
        with self.assertRaisesRegex(EvidenceError, "RUN_WINDOW_INVALID"):
            bound(checkout, started=NOW.isoformat(),
                  completed=(NOW.replace(hour=8)).isoformat()).snapshot()

    def test_selection_input_is_frozen(self):
        checkout = StubCheckout()
        old = copy.deepcopy(checkout.selection)
        wrapper = bound(checkout)
        checkout.selection["selectedSlugs"] = []
        self.assertEqual(wrapper.pre_crawl_selection, old)
        self.assertEqual(wrapper.snapshot().base_sha, SHA)

    def test_real_detached_temp_git_checkout_is_bound_to_base_blobs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def git(*args):
                subprocess.run(["git", *args], cwd=root, check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            git("init", "-q")
            git("config", "user.email", "synthetic@example.invalid")
            git("config", "user.name", "Synthetic Test")
            git("remote", "add", "origin", "https://github.com/VCIQ/VCIQ.github.io.git")
            checkout = StubCheckout()
            for name in (QUEUE, PROFILES, ARTICLES, CATALOG):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                if name in checkout.base:
                    payload = encoded(checkout.base[name])
                elif name == ARTICLES:
                    payload = encoded(checkout.sources[name])
                else:
                    payload = checkout.sources[name]
                path.write_text(payload, encoding="utf-8")
            git("add", "--", QUEUE, PROFILES, ARTICLES, CATALOG)
            git("commit", "-qm", "synthetic base")
            git("checkout", "--detach", "HEAD")
            for name in (QUEUE, PROFILES):
                (root / name).write_text(encoded(checkout.after[name]), encoding="utf-8")
            wrapper = EvidenceBoundWorkspace(
                DetachedWorkspace(root), checkout.selection,
                NOW.isoformat(), NOW.isoformat(),
            )
            result = wrapper.snapshot()
            self.assertEqual(set(result.files), {QUEUE, PROFILES})
            self.assertEqual(len(result.base_sha), 40)


if __name__ == "__main__":
    unittest.main()
