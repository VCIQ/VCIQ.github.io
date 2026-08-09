#!/usr/bin/env python3
"""Detect whether a full-refresh run still matches current live inputs.

A full public-intelligence refresh is expensive and may wait in the shared
repository-writer queue.  This module centralizes the paths that define crawler
execution semantics so both the cheap preflight and the final publication guard
can determine whether a queued/running refresh is stale.

Only *live refresh inputs* belong here.  Generated public snapshots are
intentionally excluded: a data-only commit must not invalidate a crawl that was
started from the same source/runtime configuration.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]

LIVE_REFRESH_INPUTS: tuple[str, ...] = (
    ".github/workflows/scheduled-sync.yml",
    "tools/crawl_with_wechat_registry.py",
    "tools/article_publication_gate.py",
    "tools/core_official_adapters.py",
    "tools/source_portfolio.py",
    "tools/full_refresh_input_guard.py",
    "config/automation_jobs.json",
    "config/company_registry.json",
    "config/intelligence_sources.json",
    "config/user_tracking.json",
    "config/listed_company_disclosure_sources.json",
    "config/professional_technology_media_sources.json",
    "config/wechat_sources.json",
    "config/wechat_public_indexes.json",
    "config/official_company_sources.json",
    "config/person_profile_overrides.json",
    "config/source_health_policy.json",
    "config/source_quality_reviews.json",
)


def changed_live_inputs(
    base: str,
    target: str,
    *,
    cwd: Path | str = ROOT,
    inputs: Sequence[str] = LIVE_REFRESH_INPUTS,
) -> list[str]:
    """Return live input paths changed between two git refs."""

    completed = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            base,
            target,
            "--",
            *inputs,
        ],
        cwd=str(cwd),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def evaluate_currentness(
    base: str,
    target: str,
    *,
    cwd: Path | str = ROOT,
) -> dict[str, object]:
    changed = changed_live_inputs(base, target, cwd=cwd)
    return {
        "current": not changed,
        "base": base,
        "target": target,
        "changedPaths": changed,
        "inputCount": len(LIVE_REFRESH_INPUTS),
    }


def _append_github_output(path: str, current: bool) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"current={'true' if current else 'false'}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument(
        "--github-output",
        default="",
        help="Append current=true/false to this GitHub Actions output file.",
    )
    args = parser.parse_args()

    result = evaluate_currentness(args.base, args.target)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    output_path = args.github_output or os.environ.get("GITHUB_OUTPUT", "")
    if output_path:
        _append_github_output(output_path, bool(result["current"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
