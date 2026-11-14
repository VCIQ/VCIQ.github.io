"""Explicit human-adjudicated event metrics, not post-count or acceptance proxies."""
from __future__ import annotations

import re

from .contracts import ContractError, assert_safe, digest


def evaluate(source, assessment, baseline):
    from .review import read_transaction
    with read_transaction(source.db):
        return _evaluate(source, assessment, baseline)


def _evaluate(source, assessment, baseline):
    """Inputs are private snapshots. eventId grouping is supplied by the reviewer.

    baseline has windowStart/windowEnd, complete and articleIds. A valid event
    with no baseline matches counts as additional only for a complete baseline.
    No inferred entity matching, cost estimate, or benefit from synthetic tests.
    """
    assert_safe([assessment, baseline])
    if (not isinstance(baseline, dict) or set(baseline) != {"windowStart", "windowEnd", "complete", "articleIds"}
            or type(baseline["complete"]) is not bool or not isinstance(baseline["articleIds"], list)
            or len(baseline["articleIds"]) > 100000):
        raise ContractError("evaluation_baseline_shape")
    from .scheduler import instant
    try:
        start, end = instant(baseline["windowStart"]), instant(baseline["windowEnd"])
        if start >= end: raise ValueError
    except (TypeError, ValueError, AttributeError):
        raise ContractError("evaluation_window") from None
    article_ids = baseline["articleIds"]
    if any(not isinstance(x, str) or not x or len(x) > 300 for x in article_ids) or len(set(article_ids)) != len(article_ids):
        raise ContractError("evaluation_article_ids")
    if (not isinstance(assessment, dict) or set(assessment) != {"baselineHash", "reviewedBy", "events"}
            or assessment["baselineHash"] != digest(baseline)
            or not isinstance(assessment["reviewedBy"], str) or not assessment["reviewedBy"].strip()
            or len(assessment["reviewedBy"]) > 160 or any(c in assessment["reviewedBy"] for c in "@\r\n")
            or not isinstance(assessment["events"], list) or len(assessment["events"]) > 10000):
        raise ContractError("evaluation_assessment_shape")
    known = set(article_ids)
    seen_events, seen_signals = set(), set()
    valid = invalid = uncertain = additional = overlap = identity_errors = 0
    for event in assessment["events"]:
        if (not isinstance(event, dict) or set(event) != {"eventId", "verdict", "evidence", "baselineArticleIds", "identityError"}
                or not isinstance(event["eventId"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}", event["eventId"])
                or event["eventId"] in seen_events or event["verdict"] not in {"valid", "invalid", "uncertain"}
                or type(event["identityError"]) is not bool or not isinstance(event["evidence"], list)
                or not 1 <= len(event["evidence"]) <= 100 or not isinstance(event["baselineArticleIds"], list)
                or len(event["baselineArticleIds"]) > 100):
            raise ContractError("evaluation_event_shape")
        seen_events.add(event["eventId"])
        for evidence in event["evidence"]:
            if (not isinstance(evidence, dict) or set(evidence) != {"signalId", "contentHash"}
                    or not isinstance(evidence["contentHash"], str) or not re.fullmatch(r"[0-9a-f]{64}", evidence["contentHash"])):
                raise ContractError("evaluation_evidence_shape")
            signal_id = evidence["signalId"]
            if not isinstance(signal_id, str) or signal_id in seen_signals:
                raise ContractError("evaluation_duplicate_signal")
            signal = source.get_signal(signal_id)
            if signal is None: raise ContractError("evaluation_unknown_signal")
            if not source.db.execute("SELECT 1 FROM versions WHERE signal_id=? AND content_hash=?", (signal_id, evidence["contentHash"])).fetchone():
                raise ContractError("evaluation_evidence_missing")
            # Cohort is first-discovered events within the same explicit window.
            if not start <= instant(signal["firstSeenAt"]) < end:
                raise ContractError("evaluation_outside_cohort")
            seen_signals.add(signal_id)
        refs = event["baselineArticleIds"]
        if any(not isinstance(x, str) or x not in known for x in refs) or len(set(refs)) != len(refs):
            raise ContractError("evaluation_unknown_baseline_article")
        identity_errors += int(event["identityError"])
        if event["verdict"] == "valid":
            valid += 1
            overlap += bool(refs)
            additional += not refs
        elif event["verdict"] == "invalid": invalid += 1
        else: uncertain += 1
    total = len(seen_events)
    cohort = sum(start <= instant(row[0]) < end for row in source.db.execute("SELECT first_seen FROM signals"))
    return {"ok": True, "mode": "shadow", "publish": False, "liveExecuted": False,
        "status": "evaluated" if total else "not_evaluated", "baselineHash": digest(baseline),
        "assessmentHash": digest(assessment), "baselineComplete": baseline["complete"],
        "reviewedEvents": total, "validEvents": valid, "invalidEvents": invalid, "uncertainEvents": uncertain,
        "overlappingValidEvents": overlap, "additionalValidEvents": additional if baseline["complete"] and total else None,
        "validRate": valid / total if total else None, "identityErrorRate": identity_errors / total if total else None,
        "cohortSignals": cohort, "reviewedSignals": len(seen_signals), "unreviewedSignals": cohort - len(seen_signals),
        "reviewCoverage": len(seen_signals) / cohort if cohort else None,
        "sampling": "reviewer-selected-not-random", "baselineProvenance": "explicit-operator-snapshot-not-independently-attested",
        "cost": None, "discoveryLatency": None, "factVerification": "external-reviewer-judgement-not-automatically-verified",
        "productionChanged": False}
