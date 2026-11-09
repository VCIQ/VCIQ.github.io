# Company-profile run receipt journal — local review prototype

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
- A second/different run ID is not blocked by local storage. Production needs
  a global writer reservation and cross-worker deduplication.
- SHA-256 is not a trusted timestamp, signature, source-fetch attestation,
  cryptographic identity proof or protection from host-level modifications.
- The current subprocess adapter is not an OS sandbox. Authentic GitHub
  provenance, exclusive CI isolation and actual HTTP origin evidence remain
  independent prerequisites.

## Testing and production gates

tests/test_company_profile_writer_receipt_journal.py contains isolated,
synthetic tests covering successful recording, crashes and partial runs,
duplicate IDs, missing/gapped/corrupt files, tampering, unsafe directories,
symlinks and failed disk writes. No real company crawling occurs.

Separate production approval still requires immutable external receipt
retention, authenticated Git-pinned inputs, a trusted OS-isolated runner,
queue consistency and final data checks, lock/recovery rehearsal, independent
review, exact-head CI approval and explicit publication reconciliation.

**Existing production schedules, main, company data, Pages and the social
Shadow stop switches are not modified by this prototype.**
