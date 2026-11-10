# Company-profile run receipts and recovery

Parent: Issue #664. This is a **non-deployed, opt-in review component**
inside stacked Draft PR #670, dependent on Draft #669 and #668.

## Why this is needed

The prior in-memory runner refuses duplicate companies only within one
process. A process crash between crawler exit and downstream queue
reconciliation leaves the next process uncertain whether a company ran.
Silently restarting can repeat source requests or mark the wrong events.

The module tools/company_profile_writer_receipt_journal.py adds a local
one-shot reservation and per-company receipt records. A local SHA-256 chain
checks accidental inconsistency, but **this is NOT immutable evidence**:
an actor with write access could replace both records and hashes.

## Explicit API and storage

Only a separately authorized operator could supply a trusted base SHA,
exclusive detached checkout, pinned selection, externally trusted runner,
and private journal root outside the checkout. It would explicitly call
RunReceiptJournal(private_parent, authorized=True) and then
observe_selected_company_crawls(..., authorized=True, journal=journal).

There is no CLI, import-time execution, scheduled trigger, real crawler
invocation, GitHub write, merge or publication path in this module.
The authorized flag is a local API guard, NOT identity authentication.

A user-owned mode-0700 private parent contains run-ID-specific directories,
created with an exclusive OS mkdir and parent directory fsync BEFORE any
crawler subprocess. A duplicate run ID is rejected without executing it.

Each run directory contains:
- manifest.json: run ID, expected commit SHA, selected slugs, hashes of the
  frozen selection/source map, and start time; never raw URLs or tokens
- receipt-00.json and successors: verified per-company exit status, capture
  timestamp, status/profile digests and a hash link to the previous receipt
- complete.json: created only after final snapshot verification; binds
  recorded count, chain head, final snapshot digest and completion timestamp

Every record uses exclusive, no-follow file creation (mode 0600), file
fsync and parent-directory fsync. inspect_run(parent, run_id) checks
permissions, file order, shape, hashes and completion. Interrupted records
return incomplete/manual triage; tampered or malformed records fail closed.
Any run-ID reservation remains until a separately reviewed recovery action.

## Important limits

- There is NO automatic retry, resume, cleanup, mark-processed, merge or
  Pages publication. Recording success does not authorize any of these.
- Local-only storage rejects a reused run ID on the same volume. Enable the
  optional cross-job archive below to use a shared reservation.
- SHA-256 is not a trusted timestamp, signature, source-fetch attestation,
  cryptographic identity proof or protection from host-level modifications.
- The current subprocess adapter is not an OS sandbox. Authentic GitHub
  provenance, exclusive CI isolation and actual HTTP origin evidence remain
  independent prerequisites.

## Optional shared reservation and S3 archive

For a separately approved pilot, pass
`CrossJobReceiptArchive(github, store, authorized=True)` as the journal's
`archive` argument. `github` is the existing `GitHubCli` adapter and
`store` is `S3ReceiptStore(client, bucket=..., owner=...)` with an
operator-supplied AWS SDK S3 client. Construct the SDK client with bounded
connect/read timeouts, one total attempt, AWS endpoints, and a narrowly
scoped role held by the trusted orchestrator outside the crawler sandbox.
The repository has no cloud dependency, credential configuration or
workflow for this mode.

1. Check the pinned remote base, complete branch inventory and open writer
   PRs. Conditionally archive the run manifest before attempting any GitHub
   mutation. That prevents reusing the run ID from a new machine even after
   the GitHub reservation has been reconciled.
2. Create a metadata-only Git commit with the pinned base's tree and the
   manifest hash, then atomically create the existing fixed writer
   reservation ref pointing to that commit. Read back the ref and recheck
   the base and inventories. The SHA identifies this run's reservation,
   including when two different run IDs race on the same base. Smoke uses
   its existing separate GitHub reservation ref and a separate S3 prefix.
