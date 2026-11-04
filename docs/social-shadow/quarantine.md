# Quarantine a known zero-content WeChat budget failure

This is an offline, explicit administrative recovery path for the record-budget
bug fixed in PR #646. It is NOT a general-purpose skip, force-success, retry,
authentication-resume, or quota-reset command. It does not run a collector.

## Narrow admission criteria

The original checksummed report must be `blocked` at `collect-results` with
`batch_record_budget`. The original plan must be valid and contain only WeChat
jobs. At least one uncheckpointed result must reproduce that validation error
and its original journal must record that exact error. All results from every
source (saved files, pending files, and SQLite checkpoints) must agree. No result
may contain normalized observations, including results that would otherwise be
valid. Valid receipts in the same run are retained for the normal storage path.

Unknown errors, missing execution evidence, mismatched identities, conflicting
copies, already closed/imported runs, nonempty results, or authentication,
verification and rate-limit results are rejected. An existing platform pause is
not cleared or worked around. Corrupt, public, linked, or oversized files are
rejected using the existing private-path and bounded-read guards. Reads across
the run have a 16 MiB aggregate bound.

The coordinator stop marker must remain present and valid. No current query or
platform lease may still be active. Lease expiry is NOT proof that a process has
stopped: applying additionally requires the operator to actually verify no worker
is running and pass `--confirm-workers-stopped`. A local reviewer label records
who asserted this; it is not independently verified identity or a signed audit.

## Operator sequence

Do not delete the blocked run, pending receipt, database or stop file. Do not
alter counts, raise the historic job budget, or create fresh STATE to reset an
exhausted request grant. Keep the same private state directory and runtime.

First inspect the worker state on the actual host. Then preview:

```sh
python -m tools.social.quarantine \
  --state-dir "$STATE" --runtime-config "$STATE/runtime.json" \
  --run-id "$RUN_ID"
```

Preview does not create locks, databases, audit files or a closure. Its fingerprint
binds the exact intent, journal, original report, every original file source and
every checkpoint result (including missing sources). It does not print receipt
contents, URLs, hints or private paths. Review the requested operation before
applying, using the fingerprint returned by that preview:

```sh
python -m tools.social.quarantine \
  --state-dir "$STATE" --runtime-config "$STATE/runtime.json" \
  --run-id "$RUN_ID" --apply \
  --expected-fingerprint "$FINGERPRINT" \
  --reviewed-by local-operator --confirm-workers-stopped
```

Apply rechecks evidence under the existing coordinator lock. It atomically saves
`orchestration/<runId>/quarantine.json` before advancing recovery. This immutable,
checksummed record contains the original blocked report as an exact UTF-8 byte
representation, its fingerprint, the operator attestation, and the chosen closure.
The original report bytes remain recoverable from `originalReportRaw.encode('utf-8')`.
Original pending/saved receipts and their counts remain in place, unchanged.

The closure excludes invalid receipts from the sealed batch; it records them as
`quarantined_invalid_result` with their original error, observed raw count and
configured limit. `rawReceiptPresent=true` and `receiptAccepted=false` distinguish
an invalid received receipt from a genuinely missing one. It does not invent a
replacement receipt. The existing storage-only recovery code seals and imports
only valid zero-content receipts, if any, and refreshes the review queue normally.
No invalid content is admitted, and scheduler finish/claim are not invoked.

## Results are not crawl success

`ok=true` in this command means the administrative quarantine operation finished.
It always returns `runHealthy=false`, zero new observations and `liveExecuted=false`.
The normal run report stays `degraded`, not `completed`, with the rejected attempt
visible and `checkpointReconciliationRequired=true`. `pipelineComplete=true` means
only that its accepted storage subset has finished, not that the original crawl
or every job succeeded. Health and ordinary recover continue to show this failure.

The stop marker, scheduler leases, coverage dates, failures, request usage, quota,
retry cooldowns, runtime switches and production files are not modified by this
command. No automatic resume follows quarantine. Before any new bounded trial,
inspect health, reconcile the host/network problem, verify workers have stopped,
and authorize a legitimate non-overlapping budget window through the existing
process. Never treat quarantine as permission to bypass a restriction.

## Interrupted operations

The first audit decision and its original report archive are immutable. A crash
after the decision, materializing valid results, closure creation, or content
import can be retried with the same fingerprint and reviewer. A newly generated
valid saved copy is allowed only when its content matches that decision. Any
original artifact change, changed closure, altered checkpoint, or different
reviewer is rejected. The operation does not re-query the source or double-import.
If storage recovery is still blocked, the command reports that stage as failure
and preserves evidence for another offline recovery attempt.

## Validation and deployment boundary

`tests/test_social_quarantine.py` uses actual temporary private files, SQLite,
locks, original orchestration, sealing, import and review operations. Collectors
are injected and all external I/O is denied. The existing Linux/macOS social test
workflows discover this new test module; no new workflow or secret is needed.

```sh
python -m unittest tests.test_social_quarantine
python -m tools.social.quarantine --help
```

Creating this implementation does not mean it was applied to the user's Mac.
The latest connection attempt failed. No real saved run, credential, quota,
worker, authentication pause or production state was changed in this work.
TLS trust-store failures, rejected destination URLs, pinned MediaCrawler checkout,
real browser authentication/search and real incremental value remain separate
live-acceptance items; this command does not fix or certify them.
