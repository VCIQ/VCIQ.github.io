# PR-02: full-vocabulary planning and WeChat shadow collection

## Boundary

This change depends on PR-01 / PR #622. No production crawler, workflow, source
configuration, Article snapshot, formal project pool, or existing review decision
is changed. No MediaCrawler process is run here. Only WeChat has a live execution
adapter in this PR; four other platforms can be planned but not executed.
All fixtures are synthetic. Real-source acceptance remains `live_pending` until
an operator supplies the private runtime and a combined request-budget reservation.

## Query registry and scheduler

`build_query_registry()` reads complete enabled tracks, including all keywords,
companies and people. It does not call a production helper that truncates lists.
NFKC/whitespace normalization preserves literal meaning. Alias merging is explicit
only. Identical native queries share a queryId across tracks. List insertion,
reordering, or unrelated terms do not change existing identities. Excessive length,
unsupported quoting/comma syntax, and sensitive input have explicit exclusions.
Exclusions count in coverage; they are not silently dropped. Empty/invalid list
shapes are rejected. The optional account registry adds account-scoped queries;
track-scoped queries never acquire an implicit account restriction.

Planning is read-only by default. Ranking uses oldest successful coverage, then
oldest attempt and priority. At least one ready long-tail query is reserved per
nonempty platform batch. Limits are per platform, not an accidental global prefix.
SQLite state is under an explicit private directory outside both repositories.
Successful and confirmed-empty receipts advance coverage; partial/error receipts
do not. Receipt, observations/hints and the next-due checkpoint commit together.
A platform lease serializes its network work. Expired leases can be reclaimed;
a late worker cannot overwrite the newer attempt. Query removal tombstones state
without erasing prior receipts. Same-result replay is idempotent; conflicting
results for the same attempt fail closed.

## WeChat discovery and verification

- Sogou calls the existing pure `build_search_url(..., query=job.query.text)`.
  Queries longer than its 38-character limit are excluded before transmission.
- Bing uses an exact quoted term plus the fixed original-article domain. It has
  one response page in this adapter; positive results are explicitly bounded.
- Unknown HTML is a schema failure. An explicit zero-result search response is
  different from an empty output file, a login page, or failed original retrieval.
- Production search and article parsing helpers are reused without `install()` or
  calling the production crawler main. Account attribution comes from the original
  page, not the search snippet or configured account name. Future, over-45-day,
  irrelevant, and wrong-account originals are rejected. Missing original dates
  remain hints; observation time is never substituted for publication time.
- Original fetch failure keeps a safe discovery hint and a failure receipt. A
  successfully fetched page is still D/discovery evidence, not a verified fact.
- Only complete HTML ampersand entities are decoded in URLs. Literal `&timestamp`
  is not interpreted as the HTML entity `&times`. Signed fetch locators are used
  internally without stripping necessary parameters. Safe identities retain
  `__biz`, `mid`, `idx` or the opaque `/s/...` ID; signed locators are never exported.
- Redirect destinations are checked on every hop against exact HTTPS hosts/paths.
  DNS results must be public IPs; TLS connects to a pinned IP with hostname
  verification. Proxy environment variables are not used. No CAPTCHA solving,
  login automation, secret headers, or persistent browser sessions are involved.

## Private execution, quotas and hard time limits

Only `run-wechat` with **both** `--live` and an enabled private RuntimeConfig can
start network work. Merge, import, doctor, coverage, and plan cannot do so.
Each job executes in a spawned child with a parent-enforced wall-time limit.
Search, resolution, original retrieval and redirect requests all debit the same
private SQLite quota. Requests across jobs reserve at least 1.25 seconds spacing.
Authentication/verification pauses the whole platform until explicit local
`resume-wechat --confirmed`; this is not verification bypass. An unelapsed
Retry-After cannot be cleared by that command.

A required private budget grant has exactly these fields (illustration only):

```json
{
  "windowStart": "2026-10-24T12:00:00+00:00",
  "windowEnd": "2026-10-24T13:00:00+00:00",
  "combinedMaxRequests": 50,
  "productionReservedRequests": 40
}
```

Choose a current window, at most 24 hours, based on the actual source budget.
The example leaves at most 10 shadow request reservations. The production number
is an **operator reservation**, not measured production traffic. Existing remote
GitHub Actions do not share this local database. Operators must reconcile their
production allocation and use nonoverlapping collection windows; this PR does
not claim to meter remote production traffic. Altering an existing grant or
opening an overlapping grant cannot reset consumed shadow quota. A crash can
conservatively spend a reservation without obtaining a response.

## Commands

The original `validate` / `doctor --offline` commands remain available.

```sh
# No writes and no network. STATE_DIR must be an absolute path outside worktrees.
python -m tools.social.cli plan --config config/user_tracking.json \
  --policy config/social_discovery.json --state-dir "$STATE_DIR" --dry-run

# Explicitly save a plan privately; still no network, no lease, no state sync.
python -m tools.social.cli plan --config config/user_tracking.json \
  --state-dir "$STATE_DIR" --wechat-provider sogou-weixin --output plan.json

python -m tools.social.cli coverage --state-dir "$STATE_DIR"

# Operator-only opt-in. Plan, runtime.json and budget.json all reside in STATE_DIR.
python -m tools.social.cli run-wechat --state-dir "$STATE_DIR" \
  --plan "$STATE_DIR/plan.json" --runtime-config "$STATE_DIR/runtime.json" \
  --budget-file "$STATE_DIR/budget.json" --live

# After manually addressing verification. Never overrides a pending Retry-After.
python -m tools.social.cli resume-wechat --state-dir "$STATE_DIR" \
  --runtime-config "$STATE_DIR/runtime.json" --confirmed
```

Git metadata is read without executing git; archive checkouts require explicit
`--vciq-commit`. Running requires the plan's code/configuration to match the current
inputs and enforces the policy budget again. The default committed policy remains
disabled; an explicit private runtime may opt into implemented platforms without
rewriting it. Runtime cannot enlarge budgets. State directories/database files
require private POSIX permissions. Plan previews never create absent directories.

PR-02 results live in `social_query_results` in private `state.sqlite3`. They are
not sealed ingestion batches: batch hashes/import integrity belong to PR-07, and
CLI continues to report `batchIntegrityChecked=false`. A hard-killed child does
not manufacture successful page evidence. An unfinished private output can be
inspected but is never treated as a successful receipt.

## Acceptance and rollback

Offline tests cover W01-W09 plus state fencing, transactional/idempotent results,
real downstream query URLs, original-page account checks, signed URL identity,
redirect/DNS controls, quotas, and read-only planning. The 447-keyword synthetic
case must cover all 447 in 45 batches of 10 when every attempt succeeds. Actual
VCIQ parent-package and production-wrapper regression results must come from the
GitHub checkout, not a substitute test-only package.

No live WeChat collection is performed by the tests. CI success does not prove
Sogou/Bing availability, platform completeness, or permission for publication.

Rollback: disable the private runtime and stop launching shadow commands. Revert
this PR's new modules/tests and its additions to the new CLI/policy. Keep private
state for diagnosis. No production snapshots or existing workflow state need
restoration. Do not suppress the unrelated existing npm dependency security gate.