3. Before each command, archive its dispatch intent and reconfirm the
   reservation and remote base. After validation, archive its chained
   receipt before the next company. Archive completion after the final
   snapshot passes validation. On any failed or ambiguous write or
   verification, stop and retain evidence and the reservation for review.

Each S3 record uses `If-None-Match: *`, SHA-256 and Object Lock
`COMPLIANCE` retention for 365 days. The store reads back the specific
returned version and checks its content, checksum, mode and retention.
Configure a dedicated versioned bucket with Object Lock enabled. Enforce
conditional writes at bucket level and deny application principals object
deletion (including delete markers), overwrites, lifecycle/policy changes
and retention bypass. Restrict writers to their own environment prefix.
The reader needs object and version reads, retention metadata and
prefix-limited list permissions so an absent key can be distinguished
from access denied. Review the bucket owner, IAM, retention and lifecycle
settings with the cloud administrator before exercising the live API.

References:
[conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html),
[Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html),
[Git references](https://docs.github.com/en/rest/git/refs).

## Continue to a Draft proposal

In the same reviewed, approved process, the pilot can pass its finished
`RunReceiptJournal` and an `EvidenceBoundWorkspace` to
`submit(..., journal=journal, authorized=True)`. This path independently
checks the archived chain, run identity, pinned base and selection,
then checks the existing GitHub reservation before remote mutations.
The candidate must pass the queue transition verifier and contain the
exact archived profile snapshot (comparison uses canonical JSON).

The writer conditionally creates a single `handoff.json` containing the
reservation anchor and hashes of both candidate files before creating
the candidate ref and Draft PR. This claim covers the run across attempt
numbers. A conflicting or ambiguous claim blocks any repeat. The recovery
reader exposes the claim for manual reconciliation with GitHub; it does
not recreate a lost job's journal or start another handoff. Neither the
proposal nor the S3 claim releases the original reservation.

If enrichment or a publication guard changes the crawled profile
snapshot, the current pilot rejects it. Production needs a separately
verified post-processing path that binds the changed snapshot to the
observed one and proves the final queue transition.

## Recovery after job loss

Stop the old worker before inspection. Preserve the GitHub ref and compare
its SHA with the archived anchor, base commit and manifest digest.
`inspect_archived_run(store, scope=..., run_id=...)` re-reads the archive
without requiring the checkout or local journal. It validates record order,
checksums, retention, the receipt chain and completion, and returns S3
version IDs for review. A company can have a verified receipt, a durable
dispatch intent without a receipt (possibly dispatched), or no dispatch
record. A missing manifest or reservation record requires checking GitHub
and job logs. A completion record with a lost acknowledgment can be
recovered from S3 even when the local completion file is absent.

The operator reconciles the archived run with the current base queue,
candidate refs and any open PR. In an ambiguous case, keep the reservation
until the status of each possibly dispatched command is reviewed. Release
requires a separate approved operation, a stopped old worker and either
reconciled queue history or an explicit decision about the pending work.
An expired or missing archive, a new run ID and an empty local volume do
not authorize retry, reservation removal or queue updates.

## Testing and production gates

tests/test_company_profile_writer_receipt_journal.py contains isolated,
synthetic tests covering successful recording, crashes and partial runs,
duplicate IDs, missing/gapped/corrupt files, tampering, unsafe directories,
symlinks and failed disk writes. No real company crawling occurs.

The archive suite runs independent simulated jobs with shared fake GitHub
and S3 APIs, plus one real offline fixture subprocess. The hosted
reservation, cloud IAM/retention and interrupted-job drill still require an
isolated live pilot. Global exclusion covers participants using the fixed ref.
The legacy direct writer does not participate and must be handled during cutover.

Independent review, an OS-isolated runner, exact-head CI and an explicit
publication handoff remain production prerequisites.

**Existing production schedules, main, company data, Pages and the social
Shadow stop switches are not modified by this prototype.**
