# PR-04: Weibo keyword search in the isolated shadow Worker

## Scope and dependencies

This stacked change builds on PR #638 (XHS/Worker), #623 (scheduler/WeChat), and
#622 (contracts). It adds `wb` to the independent MediaCrawler CLI and Worker.
It does not merge or enable any collector, publish Articles, change the formal
innovation pool, or update existing review decisions. All committed platform
switches remain false. Real-platform acceptance is `live_pending`.

The pinned upstream remains `NanmiCoder/MediaCrawler` commit
`8f583999006d5b692272c608440e193ca282e73b`. No upstream checkout is modified. There
is no automatic pull, dependency installation, login, account rotation, proxy
rotation, or CAPTCHA workaround.

## How it works

1. The existing scheduler builds one literal query per job with `platform=wb`.
2. The shared process manager checks runtime, explicit `--live`, checkout pin,
   private state, and policy limits through the CLI.
3. It uses `profiles/wb`, `locks/wb.lock`, and a fresh `python -I -B` child whose
   entrypoint is `workers/mediacrawler/bootstrap_weibo.py`.
4. The child reads only the dedicated mobile-Weibo session. It calls the pinned
   client's `/api/config` and `get_note_by_keyword(keyword=..., page=...)`.
   Its automatic retry wrapper is removed in the isolated child only.
5. A restricted transport validates successful JSON before the upstream parser
   can trigger its invalid-JSON browser-refresh/Cookie-refresh fallback.
6. The observer recognizes type-9 cards, including nested `card_group`, and the
   parent normalizes whitelisted fields into v1 observations and query receipts.
7. Existing SQLite leases and transactional checkpoints record the result.
   Sealed batch ingestion remains PR-07; the result says
   `batchIntegrityChecked=false`.

XHS still uses its original bootstrap, client, and normalizer. The shared worker
has optional platform arguments defaulting to XHS for backward compatibility.
Unsupported platforms are rejected before launching a process.

## Semantics and data limits

- IDs are exact decimal strings. Python JSON integers are converted directly to
  strings without a float intermediate. Floats, Boolean IDs and conflicting
  `id`/`idstr`/`mid` are rejected. Reposted text does not identify its parent post.
- Only search card text is collected. No comments, user graph, media, long-text
  detail expansion or personal profile fetch is performed. Diagnostics report
  `fullTextFetched=false` and `repostRelationshipsResolved=false`.
- The projection uses the pinned store's field conventions but does not call the
  store's mandatory date parser or zero-default metric conversion. It preserves
  source `created_at` until validation and missing metrics remain unknown.
  Original user IDs are hashed using the pinned upstream helper before crossing
  the process boundary; names are masked. These are not verified VCIQ entities.
- `create_time` is seconds, not milliseconds. A supplied timezone-bearing
  `create_date_time` and an absolute original source date must agree. Relative
  date labels remain null rather than being derived from observation time.
  Upstream `last_modify_ts` is never treated as publication or update time.
- Titles are derived from plain post text. Scripts/styles are not text evidence.
  Only the retained visible excerpt contributes matched terms. Merely searching
  for a company does not establish that it is mentioned in the post.
- Normalized URLs are reconstructed from the exact post ID. Access tokens,
  original profile URLs and raw user IDs are not exported. All observations
  remain `D / discovery / unverified`.

## Pagination and budgets

The pinned search interface does not establish a trustworthy positive-page
`has_more` marker. Nonempty responses therefore remain bounded at the page or
item cap, regardless of an estimated total. A successfully validated `ok=1`
response with an empty `cards` array ends that accessible query, not the entire
platform corpus. A nonempty array containing only recommendation cards is not
proof of zero content. Negative `ok`, login HTML and missing/malformed `cards`
never become successful empty results.

Duplicates across pages do not consume another projection. `maxRecords` bounds
projected candidates, not only accepted output. The retained legacy capture
counter `detailsNotRequested` is exposed as `searchItemsNotProjected` for Weibo;
there are no detail requests in this adapter. On success, search-card accounting
must balance projected rows, duplicate hits and unprojected hits.

