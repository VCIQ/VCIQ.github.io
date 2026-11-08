"""Pure fair planning: previewing never creates a database or execution lease."""
from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Callable
from uuid import uuid4

from .contracts import ContractError, digest, validate
from .query_registry import PRIORITY, QueryRegistry


def utc(now: datetime) -> str:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ContractError("clock_timezone_required")
    return now.astimezone(UTC).isoformat(timespec="seconds")


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ContractError("clock_timezone_required")
    return parsed.astimezone(UTC)


def plan_jobs(registry: QueryRegistry, state: dict, now: datetime, policy: dict, *,
              vciq_commit: str, config_hash: str, upstream_commit: str,
              uuid_factory: Callable = uuid4) -> dict:
    validate(policy, expected_kind="discovery_policy")
    stamp = utc(now)
    now = instant(stamp)
    limit = int(policy["budget"]["jobsPerPlatformPerRun"])
    known = state.get("queries", {})
    platforms = state.get("platforms", {})
    eligible = [entry for entry in registry.entries if not entry["excludedReason"]]
    selected: list[dict] = []
    for platform in sorted({entry["platform"] for entry in eligible}):
        pause = platforms.get(platform, {})
        if pause.get("pauseReason") and (not pause.get("pauseUntil") or instant(pause["pauseUntil"]) > now):
            continue
        ready = []
        for entry in eligible:
            if entry["platform"] != platform:
                continue
            row = known.get(entry["queryId"], {})
            if row.get("leaseUntil") and instant(row["leaseUntil"]) > now:
                continue
            if row.get("nextDueAt") and instant(row["nextDueAt"]) > now:
                continue
            ready.append(entry)
        def rank(entry: dict) -> tuple:
            row = known.get(entry["queryId"], {})
            return (row.get("lastCoveredAt") or "", row.get("lastAttemptAt") or "",
                    PRIORITY[entry["priority"]], entry["queryId"])
        ready.sort(key=rank)
        # Explicit tail reservation; never exhaust every run on high-priority names.
        tail = next((entry for entry in ready if entry["priority"] == "longTail"), None)
        picked = ([tail] if tail else [])
        picked.extend(entry for entry in ready if entry is not tail)
        selected.extend(picked[:limit])
    run_id = str(uuid_factory())
    jobs = []
    for entry in selected:
        budget = policy["budget"]
        job = {"schemaVersion": 1, "kind": "crawl_job", "queryId": entry["queryId"],
               "jobId": digest({"queryId": entry["queryId"], "operation": "search"}),
               "runId": run_id, "attemptId": str(uuid_factory()), "platform": entry["platform"],
               "engine": "wechat-public" if entry["platform"] == "wechat" else "mediacrawler",
               "provider": entry["provider"], "operation": "search", "mode": "shadow",
               "query": copy.deepcopy(entry["query"]), "trackRefs": list(entry["trackRefs"]),
               "window": {"from": None, "to": None, "filterMode": "none"},
               "limits": {"maxSearchPages": budget["pagesPerJob"],
                          "maxRecords": min(6, budget["recordsPerJob"]) if entry["platform"] == "wechat" else budget["recordsPerJob"],
                          "maxWallSeconds": budget["wallSecondsPerJob"]},
               "vciqCommit": vciq_commit, "configHash": config_hash,
               "upstreamCommit": None if entry["platform"] == "wechat" else upstream_commit,
               "policyVersion": policy["policyVersion"]}
        jobs.append(job)
    plan = {"schemaVersion": 1, "kind": "job_plan", "generatedAt": stamp,
            "vciqCommit": vciq_commit, "configHash": config_hash,
            "stats": {"registeredQueries": len(registry.entries), "eligibleQueries": len(eligible),
                      "selectedJobs": len(jobs), "deferredQueries": len(eligible) - len(jobs),
                      "excludedQueries": len(registry.entries) - len(eligible)}, "jobs": jobs}
    plan["planId"] = digest({key: value for key, value in plan.items() if key != "generatedAt"})
    return validate(plan, expected_kind="job_plan")
