#!/usr/bin/env python3
"""Origin-aware batch writer entrypoint with first-class keyword support.

The canonical batch engine remains fail-closed for direct/manual callers. The
web capture flow uses ``invalid-policy=skip`` for machine-generated candidates;
when every row in such a batch is an invalid ``origin=automatic`` suggestion,
the safe result is a successful no-op with an explicit skipped audit rather
than a failed GitHub Actions run. Human and human-confirmed rows are never
converted into this no-op path.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from typing import Any

try:
    import manual_tracking as manual
    import manual_tracking_batch as batch
    from manual_tracking_keyword_support import enable_keyword_tracking
except ImportError:  # pragma: no cover
    from tools import manual_tracking as manual
    from tools import manual_tracking_batch as batch
    from tools.manual_tracking_keyword_support import enable_keyword_tracking


ALL_AUTOMATIC_SKIPPED_PREFIX = "整批对象均未通过验证，没有可安全写入的对象。"


def _argument_value(argv: list[str], name: str, default: str = "") -> str:
    try:
        index = argv.index(name)
    except ValueError:
        return default
    return argv[index + 1] if index + 1 < len(argv) else default


def _last_json_report(output: str) -> dict[str, Any] | None:
    for line in reversed(output.splitlines()):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _skip_reason(error: str) -> str:
    detail = error
    if "（" in error and error.endswith("）"):
        detail = error.split("（", 1)[1][:-1]
    return manual.clean(detail, 500) or "未通过规范校验，已安全跳过。"


def _automatic_noop_report(
    argv: list[str],
    exit_code: int,
    report: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Convert only an all-invalid automatic skip batch into a successful no-op."""

    if exit_code == 0 or not report:
        return None
    invalid_policy = _argument_value(argv, "--invalid-policy", "strict")
    error = manual.clean(report.get("error"), 1200)
    if invalid_policy != "skip" or not error.startswith(ALL_AUTOMATIC_SKIPPED_PREFIX):
        return None

    try:
        rows = batch.parse_batch(_argument_value(argv, "--batch-json"))
        origins = [
            batch.tracking_origin(index, row, invalid_policy)
            for index, row in enumerate(rows, start=1)
        ]
    except manual.ManualTrackingError:
        return None
    if not rows or any(origin != "automatic" for origin in origins):
        return None

    reason = _skip_reason(error)
    skipped = [
        {
            "index": index,
            "objectType": manual.clean(row.get("objectType"), 30),
            "name": manual.clean(row.get("name"), 160),
            "origin": "automatic",
            "error": reason,
        }
        for index, row in enumerate(rows, start=1)
    ]
    outcomes = [batch.skipped_outcome(item) for item in skipped]
    return {
        "ok": True,
        "mode": _argument_value(argv, "--mode"),
        "invalidPolicy": invalid_policy,
        "actor": manual.clean(_argument_value(argv, "--actor"), 120),
        "triggeringActor": manual.clean(
            _argument_value(argv, "--triggering-actor"), 120
        ),
        "count": len(rows),
        "acceptedCount": 0,
        "skippedCount": len(skipped),
        "repairedCount": 0,
        "removedKeywordCount": 0,
        "appliedCount": 0,
        "reviewQueuedCount": 0,
        "recordedCount": 0,
        "unchangedCount": 0,
        "changed": False,
        "configChanged": False,
        "inboxChanged": False,
        "intentsChanged": False,
        "reviewQueued": False,
        "items": [],
        "outcomes": outcomes,
        "skipped": skipped,
        "repaired": [],
        "detail": f"全部 {len(skipped)} 个自动候选未通过规范校验，已安全跳过；没有写入任何状态。",
    }


def main(argv: list[str] | None = None) -> int:
    enable_keyword_tracking(manual)
    effective_argv = list(argv) if argv is not None else sys.argv[1:]
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        exit_code = batch.main(effective_argv)
    output = captured.getvalue()
    noop_report = _automatic_noop_report(
        effective_argv,
        exit_code,
        _last_json_report(output),
    )
    if noop_report is not None:
        print(json.dumps(noop_report, ensure_ascii=False, sort_keys=True))
        return 0
    print(output, end="")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
