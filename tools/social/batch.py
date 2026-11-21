"""Sealed, bounded shadow batches. Hashes prove integrity, not source authenticity.

No import-time I/O. Inputs and outputs stay under an explicit private state root.
The existing production source-replacement pipeline is never called.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .contracts import ContractError, canonical_bytes, digest, validate
from .guard import GuardError, output_path, state_path
from .scheduler import instant

FILES = {"jobs.jsonl": "crawl_job", "observations.jsonl": "signal_observation",
         "query_receipts.jsonl": "query_receipt"}
MAX_JOBS = 200
MAX_ROWS = 40000
MAX_LINE = 512 * 1024
MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[2]


class BatchError(ContractError):
    pass


def decode(raw: bytes):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise BatchError("batch_duplicate_json_key")
            result[key] = value
        return result
    def constant(_):
        raise BatchError("batch_nonfinite_json")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise BatchError("batch_invalid_json") from None


def private_root(state_dir, repo_roots):
    root = state_path(state_dir, repo_roots=repo_roots)
    if not root.is_dir():
        raise GuardError("private_state_directory_required")
    if os.name == "posix" and root.stat().st_mode & 0o077:
        raise GuardError("private_state_permissions_required")
    return root


def read_private(root, relative, roots, *, maximum=MAX_FILE):
    path = output_path(root, relative, repo_roots=roots)
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise GuardError("batch_regular_private_file_required")
            if os.name == "posix" and before.st_mode & 0o077:
                raise GuardError("private_file_permissions_required")
            if before.st_size > maximum:
                raise BatchError("batch_file_too_large")
            raw = stream.read(maximum + 1)
            after = os.fstat(stream.fileno())
            if len(raw) > maximum:
                raise BatchError("batch_file_too_large")
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise BatchError("batch_changed_during_read")
            return raw
    except OSError:
        raise BatchError("batch_file_unavailable") from None


def write_private(root, relative, raw, roots):
    path = output_path(root, relative, repo_roots=roots)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output_path(root, relative, repo_roots=roots)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def cross_validate(manifest, jobs, receipts, observations):
    """Validate identities, references, counts, budgets and time across all files."""
    if not 1 <= len(jobs) <= MAX_JOBS or len(receipts) != len(jobs) or len(observations) > MAX_ROWS:
        raise BatchError("batch_record_limit")
    if manifest["counts"] != {"jobs": len(jobs), "receipts": len(receipts), "observations": len(observations)}:
        raise BatchError("batch_manifest_counts")
    attempts, receipt_map = {}, {}
    for job in jobs:
        validate(job, expected_kind="crawl_job")
        if job["attemptId"] in attempts:
            raise BatchError("batch_duplicate_job")
        if any(type(value) is not int for value in job["limits"].values()):
            raise BatchError("batch_integer_required")
        attempts[job["attemptId"]] = job
    if len({job["jobId"] for job in jobs}) != len(jobs):
        raise BatchError("batch_duplicate_job_identity")
    for key in ("vciqCommit", "configHash", "policyVersion"):
        if len({job[key] for job in jobs}) != 1:
            raise BatchError("batch_mixed_configuration")
    for receipt in receipts:
        validate(receipt, expected_kind="query_receipt")
        attempt = receipt["attemptId"]
        if attempt in receipt_map or attempt not in attempts:
            raise BatchError("batch_receipt_reference")
        job = attempts[attempt]
        if any(receipt[key] != job[key] for key in ("jobId", "queryId", "runId", "platform", "provider", "upstreamCommit")):
            raise BatchError("batch_receipt_job_mismatch")
        if any(type(value) is not int for value in receipt["counts"].values()):
            raise BatchError("batch_integer_required")
        pages = receipt["pageReceipts"]
        if any(type(p["pageIndex"]) is not int or type(p["contentItems"]) is not int for p in pages):
            raise BatchError("batch_integer_required")
        if len(pages) > job["limits"]["maxSearchPages"] or [p["pageIndex"] for p in pages] != list(range(1, len(pages) + 1)):
            raise BatchError("batch_page_budget_or_order")
        if receipt["counts"]["rawRows"] > job["limits"]["maxRecords"]:
            raise BatchError("batch_record_budget")
        if instant(receipt["completedAt"]) > instant(manifest["createdAt"]):
            raise BatchError("batch_sealed_before_completion")
        receipt_map[attempt] = receipt
    seen, observed_counts = set(), Counter()
    for observation in observations:
        validate(observation, expected_kind="signal_observation")
        attempt = observation["attemptId"]
        if attempt not in attempts or attempt not in receipt_map:
            raise BatchError("batch_observation_reference")
        job, receipt = attempts[attempt], receipt_map[attempt]
        if any(observation[key] != job[key] for key in ("jobId", "queryId", "runId", "platform")) or observation["trackRefs"] != job["trackRefs"]:
            raise BatchError("batch_observation_job_mismatch")
        if not set(observation["matchedTerms"]).issubset(observation["queryTerms"]):
            raise BatchError("batch_matched_terms")
        window = job["window"]
        day = observation["publishedAt"][:10] if observation["publishedAt"] else None
        if window["filterMode"] == "post_filter" and (not day or window["from"] and day < window["from"] or window["to"] and day > window["to"]):
            raise BatchError("batch_publication_window")
        identity = (attempt, observation["signalId"])
        if identity in seen:
            raise BatchError("batch_duplicate_observation")
        seen.add(identity)
        observed_counts[attempt] += 1
        if not instant(receipt["startedAt"]) <= instant(observation["observedAt"]) <= instant(receipt["completedAt"]):
            raise BatchError("batch_observation_time")
    for attempt, receipt in receipt_map.items():
        if observed_counts[attempt] != receipt["counts"]["emittedRows"]:
            raise BatchError("batch_emitted_count")
    if any(row["runId"] != manifest["runId"] for rows in (jobs, receipts, observations) for row in rows):
        raise BatchError("batch_run_mismatch")


@dataclass(frozen=True)
class VerifiedBatch:
    """Immutable bytes; public import APIs revalidate them, not this type alone."""
    manifest_bytes: bytes
    payloads: tuple[tuple[str, bytes], ...]

    @property
    def manifest(self):
        return decode(self.manifest_bytes)

    @property
    def fingerprint(self):
        return digest(self.manifest)

    def records(self, filename):
        return [decode(line) for line in dict(self.payloads)[filename].splitlines()]


def verify_payloads(manifest_raw, payloads):
    if not isinstance(manifest_raw, bytes) or len(manifest_raw) > MAX_LINE or set(payloads) != set(FILES):
        raise BatchError("batch_file_set")
    if any(not isinstance(raw, bytes) or len(raw) > MAX_FILE for raw in payloads.values()) or sum(map(len, payloads.values())) > MAX_TOTAL:
        raise BatchError("batch_file_too_large")
    manifest = validate(decode(manifest_raw), expected_kind="run_manifest")
    if any(type(v) is not int for v in manifest["counts"].values()):
        raise BatchError("batch_integer_required")
    meta = {row["path"]: row for row in manifest["files"]}
    parsed = {}
    for name, kind in FILES.items():
        raw, expected = payloads[name], meta[name]
        if any(type(expected[key]) is not int for key in ("bytes", "rows")):
            raise BatchError("batch_integer_required")
        if len(raw) != expected["bytes"] or hashlib.sha256(raw).hexdigest() != expected["sha256"]:
            raise BatchError("batch_checksum_mismatch")
        if raw and not raw.endswith(b"\n"):
            raise BatchError("batch_truncated_jsonl")
        lines = raw.split(b"\n")[:-1] if raw else []
        limit = MAX_ROWS if kind == "signal_observation" else MAX_JOBS
        if len(lines) != expected["rows"] or len(lines) > limit:
            raise BatchError("batch_row_count")
        if any(not line.strip() or len(line) > MAX_LINE for line in lines):
            raise BatchError("batch_jsonl_line")
        parsed[name] = [validate(decode(line), expected_kind=kind) for line in lines]
    cross_validate(manifest, parsed["jobs.jsonl"], parsed["query_receipts.jsonl"], parsed["observations.jsonl"])
    return VerifiedBatch(canonical_bytes(manifest), tuple((name, payloads[name]) for name in sorted(FILES)))


def build_batch(jobs, receipts, observations, *, created_at=None):
    if not isinstance(jobs, list) or not jobs or len(jobs) > MAX_JOBS or not isinstance(receipts, list) or not isinstance(observations, list) or len(receipts) > MAX_JOBS or len(observations) > MAX_ROWS:
        raise BatchError("batch_record_limit")
    payloads, total = {}, 0
    for name, rows in (("jobs.jsonl", jobs), ("query_receipts.jsonl", receipts), ("observations.jsonl", observations)):
        encoded, size = [], 0
        for row in rows:
            line = canonical_bytes(validate(row, expected_kind=FILES[name]))
            if len(line) > MAX_LINE:
                raise BatchError("batch_jsonl_line")
            size += len(line) + 1
            if size > MAX_FILE or total + size > MAX_TOTAL:
                raise BatchError("batch_file_too_large")
            encoded.append(line)
        payloads[name] = b"".join(line + b"\n" for line in sorted(encoded))
        total += size
    manifest = {"schemaVersion": 1, "kind": "run_manifest", "runId": jobs[0]["runId"],
        "mode": "shadow", "sealed": True, "createdAt": created_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "files": [{"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                   "rows": len(raw.splitlines())} for name, raw in sorted(payloads.items())],
        "counts": {"jobs": len(jobs), "receipts": len(receipts), "observations": len(observations)},
        "privacyClass": "sanitized-shadow", "publication": "forbidden"}
    return verify_payloads(canonical_bytes(manifest), payloads)


def read_batch(state_dir, relative, *, repo_roots=(ROOT,)):
    root = private_root(state_dir, repo_roots)
    manifest_path = output_path(root, relative + "/manifest.json", repo_roots=repo_roots)
    directory = manifest_path.parent
    if not directory.is_dir():
        raise BatchError("batch_unsealed")
    if os.name == "posix" and directory.stat().st_mode & 0o077:
        raise GuardError("private_batch_permissions_required")
    if {p.name for p in directory.iterdir()} != set(FILES) | {"manifest.json"}:
        raise BatchError("batch_file_set")
    raw = read_private(root, relative + "/manifest.json", repo_roots, maximum=MAX_LINE)
    payloads, total = {}, 0
    for name in FILES:
        payloads[name] = read_private(root, relative + "/" + name, repo_roots, maximum=min(MAX_FILE, MAX_TOTAL - total))
        total += len(payloads[name])
    return verify_payloads(raw, payloads)


def seal_batch(state_dir, relative, jobs, receipts, observations, *, repo_roots=(ROOT,), created_at=None):
    # Validate before creating any output. A failed staged write never looks sealed.
    bundle = build_batch(jobs, receipts, observations, created_at=created_at)
    root = private_root(state_dir, repo_roots)
    target = output_path(root, relative + "/manifest.json", repo_roots=repo_roots).parent
    if target.exists():
        previous = read_batch(root, relative, repo_roots=repo_roots)
        if previous.fingerprint != bundle.fingerprint:
            raise BatchError("batch_destination_conflict")
        return previous
    staging = relative + ".staging-" + str(uuid4())
    for name, raw in bundle.payloads:
        write_private(root, staging + "/" + name, raw, repo_roots)
    write_private(root, staging + "/manifest.json", bundle.manifest_bytes + b"\n", repo_roots)
    checked = read_batch(root, staging, repo_roots=repo_roots)
    stage = output_path(root, staging + "/manifest.json", repo_roots=repo_roots).parent
    if target.exists():
        raise BatchError("batch_destination_conflict")
    os.rename(stage, target)
    if os.name == "posix":
        fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return checked
