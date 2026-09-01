#!/usr/bin/env python3
"""Automation control-plane CLI for VCIQ producer and deploy workflows.

This command deliberately does not invoke crawler implementations. It gives
existing workflows a shared registry, run identity, finalization contract, data
lineage, freshness health, and deployment provenance without changing their
domain-specific collection logic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

try:
    from .build_pipeline_health import (
        ROOT,
        atomic_write_json,
        isoformat,
        load_json,
        load_registry,
        parse_datetime,
        relative_path,
        validate_health_snapshot,
        validate_lineage_snapshot,
    )
    from .pipeline_health_runtime import build_snapshots, write_snapshots
except ImportError:
    from build_pipeline_health import (  # type: ignore
        ROOT,
        atomic_write_json,
        isoformat,
        load_json,
        load_registry,
        parse_datetime,
        relative_path,
        validate_health_snapshot,
        validate_lineage_snapshot,
    )
    from pipeline_health_runtime import build_snapshots, write_snapshots  # type: ignore


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return os.environ.get("GITHUB_SHA", "").strip() or "unknown"


def git_ref() -> str:
    return (
        os.environ.get("GITHUB_REF", "").strip()
        or os.environ.get("GITHUB_HEAD_REF", "").strip()
        or "local"
    )


def _job(registry: Mapping[str, Any], job_id: str) -> dict[str, Any]:
    for job in registry.get("jobs", []):
        if isinstance(job, dict) and job.get("id") == job_id:
            return dict(job)
    raise ValueError(f"unknown automation job: {job_id}")


def derive_run_id(job_id: str, started_at: datetime) -> str:
    explicit = os.environ.get("VCIQ_PIPELINE_RUN_ID", "").strip()
    if explicit:
        return explicit
    github_run = os.environ.get("GITHUB_RUN_ID", "").strip()
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1").strip() or "1"
    if github_run:
        return f"gha:{github_run}:{attempt}:{job_id}"
    timestamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    entropy = hashlib.sha256(
        f"{job_id}|{timestamp}|{os.getpid()}".encode("utf-8")
    ).hexdigest()[:8]
    return f"local:{job_id}:{timestamp}:{entropy}"


def make_run_context(
    root: Path,
    registry: Mapping[str, Any],
    job_id: str,
    *,
    started_at: datetime | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    job = _job(registry, job_id)
    started = (started_at or utc_now()).astimezone(UTC).replace(microsecond=0)
    return {
        "schemaVersion": 1,
        "pipelineVersion": registry["pipelineVersion"],
        "jobId": job_id,
        "runId": run_id or derive_run_id(job_id, started),
        "codeSha": git_head(root),
        "sourceRef": git_ref(),
        "startedAt": isoformat(started),
        "completedAt": None,
        "status": "running",
        "qualityGate": "pending",
        "inputs": list(job["inputs"]),
        "outputs": [dict(output) for output in job["outputs"]],
        "freshnessSlaHours": job["freshnessSlaHours"],
        "failurePolicy": job["failurePolicy"],
    }


def validate_run_context(
    context: Mapping[str, Any],
    registry: Mapping[str, Any],
    expected_job_id: str | None = None,
) -> None:
    if context.get("schemaVersion") != 1:
        raise ValueError("run context schemaVersion must be 1")
    if context.get("pipelineVersion") != registry.get("pipelineVersion"):
        raise ValueError("run context pipelineVersion does not match registry")
    job_id = str(context.get("jobId") or "")
    _job(registry, job_id)
    if expected_job_id and job_id != expected_job_id:
        raise ValueError(
            f"run context belongs to {job_id}, expected {expected_job_id}"
        )
    if not str(context.get("runId") or "").strip():
        raise ValueError("run context requires runId")
    if not parse_datetime(context.get("startedAt")):
        raise ValueError("run context requires a valid startedAt")


def required_outputs(root: Path, job: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    for output in job["outputs"]:
        if output.get("required", True) and not relative_path(root, output["path"]).exists():
            missing.append(str(output["path"]))
    return missing


def resume_run_metadata(
    context: dict[str, Any],
    job: Mapping[str, Any],
    lineage_path: Path,
) -> dict[str, Any]:
    """Keep the original source commit when one workflow run rebases its data commit.

    GitHub Actions keeps one run ID across push retries. The first successful
    finalization records the code SHA used for collection. A later rebase must
    not replace that SHA with the transient pre-amend data commit.
    """

    lineage = load_json(lineage_path, required=False)
    artifacts = lineage.get("artifacts")
    if not isinstance(artifacts, dict):
        return context
    for output in job.get("outputs", []):
        if not isinstance(output, dict):
            continue
        record = artifacts.get(str(output.get("path") or ""))
        if not isinstance(record, dict):
            continue
        producer = record.get("producer")
        if not isinstance(producer, dict):
            continue
        if (
            producer.get("jobId") == job.get("id")
            and producer.get("runId") == context.get("runId")
        ):
            for field in ("codeSha", "sourceRef"):
                if str(producer.get(field) or "").strip():
                    context[field] = producer[field]
            break
    return context


def finalize_pipeline(
    root: Path,
    registry: Mapping[str, Any],
    job_id: str,
    *,
    context: Mapping[str, Any] | None = None,
    run_id: str | None = None,
    quality_gate: str = "passed",
    status: str = "success",
    completed_at: datetime | None = None,
    lineage_output: Path | None = None,
    health_output: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    job = _job(registry, job_id)
    if status not in {"success", "degraded"}:
        raise ValueError("only successful or explicitly degraded runs may update public lineage")
    if status == "degraded" and job_id != "research-agent-daily":
        raise ValueError("degraded publication is only supported for research-agent-daily")
    if quality_gate != "passed":
        raise ValueError("public lineage requires quality_gate=passed")

    missing = required_outputs(root, job)
    if missing:
        raise FileNotFoundError(
            f"job {job_id} cannot finalize; required outputs are missing: {missing}"
        )

    lineage_path = lineage_output or (root / "public/data/data_lineage.json")
    health_path = health_output or (root / "public/data/pipeline_health.json")
    current = (
        dict(context)
        if isinstance(context, Mapping)
        else make_run_context(root, registry, job_id, run_id=run_id)
    )
    if not isinstance(context, Mapping):
        current = resume_run_metadata(current, job, lineage_path)
    validate_run_context(current, registry, expected_job_id=job_id)
    if run_id:
        current["runId"] = run_id
    current.update(
        {
            "completedAt": isoformat(completed_at or utc_now()),
            "status": status,
            "qualityGate": quality_gate,
        }
    )
    lineage, health = write_snapshots(
        root,
        registry,
        lineage_output=lineage_path,
        health_output=health_path,
        current_run=current,
        now=completed_at,
    )
    return current, lineage, health


def build_deployment_provenance(
    root: Path,
    registry: Mapping[str, Any],
    *,
    output: Path,
    job_id: str = "pages-deploy",
    generated_at: datetime | None = None,
    lineage_path: Path | None = None,
    health_path: Path | None = None,
) -> dict[str, Any]:
    job = _job(registry, job_id)
    generated = (generated_at or utc_now()).astimezone(UTC).replace(microsecond=0)
    lineage_file = lineage_path or (root / "public/data/data_lineage.json")
    health_file = health_path or (root / "public/data/pipeline_health.json")

    def fingerprint(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        raw = path.read_bytes()
        return {
            "path": str(path.relative_to(root))
            if path.is_relative_to(root)
            else str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }

    payload = {
        "schemaVersion": 1,
        "pipelineVersion": registry["pipelineVersion"],
        "repository": os.environ.get("GITHUB_REPOSITORY", "").strip()
        or "VCIQ/VCIQ.github.io",
        "jobId": job_id,
        "runId": derive_run_id(job_id, generated),
        "sourceSha": git_head(root),
        "sourceRef": git_ref(),
        "generatedAt": isoformat(generated),
        "qualityGate": "passed",
        "failurePolicy": job["failurePolicy"],
        "controlPlane": {
            "registry": fingerprint(root / "config/automation_jobs.json"),
            "dataLineage": fingerprint(lineage_file),
            "pipelineHealth": fingerprint(health_file),
        },
    }
    atomic_write_json(output, payload)
    return payload


def check_control_plane(
    root: Path,
    registry: Mapping[str, Any],
    *,
    lineage_path: Path,
    health_path: Path,
) -> dict[str, Any]:
    validate_lineage_snapshot(load_json(lineage_path), registry)
    validate_health_snapshot(load_json(health_path), registry)
    return {
        "valid": True,
        "pipelineVersion": registry["pipelineVersion"],
        "jobCount": len(registry["jobs"]),
        "objectTypes": [item["id"] for item in registry["publicObjectTypes"]],
    }


def _datetime_argument(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = parse_datetime(value)
    if not parsed:
        raise ValueError(f"invalid timestamp: {value}")
    return parsed


def _path(root: Path, value: str | None, default: Path) -> Path:
    if value is None:
        return default
    candidate = Path(value)
    return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()


def _load_context(path: Path | None) -> dict[str, Any] | None:
    return load_json(path) if path else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--registry")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--lineage")
    check_parser.add_argument("--health")

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("job_id")
    start_parser.add_argument("--output")
    start_parser.add_argument("--run-id")
    start_parser.add_argument("--started-at")

    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("job_id")
    finalize_parser.add_argument("--context")
    finalize_parser.add_argument("--run-id")
    finalize_parser.add_argument("--completed-at")
    finalize_parser.add_argument("--quality-gate", default="passed")
    finalize_parser.add_argument("--status", default="success")
    finalize_parser.add_argument("--lineage-output")
    finalize_parser.add_argument("--health-output")

    refresh_parser = subparsers.add_parser("refresh")
    refresh_parser.add_argument("--now")
    refresh_parser.add_argument("--lineage-output")
    refresh_parser.add_argument("--health-output")

    provenance_parser = subparsers.add_parser("build-provenance")
    provenance_parser.add_argument("--output", required=True)
    provenance_parser.add_argument("--job-id", default="pages-deploy")
    provenance_parser.add_argument("--generated-at")
    provenance_parser.add_argument("--lineage")
    provenance_parser.add_argument("--health")

    args = parser.parse_args()
    root = Path(args.root).resolve()
    registry_path = (
        _path(root, args.registry, root / "config/automation_jobs.json")
        if args.registry
        else root / "config/automation_jobs.json"
    )
    registry = load_registry(root, registry_path)

    if args.command == "check":
        lineage = _path(root, args.lineage, root / "public/data/data_lineage.json")
        health = _path(root, args.health, root / "public/data/pipeline_health.json")
        result = check_control_plane(
            root, registry, lineage_path=lineage, health_path=health
        )
    elif args.command == "start":
        context = make_run_context(
            root,
            registry,
            args.job_id,
            started_at=_datetime_argument(args.started_at),
            run_id=args.run_id,
        )
        if args.output:
            atomic_write_json(_path(root, args.output, root / "run-context.json"), context)
        result = context
    elif args.command == "finalize":
        context_path = _path(root, args.context, root / "run-context.json") if args.context else None
        current, lineage, health = finalize_pipeline(
            root,
            registry,
            args.job_id,
            context=_load_context(context_path),
            run_id=args.run_id,
            quality_gate=args.quality_gate,
            status=args.status,
            completed_at=_datetime_argument(args.completed_at),
            lineage_output=_path(
                root, args.lineage_output, root / "public/data/data_lineage.json"
            ),
            health_output=_path(
                root, args.health_output, root / "public/data/pipeline_health.json"
            ),
        )
        result = {
            "jobId": current["jobId"],
            "runId": current["runId"],
            "completedAt": current["completedAt"],
            "lineageArtifacts": len(lineage["artifacts"]),
            "pipelineStatus": health["overallStatus"],
        }
    elif args.command == "refresh":
        lineage_path = _path(
            root, args.lineage_output, root / "public/data/data_lineage.json"
        )
        health_path = _path(
            root, args.health_output, root / "public/data/pipeline_health.json"
        )
        committed_lineage = load_json(
            root / "public/data/data_lineage.json", required=False
        )
        lineage, health = build_snapshots(
            root,
            registry,
            now=_datetime_argument(args.now),
            previous_lineage=committed_lineage,
        )
        atomic_write_json(lineage_path, lineage)
        atomic_write_json(health_path, health)
        result = {
            "lineageOutput": str(lineage_path),
            "healthOutput": str(health_path),
            "lineageArtifacts": len(lineage["artifacts"]),
            "pipelineStatus": health["overallStatus"],
        }
    elif args.command == "build-provenance":
        payload = build_deployment_provenance(
            root,
            registry,
            output=_path(root, args.output, root / "out/build-provenance.json"),
            job_id=args.job_id,
            generated_at=_datetime_argument(args.generated_at),
            lineage_path=_path(
                root, args.lineage, root / "public/data/data_lineage.json"
            ),
            health_path=_path(
                root, args.health, root / "public/data/pipeline_health.json"
            ),
        )
        result = {
            "output": args.output,
            "sourceSha": payload["sourceSha"],
            "runId": payload["runId"],
        }
    else:
        parser.error(f"unsupported command: {args.command}")
        return 2

    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"PIPELINE_CONTROL_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
