"""Sealed, bounded, sanitized local batches. Hashes prove integrity, not origin."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .contracts import ContractError, canonical_bytes, digest, validate
from .guard import GuardError, output_path, state_path
from .scheduler import instant

FILES = {"jobs.jsonl": "crawl_job", "observations.jsonl": "signal_observation", "query_receipts.jsonl": "query_receipt"}
MAX_FILE = 32 * 1024 * 1024
MAX_LINE = 1024 * 1024
MAX_ROWS = 20000


def parse_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ContractError("duplicate_key")
            value[key] = item
        return value
    def bad(_):
        raise ContractError("non_finite_number")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=bad)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError("invalid_batch_json") from None


def _read(path, *, limit=MAX_FILE):
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise GuardError("batch_symlink")
    stat = path.stat()
    if not path.is_file() or stat.st_nlink != 1 or stat.st_size > limit:
        raise ContractError("batch_file_bounds")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ContractError("batch_file_bounds")
    return raw


def decode_rows(raw, kind):
    if raw and not raw.endswith(b"\n"):
        raise ContractError("truncated_jsonl")
    lines = raw.splitlines()
    if len(lines) > MAX_ROWS or any(not line or len(line) > MAX_LINE for line in lines):
        raise ContractError("batch_row_bounds")
    return [validate(parse_json(line), expected_kind=kind) for line in lines]


def validate_links(jobs, observations, receipts, *, run_id=None):
    if not jobs or len(jobs) != len(receipts):
        raise ContractError("batch_receipt_count")
    for row in jobs:
        validate(row, expected_kind="crawl_job")
    for row in receipts:
        validate(row, expected_kind="query_receipt")
    for row in observations:
        validate(row, expected_kind="signal_observation")
    job_map = {job["attemptId"]: job for job in jobs}
    receipt_map = {row["attemptId"]: row for row in receipts}
    if len(job_map) != len(jobs) or len(receipt_map) != len(receipts) or set(job_map) != set(receipt_map):
        raise ContractError("batch_attempt_identity")
    selected_run = run_id or jobs[0]["runId"]
    counts, identities = Counter(), set()
    for attempt, job in job_map.items():
        receipt = receipt_map[attempt]
        if job["runId"] != selected_run or any(job[key] != receipt[key] for key in ("jobId", "queryId", "runId", "platform", "provider", "upstreamCommit")):
            raise ContractError("batch_receipt_link")
        if len(receipt["pageReceipts"]) > job["limits"]["maxSearchPages"] or receipt["counts"]["emittedRows"] > job["limits"]["maxRecords"]:
            raise ContractError("batch_job_budget")
        pages = [p["pageIndex"] for p in receipt["pageReceipts"]]
        if pages != list(range(1, len(pages) + 1)):
            raise ContractError("batch_page_order")
    for row in observations:
        job = job_map.get(row["attemptId"])
        if job is None or any(job[key] != row[key] for key in ("jobId", "queryId", "runId", "platform", "trackRefs")):
            raise ContractError("batch_observation_link")
        key = (row["attemptId"], row["signalId"])
        if key in identities:
            raise ContractError("batch_duplicate_observation")
        identities.add(key)
        receipt = receipt_map[row["attemptId"]]
        if not instant(receipt["startedAt"]) <= instant(row["observedAt"]) <= instant(receipt["completedAt"]):
            raise ContractError("batch_observation_time")
        counts[row["attemptId"]] += 1
    if any(counts[key] != receipt["counts"]["emittedRows"] for key, receipt in receipt_map.items()):
        raise ContractError("batch_emitted_count")
    return selected_run


def read_batch(directory):
    directory = Path(directory)
    if not directory.is_absolute() or not directory.is_dir() or any(p.is_symlink() for p in (directory, *directory.parents)):
        raise GuardError("batch_directory")
    if {item.name for item in directory.iterdir()} != set(FILES) | {"manifest.json"}:
        raise ContractError("batch_file_allowlist")
    manifest_bytes = _read(directory / "manifest.json", limit=1024 * 1024)
    manifest = validate(parse_json(manifest_bytes), expected_kind="run_manifest")
    entries = {entry["path"]: entry for entry in manifest["files"]}
    data = {}
    for name, kind in FILES.items():
        raw = _read(directory / name)
        entry = entries[name]
        if entry["bytes"] != len(raw) or entry["sha256"] != hashlib.sha256(raw).hexdigest():
            raise ContractError("batch_integrity")
        rows = decode_rows(raw, kind)
        if len(rows) != entry["rows"]:
            raise ContractError("batch_row_count")
        data[name] = rows
    validate_links(data["jobs.jsonl"], data["observations.jsonl"], data["query_receipts.jsonl"], run_id=manifest["runId"])
    return {"manifest": manifest, "batchHash": hashlib.sha256(manifest_bytes).hexdigest(),
            "jobs": data["jobs.jsonl"], "observations": data["observations.jsonl"], "receipts": data["query_receipts.jsonl"]}


def seal_batch(state_dir, jobs, observations, receipts, *, roots, now=None):
    run_id = validate_links(jobs, observations, receipts)
    root = state_path(state_dir, repo_roots=roots)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix" and root.stat().st_mode & 0o077:
        raise GuardError("private_state_permissions_required")
    values = {"jobs.jsonl": jobs, "observations.jsonl": observations, "query_receipts.jsonl": receipts}
    encoded = {name: b"".join(canonical_bytes(row) + b"\n" for row in rows) for name, rows in values.items()}
    if any(len(raw) > MAX_FILE for raw in encoded.values()):
        raise ContractError("batch_file_bounds")
    suffix = digest(sorted(job["attemptId"] for job in jobs))[:20]
    relative = f"batches/{run_id}-{suffix}"
    probe = output_path(root, relative + "/manifest.json", repo_roots=roots)
    destination = probe.parent
    if destination.exists():
        existing = read_batch(destination)
        if existing["jobs"] != jobs or existing["observations"] != observations or existing["receipts"] != receipts:
            raise ContractError("sealed_batch_conflict")
        return destination
    stage = output_path(root, f"batches/.staging-{uuid4()}/manifest.json", repo_roots=roots).parent
    stage.mkdir(mode=0o700, parents=True, exist_ok=False)
    metadata = []
    try:
        for name, raw in encoded.items():
            decode_rows(raw, FILES[name])
            fd = os.open(stage / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            metadata.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "rows": len(values[name])})
        manifest = {"schemaVersion": 1, "kind": "run_manifest", "runId": run_id, "mode": "shadow", "sealed": True,
            "createdAt": (now or datetime.now(UTC)).astimezone(UTC).isoformat(), "files": metadata,
            "counts": {"jobs": len(jobs), "observations": len(observations), "receipts": len(receipts)},
            "privacyClass": "sanitized-shadow", "publication": "forbidden"}
        validate(manifest)
        fd = os.open(stage / "manifest.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical_bytes(manifest) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        read_batch(stage)
        output_path(root, relative + "/manifest.json", repo_roots=roots)
        os.rename(stage, destination)
        if os.name == "posix":
            fd = os.open(destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try: os.fsync(fd)
            finally: os.close(fd)
        return destination
    except BaseException:
        # Only remove our unique newly created staging directory, never user data.
        if stage.exists():
            shutil.rmtree(stage)
        raise
