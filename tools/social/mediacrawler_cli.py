"""Explicit XHS shadow execution and manual session setup, never production writes."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from .contracts import ContractError, load_json, validate
from .guard import GuardError, assert_unchanged, output_path, protected_snapshot, runtime_paths
from .planning_cli import ROOT, _add_inputs, _inputs, revision
from .policy import activation, load_policy
from .scheduler_state import SchedulerStore
from .worker import execute_job, bootstrap_session, preflight
from workers.mediacrawler.upstream import UpstreamError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run-mediacrawler")
    _add_inputs(run)
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--vciq-commit")
    setup = sub.add_parser("bootstrap-session")
    _add_inputs(setup)
    setup.add_argument("--interactive", action="store_true", required=True)
    resume = sub.add_parser("resume-platform")
    _add_inputs(resume)
    resume.add_argument("--confirmed", action="store_true", required=True)
    for item in (run, setup, resume):
        item.add_argument("--platform", choices=["xhs"], default="xhs")
        item.add_argument("--runtime-config", type=Path, required=True)
        item.add_argument("--python", type=Path)
        item.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    before, started = None, False
    try:
        policy = load_policy(args.policy)
        runtime = validate(load_json(args.runtime_config), expected_kind="runtime_config")
        if activation(policy, runtime, live=args.live, implemented=frozenset({"xhs"}))["xhs"] != "eligible":
            raise ContractError("live_activation_required")
        root = runtime_paths(runtime, repo_root=ROOT, runtime_file=args.runtime_config)
        if root != args.state_dir.absolute():
            raise GuardError("state_directory_mismatch")
        before = protected_snapshot(ROOT)
        if args.command == "bootstrap-session":
            started = True
            result = bootstrap_session(runtime=runtime, policy=policy, runtime_file=args.runtime_config,
                live=args.live, interactive=args.interactive, python_executable=args.python)
        else:
            state, upstream, _, lock = preflight(runtime, policy, runtime_file=args.runtime_config,
                live=args.live, python_executable=args.python)
            roots = (ROOT, upstream)
            if args.command == "resume-platform":
                with SchedulerStore(state, repo_roots=roots) as store:
                    store.resume("xhs", datetime.now(UTC))
                result = {"ok": True, "resumeRequested": True, "liveExecuted": False}
            else:
                relative = args.plan.resolve(strict=True).relative_to(state).as_posix()
                if output_path(state, relative, repo_roots=roots) != args.plan.absolute():
                    raise GuardError("unsafe_input_path")
                plan = validate(load_json(args.plan), expected_kind="job_plan")
                policy, registry, config_hash = _inputs(args, ("xhs",), ("sogou-weixin",))
                commit = args.vciq_commit or revision(ROOT)
                if plan["configHash"] != config_hash or plan["vciqCommit"] != commit:
                    raise ContractError("stale_plan")
                if len(plan["jobs"]) > policy["budget"]["jobsPerPlatformPerRun"]:
                    raise ContractError("plan_budget_exceeded")
                contexts = registry.by_id()
                for job in plan["jobs"]:
                    entry = contexts.get(job["queryId"])
                    if job["platform"] != "xhs" or not entry or entry["excludedReason"] or entry["query"] != job["query"] or entry["trackRefs"] != job["trackRefs"]:
                        raise ContractError("stale_query_plan")
                    budget = policy["budget"]
                    if job["limits"] != {"maxSearchPages": budget["pagesPerJob"], "maxRecords": budget["recordsPerJob"], "maxWallSeconds": budget["wallSecondsPerJob"]}:
                        raise ContractError("job_budget_mismatch")
                    if job["vciqCommit"] != commit or job["configHash"] != config_hash or job["upstreamCommit"] != lock["commit"] or job["policyVersion"] != policy["policyVersion"]:
                        raise ContractError("job_plan_mismatch")
                summaries = []
                with SchedulerStore(state, repo_roots=roots) as store:
                    store.sync(registry)
                    for job in plan["jobs"]:
                        if not store.claim(job, datetime.now(UTC)):
                            summaries.append({"queryId": job["queryId"], "status": "not_started"})
                            continue
                        started = True
                        execution = execute_job(job, contexts[job["queryId"]], runtime=runtime, policy=policy,
                            runtime_file=args.runtime_config, live=args.live, python_executable=args.python)
                        store.finish(job, execution, datetime.now(UTC), cadence_hours=policy["cadenceHours"][contexts[job["queryId"]]["priority"]])
                        summaries.append({"queryId": job["queryId"], "status": execution["receipt"]["status"], "counts": execution["receipt"]["counts"]})
                result = {"ok": all(item["status"] in {"ok", "empty", "not_started"} for item in summaries),
                    "jobs": summaries, "liveExecuted": started, "batchIntegrityChecked": False}
        assert_unchanged(before, repo_root=ROOT)
        print(json.dumps({"mode": "shadow", "publish": False, **result}, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("ok") else 1
    except (ContractError, GuardError) as exc:
        code = exc.code
    except UpstreamError:
        code = "upstream_preflight_failed"
    except Exception:
        code = "input_or_execution_error"
    if before is not None:
        try:
            assert_unchanged(before, repo_root=ROOT)
        except GuardError:
            code = "production_modified"
    print(json.dumps({"ok": False, "error": code, "liveExecuted": started}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
