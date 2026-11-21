"""Explicit, offline shadow batch/storage commands. No browser or production write."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

from .batch import ROOT, MAX_FILE, MAX_LINE, decode, private_root, read_batch, read_private, seal_batch
from .contracts import ContractError, assert_safe, digest, validate
from .guard import GuardError, assert_unchanged, output_path, protected_snapshot, runtime_paths
from .ingest import import_from_path
from .retention import retain
from .signal_store import SignalStore, StoreError


def input_json(root, value, roots, *, maximum=MAX_FILE):
    path = Path(value)
    try:
        relative = path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
    except ValueError:
        raise GuardError("input_outside_state") from None
    return decode(read_private(root, relative, roots, maximum=maximum))


def checkpoint_results(root, jobs, roots):
    """One read-only SQLite snapshot; never claim/finish/rewrite scheduler state."""
    path = output_path(root, "state.sqlite3", repo_roots=roots)
    if not path.is_file(): raise StoreError("checkpoint_database_missing")
    if os.name == "posix" and path.stat().st_mode & 0o077:
        raise GuardError("private_database_permissions_required")
    db = sqlite3.connect("file:" + quote(str(path), safe="/") + "?mode=ro", uri=True, timeout=5)
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("BEGIN")
        results = []
        for job in jobs:
            meta = db.execute("SELECT result_hash,length(result) FROM social_query_results WHERE attempt_id=?", (job["attemptId"],)).fetchone()
            if not meta: raise StoreError("checkpoint_result_missing")
            if meta[1] > 4 * 1024 * 1024: raise StoreError("checkpoint_result_too_large")
            raw = db.execute("SELECT result FROM social_query_results WHERE attempt_id=?", (job["attemptId"],)).fetchone()[0]
            result = decode(raw.encode())
            if digest(result) != meta[0]: raise StoreError("checkpoint_checksum")
            results.append(result)
        return results
    finally:
        db.close()


def prepare_rows(plan, results):
    validate(plan, expected_kind="job_plan")
    if not isinstance(results, list) or len(results) != len(plan["jobs"]):
        raise StoreError("plan_results_incomplete")
    receipts, observations = [], []
    for result in results:
        if not isinstance(result, dict) or set(result) != {"receipt", "observations", "hints", "diagnostics"} or not isinstance(result["observations"], list):
            raise StoreError("worker_result_shape")
        assert_safe(result)
        receipts.append(result["receipt"])
        observations.extend(result["observations"])
    # Index hints/worker diagnostics remain in their original private checkpoints.
    # They are not promoted to normalized observations by this exporter.
    return plan["jobs"], receipts, observations


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    seal = sub.add_parser("seal")
    seal.add_argument("--plan", required=True)
    source = seal.add_mutually_exclusive_group(required=True)
    source.add_argument("--results")
    source.add_argument("--from-checkpoints", action="store_true")
    seal.add_argument("--output", required=True, help="Relative new batch directory under private state")
    seal.add_argument("--created-at")
    verify = sub.add_parser("verify")
    verify.add_argument("--batch", required=True)
    ingest = sub.add_parser("import")
    ingest.add_argument("--batch", required=True)
    ingest.add_argument("--apply", action="store_true", help="Without this flag, verify only")
    inspect = sub.add_parser("inspect")
    pin = sub.add_parser("pin")
    pin.add_argument("--reference", required=True)
    pin.add_argument("--signal-id", required=True)
    pin.add_argument("--content-hash", required=True)
    retention = sub.add_parser("retain")
    retention.add_argument("--before", required=True)
    retention.add_argument("--apply", action="store_true")
    retention.add_argument("--plan-hash")
    for command in (seal, verify, ingest, inspect, pin, retention):
        command.add_argument("--state-dir", type=Path, required=True)
        command.add_argument("--runtime-config", type=Path, required=True)
    args = parser.parse_args(argv)
    before = None
    try:
        root = private_root(args.state_dir, (ROOT,))
        runtime = validate(input_json(root, args.runtime_config, (ROOT,), maximum=MAX_LINE), expected_kind="runtime_config")
        roots = (ROOT,) + ((Path(runtime["mediacrawlerDir"]),) if runtime["mediacrawlerDir"] else ())
        if runtime_paths(runtime, repo_root=ROOT, runtime_file=args.runtime_config) != root:
            raise GuardError("state_directory_mismatch")
        before = protected_snapshot(ROOT)
        if args.command == "seal":
            plan = validate(input_json(root, args.plan, roots), expected_kind="job_plan")
            results = checkpoint_results(root, plan["jobs"], roots) if args.from_checkpoints else input_json(root, args.results, roots)
            rows = prepare_rows(plan, results)
            created = args.created_at
            target = output_path(root, args.output + "/manifest.json", repo_roots=roots)
            if created is None and target.exists():
                created = read_batch(root, args.output, repo_roots=roots).manifest["createdAt"]
            bundle = seal_batch(root, args.output, *rows, repo_roots=roots, created_at=created)
            result = {"ok": True, "sealed": True, "manifestHash": bundle.fingerprint, "counts": bundle.manifest["counts"], "batchIntegrityChecked": True}
        elif args.command in {"verify", "import"}:
            if args.command == "import" and args.apply:
                result = import_from_path(root, args.batch, repo_roots=roots)
            else:
                bundle = read_batch(root, args.batch, repo_roots=roots)
                result = {"ok": True, "applied": False, "counts": bundle.manifest["counts"], "manifestHash": bundle.fingerprint, "batchIntegrityChecked": True}
        else:
            readonly = args.command == "inspect" or args.command == "retain" and not args.apply
            with SignalStore(root, repo_roots=roots, readonly=readonly) as store:
                if args.command == "inspect":
                    result = {"ok": True, "counts": store.counts(), "writesPerformed": False}
                elif args.command == "pin":
                    changed = store.pin_evidence(args.reference, args.signal_id, args.content_hash)
                    result = {"ok": True, "pinned": True, "changed": changed}
                else:
                    result = retain(store, args.before, apply=args.apply, expected_plan_hash=args.plan_hash)
        assert_unchanged(before, repo_root=ROOT)
        print(json.dumps({"mode": "shadow", "publish": False, "liveExecuted": False, **result}, ensure_ascii=False, sort_keys=True))
        return 0 if result["ok"] else 1
    except (ContractError, GuardError) as exc:
        code = exc.code
    except Exception:
        code = "storage_input_or_io_error"
    if before is not None:
        try:
            assert_unchanged(before, repo_root=ROOT)
        except GuardError:
            code = "production_modified"
    print(json.dumps({"ok": False, "error": code, "mode": "shadow", "publish": False, "liveExecuted": False}), file=sys.stderr)
    return 2


if __name__ == "__main__": raise SystemExit(main())
