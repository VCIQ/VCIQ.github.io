# Company profile refresh: offline transition contract

**Status: isolated proposal, not activated.** Related: Issue #664 and
Draft PR #665. This contract does not modify the active
`company-profile-incremental-refresh.yml` workflow.

## Why this check is needed

The current writer selects up to 10 companies, crawls them, marks article
fingerprints processed, reconciles profiles, validates, and directly commits
two JSON files to `main`. When the queue is rebuilt after
`--mark-processed`, the originally selected entries may disappear. Therefore
a proposal based only on the final queue cannot demonstrate that each
processed fingerprint belonged to the original permitted selection.

The future PR writer must hold **three separate immutable snapshots**:

1. **Base:** `company_profile_refresh_queue.json` and
   `venture_profiles.json` from the identical recorded `main` commit.
2. **Pre-crawl selection:** the queue immediately after high-signal event
   selection and *before* crawler execution or `--mark-processed`.
3. **Candidate:** the final queue and profile snapshots after the existing
   publication and cross-field validation gates complete.

It must also preserve a separately attested **runtime window**
(`run_started_at` / `run_completed_at`, UTC, maximum 90 minutes) from the
actual job execution. The queue's `generatedAt` reflects the underlying
**article snapshot timestamp**, not necessarily the wall-clock time at which
`--mark-processed` executes. A real run may therefore have
`processedAt` later than `generatedAt`; rejecting it for that reason is
incorrect. Event timestamps and the 90-day retention cutoff are evaluated
against the explicit runtime window, while the article snapshot chronology
is checked separately. Missing, reversed or implausibly long runtime
windows cause the validator to fail closed.

Pass those JSON objects and the attested runtime window to
`tools.company_profile_writer_transition_gate.check_transition(...)`.
Any additional coverage-only company slugs must come from a separately
authenticated, bounded pre-crawl coverage report; they are **not inferred**
from candidate changes or automatically trusted.

## What is checked

- Input schema and timestamp chronology, fingerprint structure, unique
  selected companies and the maximum selection limit. The chosen slugs must
  be precisely the first `min(selectionLimit, pendingCount)` queue entries;
  `selected`/`pending` statuses must match the ordered selection. The final
  queue must also have internally consistent counts, selection and status.
  Truncated queue entries must use exactly `min(pendingCount, 100)` rows,
  and their ordering must follow the existing deterministic priority sorter
  (descending priority, then publishedAt and companySlug).
- No article marked processed before its crawl; exactly the selected event
  fingerprints become newly processed.
- No rewriting of prior processed-event records, and no recent history lost.
  Removal of records older than the queue's retention period is permitted.
- No unexpected deletion or mutation of company records. Changed companies
  must belong to the pre-crawl selection or separately attested coverage set.
- Bounded profile root metadata; unexpected schema/identity changes are
  rejected instead of silently reconciled.

The existing public queue/profile snapshot was additionally checked against
these structural invariants without modifying it. That check is a single
read-only compatibility inspection, not real collection acceptance.

## What this does *not* prove

A passing synthetic check cannot certify successful fetching, sufficient
official-source evidence, correct financial facts, fresh authentication, or
real company change quality. It also cannot establish that `main` has not
advanced. The future writer must compare the actual current GitHub main SHA
with the candidate base SHA at every commit/PR boundary, and rerun existing
coverage, publication and cross-field guards before review.

**No merge, publication or Pages dispatch is authorized by this checker.**
There is no CLI apply path or production workflow call. It requires human
review and a separate, explicitly approved integration PR before use in any
scheduled company refresh job.
