# PR-07: sealed batches and the private incremental content store

## Scope and rollout boundary

Depends on PR-06 / #641 and its stacked predecessors. This PR adds an offline
storage path only. It does not change a production crawler, scheduler workflow,
static enable switch, public/data, people snapshot, innovation pool, prior review
decision, npm dependency or the pinned MediaCrawler version. No live query was
performed to implement or test this storage layer. It remains a draft integration.

All runtime files must remain under an explicit private STATE outside both VCIQ
and the configured MediaCrawler checkout. POSIX STATE/batch directories must be
0700 and input/database files 0600. The CLI requires the existing private runtime
configuration to validate those boundaries, but does not require a live platform
switch: explicit offline storage can be used while every crawler is disabled.
It never imports an upstream client, starts a browser or performs a network call.

## Batch contract

Exactly four files form a completed batch:

- jobs.jsonl: the frozen crawl_job records;
- observations.jsonl: the sanitized signal_observation records;
- query_receipts.jsonl: one frozen query_receipt per job attempt;
- manifest.json: the frozen run_manifest with hashes, byte/row counts and the
  shadow-only, publication-forbidden markers.

A package contains one runId and at most 200 jobs / 40,000 observations. Each
JSONL row is at most 512 KiB, each content file at most 32 MiB, aggregate content
files at most 64 MiB. Limits are checked during construction and reading, before
combining oversized files. The final newline is mandatory, including on a
single-row file. Empty observation files are valid; missing receipts are not.
Duplicate JSON keys, nonfinite numbers, blank lines, unknown files, malformed
UTF-8, invalid schemas, mismatched hashes/counts, orphan references, conflicting
run/configuration identities, cross-job observation metadata, invalid time
windows, impossible page budgets and duplicate observations fail closed.

Byte integrity does NOT establish authenticity of a platform response or truth
of an event. A caller who controls both payload and manifest can recompute their
hashes. The source collector and trusted local operator remain the trust boundary.
All observations retain their D/discovery/unverified evidence classification.

The writer uses a new private staging directory, fsyncs files, writes the manifest
last, validates it, then renames the directory into place. Interrupted staging
remains diagnostic material and is never imported by the import CLI. Existing
batch destinations are never overwritten. CLI resealing of identical inputs
reuses the original createdAt and is idempotent. Callers of the lower-level
seal_batch API should pass the same created_at when intentionally replaying a seal.
These are local integrity checks, not an OS sandbox against an adversarial user
who can concurrently replace owned directories. Use a single trusted sealing
process per destination; immutable published packages may be read repeatedly.

## Independent database and identity

The content database is STATE/signals.sqlite3, separate from the existing
scheduler STATE/state.sqlite3. The initial SQL migration is
`tools/social/migrations/001_signals.sql`. Application ID, schema version, the
expected table set and migration fingerprint are checked. An unrelated or unknown
database is rejected, not overwritten or silently migrated. SQL parameters carry
all user data; foreign keys are enabled and writes use BEGIN IMMEDIATE.

The store separates:

- batches: the immutable run identity and manifest hash;
- attempts: original jobs and their receipts, including failed/empty results;
- signals: one platform/type/native identity, first/last seen and newest snapshot;
- versions: immutable CONTENT_FIELDS snapshots keyed by contentHash;
- observations: per-attempt content provenance, metrics and original timestamps;
- aliases: only explicitly supported content aliases, currently BVID;
- evidence_pins: immutable review-reference-to-version protection;
- retention_events: explicit historical-text deletion audit entries.

One imported runId has one manifest fingerprint. Importing that same package
again is a no-op. Changing the same run or reusing an attempt in another run is
a conflict, not an overwrite. Distinct keywords can point to one signal and one
content version while retaining separate observations and query receipts.
Content changes create new versions. Likes, observation time, update metadata
and alias enrichment do not create versions unless frozen CONTENT_FIELDS change.

All inserts for a batch commit together or roll back together, including a late
alias conflict or a database lock failure. Empty results, partial failures and
platform deactivation never delete prior content. A failure receipt with valid
observations can retain those observations without being upgraded to success.
Importing storage never updates a query's scheduler coverage or authentication
pause state.

Latest selection uses normalized observedAt, then attemptId and payload digest
as a deterministic tie-break. Older imports can extend firstSeen/history but
cannot roll back lastSeen or the latest metrics/content. A BVID cannot refer to
two aids, an aid cannot claim conflicting BVIDs, and a Zhihu answer cannot change
its known parent question. Missing parent information may be enriched later.
Same titles never cause cross-platform or cross-ID merges. Unknown alias families
are rejected until their semantics are deliberately implemented.

## Quarantine and explicit retention

