#!/usr/bin/env python3
"""Runtime-health semantics layered on top of the artifact freshness snapshot.

The legacy control-plane builder intentionally treats an artifact's embedded data
 timestamp as its freshness signal.  That is useful for evidence age, but it is
not the same thing as producer health: a successful scheduled check may find no
new domain data and therefore leave the artifact timestamp unchanged.

This module preserves artifact freshness while deriving job health from the most
recent successful producer heartbeat.  It is imported by ``run_pipeline.py`` so
all producer finalization and refresh operations use the corrected semantics.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

try:
    from . import build_pipeline_health as legacy
except ImportError:
    import build_pipeline_health as legacy  # type: ignore


def _age_hours(value: datetime | None, now: datetime) -> float | None:
    if value is None:
        return None
    return round(max(0.0, (now - value).total_seconds() / 3600), 2)


def _freshness_status(outputs: list[Mapping[str, Any]]) -> str:
    if any(
        bool(output.get("required")) and output.get("status") == "missing"
        for output in outputs
    ):
        return "missing"
    statuses = [
        str(output.get("freshnessStatus") or output.get("status") or "unknown")
        for output in outputs
    ]
    if "stale" in statuses:
        return "stale"
    if "degraded" in statuses:
        return "degraded"
    if statuses and all(value == "healthy" for value in statuses):
        return "healthy"
    if "healthy" in statuses:
        return "healthy"
    if "missing" in statuses:
        return "missing"
    return "unknown"


def _previous_health(root: Path) -> dict[str, Any]:
    return legacy.load_json(root / "public/data/pipeline_health.json", required=False)


def _successful_run_candidates(
    *,
    job_id: str,
    outputs: list[Mapping[str, Any]],
    previous_job: Mapping[str, Any] | None,
    current_run: Mapping[str, Any] | None,
) -> tuple[list[datetime], bool]:
    candidates: list[datetime] = []
    degraded = False

    if isinstance(previous_job, Mapping):
        previous = legacy.parse_datetime(
            previous_job.get("lastSuccessfulRunAt") or previous_job.get("lastCompletedAt")
        )
        if previous:
            candidates.append(previous)
        if previous_job.get("status") == "degraded":
            degraded = True

    if isinstance(current_run, Mapping) and current_run.get("jobId") == job_id:
        current_status = str(current_run.get("status") or "")
        if current_status in {"success", "degraded"}:
            completed = legacy.parse_datetime(current_run.get("completedAt"))
            if completed:
                candidates.append(completed)
            degraded = current_status == "degraded"

    for output in outputs:
        producer = output.get("producer")
        if not isinstance(producer, Mapping):
            continue
        # A shared artifact may most recently have been written by another job.
        # Do not use that producer as a heartbeat for this job.
        if producer.get("jobId") != job_id:
            continue
        producer_status = str(producer.get("status") or "")
        if producer_status not in {"success", "degraded"}:
            continue
        completed = legacy.parse_datetime(producer.get("completedAt"))
        if completed:
            candidates.append(completed)
        if producer_status == "degraded":
            degraded = True

    # Backward-compatibility bootstrap for snapshots written before explicit
    # heartbeats existed.  Once a heartbeat is available it always wins.
    if not candidates:
        for output in outputs:
            data_time = legacy.parse_datetime(output.get("dataTimestamp"))
            if data_time:
                candidates.append(data_time)

    return candidates, degraded


def _apply_runtime_semantics(
    root: Path,
    registry: Mapping[str, Any],
    lineage: dict[str, Any],
    health: dict[str, Any],
    *,
    current_run: Mapping[str, Any] | None,
    previous_health: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    generated = legacy.parse_datetime(health.get("generatedAt")) or legacy.utc_now()
    artifacts = lineage.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}

    # Keep the existing artifact status for compatibility, but make its meaning
    # explicit for new consumers.
    for artifact in artifacts.values():
        if isinstance(artifact, dict):
            artifact["freshnessStatus"] = str(artifact.get("status") or "unknown")

    previous_jobs = previous_health.get("jobs")
    if not isinstance(previous_jobs, dict):
        previous_jobs = {}

    registry_jobs = {
        str(job.get("id")): job
        for job in registry.get("jobs", [])
        if isinstance(job, Mapping) and job.get("id")
    }
    jobs = health.get("jobs")
    if not isinstance(jobs, dict):
        jobs = {}
        health["jobs"] = jobs

    for job_id, job in registry_jobs.items():
        row = jobs.get(job_id)
        if not isinstance(row, dict):
            continue
        output_rows = [
            artifacts[path]
            for path in row.get("outputs", [])
            if path in artifacts and isinstance(artifacts[path], dict)
        ]
        row["freshnessStatus"] = (
            _freshness_status(output_rows) if output_rows else "unknown"
        )

        if not output_rows:
            # Dependency-only jobs are finalized below after producer jobs have
            # their corrected runtime status.
            row["lastSuccessfulRunAt"] = row.get("lastCompletedAt")
            row["runAgeHours"] = _age_hours(
                legacy.parse_datetime(row.get("lastCompletedAt")), generated
            )
            continue

        required_missing = any(
            bool(output.get("required")) and output.get("status") == "missing"
            for output in output_rows
        )
        candidates, degraded = _successful_run_candidates(
            job_id=job_id,
            outputs=output_rows,
            previous_job=(
                previous_jobs.get(job_id)
                if isinstance(previous_jobs.get(job_id), Mapping)
                else None
            ),
            current_run=current_run,
        )
        last_successful = max(candidates) if candidates else None
        run_age = _age_hours(last_successful, generated)

        if required_missing:
            runtime_status = "missing"
        elif degraded:
            runtime_status = "degraded"
        elif run_age is None:
            runtime_status = "unknown"
        elif run_age > float(job.get("freshnessSlaHours") or 0):
            runtime_status = "stale"
        else:
            runtime_status = "healthy"

        row["status"] = runtime_status
        row["lastSuccessfulRunAt"] = (
            legacy.isoformat(last_successful) if last_successful else None
        )
        # Preserve the old field for existing UI/consumers, but give it the new
        # operational meaning rather than mixing in dataTimestamp.
        row["lastCompletedAt"] = row["lastSuccessfulRunAt"]
        row["runAgeHours"] = run_age

    # Resolve dependency-only jobs after producer statuses are corrected.
    for job_id, job in registry_jobs.items():
        row = jobs.get(job_id)
        if not isinstance(row, dict) or row.get("outputs"):
            continue
        dependencies = [
            jobs[dependency]
            for dependency in job.get("dependencies", [])
            if dependency in jobs and isinstance(jobs[dependency], dict)
        ]
        if not dependencies:
            continue

        runtime_statuses = [str(dep.get("status") or "unknown") for dep in dependencies]
        if any(value in {"missing", "stale"} for value in runtime_statuses):
            row["status"] = "stale"
        elif any(value == "degraded" for value in runtime_statuses):
            row["status"] = "degraded"
        elif runtime_statuses and all(value == "healthy" for value in runtime_statuses):
            row["status"] = "healthy"
        else:
            row["status"] = "unknown"

        freshness_statuses = [
            str(dep.get("freshnessStatus") or dep.get("status") or "unknown")
            for dep in dependencies
        ]
        if any(value in {"missing", "stale"} for value in freshness_statuses):
            row["freshnessStatus"] = "stale"
        elif any(value == "degraded" for value in freshness_statuses):
            row["freshnessStatus"] = "degraded"
        elif freshness_statuses and all(value == "healthy" for value in freshness_statuses):
            row["freshnessStatus"] = "healthy"
        else:
            row["freshnessStatus"] = "unknown"

        completed = [
            legacy.parse_datetime(dep.get("lastSuccessfulRunAt") or dep.get("lastCompletedAt"))
            for dep in dependencies
        ]
        completed = [value for value in completed if value]
        if completed:
            latest = max(completed)
            row["lastSuccessfulRunAt"] = legacy.isoformat(latest)
            row["lastCompletedAt"] = row["lastSuccessfulRunAt"]
            row["runAgeHours"] = _age_hours(latest, generated)

    allowed = legacy.ALLOWED_JOB_STATUSES
    counts = {
        status: sum(1 for row in jobs.values() if row.get("status") == status)
        for status in allowed
    }
    freshness_warning_jobs = sum(
        1 for row in jobs.values() if row.get("freshnessStatus") == "stale"
    )
    stale_artifacts = sum(
        1
        for artifact in artifacts.values()
        if isinstance(artifact, Mapping)
        and (artifact.get("freshnessStatus") or artifact.get("status")) == "stale"
    )

    summary = health.setdefault("summary", {})
    summary.update(
        {
            "totalJobs": len(jobs),
            "healthyJobs": counts["healthy"],
            "staleJobs": counts["stale"],
            "missingJobs": counts["missing"],
            "unknownJobs": counts["unknown"],
            "degradedJobs": counts["degraded"],
            "freshnessWarningJobs": freshness_warning_jobs,
            "staleArtifacts": stale_artifacts,
        }
    )
    health["overallStatus"] = (
        "degraded"
        if counts["missing"] or counts["stale"] or counts["degraded"]
        else "healthy"
    )
    return lineage, health


def build_snapshots(
    root: Path,
    registry: Mapping[str, Any],
    *,
    previous_lineage: Mapping[str, Any] | None = None,
    current_run: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    previous_health: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    lineage, health = legacy.build_snapshots(
        root,
        registry,
        previous_lineage=previous_lineage,
        current_run=current_run,
        now=now,
    )
    prior_health = (
        dict(previous_health)
        if isinstance(previous_health, Mapping)
        else _previous_health(root)
    )
    return _apply_runtime_semantics(
        root,
        registry,
        lineage,
        health,
        current_run=current_run,
        previous_health=prior_health,
    )


def write_snapshots(
    root: Path,
    registry: Mapping[str, Any],
    *,
    lineage_output: Path,
    health_output: Path,
    current_run: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    previous_lineage = legacy.load_json(lineage_output, required=False)
    previous_health = legacy.load_json(health_output, required=False)
    lineage, health = build_snapshots(
        root,
        registry,
        previous_lineage=previous_lineage,
        previous_health=previous_health,
        current_run=current_run,
        now=now,
    )
    legacy.atomic_write_json(lineage_output, lineage)
    legacy.atomic_write_json(health_output, health)
    return lineage, health
