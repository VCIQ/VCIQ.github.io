"""Shadow CLI: offline validation/planning and explicitly gated WeChat execution."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .contracts import ContractError, MAX_DOCUMENT_BYTES, load_json, validate, load_schema
from .guard import GuardError, runtime_paths, state_path
from .policy import DEFAULT_POLICY, IMPLEMENTED_PLATFORMS, activation, load_policy

REPO_ROOT = Path(__file__).resolve().parents[2]


def _rows(path: Path) -> list[dict[str, Any]]:
    if path.is_symlink():
        raise ContractError("fixture_symlink")
    try:
        if path.stat().st_size > MAX_DOCUMENT_BYTES:
            raise ContractError("document_too_large")
        # Reuse duplicate-key/non-finite parsing through a small pure loader below.
        with path.open(encoding="utf-8") as stream:
            lines = stream.readlines()
        if not lines or any(not line.endswith("\n") for line in lines):
            raise ContractError("fixture_line_ending")
        result = []
        for line in lines:
            def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
                row: dict[str, Any] = {}
                for key, item in items:
                    if key in row:
                        raise ContractError("duplicate_key")
                    row[key] = item
                return row
            def constant(_: str) -> Any:
                raise ContractError("non_finite_number")
            result.append(json.loads(line, object_pairs_hook=pairs, parse_constant=constant))
        return result
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        raise ContractError("invalid_fixture") from None


def validate_fixtures(directory: Path) -> dict[str, Any]:
    """Positive records and explicit negative cases, never live evidence."""
    if directory.is_symlink() or not directory.is_dir():
        raise ContractError("invalid_fixture_directory")
    good = _rows(directory / "valid.jsonl")
    bad = _rows(directory / "invalid.jsonl")
    for doc in good:
        validate(doc)
    for case in bad:
        if not isinstance(case, dict) or set(case) != {"caseId", "errorCode", "document"}:
            raise ContractError("invalid_negative_case")
        try:
            validate(case["document"])
        except ContractError as exc:
            if exc.code != case["errorCode"]:
                raise ContractError("negative_code_mismatch") from None
        else:
            raise ContractError("negative_case_accepted")
    return {"ok": True, "validRecords": len(good), "rejectedNegativeCases": len(bad), "synthetic": True, "liveExecuted": False, "batchIntegrityChecked": False}


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] in {"plan", "coverage", "run-wechat", "resume-wechat"}:
        from .planning_cli import main as planning_main
        return planning_main(arguments)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("validate", help="Validate one contract or the synthetic corpus, without writing")
    group = check.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=Path)
    group.add_argument("--fixtures", type=Path)
    doctor = sub.add_parser("doctor", help="Read-only offline policy and path checks")
    doctor.add_argument("--offline", action="store_true", required=True)
    doctor.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    doctor.add_argument("--runtime", type=Path)
    doctor.add_argument("--state-dir", type=Path)
    args = parser.parse_args(arguments)
    try:
        if args.command == "validate":
            if args.fixtures:
                result = validate_fixtures(args.fixtures)
            else:
                document = validate(load_json(args.file))
                result = {"ok": True, "kind": document["kind"], "liveExecuted": False, "batchIntegrityChecked": False}
        else:
            load_schema()
            policy = load_policy(args.policy)
            runtime = validate(load_json(args.runtime), expected_kind="runtime_config") if args.runtime else None
            if runtime is not None:
                runtime_root = runtime_paths(runtime, repo_root=REPO_ROOT, runtime_file=args.runtime)
                if args.state_dir is not None and state_path(args.state_dir, repo_roots=[REPO_ROOT, *([runtime["mediacrawlerDir"]] if runtime["mediacrawlerDir"] else [])]) != runtime_root:
                    raise GuardError("state_directory_mismatch")
            elif args.state_dir is not None:
                state_path(args.state_dir, repo_roots=[REPO_ROOT])
            result = {"ok": True, "status": "disabled" if runtime is None or not runtime["enabled"] else "offline_only", "mode": "shadow", "publish": False, "platforms": activation(policy, runtime), "implementedPlatforms": sorted(IMPLEMENTED_PLATFORMS), "liveExecuted": False, "writesPerformed": False, "pathChecks": "checked" if runtime is not None or args.state_dir is not None else "not_requested"}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ContractError, GuardError) as exc:
        print(json.dumps({"ok": False, "error": exc.code, "path": getattr(exc, "path", "$"), "liveExecuted": False}, sort_keys=True), file=sys.stderr)
        return 2
    except (OSError, RuntimeError, ValueError):
        # No input paths, credentials or raw exception strings in CLI logs.
        print(json.dumps({"ok": False, "error": "input_error", "liveExecuted": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
