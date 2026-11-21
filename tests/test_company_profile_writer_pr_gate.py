"""Offline, synthetic tests for the proposed (not deployed) PR writer gate."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest

from tools.company_profile_writer_pr_gate import GateError, decide


def payload(**updates):
    record = {
        "schemaVersion": 1,
        "repository": "VCIQ/VCIQ.github.io",
        "baseBranch": "main",
        "sourceHeadSha": "a" * 40,
        "observedMainSha": "a" * 40,
        "runId": "12345",
        "runAttempt": 1,
        "changedPaths": [
            "public/data/company_profile_refresh_queue.json",
            "public/data/venture_profiles.json",
        ],
        "openProposalHeads": [],
        "knownRemoteBranches": [],
        "inventoryComplete": True,
        "tokenKind": "GITHUB_TOKEN",
    }
    record.update(updates)
    return record


class CompanyProfileWriterPrGateTests(unittest.TestCase):
    def test_valid_proposal_is_only_a_non_executable_plan(self):
        result = decide(payload())
        self.assertEqual(result["decision"], "would_prepare_draft_pr")
        self.assertEqual(result["candidateBranch"],
                         "automation/company-profile-refresh/run-12345-attempt-1")
        self.assertEqual(result["ciWorkflowApproval"],
                         "manual_required_for_GITHUB_TOKEN_created_PR")
        self.assertTrue(result["humanApprovalRequired"])
        self.assertFalse(result["productionWrites"])
        self.assertFalse(result["automaticMerge"])
        self.assertFalse(result["handoffExecuted"])
        self.assertFalse(result["approvalGateVerified"])

    def test_pending_proposal_blocks_duplicate_scheduled_run(self):
        first = decide(payload())
        second = decide(payload(
            runId="12346",
            openProposalHeads=[first["candidateBranch"]]))
        self.assertEqual(second["decision"], "blocked_open_proposal")
        self.assertNotIn("candidateBranch", second)

    def test_existing_run_branch_never_overwritten(self):
        result = decide(payload(knownRemoteBranches=[
            "automation/company-profile-refresh/run-12345-attempt-1"]))
        self.assertEqual(result["decision"], "blocked_existing_branch")

    def test_other_attempt_or_prior_run_branch_needs_triage(self):
        for branch in (
            "automation/company-profile-refresh/run-12345-attempt-2",
            "automation/company-profile-refresh/run-12344-attempt-1",
        ):
            with self.subTest(branch=branch):
                result = decide(payload(knownRemoteBranches=[branch]))
                self.assertEqual(result["decision"], "blocked_existing_branch")

    def test_stale_main_fails_closed_before_proposal(self):
        result = decide(payload(observedMainSha="b" * 40))
        self.assertEqual(result["decision"], "blocked_stale_main")

    def test_no_changes_does_not_propose(self):
        result = decide(payload(changedPaths=[]))
        self.assertEqual(result["decision"], "no_changes")

    def test_only_one_allowlisted_file_can_change(self):
        result = decide(payload(changedPaths=["public/data/venture_profiles.json"]))
        self.assertEqual(result["allowlistedPaths"], ["public/data/venture_profiles.json"])

    def test_refuse_non_data_and_private_paths(self):
        for path in ("config/social_discovery.json", ".env",
                     "public/data/private.json", "../secrets", "tools/worker.py"):
            with self.subTest(path=path), self.assertRaisesRegex(
                GateError, "WRITER_GATE_UNEXPECTED_FILES"
            ):
                decide(payload(changedPaths=[path]))

    def test_reject_missing_or_incomplete_open_pr_inventory(self):
        for value in (False, None, "true", 1):
            with self.subTest(value=value), self.assertRaisesRegex(
                GateError, "WRITER_GATE_INVENTORY_UNVERIFIED"
            ):
                decide(payload(inventoryComplete=value))

    def test_reject_wrong_repository_or_target_branch(self):
        for update in ({"repository": "elsewhere/repo"}, {"baseBranch": "release"}):
            with self.subTest(update=update), self.assertRaisesRegex(
                GateError, "WRITER_GATE_REPOSITORY_INVALID"
            ):
                decide(payload(**update))

    def test_sandbox_base_has_separate_candidate_namespace(self):
        result = decide(payload(baseBranch="codex/writer-token-smoke-base-20261108"))
        self.assertEqual(result["decision"], "would_prepare_draft_pr")
        self.assertEqual(result["baseBranch"], "codex/writer-token-smoke-base-20261108")
        self.assertTrue(result["candidateBranch"].startswith(
            "automation/company-profile-refresh-smoke/"))

    def test_no_unverified_sha_or_fake_run_id(self):
        for update in ({"sourceHeadSha": "main"}, {"observedMainSha": "B" * 40},
                       {"runId": "12/3"}, {"runAttempt": True}, {"runAttempt": 21}):
            with self.subTest(update=update), self.assertRaises(GateError):
                decide(payload(**update))

    def test_token_mode_is_reported_but_not_used_as_approval(self):
        result = decide(payload(tokenKind="GITHUB_APP"))
        self.assertEqual(result["ciWorkflowApproval"], "verify_actual_check_runs")
        self.assertFalse(result["approvalGateVerified"])
        with self.assertRaisesRegex(GateError, "WRITER_GATE_TOKEN_UNSUPPORTED"):
            decide(payload(tokenKind="PERSONAL_TOKEN"))

    def test_reject_unknown_or_sensitive_fields(self):
        with self.assertRaisesRegex(GateError, "WRITER_GATE_INPUT_INVALID"):
            decide(payload(ghToken="SECRET-SENTINEL"))

    def test_reject_duplicate_and_non_writer_remote_entries(self):
        for update in (
            {"changedPaths": ["public/data/venture_profiles.json"] * 2},
            {"openProposalHeads": ["some-other-branch"]},
            {"knownRemoteBranches": ["main"]},
        ):
            with self.subTest(update=update), self.assertRaises(GateError):
                decide(payload(**update))

    def test_command_line_error_is_fixed_and_does_not_echo_secret(self):
        proc = subprocess.run(
            [sys.executable, "-B", "-m", "tools.company_profile_writer_pr_gate",
             "--stdin-json"], input='{"secret":"SECRET-SENTINEL"}',
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["errorCode"], "WRITER_GATE_REJECTED")
        self.assertNotIn("SECRET-SENTINEL", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
