"""Explicit MediaCrawler commands. No credentials, browser or network in doctor."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .contracts import ContractError, digest, load_json, query_id, validate
from .guard import GuardError, assert_unchanged, output_path, protected_snapshot, runtime_paths
from .planning_cli import ROOT, revision
from .policy import DEFAULT_POLICY, load_policy
from .query_registry import build_query_registry
from .scheduler_state import SchedulerStore
from .worker import ADAPTERS, execute_job, verify_upstream
from .wechat_runner import atomic_json


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("run", "bootstrap-session", "worker-doctor", "resume-platform"))
    p.add_argument("--runtime-config", type=Path, required=True)
    p.add_argument("--state-dir", type=Path, required=True)
    p.add_argument("--platform", choices=tuple(ADAPTERS), default="xhs")
    p.add_argument("--job", type=Path)
    p.add_argument("--config", type=Path, default=ROOT / "config/user_tracking.json")
    p.add_argument("--accounts", type=Path, default=ROOT / "config/wechat_sources.json")
    p.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    p.add_argument("--live", action="store_true")
    p.add_argument("--interactive", action="store_true")
    p.add_argument("--confirmed", action="store_true")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    before = protected_snapshot(ROOT)
    live_started = False
    try:
        runtime = validate(load_json(args.runtime_config), expected_kind="runtime_config")
        root = runtime_paths(runtime, repo_root=ROOT, runtime_file=args.runtime_config)
        if root != args.state_dir.absolute():
            raise GuardError("state_directory_mismatch")
        if not runtime["mediacrawlerDir"]:
            raise ContractError("upstream_directory_required")
        roots = (ROOT, Path(runtime["mediacrawlerDir"]))
        policy = load_policy(args.policy)
        if args.command == "worker-doctor":
            checked = verify_upstream(runtime["mediacrawlerDir"])
            result = {"ok": True, "implementedPlatforms": sorted(ADAPTERS), "upstreamCommit": checked["commit"],
                      "browserSession": "not_checked", "liveExecuted": False, "writesPerformed": False}
        else:
            if not runtime["enabled"] or not runtime["platforms"][args.platform]["enabled"]:
                raise ContractError("live_activation_required")
            if args.command == "resume-platform":
                if not args.confirmed:
                    raise ContractError("resume_confirmation_required")
                with SchedulerStore(root, repo_roots=roots) as store:
                    store.resume(args.platform, datetime.now(UTC))
                result = {"ok": True, "liveExecuted": False, "resumed": args.platform}
            elif args.command == "bootstrap-session":
                if not args.live or not args.interactive or not runtime["interactiveAuthAllowed"]:
                    raise ContractError("interactive_auth_not_allowed")
                # Synthetic identity for an explicit login-only operation. It is
                # never stored as a query receipt or counted toward coverage.
                job = {"schemaVersion": 1, "kind": "crawl_job", "platform": args.platform,
                    "provider": "mediacrawler", "engine": "mediacrawler", "operation": "search", "mode": "shadow",
                    "query": {"text": "session-bootstrap", "scope": "track", "targetId": None, "termRefs": ["session-bootstrap"], "providerFilters": {}},
                    "trackRefs": ["session-bootstrap"], "runId": str(uuid4()), "attemptId": str(uuid4()),
                    "window": {"from": None, "to": None, "filterMode": "none"},
                    "limits": {"maxSearchPages": 1, "maxRecords": 1, "maxWallSeconds": policy["budget"]["wallSecondsPerJob"]},
                    "vciqCommit": revision(ROOT), "configHash": digest(policy), "policyVersion": policy["policyVersion"],
                    "upstreamCommit": load_json(ROOT / "workers/mediacrawler/upstream.lock.json")["commit"]}
                job["queryId"] = query_id(job)
                job["jobId"] = digest({"queryId": job["queryId"], "operation": "search"})
                live_started = True
                session = execute_job(job, runtime, live=True, interactive=True)
                result = {"ok": session.get("sessionStatus") == "ready", "session": session,
                          "liveExecuted": True, "queryCoverageAdvanced": False}
            else:
                if not args.live or args.interactive or args.job is None:
                    raise ContractError("live_activation_required")
                relative = args.job.absolute().relative_to(root).as_posix()
                output_path(root, relative, repo_roots=roots)
                job = validate(load_json(args.job), expected_kind="crawl_job")
                if job["platform"] != args.platform:
                    raise ContractError("job_platform_mismatch")
                tracking, accounts = load_json(args.config), load_json(args.accounts)
                config_hash = digest({"tracking": tracking, "policy": policy, "accounts": accounts})
                registry = build_query_registry(tracking, policy, platforms=(args.platform,), accounts=accounts)
                entry = registry.by_id().get(job["queryId"])
                if entry is None or entry["excludedReason"] or entry["query"] != job["query"] or entry["trackRefs"] != job["trackRefs"]:
                    raise ContractError("stale_query_plan")
                if job["configHash"] != config_hash or job["vciqCommit"] != revision(ROOT) or job["policyVersion"] != policy["policyVersion"]:
                    raise ContractError("stale_plan")
                limits = policy["budget"]
                if job["limits"] != {"maxSearchPages": limits["pagesPerJob"], "maxRecords": limits["recordsPerJob"], "maxWallSeconds": limits["wallSecondsPerJob"]}:
                    raise ContractError("job_budget_mismatch")
                verify_upstream(runtime["mediacrawlerDir"])
                with SchedulerStore(root, repo_roots=roots) as store:
                    store.sync(registry)
                    if not store.claim(job, datetime.now(UTC)):
                        result = {"ok": True, "status": "not_started", "liveExecuted": False}
                    else:
                        live_started = True
                        try:
                            execution = execute_job(job, runtime, live=True, terms=[term["text"] for term in entry["terms"]])
                        except Exception:
                            from .worker import failed_result
                            execution = failed_result(job, "schema_error", "WORKER_CONTROLLER_ERROR")
                        store.finish(job, execution, datetime.now(UTC), cadence_hours=policy["cadenceHours"][entry["priority"]])
                        atomic_json(root, f'pending/{job["attemptId"]}.json', execution, roots=roots)
                        result = {"ok": execution["receipt"]["status"] in {"ok", "empty"}, "receipt": execution["receipt"],
                                  "liveExecuted": True, "batchIntegrityChecked": False}
        assert_unchanged(before, repo_root=ROOT)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["ok"] else 1
    except (ContractError, GuardError) as exc:
        code = exc.code
    except Exception:
        code = "worker_input_or_execution_error"
    try:
        assert_unchanged(before, repo_root=ROOT)
    except GuardError:
        code = "production_modified"
    print(json.dumps({"ok": False, "error": code, "liveExecuted": live_started}), file=sys.stderr)
    return 2
