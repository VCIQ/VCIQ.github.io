# WeChat smoke follow-up: record budgets and TLS diagnostics

## Provenance and scope

This follow-up is based on integration PR #645 at
`c6ed50e7db62d53c53a156d38cc6bd329bbfcf1c` (tree
`541342f40757bbda7a93f816ca14bc1b9cd5394c`). The reconnect inspection found a
local validation commit with the same complete tree, plus two uncommitted
adapter fixes and a regression module. Those edits were read and preserved,
not overwritten or reset. This change publishes that previously uncommitted
fix for independent review and CI. It does not claim those local edits were
all newly authored during the reconnect.

The existing private smoke records showed:

- One completed degraded run: two error receipts, no normalized observations.
- One blocked run: `batch_record_budget` during result collection. A pending
  receipt had `rawRows=3` while the job cap was one, and the combined request
  grant stopped further requests with `REQUEST_BUDGET_EXHAUSTED`.
- A separate receipt had `UNSAFE_DESTINATION`; this patch does not relax URL
  validation or claim that redirect issue is resolved.
- The recorded grant reserved six of twelve combined requests for production;
  the six-request shadow allowance in that window had been consumed. The
  existing stop marker and all historical data are intentionally retained.

These are findings from saved operational records, not a new successful live
crawl. They do not demonstrate new usable articles, keyword coverage, or gains.

## Fix

`maxRecords` now bounds attempted raw records, including rejected details,
content-relevance rejections, and duplicate records. The count does not reset
across search pages. The producer therefore observes the same hard bound as
the sealed-batch validator. The validator and frozen schema are unchanged.

Unvisited search cards are counted separately as `detailsNotRequested`, not
as fabricated normalization outcomes. `searchItems` remains the actual number
of returned cards. Reaching the record cap does not claim search exhaustion.
Authentication, verification, and rate-limit errors still terminate requests.

TLS certificate-validation and other TLS errors now have distinct fixed error
codes. Certificate and hostname validation, DNS checks, URL allowlists,
redirect rules, request quotas and retry behavior are unchanged. No exception
text, certificate content, access token, or credential is exported. This is
error classification, not a certificate-store repair or a TLS bypass.

## Verification and operating boundary

The regression module uses only synthetic transports. It checks six record
budget cases and four TLS/network/timeout classifications, including real
`build_batch` validation of resulting records. Use:

```sh
python -m unittest tests.test_social_wechat_live_regressions
```

The existing Linux and macOS social workflows discover the new module.
Passing CI does not retroactively validate an over-budget pending receipt.
Do not trim historical counts, replace a real failure with an empty result,
delete the blocked run, clear the stop marker blindly, or recreate state to
reset an exhausted grant. Recovery of the preserved invalid batch needs a
separately audited rejection/quarantine path before another live trial.

The newly supplied connection passed command execution and patch dry-run;
subsequent execution requests returned 502. Remote publication and CI use the
GitHub connector. No successful new deployment, platform login, or real
search is claimed by this change. No production files, workflows, default
activation flags, npm dependencies or previous review decisions are changed.
