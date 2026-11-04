"""Explicit offline disposition of the known, zero-content WeChat budget failure.

Preview is read-only. Apply requires a fingerprint and a stopped-worker attestation.
Original receipts, scheduler state, quota, pauses and the stop marker are never edited.
Only valid receipts enter the existing storage-only recovery path. A rejected receipt
is never rewritten as a successful or empty receipt. This is not a general skip switch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from .batch import ROOT, MAX_LINE, decode, private_root, read_private
from .contracts import ContractError, assert_safe, canonical_bytes, digest, validate
from .guard import assert_unchanged, output_path, protected_snapshot, runtime_paths
from .scheduler import instant, utc
from .scheduler_state import read_state
from .shadow_run import Coordinator, code, validate_plan, validate_result
from .shadow_state import load, save, run_lock, run_prefix, stopped
from .signal_store import SignalStore
from .storage_cli import checkpoint_results, input_json

REASON = "batch_record_budget"
MAX_EVIDENCE_BYTES = 16 * 1024 * 1024
SAFE_MISSING = {"not_started", "stopped", "disabled", "wall_budget"}
SAFE_FAILURES = {"network_error", "schema_error", "timeout", "cancelled"}
DECISION_KEYS = {"schemaVersion", "kind", "runId", "reason", "reviewedBy", "recordedAt",
    "workersStoppedConfirmed", "fingerprint", "evidence", "originalReportRaw", "closure"}


def _require(condition, error):
    if not condition:
        raise ContractError(error)


def _actor(value):
    _require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value),
        "quarantine_reviewer_required")
    return value


def _unwrap(raw):
    value = decode(raw)
    _require(isinstance(value, dict) and set(value) == {"schemaVersion", "payload", "sha256"}
        and type(value["schemaVersion"]) is int and value["schemaVersion"] == 1
        and digest(value["payload"]) == value["sha256"], "shadow_journal_checksum")
    assert_safe(value["payload"])
    return value["payload"]


def _decision(root, prefix, roots):
    path = output_path(root, prefix + "/quarantine.json", repo_roots=roots)
    if not path.exists():
        return None
    value = load(root, prefix + "/quarantine.json", roots)
    _require(isinstance(value, dict) and set(value) == DECISION_KEYS
        and type(value["schemaVersion"]) is int and value["schemaVersion"] == 1
        and value["kind"] == "shadow_run_quarantine" and value["reason"] == REASON
        and value["workersStoppedConfirmed"] is True
        and value["fingerprint"] == digest(value["evidence"])
        and run_prefix(value["runId"]) == prefix, "quarantine_decision_invalid")
    _actor(value["reviewedBy"])
    instant(value["recordedAt"])
    return value


def _inspect(root, run_id, roots, now, decision=None):
    """Revalidate every original artifact; do not print or persist their contents."""
    prefix = run_prefix(run_id)
    used = 0

    def exists(relative):
        return output_path(root, relative, repo_roots=roots).exists()

    def account(raw):
        nonlocal used
        used += len(raw)
        _require(used <= MAX_EVIDENCE_BYTES, "quarantine_evidence_limit")
        return raw

    def read(relative):
        return account(read_private(root, relative, roots, maximum=4 * 1024 * 1024 + MAX_LINE))

    def sha(raw):
        return hashlib.sha256(raw).hexdigest()

    _require(stopped(root, roots), "quarantine_stop_required")
    _require(decode(read("shadow.stop")) == {"stop": True}, "quarantine_stop_invalid")
    raw_intent, raw_journal = read(prefix + "/intent.json"), read(prefix + "/journal.json")
    intent, journal = _unwrap(raw_intent), _unwrap(raw_journal)
    _require(isinstance(intent, dict) and set(intent) == {"schemaVersion", "plan", "contexts", "policy", "companies"}
        and type(intent["schemaVersion"]) is int and intent["schemaVersion"] == 1, "shadow_intent_shape")
    plan = intent["plan"]
    validate_plan(plan, intent["contexts"], intent["policy"])
    _require(plan["jobs"][0]["runId"] == run_id and journal.get("runId") == run_id, "shadow_run_mismatch")
    _require(all(j["platform"] == "wechat" for j in plan["jobs"]), "quarantine_wechat_only")
    _require(isinstance(journal.get("attempts"), dict), "quarantine_journal_invalid")
    if decision is None:
        _require(not exists(prefix + "/closure.json") and not (root / prefix / "batch").exists(),
            "quarantine_run_already_closed")
        raw_report = read(prefix + "/report.json")
    else:
        _require(isinstance(decision["originalReportRaw"], str), "quarantine_decision_invalid")
        raw_report = account(decision["originalReportRaw"].encode("utf-8"))
        if not exists(prefix + "/closure.json"):
            _require(read(prefix + "/report.json") == raw_report, "quarantine_original_report_changed")
        else:
            _require(_unwrap(read(prefix + "/closure.json")) == decision["closure"], "quarantine_closure_changed")
    report = _unwrap(raw_report)
    _require(isinstance(report, dict) and report.get("runId") == run_id and report.get("status") == "blocked"
        and report.get("pipelineComplete") is False and report.get("stage") == "collect-results"
        and report.get("error") == REASON, "quarantine_known_failure_required")

    # Do not dispose a batch already admitted to storage. After our own closure,
    # recovery may have imported its valid, zero-content receipt subset.
    if exists("signals.sqlite3") and (decision is None or not exists(prefix + "/closure.json")):
        with SignalStore(root, repo_roots=roots, readonly=True) as store:
            _require(store.db.execute("SELECT 1 FROM batches WHERE run_id=?", (run_id,)).fetchone() is None,
                "quarantine_run_already_imported")
    _require(exists("state.sqlite3"), "quarantine_scheduler_missing")
    state = read_state(root, repo_roots=roots)
    _require("wechat" in state["platforms"], "quarantine_scheduler_incomplete")
    for job in plan["jobs"]:
        _require(job["queryId"] in state["queries"], "quarantine_scheduler_incomplete")
        for lease in (state["queries"][job["queryId"]], state["platforms"]["wechat"]):
            _require(not lease.get("leaseUntil") or instant(lease["leaseUntil"]) <= now,
                "quarantine_active_lease")
        pause = state["platforms"]["wechat"]
        _require(not pause.get("pauseReason"), "quarantine_platform_pause")

    sources, statuses, completed, valid_results, rejected = {}, [], [], {}, []
    closed_at = decision["recordedAt"] if decision else utc(now)
    _require(instant(closed_at) <= now, "quarantine_future_decision")
    for job in plan["jobs"]:
        aid = job["attemptId"]
        saved_path, pending_path = prefix + "/results/" + aid + ".json", "pending/" + aid + ".json"
        raw_saved = read(saved_path) if exists(saved_path) else None
        raw_pending = read(pending_path) if exists(pending_path) else None
        saved = _unwrap(raw_saved) if raw_saved is not None else None
        pending = decode(raw_pending) if raw_pending is not None else None
        checkpoint = None
        try:
            checkpoint = checkpoint_results(root, [job], roots)[0]
            account(canonical_bytes(checkpoint))
        except ContractError as exc:
            if exc.code != "checkpoint_result_missing":
                raise
        values = [v for v in (saved, pending, checkpoint) if v is not None]
        _require(len({digest(v) for v in values}) <= 1, "quarantine_result_conflict")
        result = values[0] if values else None
        source = {"saved": sha(raw_saved) if raw_saved is not None else None,
            "pending": sha(raw_pending) if raw_pending is not None else None,
            "checkpoint": digest(checkpoint) if checkpoint is not None else None,
            "resultHash": digest(result) if result is not None else None}
        if result is None:
            status = journal["attempts"].get(aid)
            _require(status in SAFE_MISSING, "quarantine_missing_execution_evidence")
            statuses.append({"attemptId": aid, "platform": "wechat", "status": status, "receiptPresent": False})
            source["valid"] = None
        else:
            _require(isinstance(result, dict) and set(result) == {"receipt", "observations", "hints", "diagnostics"},
                "quarantine_result_shape")
            assert_safe(result)
            receipt = validate(result["receipt"], expected_kind="query_receipt")
            _require(result["observations"] == [] and receipt["counts"]["emittedRows"] == 0,
                "quarantine_nonempty_result")
            _require(receipt["status"] in SAFE_FAILURES | {"ok", "empty"}, "quarantine_restricted_result")
            _require(instant(receipt["completedAt"]) <= instant(closed_at), "quarantine_future_receipt")
            try:
                validate_result(job, result, instant(closed_at))
            except ContractError as exc:
                _require(exc.code == REASON and receipt["status"] in SAFE_FAILURES
                    and journal["attempts"].get(aid) == "error:" + REASON
                    and checkpoint is None, "quarantine_unsupported_invalid_result")
                source["valid"] = False
                rejected.append(aid)
                statuses.append({"attemptId": aid, "platform": "wechat", "status": "quarantined_invalid_result",
                    "receiptPresent": False, "rawReceiptPresent": True, "receiptAccepted": False,
                    "reason": REASON, "rawRows": receipt["counts"]["rawRows"], "maxRecords": job["limits"]["maxRecords"],
                    "originalStatus": receipt["status"], "originalErrorCode": receipt["errorCode"],
                    "resultHash": digest(result)})
            else:
                source["valid"] = True
                completed.append({"attemptId": aid, "resultHash": digest(result)})
                valid_results[aid] = result
                statuses.append({"attemptId": aid, "platform": "wechat", "status": receipt["status"],
                    "receiptPresent": True, "checkpointed": checkpoint is not None,
                    "completeness": receipt["completeness"], "emittedRows": 0,
                    "durationSeconds": (instant(receipt["completedAt"]) - instant(receipt["startedAt"])).total_seconds()})
        if decision is not None:
            original = decision["evidence"]["sources"].get(aid)
            _require(isinstance(original, dict), "quarantine_decision_invalid")
            # A crash after the decision may leave a newly materialized VALID
            # result. Original saved files cannot be edited or removed.
            if original["saved"] is None and raw_saved is not None:
                _require(original["valid"] is True and digest(saved) == original["resultHash"],
                    "quarantine_generated_result_changed")
                source["saved"] = None
        sources[aid] = source
    _require(bool(rejected), "quarantine_no_invalid_result")
    evidence = {"runId": run_id, "intent": sha(raw_intent), "journal": sha(raw_journal),
        "originalReport": sha(raw_report), "sources": sources}
    fingerprint = digest(evidence)
    closure = {"runId": run_id, "planHash": digest(plan), "closedAt": closed_at, "completed": completed,
        "jobs": statuses, "checkpointReconciliationRequired": True,
        "quarantineFingerprint": fingerprint, "rejectedAttemptIds": rejected}
    if decision is not None:
        _require(evidence == decision["evidence"] and closure == decision["closure"], "quarantine_evidence_changed")
    return {"evidence": evidence, "fingerprint": fingerprint, "closure": closure,
        "originalReportRaw": raw_report.decode("utf-8"), "validResults": valid_results, "rejected": rejected}


def preview(root, run_id, *, roots=(ROOT,), now=None):
    root = private_root(root, roots)
    decision = _decision(root, run_prefix(run_id), roots)
    data = _inspect(root, run_id, roots, now or datetime.now(UTC), decision)
    return {"ok": True, "runId": run_id, "fingerprint": data["fingerprint"],
        "invalidReceiptJobs": len(data["rejected"]), "validReceiptJobs": len(data["validResults"]),
        "alreadyRecorded": decision is not None, "applied": False, "writesPerformed": False,
        "liveExecuted": False, "mode": "shadow", "publish": False, "stopRequested": True}


def apply(root, run_id, *, expected_fingerprint, reviewed_by, workers_stopped=False, roots=(ROOT,), now=None):
    root = private_root(root, roots)
    _require(workers_stopped is True, "quarantine_workers_confirmation_required")
    _actor(reviewed_by)
    _require(isinstance(expected_fingerprint, str) and re.fullmatch(r"[0-9a-f]{64}", expected_fingerprint),
        "quarantine_fingerprint_required")
    moment = now or datetime.now(UTC)
    prefix = run_prefix(run_id)
    with run_lock(root, roots):
        decision = _decision(root, prefix, roots)
        data = _inspect(root, run_id, roots, moment, decision)
        _require(data["fingerprint"] == expected_fingerprint, "quarantine_fingerprint_changed")
        replayed = decision is not None
        if decision is None:
            decision = {"schemaVersion": 1, "kind": "shadow_run_quarantine", "runId": run_id, "reason": REASON,
                "reviewedBy": reviewed_by, "recordedAt": utc(moment), "workersStoppedConfirmed": True,
                "fingerprint": data["fingerprint"], "evidence": data["evidence"],
                "originalReportRaw": data["originalReportRaw"], "closure": data["closure"]}
            # Preserve the exact original report bytes BEFORE recovery updates it.
            save(root, prefix + "/quarantine.json", decision, roots, exclusive=True)
        else:
            _require(decision["reviewedBy"] == reviewed_by, "quarantine_decision_conflict")
        for aid, result in data["validResults"].items():
            relative = prefix + "/results/" + aid + ".json"
            if not output_path(root, relative, repo_roots=roots).exists():
                save(root, relative, result, roots, exclusive=True)
        closure_path = prefix + "/closure.json"
        if not output_path(root, closure_path, repo_roots=roots).exists():
            save(root, closure_path, data["closure"], roots, exclusive=True)
        # The existing recovery path only seals/imports the validated subset.
        # We already hold its coordinator lock; never invoke dispatch or finish.
        report = Coordinator(root, roots, clock=lambda: moment)._complete(run_id, own_execution=False)
        return {"ok": report.get("pipelineComplete") is True and report.get("status") == "degraded",
            "runId": run_id, "fingerprint": data["fingerprint"], "quarantined": True,
            "replayed": replayed, "runHealthy": False, "runStatus": report.get("status"),
            "pipelineComplete": report.get("pipelineComplete", False), "error": report.get("error"),
            "invalidReceiptJobs": len(data["rejected"]), "validReceiptJobs": len(data["validResults"]),
            "observations": 0, "liveExecuted": False, "mode": "shadow", "publish": False,
            "stopRequested": stopped(root, roots), "schedulerUnchanged": True, "quotaUnchanged": True,
            "manualResumeRequired": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--runtime-config", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-fingerprint")
    parser.add_argument("--reviewed-by")
    parser.add_argument("--confirm-workers-stopped", action="store_true")
    args = parser.parse_args(argv)
    before = None
    try:
        root = private_root(args.state_dir, (ROOT,))
        runtime = validate(input_json(root, args.runtime_config, (ROOT,), maximum=MAX_LINE), expected_kind="runtime_config")
        roots = (ROOT,) + ((Path(runtime["mediacrawlerDir"]),) if runtime["mediacrawlerDir"] else ())
        _require(runtime_paths(runtime, repo_root=ROOT, runtime_file=args.runtime_config) == root, "state_directory_mismatch")
        before = protected_snapshot(ROOT)
        if args.apply:
            result = apply(root, args.run_id, expected_fingerprint=args.expected_fingerprint,
                reviewed_by=args.reviewed_by, workers_stopped=args.confirm_workers_stopped, roots=roots)
        else:
            result = preview(root, args.run_id, roots=roots)
        assert_unchanged(before, repo_root=ROOT)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["ok"] else 1
    except Exception as exc:
        error = code(exc)
        if before is not None:
            try:
                assert_unchanged(before, repo_root=ROOT)
            except Exception:
                error = "production_modified"
        print(json.dumps({"ok": False, "error": error, "liveExecuted": False, "mode": "shadow", "publish": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
