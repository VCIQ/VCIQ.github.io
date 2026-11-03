"""Synthetic private-storage data. Never a real platform record or credential."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from tests.test_social_contracts import fixture
from tools.social.contracts import digest, query_id

SEALED_AT = "2026-11-03T12:00:00Z"


def sample(platform="xhs", *, at="2026-10-23T12:00:00Z", keyword=None, run_id=None):
    job = fixture("crawl_job", platform)
    observation = fixture("signal_observation", platform)
    receipt = fixture("query_receipt", platform)
    job.update(runId=run_id or str(uuid4()), attemptId=str(uuid4()))
    if keyword:
        job["query"]["text"] = keyword
    job["queryId"] = query_id(job)
    job["jobId"] = digest({"queryId": job["queryId"], "operation": "search"})
    for row in (observation, receipt):
        row.update({key: job[key] for key in ("jobId", "queryId", "runId", "attemptId")})
    observation["observedAt"] = at
    observation["queryTerms"] = [job["query"]["text"]]
    observation["matchedTerms"] = []
    time = datetime.fromisoformat(at.replace("Z", "+00:00")).astimezone(UTC)
    receipt["startedAt"] = (time - timedelta(seconds=1)).isoformat()
    receipt["completedAt"] = (time + timedelta(seconds=1)).isoformat()
    receipt.update(status="ok", completeness="bounded", stopReason="page_limit", errorCode=None)
    receipt["counts"] = dict(searchItems=1, rawRows=1, emittedRows=1, rejectedRows=0,
                             duplicateRows=0, budgetSkipped=0, detailFailures=0)
    receipt["pageReceipts"] = [dict(pageIndex=1, schemaValid=True, contentItems=1, processed=True, hasMore=None)]
    return [job], [receipt], [observation]


def combined(*samples):
    return tuple([row for sample_rows in samples for row in sample_rows[index]] for index in range(3))


def no_result(rows, *, status="empty"):
    jobs, receipts, _ = rows
    receipt = receipts[0]
    receipt["counts"] = {key: 0 for key in receipt["counts"]}
    receipt.update(status=status, completeness="exhausted" if status == "empty" else "incomplete",
                   stopReason="exhausted" if status == "empty" else "network",
                   errorCode=None if status == "empty" else "SYNTHETIC_NETWORK_FAILURE")
    receipt["pageReceipts"] = [dict(pageIndex=1, schemaValid=True, contentItems=0, processed=True, hasMore=False)] if status == "empty" else []
    return jobs, receipts, []
