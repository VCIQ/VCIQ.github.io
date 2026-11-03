"""Local sanitized batch/storage commands; never fetches or publishes."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .batch import read_batch, seal_batch
from .contracts import ContractError, digest, load_json
from .guard import GuardError, output_path, protected_snapshot, assert_unchanged, state_path
from .ingest import ingest_batch
from .retention import collect
from .signal_store import SignalStore
from .wechat_runner import atomic_json

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("seal", "ingest", "inspect", "gc", "backup"))
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--batch", type=Path)
    parser.add_argument("--job", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--upstream-dir", type=Path)
    args = parser.parse_args(argv)
    roots = (ROOT, *([args.upstream_dir] if args.upstream_dir else []))
    before = protected_snapshot(ROOT)
    try:
        root = state_path(args.state_dir, repo_roots=roots)
        if args.command == "seal":
            if args.job is None or args.result is None:
                raise ContractError("job_and_result_required")
            for path in (args.job, args.result):
                relative = path.absolute().relative_to(root).as_posix()
                output_path(root, relative, repo_roots=roots)
            job, execution = load_json(args.job), load_json(args.result)
            path = seal_batch(root, [job], execution["observations"], [execution["receipt"]], roots=roots)
            result = {"ok": True, "batch": path.relative_to(root).as_posix(), "batchIntegrityChecked": True}
        else:
            if args.command == "ingest":
                if args.batch is None:
                    raise ContractError("batch_required")
                # Validate all bytes before opening or creating the content DB.
                try:
                    verified = read_batch(args.batch.absolute())
                except (ContractError, GuardError) as exc:
                    marker = {"status": "quarantined", "error": exc.code, "inputPathHash": digest(str(args.batch))}
                    atomic_json(root, "quarantine/" + digest(marker) + ".json", marker, roots=roots)
                    raise
            with SignalStore(root, repo_roots=roots) as store:
                if args.command == "ingest":
                    result = {"ok": True, "batchIntegrityChecked": True, **store.import_validated(verified)}
                elif args.command == "inspect":
                    result = {"ok": True, "counts": store.counts(), "schemaVersion": 1}
                elif args.command == "gc":
                    result = {"ok": True, **collect(store, days=args.days, apply=args.apply)}
                else:
                    backup = store.backup()
                    result = {"ok": True, "backup": backup.relative_to(root).as_posix()}
        assert_unchanged(before, repo_root=ROOT)
        result.update(mode="shadow", publish=False, liveExecuted=False)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ContractError, GuardError) as exc:
        code = exc.code
    except Exception:
        code = "storage_input_error"
    try:
        assert_unchanged(before, repo_root=ROOT)
    except GuardError:
        code = "production_modified"
    print(json.dumps({"ok": False, "error": code, "liveExecuted": False}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