Allowed API endpoints are exactly HTTPS GET `/api/config` and
`/api/container/getIndex` on `m.weibo.cn`, with the latter constrained to the
current query, default search type, and page range. Query terms containing the
pinned client's inner-query delimiters `&`, `=`, `#`, or `?` are explicitly
excluded with a reason rather than silently escaped/truncated. Comma terms remain
excluded by the existing single-keyword contract.

There is one authentication request plus at most `maxSearchPages` search
requests, a two-second API spacing, a 2 MiB decoded-response cap, verified TLS,
no environment proxies and no automatic redirect following. HTTP 401, 403/432,
and 429 are separate auth, verification and rate-limit states. Retry-After is
preserved. Unknown negative API JSON fails closed, including a negative response
whose message claims there are no results. Live fixtures may later justify a
narrower empty-response rule; this PR does not guess one.

The API budget does not claim to count all Chromium resource traffic. Whole-job
wall time is independently enforced by the parent process-group controller.
This is not an operating-system sandbox; the operator-selected virtualenv and
private state remain trusted boundaries. POSIX process cleanup is supported;
Windows remains explicitly unsupported, as in PR-03.

## Commands (not executed as live acceptance)

All paths below must already refer to an explicitly prepared private runtime
outside VCIQ and the pinned MediaCrawler checkout. Do not send cookies or
passwords in chat, command arguments, Git commits or CI artifacts.

Offline planning:

```sh
python -m tools.social.cli plan \
  --config config/user_tracking.json \
  --policy config/social_discovery.json \
  --platform wb --state-dir "$STATE_DIR" --dry-run
```

Write a private plan explicitly:

```sh
python -m tools.social.cli plan --platform wb \
  --state-dir "$STATE_DIR" --output weibo-plan.json
```

Manual dedicated session, only after enabling local runtime `enabled`,
`platforms.wb.enabled`, and `interactiveAuthAllowed`:

```sh
python -m tools.social.mediacrawler_cli bootstrap-session --platform wb \
  --state-dir "$STATE_DIR" --runtime-config "$STATE_DIR/runtime.json" \
  --interactive --live
```

Closing the dedicated session tab ends setup, not proof of successful login.
The subsequent query independently checks `/api/config`. No existing everyday
browser or XHS profile is reused.

```sh
python -m tools.social.mediacrawler_cli run-mediacrawler --platform wb \
  --state-dir "$STATE_DIR" --runtime-config "$STATE_DIR/runtime.json" \
  --plan "$STATE_DIR/weibo-plan.json" --live
```

After a human resolves an auth/verification issue, explicit resume is available:

```sh
python -m tools.social.mediacrawler_cli resume-platform --platform wb \
  --state-dir "$STATE_DIR" --runtime-config "$STATE_DIR/runtime.json" \
  --confirmed --live
```

Existing rate-limit cooldowns cannot be bypassed by resume. The legacy
`tools.social.cli doctor` implementation registry remains unchanged for its old
entrypoints; supported MediaCrawler entrypoints are listed by
`python -m tools.social.mediacrawler_cli run-mediacrawler --help`.

## Offline acceptance and rollback

```sh
python -m unittest \
  tests.test_social_weibo_observer tests.test_social_weibo \
  tests.test_social_weibo_transport tests.test_social_weibo_worker
python -m tools.social.cli validate --fixtures tests/fixtures/social/contracts
python -m tools.social.cli doctor --offline
```

The shared PR check automatically enumerates `test_social_*.py`, including the
new tests. It performs no live API or browser calls and uses no platform secrets.
The full existing regression suite remains authoritative; test counts/results
are recorded in PR evidence, not fabricated here.

Rollback: disable only the local `wb` runtime switch, stop shadow tasks, or revert
this PR. Keep private state for diagnosis. No production snapshots need repair,
and XHS/WeChat do not need to be disabled. Do not delete another platform's
profile while removing a Weibo session.
