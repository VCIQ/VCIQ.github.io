"""Synthetic orchestration results; injected executors perform zero platform I/O."""
from datetime import UTC, datetime, timedelta

from tests.test_social_contracts import fixture
from tools.social.contracts import content_hash

NOW = datetime(2026, 11, 1, 12, tzinfo=UTC)


def result_for(job, *, now=NOW, status="ok", positive=True):
    receipt = fixture("query_receipt", job["platform"])
    receipt.update({k: job[k] for k in ("jobId", "queryId", "runId", "attemptId", "platform", "provider", "upstreamCommit")})
    receipt.update(startedAt=(now - timedelta(seconds=1)).isoformat(), completedAt=now.isoformat(),
        status=status, completeness="exhausted", stopReason="exhausted", errorCode=None)
    receipt["pageReceipts"] = [dict(pageIndex=1, schemaValid=True, contentItems=int(positive), processed=True, hasMore=False)]
    receipt["counts"] = dict(searchItems=int(positive), rawRows=int(positive), emittedRows=int(positive), rejectedRows=0,
        duplicateRows=0, budgetSkipped=0, detailFailures=0)
    observations = []
    if positive:
        observation = fixture("signal_observation", job["platform"])
        observation.update({k: job[k] for k in ("jobId", "queryId", "runId", "attemptId", "platform", "trackRefs")})
        observation.update(observedAt=now.isoformat(), publishedAt=None, publishedPrecision="unknown", updatedAt=None,
            title=job["query"]["text"] + " 融资消息（合成测试）", excerpt="这是离线合成数据，不代表真实事件。",
            queryTerms=[job["query"]["text"]], matchedTerms=[job["query"]["text"]], titleOrigin="upstream")
        observation["contentHash"] = content_hash(observation)
        observations.append(observation)
    if status not in {"ok", "empty"}:
        reason = {"partial": "network", "auth_required": "auth", "rate_limited": "rate_limit", "verification_required": "verification",
            "cancelled": "cancelled", "network_error": "network"}[status]
        receipt.update(completeness="incomplete", stopReason=reason, errorCode="SYNTHETIC_FAILURE")
        if not positive: receipt["pageReceipts"] = []
    return {"receipt": receipt, "observations": observations, "hints": [],
        "diagnostics": {"retryAfterSeconds": 600 if status == "rate_limited" else 0}}


def tracking(words=("机器人",)):
    return {"tracks": [{"name": "合成机器人", "slug": "synthetic", "enabled": True,
        "keywords": list(words), "sampleCompanies": [], "people": []}]}
