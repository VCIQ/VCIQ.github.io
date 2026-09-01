#!/usr/bin/env python3
"""Derive producer runtime health without conflating it with data freshness.

``build_pipeline_health`` remains responsible for artifact lineage and freshness.
This module overlays runtime semantics on that snapshot while preserving the
public JSON schema shape (``health.jobs`` stays a list).  Producer health is
based on the most recent successful/degraded heartbeat; stale business data is
reported separately through ``freshnessStatus``.
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
        bool(output.get("required", True)) and output.get("status") == "missing"
        for output in outputs
    ):
        return "missing"
    statuses = [str(output.get("status") or "unknown") for output in outputs]
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


def _jobs_by_id(health: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    jobs = health.get("jobs")
    if not isinstance(jobs, list):
        return {}
    return {
        str(row.get("jobId")): row
        for row in jobs
        if isinstance(row, Mapping) and row.get("jobId")
    }


def _successful_run_candidates(
    *,
    job_id: str,
    outputs: list[Mapping[str, Any]],
    previous_job: Mapping[str, Any] | None,
    current_run: Mapping[str, Any] | None,
) -> list[tuple[datetime, str]]:
    candidates: list[tuple[datetime, str]] = []

    if isinstance(previous_job, Mapping):
        previous = legacy.parse_datetime(
            previous_job.get("lastSuccessfulRunAt") or previous_job.get("lastCompletedAt")
        )
        if previous:
            # lastSuccessfulRunAt is an operational heartbeat even if the row has
            # since become stale because no newer run arrived.
            previous_status = (
                "degraded" if previous_job.get("status") == "degraded" else "success"
            )
            candidates.append((previous, previous_status))

    if isinstance(current_run, Mapping) and current_run.get("jobId") == job_id:
        current_status = str(current_run.get("status") or "")
        if current_status in {"success", "degraded"}:
            completed = legacy.parse_datetime(current_run.get("completedAt"))
            if completed:
                candidates.append((completed, current_status))

    for output in outputs:
        producer = output.get("producer")
        if not isinstance(producer, Mapping):
            continue
        # A shared artifact may most recently have been written by another job;
        # that is not a heartbeat for this job.
        if producer.get("jobId") != job_id:
            continue
        producer_status = str(producer.get("status") or "")
        if producer_status not in {"success", "degraded"}:
            continue
        completed = legacy.parse_datetime(producer.get("completedAt"))
        if completed:
            candidates.append((completed, producer_status))

    # Bootstrap snapshots that predate explicit heartbeats.  This fallback is
    # used only until the first real producer heartbeat is recorded.
    if not candidates:
        for output in outputs:
            data_time = legacy.parse_datetime(output.get("dataTimestamp"))
            if data_time:
                candidates.append((data_time, "success"))

    return candidates


def _runtime_status(
    *,
    job: Mapping[str, Any],
    outputs: list[Mapping[str, Any]],
    candidates: list[tuple[datetime, str]],
    generated: datetime,
) -> tuple[str, datetime | None, float | None]:
    if any(
        bool(output.get("required", True)) and output.get("status") == "missing"
        for output in outputs
    ):
        last = max((time for time, _ in candidates), default=None)
        return "missing", last, _age_hours(last, generated)

    if not candidates:
        return "unknown", None, None

    last, last_result = max(candidates, key=lambda item: item[0])
    run_age = _age_hours(last, generated)
    if last_result == "degraded":
        return "degraded", last, run_age
    if run_age is None:
        return "unknown", last, None
    if run_age > float(job.get("freshnessSlaHours") or 0):
        return "stale", last, run_age
    return "healthy", last, run_age


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

    # Artifact status continues to mean business-data freshness for backwards
    # compatibility.  New consumers can use the explicit alias.
    for artifact in artifacts.values():
        if isinstance(artifact, dict):
            artifact["freshnessStatus"] = str(artifact.get("status") or "unknown")

    jobs = health.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("pipeline health jobs must remain a list")

    rows_by_id = {
        str(row.get("jobId")): row
        for row in jobs
        if isinstance(row, dict) and row.get("jobId")
    }
    previous_jobs = _jobs_by_id(previous_health)
    registry_jobs = {
        str(job.get("id")): job
        for job in registry.get("jobs", [])
        if isinstance(job, Mapping) and job.get("id")
    }

    for job_id, job in registry_jobs.items():
        row = rows_by_id.get(job_id)
        if not isinstance(row, dict):
            continue
        output_paths = [
            str(output.get("path"))
            for output in job.get("outputs", [])
            if isinstance(output, Mapping)
            and output.get("public", True)
            and output.get("path")
        ]
        output_rows = [
            artifacts[path]
            for path in output_paths
            if path in artifacts and isinstance(artifacts[path], dict)
        ]
        row["freshnessStatus"] = (
            _freshness_status(output_rows) if output_rows else "unknown"
        )

        # Dependency-derived jobs are resolved in a second pass.
        if job.get("healthMode") == "dependencies":
            continue

        candidates = _successful_run_candidates(
            job_id=job_id,
            outputs=output_rows,
            previous_job=previous_jobs.get(job_id),
            current_run=current_run,
        )
        runtime_status, last_successful, run_age = _runtime_status(
            job=job,
            outputs=output_rows,
            candidates=candidates,
            generated=generated,
        )
        row["status"] = runtime_status
        row["lastSuccessfulRunAt"] = (
            legacy.isoformat(last_successful) if last_successful else None
        )
        # Keep the legacy field so existing UI continues to work, but it now
        # represents execution completion rather than data age.
        row["lastCompletedAt"] = row["lastSuccessfulRunAt"]
        row["runAgeHours"] = run_age

    # Preserve the registry's dependency health semantics, now using corrected
    # runtime status for dependencies and separate freshness status for warnings.
    for job_id, job in registry_jobs.items():
        if job.get("healthMode") != "dependencies":
            continue
        row = rows_by_id.get(job_id)
        if not isinstance(row, dict):
            continue
        dependencies = [
            rows_by_id[dependency]
            for dependency in job.get("dependencies", [])
            if dependency in rows_by_id
        ]
        runtime_statuses = [str(dep.get("status") or "unknown") for dep in dependencies]
        if any(value in {"missing", "degraded"} for value in runtime_statuses):
            row["status"] = "degraded"
        elif any(value == "stale" for value in runtime_statuses):
            row["status"] = "stale"
        elif runtime_statuses and all(value == "healthy" for value in runtime_statuses):
            row["status"] = "healthy"
        else:
            row["status"] = "unknown"

        freshness_statuses = [
            str(dep.get("freshnessStatus") or "unknown") for dep in dependencies
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
        status: sum(1 for row in jobs if row.get("status") == status)
        for status in allowed
    }
    freshness_warning_jobs = sum(
        1 for row in jobs if row.get("freshnessStatus") == "stale"
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
            "jobCount": len(jobs),
            "healthyJobs": counts["healthy"],
            "staleJobs": counts["stale"],
            "missingJobs": counts["missing"],
            "unknownJobs": counts["unknown"],
            "degradedJobs": counts["degraded"],
            "artifactCount": len(artifacts),
            "freshnessWarningJobs": freshness_warning_jobs,
            "staleArtifacts": stale_artifacts,
        }
    )

    non_advisory_statuses = [
        str(rows_by_id[job_id].get("status") or "unknown")
        for job_id, job in registry_jobs.items()
        if job.get("failurePolicy") != "advisory-only" and job_id in rows_by_id
    ]
    if any(value in {"missing", "degraded"} for value in non_advisory_statuses):
        health["overallStatus"] = "degraded"
    elif any(value == "stale" for value in non_advisory_statuses):
        health["overallStatus"] = "stale"
    elif non_advisory_statuses and all(
        value == "healthy" for value in non_advisory_statuses
    ):
        health["overallStatus"] = "healthy"
    else:
        health["overallStatus"] = "unknown"

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
