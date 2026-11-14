# PR-03: isolated MediaCrawler XHS worker

## Scope and honest readiness

Depends on PR-02 (#623) and PR-01 (#622). Adds a dedicated executable XHS search
entrypoint and reuses the same full query registry, plan contracts, SQLite leases,
checkpoint transaction and discovery-only observations. All committed activation
flags remain false. No production crawler, data, review ledger, watchlist or
production workflow is changed. No real login/query has been performed by this
implementation session. Live readiness remains `live_pending`, not a CI claim.

`python -m tools.social.mediacrawler_cli` is the new opt-in entrypoint; the original
`tools.social.cli` remains backward compatible and supplies planning. Its PR-02
static implemented-platform list is not an environment/live readiness report.

## Upstream boundary

Pinned checkout: `NanmiCoder/MediaCrawler` at
`8f583999006d5b692272c608440e193ca282e73b`. The existing lock file stays unchanged,
including the empty physical patch list. Preflight verifies the commit, repository
root, clean tracked files, absence of unexpected untracked files and local `.env`.
No checkout, install, pull, dependency update, or source mutation occurs on run.
The operator-installed virtualenv is a trust boundary, not an OS security sandbox.

The companion does NOT call the upstream `main()` or crawler `start()`, whose
defaults can reuse CDP/browser sessions or initiate login. It creates one dedicated
Playwright persistent context and reuses the pinned client methods and
`store.xhs.update_xhs_note()` mapping with an in-memory capture store in the child.
The original upstream `search()` is deliberately not used: it can exit on
`has_more=false` before processing final `items`. The independent tested loop
processes items before the terminal marker; no upstream file patch is needed.

The child runs with `python -I -B`, a minimal environment, discarded stdout/stderr,
no VCIQ root on sys.path and explicit import-origin checks. It never forwards
Cookie/API-key/proxy environment values. It does not reuse daily Chrome, CDP,
comments, media downloads, proxy rotation, or automatic login. The parent enforces
wall time by terminating the child's process group, including Chromium. Initial
live process support is POSIX (Linux/macOS); native Windows is explicitly rejected
rather than claiming untested process-tree cleanup.

The HTTP adapter allows only the fixed XHS self-info/search/feed API paths, with
TLS validation, no redirects, no proxy, 2 MiB responses, sequential calls and a
minimum two-second API interval. The upstream automatic retry decorator is not
used. HTTP 401/403/429/461/471 and known platform restriction codes stop the job;
Retry-After is retained. These API counters are not a claim to measure every
browser asset request. Browser session setup uses the normal first-party website.

## Query/result contract

One job is one literal keyword, one dedicated profile and bounded pages/details.
`maxRecords` also caps detail attempts; unrequested details are explicitly counted
as `detailsNotRequested`, NOT fabricated normalizer `budgetSkipped` rows.
Missing/invalid HTML/JSON is not an empty search. Unknown `has_more` cannot prove
exhaustion. The frozen v1 contract has no bounded-empty success representation,
so an all-empty response without an exhaustion marker fails conservatively with
`EMPTY_COVERAGE_UNPROVEN`. Normal positive bounded results remain valid.

Normalize standard mapped note fields only. Native note IDs, not search terms or
access tokens, define identity. Millisecond timestamps are validated, not guessed;
missing dates stay null. Creation/update/observation times remain distinct.
Approximate counts such as `1.2万` are marked approximate; `--` is unknown.
Author names remain masked and creator hashes are never treated as real entity
identity. Canonical URLs contain no access token and are NOT guaranteed publicly
accessible. Every admitted item stays grade D / discovery / unverified.

Capture files live only under the private state directory. Embedded sensitive
strings are rejected before normalized persistence; unstructured errors are never
printed. A process exit of zero without a valid receipt produces
`WORKER_NO_RECEIPT`, not success. Later network failure retains valid observations
with partial status. Authentication/verification/rate restrictions keep their
specific state even when earlier observations exist, so scheduling is paused.

## Operator setup (not executed by CI)

Prepare an independent checkout at the exact pin and install its dependencies in
an isolated virtualenv. Because upstream dependency ranges can change resolution,
record `pip freeze` in the private state directory; a pinned source commit alone
is not a dependency-reproducibility guarantee. Do not change the production app's
dependencies. Put browser binaries in the explicit private directory:

```sh
umask 077
# MC and STATE_DIR are absolute, non-overlapping paths outside the VCIQ checkout.
PLAYWRIGHT_BROWSERS_PATH="$STATE_DIR/browsers" \
  "$MC/.venv/bin/python" -m playwright install chromium
```

Use the existing v1 RuntimeConfig shape with `stateDir`, `mediacrawlerDir` and
`profileRoot="$STATE_DIR/profiles"`. Enable only xhs locally. Do not add cookies or
passwords to that JSON. Before manual setup, set `interactiveAuthAllowed=true`.

```sh
python -m tools.social.mediacrawler_cli bootstrap-session --platform xhs \
  --state-dir "$STATE_DIR" --runtime-config "$STATE_DIR/runtime.json" \
  --interactive --live
```

Log in through the opened dedicated browser and close its tab when finished.
Session setup is not a query, and does not claim authentication verified. Every
run independently calls the upstream self-info check. Routine runs never launch
an interactive login; an expired session returns auth_required. Restore
`interactiveAuthAllowed=false` after setup.

```sh
python -m tools.social.cli plan --platform xhs \
  --state-dir "$STATE_DIR" --output plan-xhs.json
python -m tools.social.mediacrawler_cli run-mediacrawler --platform xhs \
  --state-dir "$STATE_DIR" --plan "$STATE_DIR/plan-xhs.json" \
  --runtime-config "$STATE_DIR/runtime.json" --live
# After an operator resolves an authentication/verification interruption:
python -m tools.social.mediacrawler_cli resume-platform --platform xhs \
  --state-dir "$STATE_DIR" --runtime-config "$STATE_DIR/runtime.json" \
  --confirmed --live
```

Plans must match current code/configuration and exact policy budgets. No automatic
budget widening, native date-filter support, or comma-query reinterpretation.
Resume cannot bypass a pending Retry-After cooldown. Runtime data stays outside
both checkouts. Reverting/disabling this feature never requires production-data
rollback. Sealed batches/content-store import remain PR-07; review remains PR-08.

## Reproduction and remaining acceptance

```sh
python -m unittest tests.test_social_xhs_observer tests.test_social_xhs \
  tests.test_social_mediacrawler_worker
```

All records/callbacks are synthetic. CI installs no MediaCrawler dependencies,
launches no browser and uses no platform secrets. The dedicated offline workflow
now discovers all `test_social_*.py` modules. Live authentication, a real query,
real source-shape confirmation and environment-specific cleanup still require
separate evidence. This PR must not be represented as production integration.

Source anchors: pinned `media_platform/xhs/{core,client}.py`,
`store/xhs/__init__.py`; Python subprocess timeout/process-group documentation;
Playwright persistent-context documentation. No unsafe source-content instruction
can become a shell command, arbitrary URL, SQL statement or review decision.
