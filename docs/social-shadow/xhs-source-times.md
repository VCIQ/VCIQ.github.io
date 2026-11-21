# XHS source timestamps and bounded startup acceptance

## Scope

`xhs-shadow-v2` preserves two independently valid source claims: publication
(`time`) and update (`last_update_time`). A pinned upstream live response reported
an update earlier than publication. The v1 normalizer rejected the entire note
on that ordering assumption, even though both values were valid past millisecond
timestamps and the search/detail requests had completed.

No general contract, timestamp-unit rule, future-date validation, content identity,
authentication handling, request cap, or production activation is relaxed.

## Representation

- Keep `publishedAt` and `updatedAt` equal to the individually validated source
  values. Do not swap, clamp, shift or replace either with observation time.
- Emit `SOURCE_UPDATE_BEFORE_PUBLICATION` in the result's
  `diagnostics.metadataConflicts`, with the signal identity and both normalized
  timestamps. No account identifiers, cookies or signed access links belong here.
- Leave evidence grade D / discovery / unverified and access status unverified.
  A successful transport/normalization receipt is not factual verification.
- The local review UI displays a prominent chronology-conflict warning and both
  source timestamps. The original full observation is in the review snapshot, so
  the warning remains derivable after batch storage without a new schema field.
- An absent timestamp remains absent. Wrong units, future times, invalid identity
  and secret-bearing text are still rejected. Authentication and rate-limit
  interruptions are not upgraded to success by this change.

The ordering conflict alone does not establish its cause. Do not infer scheduled
publication, an actual edit time, a recent company event or a platform guarantee
from these two source values.

## Historical evidence and replay

Old v1 failures remain immutable. A local, read-only replay may show what v2 would
produce from saved worker output, but must not replace an old checkpoint, sealed
batch, receipt, run identity or coverage record. It is not another live query.

For live post-fix validation, create an explicitly separate bounded attempt,
respect existing scheduling/pauses, use the same private state, and retain both
old and new evidence. Never overwrite a failed result to make metrics pass.

## Startup budget

On the acceptance Mac, an offline test of the full Chromium and pinned client
reached the API-send boundary in about 34.8 seconds without sending a platform
request. The former 40-second local acceptance limit left little time for
authentication, search and detail; it is not evidence of platform failure.

A separate local acceptance candidate uses 120 seconds per job and a 150-second
round limit, below the committed policy's 180-second per-job allowance. It still
uses one literal keyword, one search page, at most one detail attempt, and at most
three API dispatches including self-info. It does not change the committed default
policy or the original private control file. A repeated invocation of a completed
one-shot acceptance mode is rejected rather than silently retrying it.

## Tests

Synthetic tests cover preserved source values, explicit conflict diagnostics,
normalizer versioning, equal/later/unknown times, invalid/future timestamps,
unmodified raw capture, secret/identity rejection and retained auth restrictions.
The browser-asset tests cover the visible warning predicate without altering
evidence. Real platform responses and account data are not committed as fixtures.
