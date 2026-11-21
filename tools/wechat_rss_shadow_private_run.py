"""Persist independent RSS shadow audits privately; never publish or edit production.

This companion is intentionally opt-in. The base RSS audit remains stdout-only.
Scheduled runs need a stable, private directory supplied by the operator.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = ROOT / "tools/wechat_rss_shadow_audit.py"
NY = ZoneInfo("America/New_York")
SOURCE_IDS = ("wechat-rss-qbitai", "wechat-rss-deepseek", "wechat-rss-kimi")
SCHEDULE_START = date(2026, 11, 19)
SCHEDULE_END = date(2026, 11, 25)


class LedgerError(ValueError):
    """Unsafe or incomplete ledger state; do not silently reset history."""


def secure_directory(raw: str) -> Path:
    """Require an explicit private directory outside this repository."""
    path = Path(raw).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise LedgerError("ledger directory must be absolute and not a symlink")
    folder = path.resolve(strict=False)
    if folder == ROOT or ROOT in folder.parents:
        raise LedgerError("private ledger must be outside the repository")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder = path.resolve(strict=True)
    if not folder.is_dir():
        raise LedgerError("ledger destination must be a directory")
    if folder.stat().st_mode & 0o077:
        raise LedgerError("ledger directory must not grant group/other access (use chmod 700)")
    return folder


def load_previous(folder: Path, run_date: date) -> tuple[Path | None, dict | None, bool]:
    """Read latest scheduled artifact only, never a manual preflight."""
    files = sorted(folder.glob("scheduled-????-??-??.json"))
    if not files:
        return None, None, False
    candidates = []
    for file in files:
        if file.is_symlink():
            raise LedgerError("symlinked scheduled ledger is not allowed")
        stamped = date.fromisoformat(file.stem.removeprefix("scheduled-"))
        if stamped >= run_date:
            raise LedgerError("same-day or future scheduled ledger exists; refusing duplicate run")
        candidates.append((stamped, file))
    prior_date, prior = candidates[-1]
    try:
        value = json.loads(prior.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise LedgerError("previous scheduled ledger is unreadable") from exc
    if (not isinstance(value, dict) or value.get("schemaVersion") != 2
            or not isinstance(value.get("seenHistory"), dict)
            or value.get("privateRunMeta", {}).get("runKind") != "scheduled"):
        raise LedgerError("previous scheduled ledger missing v2 private history")
    metadata = value["privateRunMeta"]
    continuous = (prior_date == run_date - timedelta(days=1)
                  and metadata.get("auditExitCode") == 0
                  and metadata.get("sampleComplete") is True
                  and metadata.get("observationChainComplete") is True)
    return prior, value, continuous


def atomic_private_json(folder: Path, filename: str, value: dict) -> Path:
    """Write 0600 JSON without replacing a previously recorded observation."""
    if not re.fullmatch(r"(?:scheduled-\d{4}-\d{2}-\d{2}|preflight-\d{8}T\d{6}Z-\d{6})\.json", filename):
        raise LedgerError("unexpected evidence filename")
    target = folder / filename
    serialized = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=folder,
                                         prefix=".shadow-", suffix=".tmp", delete=False) as out:
            temp_name = out.name
            os.chmod(temp_name, 0o600)
            out.write(serialized)
            out.flush()
            os.fsync(out.fileno())
        os.link(temp_name, target)  # exclusive: fail rather than overwrite
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)
    if json.loads(target.read_text(encoding="utf-8")) != value:
        raise LedgerError("persisted JSON did not survive read-back")
    return target


def run_once(folder: Path, kind: str, scheduled_for: datetime | None,
             as_of: str | None = None) -> tuple[Path, dict]:
    now = datetime.now(UTC)
    if kind not in ("scheduled", "preflight"):
        raise LedgerError("run kind must be scheduled or preflight")
    if kind == "scheduled":
        if scheduled_for is None or scheduled_for.tzinfo is None:
            raise LedgerError("scheduled runs require an offset-aware --scheduled-for")
        run_day = scheduled_for.astimezone(NY).date()
        if not SCHEDULE_START <= run_day <= SCHEDULE_END:
            raise LedgerError("scheduled day outside approved seven-day pilot")
        if abs((now.astimezone(NY).date() - run_day).days) > 1:
            raise LedgerError("scheduled day is not near actual execution day")
        if as_of is not None:
            raise LedgerError("scheduled runs may not override real observation time")
        previous_path, previous, chain_complete = load_previous(folder, run_day)
        filename = f"scheduled-{run_day.isoformat()}.json"
        if (folder / filename).exists():
            raise LedgerError("refusing to overwrite a completed scheduled day")
    else:
        if scheduled_for is not None:
            raise LedgerError("preflight cannot specify scheduled time")
        previous_path, previous, chain_complete = None, None, False
        filename = f"preflight-{now:%Y%m%dT%H%M%SZ}-{os.getpid()%1000000:06d}.json"

    cmd = [sys.executable, "-B", str(AUDIT_SCRIPT), "--window-days", "7"]
    if previous_path:
        cmd += ["--previous-ledger", str(previous_path)]
    if as_of:
        cmd += ["--as-of", as_of]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        finished = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT,
                                  env=env, timeout=150, check=False)
        audit_code, stdout, error = finished.returncode, finished.stdout, finished.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        audit_code, stdout, error = 124, "", str(exc)

    try:
        report = json.loads(stdout)
        if not isinstance(report, dict) or report.get("schemaVersion") != 2 or not isinstance(report.get("seenHistory"), dict):
            raise ValueError("audit did not output schemaVersion=2 with seenHistory")
    except (ValueError, TypeError) as exc:
        # Preserve the prior history through a catastrophic process failure.
        report = {"schemaVersion": 2, "mode": "read-only-shadow",
                  "asOf": now.isoformat(), "snapshotStatus": "unknown",
                  "seenHistory": (previous or {}).get("seenHistory", {}),
                  "sources": [{"sourceId": s, "status": "runner-failure"} for s in SOURCE_IDS],
                  "rows": [], "summary": {"observed": None, "newSincePrevious": None},
                  "runnerError": f"No valid JSON from audit: {exc}"[:180],
                  "runnerStderr": error[-240:]}

    source_health = {s.get("sourceId"): s.get("status") for s in report.get("sources", [])}
    complete = (audit_code == 0 and report.get("snapshotStatus") == "ok"
                and set(source_health) == set(SOURCE_IDS)
                and all(value == "ok" for value in source_health.values()))
    first = kind == "scheduled" and previous is None and run_day == SCHEDULE_START
    observation_chain = kind == "scheduled" and complete and (first or chain_complete)
    if kind == "scheduled" and not observation_chain:
        # Partial and missing-day observations cannot establish a complete
        # *daily* new-article count, even if some rows retain firstSeenAt.
        report.setdefault("summary", {})["newSincePrevious"] = None
        for row in report.get("rows", []):
            row["newSincePrevious"] = None
    report["privateRunMeta"] = {
        "runKind": kind,
        "scheduledFor": scheduled_for.isoformat() if scheduled_for else None,
        "capturedAtUtc": now.isoformat(),
        "auditExitCode": audit_code,
        "sampleComplete": complete,
        "observationChainComplete": observation_chain,
        "previousLedger": previous_path.name if previous_path else None,
        "historySource": "previous-scheduled-only" if previous_path else "none",
        "privateArtifact": True,
    }
    target = atomic_private_json(folder, filename, report)
    return target, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger-dir", required=True, help="private 0700 directory OUTSIDE repository")
    parser.add_argument("--kind", choices=("scheduled", "preflight"), default="preflight")
    parser.add_argument("--scheduled-for", help="scheduled ISO time with UTC offset (scheduled only)")
    parser.add_argument("--as-of", help="diagnostic override (preflight only)")
    args = parser.parse_args()
    try:
        scheduled = datetime.fromisoformat(args.scheduled_for) if args.scheduled_for else None
        directory = secure_directory(args.ledger_dir)
        file, report = run_once(directory, args.kind, scheduled, args.as_of)
    except (LedgerError, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=False))
        return 3
    print(json.dumps({"status": "saved", "runKind": args.kind,
                      "scheduledFor": args.scheduled_for,
                      "privateArtifactName": file.name,
                      "auditExitCode": report["privateRunMeta"]["auditExitCode"],
                      "observationChainComplete": report["privateRunMeta"]["observationChainComplete"],
                      "sources": [{"sourceId": s.get("sourceId"), "status": s.get("status")}
                                  for s in report.get("sources", [])],
                      "newSincePrevious": report.get("summary", {}).get("newSincePrevious")}, ensure_ascii=False))
    return 0 if report["privateRunMeta"]["sampleComplete"] else 2


if __name__ == "__main__":
    sys.exit(main())
