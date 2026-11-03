# PR-07 — sealed local batches and content revisions

A batch contains only jobs.jsonl, observations.jsonl, query_receipts.jsonl and
manifest.json. Files are UTF-8 JSONL with a final newline. Whole-file byte hashes,
byte lengths and row counts are checked, followed by strict schema, identity,
job/receipt/observation links, per-job budgets and observation-time bounds.
Missing files, symlinks, extra files, duplicate JSON keys, NaN, excessive sizes,
unsealed directories and conflicting records are rejected, never partially imported.
SHA256 establishes byte integrity only, not sender authentication. Cross-machine
transfer is not enabled by this implementation.

The writer fsyncs new private staging files and renames a completed directory.
A repeated seal of exactly the same attempts is idempotent. Differing payloads
at the same sealed path are rejected. Unique staging directories alone may be
removed on a failed write; no user-owned profile or existing batch is deleted.

The private SQLite store uses the guarded scheduler database. Schema version 1
is an additive migration, not a production migration. Jobs, receipts, observations,
content revisions and batch membership are separate. Signal identity excludes
query terms; identical content rediscovered through another query is one signal
with multiple observations. Content hashes exclude likes and observation times.
Importing older batches cannot move lastSeenAt or current content backwards.
An attempt replay is idempotent; conflicting replay rolls back the whole transaction.
Explicit aid/BVID aliases cannot point to different aids without manual resolution.

Command examples (standalone CLI, no network):

```sh
python -m tools.social.data_cli seal --state-dir "$STATE_DIR" --job "$STATE_DIR/job.json" --result "$STATE_DIR/pending/ATTEMPT.json"
python -m tools.social.data_cli ingest --state-dir "$STATE_DIR" --batch "$STATE_DIR/batches/BATCH"
python -m tools.social.data_cli inspect --state-dir "$STATE_DIR"
python -m tools.social.data_cli backup --state-dir "$STATE_DIR"
python -m tools.social.data_cli gc --state-dir "$STATE_DIR" --days 90
```

Ingest rejection writes only a sanitized quarantine marker; it does not copy
possibly sensitive corrupted source bytes into public output. GC is a dry run by
default. Explicit --apply only removes old non-current, non-review-referenced
content revisions and their observations. Current snapshots, audit receipts and
review-referenced evidence remain. Full historical backups remain private.

Rollback: disable the new importer and restore a validated private SQLite backup
while all local workers are stopped, or keep the additive tables unused. No
production data, original source batches, formal watchlist or existing decisions
need restoration. Real platform completeness is not established by storage tests.
