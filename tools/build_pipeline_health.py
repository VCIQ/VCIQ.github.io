#!/usr/bin/env python3
"""Build auditable data-lineage and pipeline-health snapshots.

The control plane never executes crawlers. It observes the repository outputs
declared in ``config/automation_jobs.json``, records immutable content hashes,
resolves the most recent producer metadata, and evaluates freshness against each
job's SLA. Producer workflows call this module only after their existing quality
gates pass, preserving the repository's last-good publication policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "config" / "automation_jobs.json"
DEFAULT_LINEAGE = ROOT / "public" / "data" / "data_lineage.json"
DEFAULT_HEALTH = ROOT / "public" / "data" / "pipeline_health.json"

JOB_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ALLOWED_FAILURE_POLICIES = {"retain-last-good", "fail-closed", "advisory-only"}
ALLOWED_JOB_STATUSES = {"healthy", "stale", "missing", "unknown", "degraded"}
TIMESTAMP_KEYS = (
    "generatedAt",
    "completedAt",
    "updatedAt",
    "refreshedAt",
    "checkedAt",
    "lastVerifiedAt",
)
CONTROL_PLANE_PATHS = {
    "public/data/data_lineage.json",
    "public/data/pipeline_health.json",
}


@dataclass(frozen=True)
class ArtifactOwner:
    job_id: str
    path: str
    required: bool
    shared: bool
    freshness_sla_hours: float


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def isoformat(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def load_json(path: Path, *, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def relative_path(root: Path, raw: str) -> Path:
    path = Path(str(raw))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"repository path must be relative and contained: {raw}")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"repository path escapes root: {raw}") from exc
    return resolved


def _number(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if result <= 0:
        raise ValueError(f"{field} must be positive")
    return result


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{field} must be a list of non-empty strings")
    return [item.strip() for item in value]


def _output_rows(job: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = job.get("outputs", [])
    if not isinstance(rows, list):
        raise ValueError(f"job {job.get('id')} outputs must be a list")
    normalized: list[dict[str, Any]] = []
    for item in rows:
        if isinstance(item, str):
            normalized.append(
                {"path": item, "required": True, "shared": False, "public": True}
            )
            continue
        if not isinstance(item, dict) or not str(item.get("path") or "").strip():
            raise ValueError(f"job {job.get('id')} has invalid output declaration")
        row = {
            "path": str(item["path"]).strip(),
            "required": bool(item.get("required", True)),
            "shared": bool(item.get("shared", False)),
            "public": bool(item.get("public", True)),
        }
        if item.get("freshnessSlaHours") is not None:
            row["freshnessSlaHours"] = _number(
                item.get("freshnessSlaHours"),
                f"{job.get('id')}.{row['path']}.freshnessSlaHours",
            )
        normalized.append(row)
    return normalized


def validate_registry(
    registry: Mapping[str, Any],
    root: Path = ROOT,
    *,
    check_paths: bool = True,
) -> dict[str, Any]:
    if registry.get("schemaVersion") != 1:
        raise ValueError("automation registry schemaVersion must be 1")
    pipeline_version = str(registry.get("pipelineVersion") or "").strip()
    if not pipeline_version:
        raise ValueError("automation registry requires pipelineVersion")

    object_types = registry.get("publicObjectTypes")
    if not isinstance(object_types, list):
        raise ValueError("publicObjectTypes must be a list")
    expected_ids = ["technology", "track", "person", "company"]
    actual_ids = [str(item.get("id") or "") for item in object_types if isinstance(item, dict)]
    if actual_ids != expected_ids:
        raise ValueError(
            "publicObjectTypes must be ordered as technology, track, person, company"
        )
    for item in object_types:
        if not isinstance(item, dict):
            raise ValueError("publicObjectTypes entries must be objects")
        for field in ("id", "label", "route"):
            if not str(item.get(field) or "").strip():
                raise ValueError(f"publicObjectTypes entry requires {field}")

    jobs = registry.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("automation registry requires at least one job")

    by_id: dict[str, dict[str, Any]] = {}
    output_owners: dict[str, list[tuple[str, bool]]] = {}
    normalized_jobs: list[dict[str, Any]] = []

    for raw in jobs:
        if not isinstance(raw, dict):
            raise ValueError("job entries must be objects")
        job = dict(raw)
        job_id = str(job.get("id") or "").strip()
        if not JOB_ID_RE.fullmatch(job_id):
            raise ValueError(f"invalid job id: {job_id!r}")
        if job_id in by_id:
            raise ValueError(f"duplicate job id: {job_id}")

        for field in ("name", "owner", "workflow", "trigger", "qualityGate"):
            if not str(job.get(field) or "").strip():
                raise ValueError(f"job {job_id} requires {field}")

        dependencies = _string_list(job.get("dependencies", []), f"{job_id}.dependencies")
        inputs = _string_list(job.get("inputs", []), f"{job_id}.inputs")
        outputs = _output_rows(job)
        sla = _number(job.get("freshnessSlaHours"), f"{job_id}.freshnessSlaHours")
        timeout = _number(job.get("timeoutMinutes"), f"{job_id}.timeoutMinutes")
        try:
            retry = int(job.get("retry"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{job_id}.retry must be an integer") from exc
        if retry < 0:
            raise ValueError(f"{job_id}.retry must be non-negative")
        failure_policy = str(job.get("failurePolicy") or "")
        if failure_policy not in ALLOWED_FAILURE_POLICIES:
            raise ValueError(f"job {job_id} has invalid failurePolicy")

        workflow = str(job["workflow"]).strip()
        relative_path(root, workflow)
        if check_paths and not relative_path(root, workflow).is_file():
            raise ValueError(f"job {job_id} workflow does not exist: {workflow}")

        for path in [*inputs, *(row["path"] for row in outputs)]:
            relative_path(root, path)
        for output in outputs:
            path = output["path"]
            if path in CONTROL_PLANE_PATHS:
                raise ValueError(
                    f"job {job_id} must not declare recursive control-plane output {path}"
                )
            output_owners.setdefault(path, []).append((job_id, output["shared"]))

        normalized = {
            **job,
            "id": job_id,
            "dependencies": dependencies,
            "inputs": inputs,
            "outputs": outputs,
            "freshnessSlaHours": sla,
            "timeoutMinutes": timeout,
            "retry": retry,
            "failurePolicy": failure_policy,
        }
        by_id[job_id] = normalized
        normalized_jobs.append(normalized)

    for job in normalized_jobs:
        for dependency in job["dependencies"]:
            if dependency not in by_id:
                raise ValueError(
                    f"job {job['id']} references unknown dependency {dependency}"
                )
            if dependency == job["id"]:
                raise ValueError(f"job {job['id']} cannot depend on itself")

    state: dict[str, int] = {}

    def visit(job_id: str, trail: Sequence[str]) -> None:
        marker = state.get(job_id, 0)
        if marker == 2:
            return
        if marker == 1:
            cycle = " -> ".join([*trail, job_id])
            raise ValueError(f"automation dependency cycle: {cycle}")
        state[job_id] = 1
        for dependency in by_id[job_id]["dependencies"]:
            visit(dependency, [*trail, job_id])
        state[job_id] = 2

    for job_id in by_id:
        visit(job_id, [])

    for path, owners in output_owners.items():
        if len(owners) > 1 and not all(shared for _, shared in owners):
            owner_names = ", ".join(job_id for job_id, _ in owners)
            raise ValueError(
                f"shared output {path} must set shared=true for every owner: {owner_names}"
            )

    return {
        **dict(registry),
        "pipelineVersion": pipeline_version,
        "jobs": normalized_jobs,
    }


def load_registry(
    root: Path = ROOT,
    registry_path: Path | None = None,
    *,
    check_paths: bool = True,
) -> dict[str, Any]:
    path = registry_path or (root / "config" / "automation_jobs.json")
    return validate_registry(load_json(path), root, check_paths=check_paths)


def artifact_owners(registry: Mapping[str, Any]) -> dict[str, list[ArtifactOwner]]:
    result: dict[str, list[ArtifactOwner]] = {}
    for job in registry.get("jobs", []):
        if not isinstance(job, dict):
            continue
        for output in _output_rows(job):
            if not output["public"]:
                continue
            owner = ArtifactOwner(
                job_id=str(job["id"]),
                path=str(output["path"]),
                required=bool(output["required"]),
                shared=bool(output["shared"]),
                freshness_sla_hours=float(
                    output.get("freshnessSlaHours", job["freshnessSlaHours"])
                ),
            )
            result.setdefault(owner.path, []).append(owner)
    return result


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def extract_data_timestamp(path: Path) -> datetime | None:
    if path.suffix.lower() != ".json":
        return None
    try:
        payload = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None

    provenance = payload.get("provenance")
    if isinstance(provenance, dict):
        for key in ("completedAt", "generatedAt"):
            parsed = parse_datetime(provenance.get(key))
            if parsed:
                return parsed

    for key in TIMESTAMP_KEYS:
        parsed = parse_datetime(payload.get(key))
        if parsed:
            return parsed

    refresh_audit = payload.get("refreshAudit")
    if isinstance(refresh_audit, dict):
        for key in ("completedAt", "startedAt"):
            parsed = parse_datetime(refresh_audit.get(key))
            if parsed:
                return parsed
    return None


def git_last_change(root: Path, path: str) -> dict[str, str] | None:
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H%x00%cI", "--", path],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        return None
    decoded = result.stdout.decode("utf-8", errors="replace").strip()
    if "\x00" not in decoded:
        return None
    sha, changed_at = decoded.split("\x00", 1)
    if not sha or not parse_datetime(changed_at):
        return None
    return {"sha": sha, "changedAt": isoformat(parse_datetime(changed_at) or utc_now())}


def _producer_from_git(
    root: Path,
    artifact_path: str,
    owner_job_ids: list[str],
) -> dict[str, Any]:
    git_info = git_last_change(root, artifact_path)
    code_sha = (
        git_info["sha"]
        if git_info
        else os.environ.get("GITHUB_SHA", "").strip() or "unknown"
    )
    completed_at = git_info["changedAt"] if git_info else None
    return {
        "jobId": owner_job_ids[0] if len(owner_job_ids) == 1 else "shared-producer",
        "runId": f"git:{code_sha}" if code_sha != "unknown" else "unknown",
        "codeSha": code_sha,
        "sourceRef": os.environ.get("GITHUB_REF", "").strip() or "repository-history",
        "completedAt": completed_at,
        "qualityGate": "committed-last-good",
        "status": "success" if code_sha != "unknown" else "unknown",
    }


def _preserved_producer(
    previous_lineage: Mapping[str, Any],
    path: str,
    content_sha: str,
) -> dict[str, Any] | None:
    artifacts = previous_lineage.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    record = artifacts.get(path)
    if not isinstance(record, dict) or record.get("contentSha256") != content_sha:
        return None
    producer = record.get("producer")
    return dict(producer) if isinstance(producer, dict) else None


def _artifact_status(
    data_timestamp: datetime | None,
    now: datetime,
    sla_hours: float,
) -> tuple[str, float | None]:
    if data_timestamp is None:
        return "unknown", None
    age_hours = max(0.0, (now - data_timestamp).total_seconds() / 3600)
    return ("stale" if age_hours > sla_hours else "healthy"), round(age_hours, 2)


def build_snapshots(
    root: Path,
    registry: Mapping[str, Any],
    *,
    now: datetime | None = None,
    current_run: Mapping[str, Any] | None = None,
    previous_lineage: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    observed_at = (now or utc_now()).astimezone(UTC).replace(microsecond=0)
    previous = (
        dict(previous_lineage)
        if isinstance(previous_lineage, Mapping)
        else load_json(root / "public/data/data_lineage.json", required=False)
    )
    owners_by_path = artifact_owners(registry)
    artifacts: dict[str, Any] = {}
    current_job_id = str((current_run or {}).get("jobId") or "")
    current_outputs = {
        output["path"]
        for job in registry["jobs"]
        if job["id"] == current_job_id
        for output in job["outputs"]
    }

    for artifact_path in sorted(owners_by_path):
        owners = owners_by_path[artifact_path]
        absolute = relative_path(root, artifact_path)
        owner_ids = [owner.job_id for owner in owners]
        required = any(owner.required for owner in owners)
        sla = min(owner.freshness_sla_hours for owner in owners)

        if not absolute.exists():
            artifacts[artifact_path] = {
                "artifactId": f"artifact:{artifact_path}",
                "ownerJobIds": owner_ids,
                "required": required,
                "shared": len(owner_ids) > 1,
                "status": "missing",
                "contentSha256": None,
                "bytes": None,
                "dataTimestamp": None,
                "ageHours": None,
                "freshnessSlaHours": sla,
                "producer": None,
            }
            continue

        content_sha, size = sha256_file(absolute)
        data_timestamp = extract_data_timestamp(absolute)
        preserved = _preserved_producer(previous, artifact_path, content_sha)

        if current_run and artifact_path in current_outputs:
            producer = {
                "jobId": current_job_id,
                "runId": str(current_run.get("runId") or "unknown"),
                "codeSha": str(current_run.get("codeSha") or "unknown"),
                "sourceRef": str(current_run.get("sourceRef") or "unknown"),
                "completedAt": current_run.get("completedAt"),
                "qualityGate": str(current_run.get("qualityGate") or "unknown"),
                "status": str(current_run.get("status") or "unknown"),
            }
        elif preserved:
            producer = preserved
        else:
            producer = _producer_from_git(root, artifact_path, owner_ids)

        producer_time = parse_datetime(producer.get("completedAt"))
        effective_timestamp = data_timestamp or producer_time
        status, age_hours = _artifact_status(effective_timestamp, observed_at, sla)
        if producer.get("status") not in {"success", "unknown"}:
            status = "degraded"

        artifacts[artifact_path] = {
            "artifactId": f"artifact:{artifact_path}",
            "ownerJobIds": owner_ids,
            "required": required,
            "shared": len(owner_ids) > 1,
            "status": status,
            "contentSha256": content_sha,
            "bytes": size,
            "dataTimestamp": isoformat(effective_timestamp)
            if effective_timestamp
            else None,
            "ageHours": age_hours,
            "freshnessSlaHours": sla,
            "producer": producer,
        }

    lineage = {
        "schemaVersion": 1,
        "pipelineVersion": registry["pipelineVersion"],
        "generatedAt": isoformat(observed_at),
        "repository": os.environ.get("GITHUB_REPOSITORY", "").strip()
        or "VCIQ/VCIQ.github.io",
        "artifacts": artifacts,
    }

    jobs: list[dict[str, Any]] = []
    for job in registry["jobs"]:
        output_paths = [
            output["path"] for output in job["outputs"] if output.get("public", True)
        ]
        rows = [artifacts[path] for path in output_paths if path in artifacts]
        required_rows = [row for row in rows if row.get("required", True)]
        required_statuses = [str(row["status"]) for row in required_rows]
        present_statuses = [
            str(row["status"]) for row in rows if row.get("status") != "missing"
        ]
        if any(status == "missing" for status in required_statuses):
            job_status = "missing"
        elif any(status == "degraded" for status in present_statuses):
            job_status = "degraded"
        elif any(status == "stale" for status in present_statuses):
            job_status = "stale"
        elif required_statuses and all(
            status == "healthy" for status in required_statuses
        ):
            job_status = "healthy"
        elif present_statuses and all(status == "healthy" for status in present_statuses):
            job_status = "healthy"
        else:
            job_status = "unknown"

        completed_values = [
            parse_datetime(
                row.get("producer", {}).get("completedAt")
                if isinstance(row.get("producer"), dict)
                else None
            )
            or parse_datetime(row.get("dataTimestamp"))
            for row in rows
        ]
        completed_values = [value for value in completed_values if value]
        jobs.append(
            {
                "jobId": job["id"],
                "name": job["name"],
                "owner": job["owner"],
                "workflow": job["workflow"],
                "trigger": job["trigger"],
                "schedule": job.get("schedule"),
                "dependencies": job["dependencies"],
                "freshnessSlaHours": job["freshnessSlaHours"],
                "timeoutMinutes": job["timeoutMinutes"],
                "failurePolicy": job["failurePolicy"],
                "qualityGate": job["qualityGate"],
                "status": job_status,
                "lastCompletedAt": isoformat(max(completed_values))
                if completed_values
                else None,
                "artifacts": [
                    {
                        "path": path,
                        "status": artifacts[path]["status"],
                        "ageHours": artifacts[path]["ageHours"],
                        "dataTimestamp": artifacts[path]["dataTimestamp"],
                    }
                    for path in output_paths
                    if path in artifacts
                ],
            }
        )

    status_by_id = {job["jobId"]: job["status"] for job in jobs}
    for job_row, job_config in zip(jobs, registry["jobs"], strict=True):
        if job_config.get("healthMode") != "dependencies":
            continue
        dependency_statuses = [
            status_by_id.get(dependency, "unknown")
            for dependency in job_config["dependencies"]
        ]
        if any(status in {"missing", "degraded"} for status in dependency_statuses):
            derived_status = "degraded"
        elif any(status == "stale" for status in dependency_statuses):
            derived_status = "stale"
        elif dependency_statuses and all(
            status == "healthy" for status in dependency_statuses
        ):
            derived_status = "healthy"
        else:
            derived_status = "unknown"
        job_row["status"] = derived_status
        job_row["healthDerivedFrom"] = list(job_config["dependencies"])
        status_by_id[job_row["jobId"]] = derived_status

    job_statuses = [
        job_row["status"]
        for job_row, job_config in zip(jobs, registry["jobs"], strict=True)
        if job_config.get("failurePolicy") != "advisory-only"
    ]
    if any(status in {"missing", "degraded"} for status in job_statuses):
        overall = "degraded"
    elif any(status == "stale" for status in job_statuses):
        overall = "stale"
    elif job_statuses and all(status == "healthy" for status in job_statuses):
        overall = "healthy"
    else:
        overall = "unknown"

    health = {
        "schemaVersion": 1,
        "pipelineVersion": registry["pipelineVersion"],
        "generatedAt": isoformat(observed_at),
        "overallStatus": overall,
        "summary": {
            "jobCount": len(jobs),
            "healthyJobs": sum(job["status"] == "healthy" for job in jobs),
            "staleJobs": sum(job["status"] == "stale" for job in jobs),
            "missingJobs": sum(job["status"] == "missing" for job in jobs),
            "degradedJobs": sum(job["status"] == "degraded" for job in jobs),
            "unknownJobs": sum(job["status"] == "unknown" for job in jobs),
            "artifactCount": len(artifacts),
        },
        "jobs": jobs,
    }
    return lineage, health


def validate_lineage_snapshot(
    lineage: Mapping[str, Any], registry: Mapping[str, Any]
) -> None:
    if lineage.get("schemaVersion") != 1:
        raise ValueError("data lineage schemaVersion must be 1")
    if lineage.get("pipelineVersion") != registry.get("pipelineVersion"):
        raise ValueError("data lineage pipelineVersion does not match registry")
    artifacts = lineage.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("data lineage artifacts must be an object")


def validate_health_snapshot(
    health: Mapping[str, Any], registry: Mapping[str, Any]
) -> None:
    if health.get("schemaVersion") != 1:
        raise ValueError("pipeline health schemaVersion must be 1")
    if health.get("pipelineVersion") != registry.get("pipelineVersion"):
        raise ValueError("pipeline health pipelineVersion does not match registry")
    if health.get("overallStatus") not in ALLOWED_JOB_STATUSES:
        raise ValueError("pipeline health has invalid overallStatus")
    jobs = health.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("pipeline health jobs must be a list")
    expected = {str(job["id"]) for job in registry["jobs"]}
    actual = {
        str(job.get("jobId"))
        for job in jobs
        if isinstance(job, dict) and job.get("jobId")
    }
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"pipeline health job coverage mismatch: missing={missing}, extra={extra}")
    for job in jobs:
        if not isinstance(job, dict) or job.get("status") not in ALLOWED_JOB_STATUSES:
            raise ValueError("pipeline health job has invalid status")


def write_snapshots(
    root: Path,
    registry: Mapping[str, Any],
    *,
    lineage_output: Path,
    health_output: Path,
    now: datetime | None = None,
    current_run: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    previous = load_json(lineage_output, required=False)
    lineage, health = build_snapshots(
        root,
        registry,
        now=now,
        current_run=current_run,
        previous_lineage=previous,
    )
    atomic_write_json(lineage_output, lineage)
    atomic_write_json(health_output, health)
    return lineage, health


def _parse_now(raw: str | None) -> datetime | None:
    if not raw:
        return None
    parsed = parse_datetime(raw)
    if not parsed:
        raise ValueError(f"invalid --now timestamp: {raw}")
    return parsed


def _read_run_context(path: Path | None) -> dict[str, Any] | None:
    return load_json(path) if path else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--lineage-output", type=Path)
    parser.add_argument("--health-output", type=Path)
    parser.add_argument("--run-context", type=Path)
    parser.add_argument("--now")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    registry_path = (
        args.registry.resolve()
        if args.registry
        else root / "config" / "automation_jobs.json"
    )
    registry = load_registry(root, registry_path)
    lineage_output = (
        args.lineage_output.resolve()
        if args.lineage_output
        else root / "public" / "data" / "data_lineage.json"
    )
    health_output = (
        args.health_output.resolve()
        if args.health_output
        else root / "public" / "data" / "pipeline_health.json"
    )

    if args.check:
        validate_lineage_snapshot(load_json(lineage_output), registry)
        validate_health_snapshot(load_json(health_output), registry)
        print(
            json.dumps(
                {
                    "valid": True,
                    "pipelineVersion": registry["pipelineVersion"],
                    "jobs": len(registry["jobs"]),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return 0

    lineage, health = write_snapshots(
        root,
        registry,
        lineage_output=lineage_output,
        health_output=health_output,
        now=_parse_now(args.now),
        current_run=_read_run_context(args.run_context),
    )
    print(
        json.dumps(
            {
                "lineageArtifacts": len(lineage["artifacts"]),
                "pipelineStatus": health["overallStatus"],
                "lineageOutput": str(lineage_output),
                "healthOutput": str(health_output),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
