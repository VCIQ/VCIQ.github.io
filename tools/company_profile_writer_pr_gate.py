"""Pure, fail-closed proposal gate for a future company-profile writer PR pilot.

This module deliberately cannot create branches, open PRs, start crawlers,
update queue records or dispatch GitHub Actions. It consumes an explicit,
complete *synthetic or separately verified* inventory and returns a bounded
decision. No import-time I/O or platform/network access.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

BRANCH_PREFIX = "automation/company-profile-refresh/"
SMOKE_BASE_BRANCH = "codex/writer-token-smoke-base-20261108"
SMOKE_BRANCH_PREFIX = "automation/company-profile-refresh-smoke/"
BASE_BRANCH_PREFIXES = {
    "main": BRANCH_PREFIX,
    SMOKE_BASE_BRANCH: SMOKE_BRANCH_PREFIX,
}
ALLOWED_FILES = frozenset({
    "public/data/company_profile_refresh_queue.json",
    "public/data/venture_profiles.json",
})
SHA = re.compile(r"[0-9a-f]{40}\Z")
RUN = re.compile(r"[1-9][0-9]{0,19}\Z")
EXPECTED_KEYS = frozenset({
    "schemaVersion", "repository", "baseBranch", "sourceHeadSha",
    "observedMainSha", "runId", "runAttempt", "changedPaths",
    "openProposalHeads", "knownRemoteBranches", "inventoryComplete",
    "tokenKind",
})


class GateError(ValueError):
    """Fixed codes only. Do not propagate raw input, paths, tokens or APIs."""


def _names(values: object, code: str) -> list[str]:
    if (not isinstance(values, list) or len(values) > 500
        or any(not isinstance(value, str) or len(value) > 255 for value in values)):
        raise GateError(code)
    if len(values) != len(set(values)):
        raise GateError(code)
    return values


def decide(payload: object) -> dict:
    """Return a non-executable plan. The caller must never treat it as approval."""
    if (not isinstance(payload, dict) or set(payload) != EXPECTED_KEYS
        or type(payload.get("schemaVersion")) is not int
        or payload["schemaVersion"] != 1):
        raise GateError("WRITER_GATE_INPUT_INVALID")
    base_branch = payload["baseBranch"]
    if (payload["repository"] != "VCIQ/VCIQ.github.io"
        or base_branch not in BASE_BRANCH_PREFIXES):
        raise GateError("WRITER_GATE_REPOSITORY_INVALID")
    branch_prefix = BASE_BRANCH_PREFIXES[base_branch]
    if (not isinstance(payload["sourceHeadSha"], str)
        or not SHA.fullmatch(payload["sourceHeadSha"])
        or not isinstance(payload["observedMainSha"], str)
        or not SHA.fullmatch(payload["observedMainSha"])):
        raise GateError("WRITER_GATE_SHA_INVALID")
    if (not isinstance(payload["runId"], str) or not RUN.fullmatch(payload["runId"])
        or type(payload["runAttempt"]) is not int
        or not 1 <= payload["runAttempt"] <= 20):
        raise GateError("WRITER_GATE_RUN_INVALID")
    if type(payload["inventoryComplete"]) is not bool or payload["inventoryComplete"] is not True:
        raise GateError("WRITER_GATE_INVENTORY_UNVERIFIED")
    if payload["tokenKind"] not in ("GITHUB_TOKEN", "GITHUB_APP"):
        raise GateError("WRITER_GATE_TOKEN_UNSUPPORTED")

    changed = _names(payload["changedPaths"], "WRITER_GATE_CHANGED_PATHS_INVALID")
    if set(changed) - ALLOWED_FILES:
        raise GateError("WRITER_GATE_UNEXPECTED_FILES")
    proposed = _names(payload["openProposalHeads"], "WRITER_GATE_OPEN_PRS_INVALID")
    branches = _names(payload["knownRemoteBranches"], "WRITER_GATE_BRANCHES_INVALID")
    if any(not name.startswith(branch_prefix) for name in proposed):
        raise GateError("WRITER_GATE_OPEN_PRS_INVALID")
    if any(not name.startswith(branch_prefix) for name in branches):
        raise GateError("WRITER_GATE_BRANCHES_INVALID")

    branch = (branch_prefix + "run-" + payload["runId"] +
              "-attempt-" + str(payload["runAttempt"]))
    common = {
        "schemaVersion": 1,
        "automaticMerge": False,
        "productionWrites": False,
        "crawlerLaunched": False,
        "simulatedOnly": True,
        "humanApprovalRequired": True,
    }
    if proposed:
        return {**common, "decision": "blocked_open_proposal"}
    # A leftover branch from any attempt is an operator-triage condition.
    # Do not create a fresh candidate until its disposition is known.
    if branches:
        return {**common, "decision": "blocked_existing_branch"}
    if payload["sourceHeadSha"] != payload["observedMainSha"]:
        return {**common, "decision": "blocked_stale_main"}
    if not changed:
        return {**common, "decision": "no_changes"}
    return {
        **common,
        "decision": "would_prepare_draft_pr",
        "candidateBranch": branch,
        "baseBranch": base_branch,
        "baseSha": payload["sourceHeadSha"],
        "allowlistedPaths": sorted(changed),
        "ciWorkflowApproval": (
            "manual_required_for_GITHUB_TOKEN_created_PR"
            if payload["tokenKind"] == "GITHUB_TOKEN"
            else "verify_actual_check_runs"
        ),
        "approvalGateVerified": False,
        "handoffExecuted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdin-json", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.read(16 * 1024 + 1)
        if len(raw) > 16 * 1024:
            raise GateError("WRITER_GATE_INPUT_SIZE")
        result = decide(json.loads(raw))
    except (GateError, ValueError, TypeError, RecursionError):
        # Never print untrusted input or exception details.
        result = {"schemaVersion": 1, "decision": "blocked",
                  "errorCode": "WRITER_GATE_REJECTED", "simulatedOnly": True}
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
