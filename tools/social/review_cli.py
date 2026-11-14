"""Offline review commands. Decisions require --apply; no production promotion."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .batch import ROOT, MAX_LINE, private_root
from .contracts import ContractError, load_json, validate
from .guard import GuardError, assert_unchanged, output_path, protected_snapshot, runtime_paths
from .lead_builder import company_index, proposal_hash, select_leads, triage_report
from .review import ReviewStore, read_transaction
from .signal_store import SignalStore
from .storage_cli import input_json

REGISTRY = ROOT / "config/company_registry.json"


def settings(state_dir, runtime_file):
    root = private_root(state_dir, (ROOT,))
    runtime = validate(input_json(root, runtime_file, (ROOT,), maximum=MAX_LINE), expected_kind="runtime_config")
    roots = (ROOT,) + ((Path(runtime["mediacrawlerDir"]),) if runtime["mediacrawlerDir"] else ())
    if runtime_paths(runtime, repo_root=ROOT, runtime_file=runtime_file) != root:
        raise GuardError("state_directory_mismatch")
    return root, roots


def registry_input(root, roots, value=None):
    # The only repository read is the known company registry. Alternate snapshots
    # must be explicit private inputs; neither source is ever rewritten.
    if value is None:
        if REGISTRY.is_symlink(): raise GuardError("registry_symlink_forbidden")
        payload = load_json(REGISTRY)
    else:
        payload = input_json(root, value, roots)
    return company_index(payload)


def require_database(root, roots, filename):
    if not output_path(root, filename, repo_roots=roots).is_file():
        raise ContractError("review_required_database_missing")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser("sync", help="Preview leads; --apply pins evidence and publishes a private queue")
    sync.add_argument("--apply", action="store_true")
    triage = commands.add_parser("triage", help="Read-only background/queue selection counts; never changes reviews")
    show = commands.add_parser("list", help="Read a page without creating or modifying databases")
    show.add_argument("--offset", type=int, default=0)
    show.add_argument("--limit", type=int, default=50)
    show.add_argument("--history", action="store_true")
    decision = commands.add_parser("decide", help="Validate a decision file; --apply records it once")
    decision.add_argument("--request", required=True)
    decision.add_argument("--apply", action="store_true")
    for command in (sync, show, decision, triage):
        command.add_argument("--state-dir", type=Path, required=True)
        command.add_argument("--runtime-config", type=Path, required=True)
    for command in (sync, decision, triage):
        command.add_argument("--companies", help="Optional registry snapshot under private state")
    args = parser.parse_args(argv)
    before = None
    try:
        root, roots = settings(args.state_dir, args.runtime_config)
        before = protected_snapshot(ROOT)
        if args.command == "list":
            with ReviewStore(root, repo_roots=roots, readonly=True) as store:
                result = {**store.view(offset=args.offset, limit=args.limit, history=args.history), "writesPerformed": False}
        else:
            index = registry_input(root, roots, args.companies)
            require_database(root, roots, "signals.sqlite3")
            request = None
            if args.command == "decide":
                request = validate(input_json(root, args.request, roots, maximum=MAX_LINE), expected_kind="decision_request")
                require_database(root, roots, "reviews.sqlite3")
            with SignalStore(root, repo_roots=roots, readonly=not getattr(args, "apply", False)) as source:
                if args.command == "triage":
                    with read_transaction(source.db): result = triage_report(source, index)
                elif args.command == "sync" and not args.apply:
                    with read_transaction(source.db): proposals = select_leads(source, index)
                    result = {"ok": True, "candidateCount": len(proposals), "proposalHash": proposal_hash(proposals),
                              "applied": False, "evidencePinned": False, "writesPerformed": False}
                else:
                    with ReviewStore(root, repo_roots=roots, readonly=not args.apply) as store:
                        if args.command == "sync":
                            result = {**store.materialize(source, index), "applied": True}
                        else:
                            result = store.decide(source, index, request, apply=args.apply)
        assert_unchanged(before, repo_root=ROOT)
        print(json.dumps({**result, "mode": "shadow", "publish": False, "liveExecuted": False, "productionChanged": False}, ensure_ascii=False, sort_keys=True))
        return 0
    except (ContractError, GuardError) as exc:
        code = exc.code
    except Exception:
        code = "review_input_or_io_error"
    if before is not None:
        try: assert_unchanged(before, repo_root=ROOT)
        except GuardError: code = "production_modified"
    print(json.dumps({"ok": False, "error": code, "mode": "shadow", "publish": False, "liveExecuted": False}), file=sys.stderr)
    return 2


if __name__ == "__main__": raise SystemExit(main())
