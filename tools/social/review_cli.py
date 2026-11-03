"""Local review queue generation and explicit imported human decisions."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .contracts import ContractError, load_json
from .guard import GuardError, assert_unchanged, protected_snapshot, state_path
from .review import apply_shadow_decision, build_review_queue, current_queue
from .signal_store import SignalStore
from .wechat_runner import atomic_json

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("review-queue", "review", "serve-review"))
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--production-snapshot", type=Path)
    parser.add_argument("--decision", type=Path)
    parser.add_argument("--upstream-dir", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    roots = (ROOT, *([args.upstream_dir] if args.upstream_dir else []))
    before = protected_snapshot(ROOT)
    try:
        root = state_path(args.state_dir, repo_roots=roots)
        if args.command == "serve-review":
            from .review_web import serve
            serve(root, args.port, roots=roots)
            return 0
        with SignalStore(root, repo_roots=roots) as store:
            if args.command == "review-queue":
                snapshot = load_json(args.production_snapshot) if args.production_snapshot else {}
                queue = build_review_queue(store, snapshot)
                result = {"ok": True, "candidates": len(queue["candidates"]), "queueVersion": queue["queueVersion"],
                          "existingProjectUpdates": len(queue["existingProjectUpdates"])}
            else:
                if args.decision is None:
                    raise ContractError("decision_file_required")
                result = apply_shadow_decision(store, load_json(args.decision))
                queue = current_queue(store)
            atomic_json(root, "review/queue.json", queue, roots=roots)
        assert_unchanged(before, repo_root=ROOT)
        print(json.dumps({**result, "mode": "shadow", "publish": False, "liveExecuted": False}, ensure_ascii=False, sort_keys=True))
        return 0
    except (ContractError, GuardError) as exc:
        code = exc.code
    except Exception:
        code = "review_input_error"
    try:
        assert_unchanged(before, repo_root=ROOT)
    except GuardError:
        code = "production_modified"
    print(json.dumps({"ok": False, "error": code, "liveExecuted": False}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
