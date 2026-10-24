"""PR-02 commands, isolated from production commands and output directories."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from .contracts import ContractError, digest, load_json, validate
from .guard import GuardError, assert_unchanged, output_path, protected_snapshot, runtime_paths, state_path
from .policy import DEFAULT_POLICY, activation, load_policy
from .query_registry import build_query_registry
from .scheduler import instant, plan_jobs
from .scheduler_state import SchedulerStore, read_state

ROOT = Path(__file__).resolve().parents[2]


def revision(root: Path) -> str:
    """Read Git metadata only. No git subprocess or automatic repository update."""
    directory = root / ".git"
    if directory.is_file():
        value = directory.read_text(encoding="utf-8").strip()
        if not value.startswith("gitdir: "):
            raise ContractError("commit_required")
        directory = (root / value[8:]).resolve()
    try:
        value = (directory / "HEAD").read_text(encoding="utf-8").strip()
        if value.startswith("ref: "):
            ref = value[5:]
            if not re.fullmatch(r"refs/[A-Za-z0-9_./-]+", ref) or ".." in ref.split("/"):
                raise ContractError("invalid_git_reference")
            roots = [directory]
            common = directory / "commondir"
            if common.exists():
                roots.append((directory / common.read_text().strip()).resolve())
            found = None
            for item in roots:
                if (item / ref).is_file():
                    found = (item / ref).read_text().strip()
                    break
                if (item / "packed-refs").exists():
                    for line in (item / "packed-refs").read_text().splitlines():
                        if line.endswith(" " + ref):
                            found = line.split()[0]
            value = found or ""
        if re.fullmatch(r"[0-9a-f]{40}", value):
            return value
    except OSError:
        pass
    raise ContractError("commit_required")


def _inputs(args, platforms=None, providers=None):
    policy = load_policy(args.policy)
    tracking = load_json(args.config)
    accounts = load_json(args.accounts) if args.accounts else {"accounts": []}
    selected = tuple(platforms or args.platform or ("wechat",))
    sources = tuple(providers or args.wechat_provider or ("sogou-weixin",))
    registry = build_query_registry(tracking, policy, platforms=selected, providers=sources, accounts=accounts)
    config_hash = digest({"tracking": tracking, "policy": policy, "accounts": accounts})
    return policy, registry, config_hash


def _add_inputs(parser):
    parser.add_argument("--config", type=Path, default=ROOT / "config/user_tracking.json")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--accounts", type=Path, default=ROOT / "config/wechat_sources.json")
    parser.add_argument("--state-dir", type=Path, required=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    _add_inputs(plan)
    plan.add_argument("--platform", action="append", choices=("wechat", "xhs", "wb", "bili", "zhihu"))
    plan.add_argument("--wechat-provider", action="append", choices=("sogou-weixin", "bing-rss"))
    plan.add_argument("--dry-run", action="store_true")
    plan.add_argument("--output", help="Explicit path relative to state-dir; incompatible with --dry-run")
    plan.add_argument("--vciq-commit")
    coverage = sub.add_parser("coverage")
    _add_inputs(coverage)
    coverage.add_argument("--platform", action="append", choices=("wechat", "xhs", "wb", "bili", "zhihu"))
    coverage.add_argument("--wechat-provider", action="append", choices=("sogou-weixin", "bing-rss"))
    run = sub.add_parser("run-wechat")
    _add_inputs(run)
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--runtime-config", type=Path, required=True)
    run.add_argument("--budget-file", type=Path, required=True)
    run.add_argument("--live", action="store_true")
    run.add_argument("--vciq-commit")
    resume = sub.add_parser("resume-wechat")
    resume.add_argument("--state-dir", type=Path, required=True)
    resume.add_argument("--runtime-config", type=Path, required=True)
    resume.add_argument("--confirmed", action="store_true", required=True)
    args = parser.parse_args(argv)
    before = None
    live_started = False
    try:
        root = state_path(args.state_dir, repo_roots=(ROOT,))
        before = protected_snapshot(ROOT)
        now = datetime.now(UTC)
        if args.command in {"plan", "coverage"}:
            policy, registry, config_hash = _inputs(args)
            snapshot = read_state(root, repo_roots=(ROOT,))
            if args.command == "plan":
                if args.dry_run and args.output:
                    raise ContractError("dry_run_cannot_write")
                commit = args.vciq_commit or revision(ROOT)
                upstream = load_json(ROOT / "workers/mediacrawler/upstream.lock.json")["commit"]
                result = plan_jobs(registry, snapshot, now, policy, vciq_commit=commit,
                                   config_hash=config_hash, upstream_commit=upstream)
                if args.output:
                    from .wechat_runner import atomic_json
                    atomic_json(root, args.output, result, roots=(ROOT,))
            else:
                counts = Counter(entry["excludedReason"] for entry in registry.entries if entry["excludedReason"])
                active = [entry for entry in registry.entries if not entry["excludedReason"]]
                result = {"registeredQueries": len(registry.entries), "eligibleQueries": len(active),
                    "excluded": dict(counts), "coveredEver": sum(bool(snapshot["queries"].get(entry["queryId"], {}).get("lastCoveredAt")) for entry in active),
                    "platforms": snapshot["platforms"], "liveExecuted": False, "writesPerformed": False}
        else:
            runtime = validate(load_json(args.runtime_config), expected_kind="runtime_config")
            runtime_root = runtime_paths(runtime, repo_root=ROOT, runtime_file=args.runtime_config)
            if runtime_root != root:
                raise GuardError("state_directory_mismatch")
            roots = (ROOT, *([Path(runtime["mediacrawlerDir"])] if runtime["mediacrawlerDir"] else []))
            if args.command == "resume-wechat":
                if not runtime["enabled"] or not runtime["platforms"]["wechat"]["enabled"]:
                    raise ContractError("platform_disabled")
                with SchedulerStore(root, repo_roots=roots) as store:
                    store.resume("wechat", now)
                result = {"ok": True, "platform": "wechat", "liveExecuted": False, "resumeRequested": True}
            else:
                selected_plan = validate(load_json(args.plan), expected_kind="job_plan")
                if any(job["platform"] != "wechat" for job in selected_plan["jobs"]):
                    raise ContractError("wechat_plan_required")
                providers = tuple(sorted({job["provider"] for job in selected_plan["jobs"]})) or ("sogou-weixin",)
                policy, registry, config_hash = _inputs(args, ("wechat",), providers)
                if activation(policy, runtime, live=args.live, implemented=frozenset({"wechat"}))["wechat"] != "eligible":
                    raise ContractError("live_activation_required")
                if selected_plan["configHash"] != config_hash or selected_plan["vciqCommit"] != (args.vciq_commit or revision(ROOT)):
                    raise ContractError("stale_plan")
                if len(selected_plan["jobs"]) > policy["budget"]["jobsPerPlatformPerRun"]:
                    raise ContractError("plan_budget_exceeded")
                for input_file in (args.plan, args.budget_file):
                    relative = input_file.resolve(strict=True).relative_to(root).as_posix()
                    if output_path(root, relative, repo_roots=roots) != input_file.absolute():
                        raise GuardError("unsafe_input_path")
                grant = load_json(args.budget_file)
                contexts = registry.by_id()
                for job in selected_plan["jobs"]:
                    entry = contexts.get(job["queryId"])
                    if entry is None or entry["excludedReason"] or entry["query"] != job["query"] or entry["trackRefs"] != job["trackRefs"]:
                        raise ContractError("stale_query_plan")
                    budget = policy["budget"]
                    if job["limits"] != {"maxSearchPages": budget["pagesPerJob"], "maxRecords": min(6, budget["recordsPerJob"]), "maxWallSeconds": budget["wallSecondsPerJob"]}:
                        raise ContractError("job_budget_mismatch")
                    if job["configHash"] != config_hash or job["vciqCommit"] != selected_plan["vciqCommit"] or job["policyVersion"] != policy["policyVersion"]:
                        raise ContractError("job_plan_mismatch")
                from .wechat_runner import execute_job
                summaries = []
                with SchedulerStore(root, repo_roots=roots) as store:
                    store.sync(registry)
                    for job in selected_plan["jobs"]:
                        if not store.claim(job, datetime.now(UTC)):
                            summaries.append({"queryId": job["queryId"], "status": "not_started"})
                            continue
                        live_started = True
                        execution = execute_job(job, contexts[job["queryId"]], state_dir=root, roots=roots, grant=grant)
                        execution["diagnostics"]["requests"] = store.request_count(job["attemptId"])
                        store.finish(job, execution, datetime.now(UTC), cadence_hours=policy["cadenceHours"][contexts[job["queryId"]]["priority"]])
                        summaries.append({"queryId": job["queryId"], "status": execution["receipt"]["status"],
                                          "counts": execution["receipt"]["counts"]})
                result = {"ok": all(row["status"] in {"ok", "empty", "not_started"} for row in summaries),
                          "mode": "shadow", "publish": False, "liveExecuted": live_started,
                          "batchIntegrityChecked": False, "jobs": summaries}
        assert_unchanged(before, repo_root=ROOT)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("ok", True) else 1
    except (ContractError, GuardError) as exc:
        error = exc.code
    except Exception:
        error = "input_or_execution_error"
    if before is not None:
        try:
            assert_unchanged(before, repo_root=ROOT)
        except GuardError:
            error = "production_modified"
    print(json.dumps({"ok": False, "error": error, "liveExecuted": live_started}), file=sys.stderr)
    return 2