Import first verifies the full input before opening the database. On failure it
leaves the source package untouched and writes a sanitized rejection ledger under
STATE/quarantine. The ledger includes a reason code and hashed source reference,
not the source path, raw content, cookies or exception text. This is logical
quarantine, not a filesystem move. If quarantine cannot be recorded, the failed
result explicitly reports quarantineRecorded=false; it never reports success.

Retention is NEVER triggered by a crawl or normal import. Preview requires an
explicit timezone-aware cutoff. It selects only historical versions whose last
observation is before that cutoff, excluding the current version and every
pinned version. Applying requires the exact preview planHash, recomputed inside
the transaction. A new pin or relevant observation invalidates a stale plan.

Pinned versions and all their retained observations survive normal retention.
A pin is idempotent but cannot be retargeted; this PR intentionally provides no
automatic unpin. Pinning is not an approval decision, publication or a claim of
verified evidence. PR-08 must pin evidence before persisting an audit reference.
Batches/attempt receipts and identity constraints survive retention, preventing a
replayed old batch from resurrecting its removed text. Current-version observations
are conservatively kept. Retention here concerns the content database only: it
does not delete source packages, scheduler checkpoints, pending worker outputs or
backups, and is NOT a claim of complete data erasure or immediate disk reclamation.

## Explicit operator entrypoints

These examples document the new commands; they are not evidence of live operation.
STATE and runtime.json must already satisfy the private path/permission rules.

```sh
# From a plan and a list of worker results (each has receipt/observations/hints/diagnostics):
python -m tools.social.storage_cli seal --state-dir "$STATE" \
  --runtime-config "$STATE/runtime.json" --plan "$STATE/plans/run.json" \
  --results "$STATE/results.json" --output "batches/$RUN_ID"

# Alternatively read completed results from the scheduler in a read-only snapshot:
python -m tools.social.storage_cli seal --state-dir "$STATE" \
  --runtime-config "$STATE/runtime.json" --plan "$STATE/plans/run.json" \
  --from-checkpoints --output "batches/$RUN_ID"

python -m tools.social.storage_cli verify --state-dir "$STATE" \
  --runtime-config "$STATE/runtime.json" --batch "batches/$RUN_ID"

# Without --apply this only verifies; it does not create the content database:
python -m tools.social.storage_cli import --state-dir "$STATE" \
  --runtime-config "$STATE/runtime.json" --batch "batches/$RUN_ID" --apply

python -m tools.social.storage_cli inspect --state-dir "$STATE" \
  --runtime-config "$STATE/runtime.json"

python -m tools.social.storage_cli pin --state-dir "$STATE" \
  --runtime-config "$STATE/runtime.json" --reference "$REVIEW_REFERENCE" \
  --signal-id "$SIGNAL_ID" --content-hash "$CONTENT_HASH"

# Preview; supply --apply --plan-hash "$PLAN_HASH" only for an explicit application:
python -m tools.social.storage_cli retain --state-dir "$STATE" \
  --runtime-config "$STATE/runtime.json" --before "$CUTOFF_WITH_TIMEZONE"
```

Checkpoint export verifies the saved result hash and requires a receipt for every
job in the supplied plan. A not-started/paused job is NOT fabricated into an empty
receipt. An incomplete plan is rejected, with no published package. The later
PR-09 coordinator must explicitly decide the completed run boundary; it must not
append new data to a run that has already been sealed. The batch API can accept
an explicitly selected set of completed jobs with its actual receipts, preserving
original identities. Raw index hints and worker diagnostics stay in their original
private checkpoints; they are not promoted to content observations.

The original worker/doctor output may still say batchIntegrityChecked=false. That
is accurate for unsealed worker results. Only the new verifier/importer's output
can attest batch integrity for the package it just processed; historical files are
not rewritten to flip that flag. Whole-pipeline automated wiring remains PR-09.

## Acceptance and rollback

```sh
python -m unittest tests.test_social_batch tests.test_social_signal_store \
  tests.test_social_storage_cli tests.test_social_storage_boundaries
python -m tools.social.storage_cli --help
python -m tools.social.cli doctor --offline
```

Tests use synthetic evidence and temporary private files, actual SQLite
transactions/locks, and the real storage CLI. Network and subprocess access is
blocked in the offline checks. The PR conversation records exact tested commits
and Actions runs; offline success does not prove live platform compatibility.

To stop, stop invoking the storage CLI/coordinator. Reverting this PR does not
require any production-data rollback. Preserve private batches, receipts and pins
for investigation rather than deleting them. The old production chain and the
existing query scheduler are untouched. Review UI/decisions remain PR-08; aggregate
shadow execution, real-traffic acceptance and benefit evaluation remain PR-09.
