"""Opt-in Draft-PR handoff for a *separately staged* company-profile result.

NOT connected to any production/scheduled workflow. No CLI apply entry point.
Call submit(..., authorized=True) only after an explicitly approved pilot.
The GitHub adapter creates immutable Git objects and new refs, never updates
main, pushes with force, merges, publishes, or starts a crawler.
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .company_profile_writer_pr_gate import (
    ALLOWED_FILES, BRANCH_PREFIX, GateError, SHA, decide,
)

REPOSITORY = "VCIQ/VCIQ.github.io"
RESERVATION = BRANCH_PREFIX + "reservation"
MAX_DATA_BYTES = 8 * 1024 * 1024
MAX_API_BYTES = 24 * 1024 * 1024
MAX_PAGE = 20


class HandoffError(ValueError):
    """Fixed code only; never interpolate response bodies or credentials."""


def _sha(value: object) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise HandoffError("HANDOFF_SHA_INVALID")
    return value


def _ref(value: object) -> str:
    if (not isinstance(value, str) or not value.startswith(BRANCH_PREFIX)
        or len(value) > 160 or not re.fullmatch(r"[a-z0-9/_-]+", value)):
        raise HandoffError("HANDOFF_REF_INVALID")
    return value


@dataclass(frozen=True)
class Snapshot:
    base_sha: str
    files: dict[str, str]

    def __post_init__(self):
        _sha(self.base_sha)
        if not self.files or set(self.files) - ALLOWED_FILES:
            raise HandoffError("HANDOFF_FILES_INVALID")
        for path, content in self.files.items():
            if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_DATA_BYTES:
                raise HandoffError("HANDOFF_DATA_INVALID")
            def unique_pairs(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise HandoffError("HANDOFF_DUPLICATE_JSON_KEYS")
                    result[key] = value
                return result
            def reject_constant(_):
                raise HandoffError("HANDOFF_NONFINITE_JSON")
            try:
                decoded = json.loads(content, object_pairs_hook=unique_pairs,
                                     parse_constant=reject_constant)
            except HandoffError:
                raise
            except (ValueError, RecursionError):
                raise HandoffError("HANDOFF_DATA_INVALID") from None
            if not isinstance(decoded, dict):
                raise HandoffError("HANDOFF_DATA_INVALID")


class DetachedWorkspace:
    """Reads staged output only; requires an isolated clean-at-HEAD checkout."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _git(self, *args: str) -> bytes:
        try:
            p = subprocess.run(
                ["git", *args], cwd=self.root, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, timeout=15, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise HandoffError("HANDOFF_LOCAL_GIT_UNAVAILABLE") from None
        if p.returncode or len(p.stdout) > MAX_API_BYTES:
            raise HandoffError("HANDOFF_LOCAL_GIT_UNAVAILABLE")
        return p.stdout

    def snapshot(self) -> Snapshot | None:
        if self.root.is_symlink() or not self.root.is_dir():
            raise HandoffError("HANDOFF_LOCAL_ROOT_UNSAFE")
        remote = self._git("remote", "get-url", "origin").decode("utf-8").strip()
        if remote not in (
            "https://github.com/VCIQ/VCIQ.github.io.git",
            "https://github.com/VCIQ/VCIQ.github.io",
            "git@github.com:VCIQ/VCIQ.github.io.git",
        ):
            raise HandoffError("HANDOFF_ORIGIN_UNEXPECTED")
        # Prevent accidental edits of the operator's main or any shared branch.
        try:
            detached = subprocess.run(
                ["git", "symbolic-ref", "--quiet", "HEAD"], cwd=self.root,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=15, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise HandoffError("HANDOFF_LOCAL_GIT_UNAVAILABLE") from None
        if detached.returncode != 1:
            raise HandoffError("HANDOFF_DETACHED_HEAD_REQUIRED")
        head = _sha(self._git("rev-parse", "HEAD").decode("ascii").strip())
        status = self._git("status", "--porcelain=v1", "-z", "--untracked-files=all")
        entries = [entry for entry in status.split(b"\x00") if entry]
        if len(entries) > len(ALLOWED_FILES):
            raise HandoffError("HANDOFF_LOCAL_DIFF_UNEXPECTED")
        files = {}
        for entry in entries:
            if not entry.startswith(b" M "):
                raise HandoffError("HANDOFF_LOCAL_DIFF_UNEXPECTED")
            try:
                name = entry[3:].decode("utf-8", errors="strict")
            except UnicodeError:
                raise HandoffError("HANDOFF_LOCAL_DIFF_UNEXPECTED") from None
            if name not in ALLOWED_FILES or name in files:
                raise HandoffError("HANDOFF_LOCAL_DIFF_UNEXPECTED")
            path = self.root / name
            if (path.is_symlink() or any(
                parent.is_symlink() for parent in (path.parent, path.parent.parent)
            )):
                raise HandoffError("HANDOFF_LOCAL_DATA_UNSAFE")
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_size > MAX_DATA_BYTES):
                raise HandoffError("HANDOFF_LOCAL_DATA_UNSAFE")
            try:
                files[name] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                raise HandoffError("HANDOFF_LOCAL_DATA_UNSAFE") from None
        return Snapshot(head, files) if files else None


class GitHubCli:
    """GitHub REST through gh; bounded, redacted, no shell or auto-retries."""

    def __init__(self, token_kind: str = "GITHUB_TOKEN"):
        if token_kind not in ("GITHUB_TOKEN", "GITHUB_APP"):
            raise HandoffError("HANDOFF_TOKEN_KIND_INVALID")
        if not os.environ.get("GH_TOKEN"):
            raise HandoffError("HANDOFF_TOKEN_UNAVAILABLE")
        self.token_kind = token_kind

    def _api(self, endpoint: str, payload: dict | None = None):
        if not endpoint.startswith("repos/VCIQ/VCIQ.github.io/"):
            raise HandoffError("HANDOFF_API_PATH_INVALID")
        args = ["gh", "api", "-H", "Accept: application/vnd.github+json"]
        stdin = None
        if payload is not None:
            args += ["--method", "POST", "--input", "-"]
            stdin = json.dumps(payload, separators=(",", ":"))
        args.append(endpoint)
        try:
            result = subprocess.run(args, input=stdin, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise HandoffError("HANDOFF_GITHUB_UNAVAILABLE") from None
        if result.returncode or len(result.stdout) > MAX_API_BYTES:
            raise HandoffError("HANDOFF_GITHUB_UNAVAILABLE")
        try:
            return json.loads(result.stdout)
        except (ValueError, RecursionError):
            raise HandoffError("HANDOFF_GITHUB_RESPONSE_INVALID") from None

    def main_sha(self) -> str:
        data = self._api(f"repos/{REPOSITORY}/branches/main")
        if not isinstance(data, dict) or data.get("name") != "main":
            raise HandoffError("HANDOFF_MAIN_RESPONSE_INVALID")
        commit = data.get("commit")
        return _sha(commit.get("sha") if isinstance(commit, dict) else None)

    def _all_pages(self, path: str) -> list[dict]:
        rows = []
        for page in range(1, MAX_PAGE + 1):
            separator = "&" if "?" in path else "?"
            results = self._api(f"repos/{REPOSITORY}/{path}{separator}per_page=100&page={page}")
            if not isinstance(results, list) or len(results) > 100 or any(
                not isinstance(item, dict) for item in results
            ):
                raise HandoffError("HANDOFF_INVENTORY_INVALID")
            rows.extend(results)
            if len(results) < 100:
                return rows
        raise HandoffError("HANDOFF_INVENTORY_INCOMPLETE")

    def open_proposals(self) -> list[str]:
        records = self._all_pages("pulls?state=open")
        result = []
        for item in records:
            head = item.get("head")
            if not isinstance(head, dict) or not isinstance(head.get("ref"), str):
                raise HandoffError("HANDOFF_INVENTORY_INVALID")
            if head["ref"].startswith(BRANCH_PREFIX):
                result.append(_ref(head["ref"]))
        return sorted(set(result))

    def candidate_branches(self) -> list[str]:
        records = self._all_pages("branches")
        result = []
        for item in records:
            value = item.get("name")
            if not isinstance(value, str):
                raise HandoffError("HANDOFF_INVENTORY_INVALID")
            if value.startswith(BRANCH_PREFIX):
                result.append(_ref(value))
        return sorted(set(result))

    def create_ref(self, branch: str, sha: str) -> None:
        branch = _ref(branch)
        sha = _sha(sha)
        expected = "refs/heads/" + branch
        record = self._api(f"repos/{REPOSITORY}/git/refs", {"ref": expected, "sha": sha})
        if (not isinstance(record, dict) or record.get("ref") != expected
            or not isinstance(record.get("object"), dict)
            or record["object"].get("sha") != sha):
            raise HandoffError("HANDOFF_REF_CREATE_UNCONFIRMED")

    def create_commit(self, base: str, files: dict[str, str], run_id: str, attempt: int) -> str:
        base = _sha(base)
        source = self._api(f"repos/{REPOSITORY}/git/commits/{base}")
        if not isinstance(source, dict) or source.get("sha") != base:
            raise HandoffError("HANDOFF_BASE_COMMIT_INVALID")
        original_tree = source.get("tree")
        base_tree = _sha(original_tree.get("sha") if isinstance(original_tree, dict) else None)
        result = self._api(f"repos/{REPOSITORY}/git/trees", {
            "base_tree": base_tree,
            "tree": [{"path": name, "mode": "100644", "type": "blob", "content": files[name]}
                     for name in sorted(files)],
        })
        tree = _sha(result.get("sha") if isinstance(result, dict) else None)
        commit = self._api(f"repos/{REPOSITORY}/git/commits", {
            "message": f"data: propose company profile refresh run {run_id} attempt {attempt}",
            "tree": tree, "parents": [base],
        })
        return _sha(commit.get("sha") if isinstance(commit, dict) else None)

    def create_draft_pr(self, branch: str, commit: str, run_id: str) -> int:
        branch, commit = _ref(branch), _sha(commit)
        data = self._api(f"repos/{REPOSITORY}/pulls", {
            "title": f"data: review company-profile refresh run {run_id}",
            "head": branch, "base": "main", "draft": True,
            "maintainer_can_modify": False,
            "body": "Automated candidate; human review required. No merge, publication or Pages dispatch authorized. Related: #664.",
        })
        self._assert_pr(data, branch, commit)
        number = data.get("number")
        if type(number) is not int or not 1 <= number <= 1_000_000_000:
            raise HandoffError("HANDOFF_PR_UNCONFIRMED")
        return number

    @staticmethod
    def _assert_pr(value: object, branch: str, sha: str) -> None:
        head = value.get("head") if isinstance(value, dict) else None
        base = value.get("base") if isinstance(value, dict) else None
        if (not isinstance(value, dict) or value.get("draft") is not True
            or value.get("state") != "open" or value.get("merged_at") is not None
            or not isinstance(head, dict) or not isinstance(base, dict)
            or head.get("ref") != branch or head.get("sha") != sha
            or base.get("ref") != "main"
            or not isinstance(head.get("repo"), dict)
            or not isinstance(base.get("repo"), dict)
            or head["repo"].get("full_name") != REPOSITORY
            or base["repo"].get("full_name") != REPOSITORY):
            raise HandoffError("HANDOFF_PR_UNCONFIRMED")

    def verify_pr(self, number: int, branch: str, commit: str) -> None:
        value = self._api(f"repos/{REPOSITORY}/pulls/{number}")
        self._assert_pr(value, branch, commit)


def submit(workspace, github, *, run_id: str, attempt: int,
           authorized: bool = False) -> dict:
    """Create only a new reservation ref, a new candidate ref, and a Draft PR.

    Ambiguous failures are not retried. Once reservation creation is attempted,
    the reservation and candidate state require human triage (including after
    a successful Draft PR); this prevents silent repeated scheduled crawls.
    """
    if authorized is not True:
        raise HandoffError("HANDOFF_EXPLICIT_APPROVAL_REQUIRED")
    # GitHub credentials must not be used from the privileged MCP service.
    # Its HOME/auth store differs from the ordinary Mac desktop operator.
    if (isinstance(github, GitHubCli) and os.name == "posix"
        and os.geteuid() == 0):
        raise HandoffError("HANDOFF_UNPRIVILEGED_OPERATOR_REQUIRED")
    stage = "preflight"
    mutation_attempted = False
    try:
        prepared = workspace.snapshot()
        if prepared is None:
            return {"decision": "no_changes", "remoteWritesAttempted": False}
        first_main = github.main_sha()
        open_heads = github.open_proposals()
        remote_branches = github.candidate_branches()
        plan = decide({
            "schemaVersion": 1, "repository": REPOSITORY, "baseBranch": "main",
            "sourceHeadSha": prepared.base_sha, "observedMainSha": first_main,
            "runId": run_id, "runAttempt": attempt,
            "changedPaths": sorted(prepared.files), "openProposalHeads": open_heads,
            "knownRemoteBranches": remote_branches, "inventoryComplete": True,
            "tokenKind": github.token_kind,
        })
        if plan["decision"] != "would_prepare_draft_pr":
            return {"decision": plan["decision"], "remoteWritesAttempted": False}
        branch = _ref(plan["candidateBranch"])
        # Atomic reservation: create_ref must refuse an already-existing ref.
        # Keep this ref until a separate reviewer triages/cleans it up.
        stage = "reserve"
        mutation_attempted = True
        github.create_ref(RESERVATION, first_main)
        stage = "recheck"
        if github.main_sha() != first_main or github.open_proposals() or github.candidate_branches() != [RESERVATION]:
            raise HandoffError("HANDOFF_RACE_DETECTED")
        stage = "commit"
        commit = _sha(github.create_commit(first_main, prepared.files, run_id, attempt))
        if commit == first_main:
            raise HandoffError("HANDOFF_EMPTY_COMMIT")
        if github.main_sha() != first_main:
            raise HandoffError("HANDOFF_MAIN_ADVANCED")
        stage = "candidate"
        github.create_ref(branch, commit)
        # Close the window between candidate ref creation and PR creation.
        # A concurrent proposal or new candidate remains a manual-triage case.
        stage = "preproposal"
        if (github.main_sha() != first_main or github.open_proposals()
            or github.candidate_branches() != sorted([RESERVATION, branch])):
            raise HandoffError("HANDOFF_RACE_DETECTED")
        stage = "proposal"
        number = github.create_draft_pr(branch, commit, run_id)
        stage = "verify"
        github.verify_pr(number, branch, commit)
        fresh = github.main_sha() == first_main
        return {
            "decision": "draft_pr_opened" if fresh else "draft_pr_opened_main_advanced",
            "prNumber": number, "candidateBranch": branch, "candidateSha": commit,
            "reservationCleanupRequiresHuman": True, "humanReviewRequired": True,
            "ciChecksVerified": False, "merged": False, "published": False,
            "remoteWritesAttempted": True,
        }
    except (GateError, HandoffError, OSError, UnicodeError, ValueError, TypeError, RecursionError):
        return {
            "decision": "blocked", "stage": stage,
            "errorCode": "HANDOFF_FAILED_CLOSED",
            "remoteWritesAttempted": mutation_attempted,
            "manualTriageRequired": mutation_attempted,
            "merged": False, "published": False,
        }
