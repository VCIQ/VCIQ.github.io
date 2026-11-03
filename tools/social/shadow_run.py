"""Explicit shadow orchestration. Recovery never invokes a collector.

The completed subset of a run is frozen once, then sealed/imported/reviewed.
Missing jobs have no invented receipts. A new run cannot overtake unfinished
storage/review work. Existing production jobs and datasets are never called.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from .batch import ROOT, MAX_LINE, build_batch, private_root, read_private, decode, seal_batch
from .contracts import PLATFORMS, ContractError, assert_safe, digest, load_json, validate
from .guard import GuardError, assert_unchanged, output_path, protected_snapshot, runtime_paths
from .planning_cli import _add_inputs, _inputs, revision
from .policy import activation
from .review import ReviewStore
from .review_cli import registry_input
from .scheduler import instant, plan_jobs, utc
from .scheduler_state import SchedulerStore, read_state
from .shadow_state import load, save, run_lock, run_prefix, request_stop, clear_stop, stopped
from .signal_store import SignalStore
from .storage_cli import checkpoint_results, input_json

MAX_RUNS = 1000


def code(exc):
    value = getattr(exc, "code", "shadow_operation_failed")
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,119}", value) else "shadow_operation_failed"


def dispatch(job, context, *, root, roots, runtime, runtime_file, policy, python, grant):
    if job["platform"] == "wechat":
        from .wechat_runner import execute_job
        return execute_job(job, context, state_dir=root, roots=roots, grant=grant, runtime_file=runtime_file)
    from .worker import execute_job
    return execute_job(job, context, runtime=runtime, policy=policy,
        runtime_file=runtime_file, live=True, python_executable=python)


def validate_plan(plan, contexts, policy):
    validate(plan, expected_kind="job_plan")
    validate(policy, expected_kind="discovery_policy")
    jobs = plan["jobs"]
    if not jobs or len(jobs) > 200 or len({j["runId"] for j in jobs}) != 1 or len({j["jobId"] for j in jobs}) != len(jobs):
        raise ContractError("shadow_plan_identity")
    budget = policy["budget"]
    upstream = load_json(ROOT / "workers/mediacrawler/upstream.lock.json")["commit"]
    if any(n > budget["jobsPerPlatformPerRun"] for n in Counter(j["platform"] for j in jobs).values()):
        raise ContractError("shadow_plan_budget")
    if set(contexts) != {j["queryId"] for j in jobs}: raise ContractError("shadow_plan_contexts")
    for job in jobs:
        context = contexts[job["queryId"]]
        limits = {"maxSearchPages": budget["pagesPerJob"], "maxWallSeconds": budget["wallSecondsPerJob"],
            "maxRecords": min(6, budget["recordsPerJob"]) if job["platform"] == "wechat" else budget["recordsPerJob"]}
        if (context["excludedReason"] or context["query"] != job["query"] or context["trackRefs"] != job["trackRefs"]
                or context["platform"] != job["platform"] or context["provider"] != job["provider"]
                or job["limits"] != limits or job["configHash"] != plan["configHash"]
                or job["vciqCommit"] != plan["vciqCommit"] or job["policyVersion"] != policy["policyVersion"]
                or (job["platform"] != "wechat" and job["upstreamCommit"] != upstream)
                or context["priority"] not in policy["cadenceHours"]):
            raise ContractError("shadow_plan_mismatch")


def validate_result(job, result, now):
    if not isinstance(result, dict) or set(result) != {"receipt", "observations", "hints", "diagnostics"}:
        raise ContractError("shadow_result_shape")
    assert_safe(result)
    # Full cross-file checking, not just an exit-code or receipt check.
    build_batch([job], [result["receipt"]], result["observations"], created_at=utc(now))
    return result


class Coordinator:
    def __init__(self, root, roots=(ROOT,), *, executor=None, clock=None, monotonic=None):
        self.roots = tuple(roots)
        self.root = private_root(root, self.roots)
        self.executor = executor or dispatch
        self.clock = clock or (lambda: datetime.now(UTC))
        self.monotonic = monotonic or time.monotonic

    def exists(self, relative):
        return output_path(self.root, relative, repo_roots=self.roots).exists()

    def unfinished(self):
        parent = output_path(self.root, "orchestration/.check", repo_roots=self.roots).parent
        if not parent.exists(): return []
        entries = list(parent.iterdir())
        if len(entries) > MAX_RUNS: raise ContractError("shadow_run_history_limit")
        result = []
        for entry in entries:
            prefix = run_prefix(entry.name)
            if entry.is_symlink() or not entry.is_dir(): raise GuardError("shadow_run_directory")
            if self.exists(prefix + "/intent.json"):
                if not self.exists(prefix + "/report.json") or not load(self.root, prefix + "/report.json", self.roots).get("pipelineComplete"):
                    result.append(entry.name)
        return sorted(result)

    def run(self, plan, registry, policy, companies, *, runtime, runtime_file, live=False, python=None, grant=None, wall_seconds=900):
        validate(plan, expected_kind="job_plan")
        contexts = {j["queryId"]: registry.by_id()[j["queryId"]] for j in plan["jobs"]}
        if not live or any(activation(policy, runtime, live=live, implemented=frozenset(PLATFORMS))[j["platform"]] != "eligible" for j in plan["jobs"]):
            raise ContractError("live_activation_required")
        if type(wall_seconds) is not int or not 10 <= wall_seconds <= 7200: raise ContractError("shadow_wall_budget")
        if not plan["jobs"]:
            return {"ok": True, "status": "idle", "liveExecuted": False, "pipelineComplete": True, "jobs": []}
        validate_plan(plan, contexts, policy)
        if any(j["platform"] == "wechat" for j in plan["jobs"]) and grant is None:
            raise ContractError("wechat_request_grant_required")
        run_id = plan["jobs"][0]["runId"]
        prefix = run_prefix(run_id)
        with run_lock(self.root, self.roots):
            if stopped(self.root, self.roots): raise ContractError("shadow_stop_requested")
            if self.unfinished(): raise ContractError("shadow_recovery_required")
            if self.exists(prefix + "/intent.json"): raise ContractError("shadow_run_exists")
            intent = {"schemaVersion": 1, "plan": plan, "contexts": contexts, "policy": policy, "companies": companies}
            save(self.root, prefix + "/intent.json", intent, self.roots, exclusive=True)
            journal = {"runId": run_id, "startedAt": utc(self.clock()), "attempts": {}, "collectorInvocations": 0}
            deadline = self.monotonic() + wall_seconds
            with SchedulerStore(self.root, repo_roots=self.roots) as store:
                store.sync(registry)
                for job in plan["jobs"]:
                    aid, platform = job["attemptId"], job["platform"]
                    # Re-read the explicit runtime between jobs, without modifying it.
                    active = validate(input_json(self.root, runtime_file, self.roots, maximum=MAX_LINE), expected_kind="runtime_config")
                    if runtime_paths(active, repo_root=ROOT, runtime_file=runtime_file) != self.root:
                        raise GuardError("state_directory_mismatch")
                    if active["mediacrawlerDir"] != runtime["mediacrawlerDir"]: raise ContractError("shadow_runtime_changed")
                    reason = ("stopped" if stopped(self.root, self.roots) else
                        "disabled" if activation(policy, active, live=True, implemented=frozenset(PLATFORMS))[platform] != "eligible" else
                        "wall_budget" if self.monotonic() + job["limits"]["maxWallSeconds"] + 10 > deadline else None)
                    if reason:
                        journal["attempts"][aid] = reason
                        save(self.root, prefix + "/journal.json", journal, self.roots)
                        continue
                    journal["attempts"][aid] = "claiming"
                    save(self.root, prefix + "/journal.json", journal, self.roots)
                    if not store.claim(job, self.clock()):
                        journal["attempts"][aid] = "not_started"
                        save(self.root, prefix + "/journal.json", journal, self.roots)
                        continue
                    journal["attempts"][aid] = "started"
                    journal["collectorInvocations"] += 1
                    save(self.root, prefix + "/journal.json", journal, self.roots)
                    try:
                        result = self.executor(job, contexts[job["queryId"]], root=self.root, roots=self.roots,
                            runtime=active, runtime_file=runtime_file, policy=policy, python=python, grant=grant)
                        validate_result(job, result, self.clock())
                        save(self.root, prefix + "/results/" + aid + ".json", result, self.roots, exclusive=True)
                        store.finish(job, result, self.clock(), cadence_hours=policy["cadenceHours"][contexts[job["queryId"]]["priority"]])
                        journal["attempts"][aid] = "checkpointed"
                    except Exception as exc:
                        journal["attempts"][aid] = "error:" + code(exc)
                        # Unknown execution state cannot be followed by new queries.
                        # Recovery is storage-only and will reconcile saved receipts.
                        request_stop(self.root, self.roots)
                    save(self.root, prefix + "/journal.json", journal, self.roots)
            return self._complete(run_id, own_execution=True)

    def _result(self, prefix, job):
        relative = prefix + "/results/" + job["attemptId"] + ".json"
        result = load(self.root, relative, self.roots) if self.exists(relative) else None
        checkpoint = None
        if self.exists("state.sqlite3"):
            try:
                checkpoint = checkpoint_results(self.root, [job], self.roots)[0]
            except ContractError as exc:
                if exc.code != "checkpoint_result_missing": raise
        if result is not None and checkpoint is not None and digest(result) != digest(checkpoint):
            raise ContractError("shadow_checkpoint_conflict")
        if result is None: result = checkpoint
        pending = "pending/" + job["attemptId"] + ".json"
        if result is None and self.exists(pending):
            result = decode(read_private(self.root, pending, self.roots, maximum=4 * 1024 * 1024))
        if result is not None:
            validate_result(job, result, self.clock())
            if not self.exists(relative): save(self.root, relative, result, self.roots, exclusive=True)
        return result, checkpoint is not None

    def recover(self, run_id):
        with run_lock(self.root, self.roots):
            return self._complete(run_id, own_execution=False)

    def _complete(self, run_id, *, own_execution):
        prefix = run_prefix(run_id)
        intent = load(self.root, prefix + "/intent.json", self.roots)
        if set(intent) != {"schemaVersion", "plan", "contexts", "policy", "companies"} or intent["schemaVersion"] != 1:
            raise ContractError("shadow_intent_shape")
        plan, contexts, policy = intent["plan"], intent["contexts"], intent["policy"]
        validate_plan(plan, contexts, policy)
        if plan["jobs"][0]["runId"] != run_id: raise ContractError("shadow_run_mismatch")
        if self.exists(prefix + "/report.json"):
            old = load(self.root, prefix + "/report.json", self.roots)
            if old.get("pipelineComplete"):
                return {**old, "replayed": True, "liveExecuted": False}
        journal = load(self.root, prefix + "/journal.json", self.roots) if self.exists(prefix + "/journal.json") else {"attempts": {}, "collectorInvocations": 0}
        closure_path = prefix + "/closure.json"
        stage = "collect-results"
        try:
            if not self.exists(closure_path):
                statuses, completed, uncheckpointed = [], [], []
                snapshot = read_state(self.root, repo_roots=self.roots)
                for job in plan["jobs"]:
                    result, checkpointed = self._result(prefix, job)
                    aid = job["attemptId"]
                    lease = snapshot["queries"].get(job["queryId"], {})
                    if (not own_execution and not checkpointed and lease.get("leaseAttemptId") == aid
                            and lease.get("leaseUntil") and instant(lease["leaseUntil"]) > self.clock()):
                        request_stop(self.root, self.roots)
                        raise ContractError("shadow_worker_may_be_running")
                    if result is None:
                        status = journal["attempts"].get(aid, "not_started")
                        if status in {"started", "claiming", "checkpointed"}: status = "interrupted_without_receipt"
                        statuses.append({"attemptId": aid, "platform": job["platform"], "status": status, "receiptPresent": False})
                    else:
                        # Recover a durable pending receipt only while its original
                        # fencing lease is valid. Never forge a clock to advance it.
                        if not checkpointed:
                            try:
                                with SchedulerStore(self.root, repo_roots=self.roots) as store:
                                    store.finish(job, result, self.clock(), cadence_hours=policy["cadenceHours"][contexts[job["queryId"]]["priority"]])
                                checkpointed = True
                            except ContractError:
                                uncheckpointed.append(aid)
                        completed.append({"attemptId": aid, "resultHash": digest(result)})
                        statuses.append({"attemptId": aid, "platform": job["platform"], "status": result["receipt"]["status"],
                            "completeness": result["receipt"]["completeness"], "receiptPresent": True, "checkpointed": checkpointed,
                            "emittedRows": result["receipt"]["counts"]["emittedRows"],
                            "durationSeconds": (instant(result["receipt"]["completedAt"]) - instant(result["receipt"]["startedAt"])).total_seconds()})
                unknown = any(not s["receiptPresent"] and (s["status"].startswith("error:") or s["status"] == "interrupted_without_receipt") for s in statuses)
                if unknown or uncheckpointed: request_stop(self.root, self.roots)
                closure = {"runId": run_id, "planHash": digest(plan), "closedAt": utc(self.clock()), "completed": completed,
                    "jobs": statuses, "checkpointReconciliationRequired": bool(unknown or uncheckpointed)}
                save(self.root, closure_path, closure, self.roots, exclusive=True)
            closure = load(self.root, closure_path, self.roots)
            if closure["runId"] != run_id or closure["planHash"] != digest(plan): raise ContractError("shadow_closure_mismatch")
            jobs, receipts, observations = [], [], []
            by_attempt = {j["attemptId"]: j for j in plan["jobs"]}
            for row in closure["completed"]:
                job = by_attempt[row["attemptId"]]
                result = load(self.root, prefix + "/results/" + row["attemptId"] + ".json", self.roots)
                if digest(result) != row["resultHash"]: raise ContractError("shadow_result_changed_after_close")
                validate_result(job, result, self.clock())
                jobs.append(job); receipts.append(result["receipt"]); observations.extend(result["observations"])
            manifest_hash, review_version = None, None
            if jobs:
                stage = "seal"
                bundle = seal_batch(self.root, prefix + "/batch", jobs, receipts, observations,
                    repo_roots=self.roots, created_at=closure["closedAt"])
                manifest_hash = bundle.fingerprint
                stage = "import"
                with SignalStore(self.root, repo_roots=self.roots) as source:
                    source.import_batch(bundle)
                    stage = "review"
                    with ReviewStore(self.root, repo_roots=self.roots) as review:
                        review_version = review.materialize(source, intent["companies"])["queueVersion"]
            healthy = (len(jobs) == len(plan["jobs"]) and not closure["checkpointReconciliationRequired"]
                and all(r["status"] in {"ok", "empty"} for r in receipts))
            report = {"ok": healthy, "status": "completed" if healthy else "degraded", "runId": run_id,
                "pipelineComplete": True, "jobs": closure["jobs"], "plannedJobs": len(plan["jobs"]),
                "receiptJobs": len(jobs), "notCompletedJobs": len(plan["jobs"]) - len(jobs),
                "observations": len(observations), "manifestHash": manifest_hash, "reviewQueueVersion": review_version,
                "batchIntegrityChecked": bool(jobs), "checkpointReconciliationRequired": closure["checkpointReconciliationRequired"],
                "collectorInvocations": journal["collectorInvocations"], "liveExecuted": own_execution and journal["collectorInvocations"] > 0,
                "stopRequested": stopped(self.root, self.roots), "mode": "shadow", "publish": False, "productionChanged": False,
                "startedAt": journal.get("startedAt"), "closedAt": closure["closedAt"],
                "replayed": False, "liveAcceptance": "not_attested"}
        except Exception as exc:
            report = {"ok": False, "status": "blocked", "runId": run_id, "pipelineComplete": False,
                "stage": stage, "error": code(exc), "mode": "shadow", "publish": False, "productionChanged": False,
                "liveExecuted": own_execution and journal["collectorInvocations"] > 0}
        save(self.root, prefix + "/report.json", report, self.roots)
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Preview by default; --live opts into bounded collectors")
    _add_inputs(run)
    run.add_argument("--platform", action="append", choices=PLATFORMS)
    run.add_argument("--wechat-provider", action="append", choices=("sogou-weixin", "bing-rss"))
    run.add_argument("--live", action="store_true")
    run.add_argument("--python", type=Path)
    run.add_argument("--budget-file")
    run.add_argument("--wall-seconds", type=int, default=900)
    run.add_argument("--companies")
    recovery = sub.add_parser("recover", help="Recover saved results/storage/review only; never re-query")
    recovery.add_argument("--run-id", required=True)
    status = sub.add_parser("health")
    stop = sub.add_parser("stop", help="Stop new jobs and subsequent guarded API requests")
    resume = sub.add_parser("resume", help="Clear coordinator stop only, never authentication/rate pauses")
    resume.add_argument("--confirmed", required=True, action="store_true")
    evaluation = sub.add_parser("evaluate")
    evaluation.add_argument("--assessment", required=True)
    evaluation.add_argument("--baseline", required=True)
    for item in (recovery, status, stop, resume, evaluation): item.add_argument("--state-dir", type=Path, required=True)
    for item in (run, recovery, status, stop, resume, evaluation): item.add_argument("--runtime-config", type=Path, required=True)
    args = parser.parse_args(argv)
    before = None
    try:
        root = private_root(args.state_dir, (ROOT,))
        runtime = validate(input_json(root, args.runtime_config, (ROOT,), maximum=MAX_LINE), expected_kind="runtime_config")
        roots = (ROOT,) + ((Path(runtime["mediacrawlerDir"]),) if runtime["mediacrawlerDir"] else ())
        if runtime_paths(runtime, repo_root=ROOT, runtime_file=args.runtime_config) != root: raise GuardError("state_directory_mismatch")
        before = protected_snapshot(ROOT)
        if args.command == "run":
            selected = tuple(args.platform or [p for p in PLATFORMS if runtime["platforms"][p]["enabled"]])
            if not selected:
                result = {"ok": True, "status": "disabled", "liveExecuted": False, "writesPerformed": False}
            else:
                policy, registry, config_hash = _inputs(args, selected, tuple(args.wechat_provider or ("sogou-weixin",)))
                upstream = load_json(ROOT / "workers/mediacrawler/upstream.lock.json")["commit"]
                plan = plan_jobs(registry, read_state(root, repo_roots=roots), datetime.now(UTC), policy,
                    vciq_commit=revision(ROOT), config_hash=config_hash, upstream_commit=upstream)
                if not args.live:
                    result = {"ok": True, "status": "preview", "plan": plan, "activation": activation(policy, runtime, implemented=frozenset(PLATFORMS)),
                        "liveExecuted": False, "writesPerformed": False, "stopRequested": stopped(root, roots)}
                else:
                    index = registry_input(root, roots, args.companies)
                    grant = input_json(root, args.budget_file, roots, maximum=MAX_LINE) if args.budget_file else None
                    result = Coordinator(root, roots).run(plan, registry, policy, index, runtime=runtime,
                        runtime_file=args.runtime_config, live=True, python=args.python, grant=grant, wall_seconds=args.wall_seconds)
        elif args.command == "recover": result = Coordinator(root, roots).recover(args.run_id)
        elif args.command == "health":
            from .health import health
            result = health(root, roots)
        elif args.command == "stop": result = {"ok": True, "changed": request_stop(root, roots), "stopRequested": True, "liveExecuted": False}
        elif args.command == "resume":
            with run_lock(root, roots):
                if Coordinator(root, roots).unfinished(): raise ContractError("shadow_recovery_required")
                changed = clear_stop(root, roots)
            result = {"ok": True, "changed": changed, "liveExecuted": False, "platformPausesUnchanged": True}
        else:
            from .evaluate import evaluate
            with SignalStore(root, repo_roots=roots, readonly=True) as source:
                result = evaluate(source, input_json(root, args.assessment, roots), input_json(root, args.baseline, roots))
        assert_unchanged(before, repo_root=ROOT)
        print(json.dumps({**result, "mode": "shadow", "publish": False}, ensure_ascii=False, sort_keys=True))
        return 0 if result["ok"] else 1
    except Exception as exc:
        error = code(exc)
        if before is not None:
            try: assert_unchanged(before, repo_root=ROOT)
            except GuardError: error = "production_modified"
        print(json.dumps({"ok": False, "error": error, "mode": "shadow", "publish": False,
            "liveExecuted": "unknown" if args.command == "run" and args.live else False}), file=sys.stderr)
        return 2


if __name__ == "__main__": raise SystemExit(main())
