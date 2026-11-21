# PR-05: Bilibili keyword search and video identity reconciliation

## Boundary

Depends on PR-04 / #639. The original `tools/person_video_discovery.py`, people
snapshots, production crawlers and workflows are unchanged. All committed
platform switches remain disabled. This is shadow code, not a production rollout.
No real Bilibili login, query or browser acceptance has been executed during
implementation. Live acceptance remains `live_pending` even when offline CI passes.

## Runtime design

The shared Worker dispatches `bili` to `bootstrap_bilibili.py`, using the dedicated
`profiles/bili` directory and `locks/bili.lock`. It requires both private runtime
activation and `--live`, a clean pinned upstream checkout, an explicit external
state directory and a separately installed Python environment. The source pin is
`8f583999006d5b692272c608440e193ca282e73b`; no auto-pull/install is performed.

Only the pinned BilibiliClient search/detail methods and user anonymization helpers
are reused. The original crawler main/start and automatic login are not called.
The child imports from the upstream tree, never VCIQ's same-named tools/config.
No cookies, tokens or credential environment are passed as command-line arguments.
The parent discards raw stdout/stderr and cleans the entire POSIX process group.
Native Windows remains unsupported; do not claim untested process-tree cleanup.

Query authentication explicitly calls nav rather than pong, so restrictions are
not swallowed. Signing keys from that response are cached inside the one-query
process; key URLs are never fetched. The pinned signer removes `!'()*` from
values. Such literal keywords are therefore excluded with an explicit reason,
not silently altered. Native date filtering is not claimed; post-filtering uses
known UTC publication dates and preserves unknown timestamps as null.

## Allowed network operations

The restricted transport allows only HTTPS GET on api.bilibili.com:

- `/x/web-interface/nav` without query parameters;
- `/x/web-interface/wbi/search/type` with the current literal keyword, video type,
  page size 20, the pinned default empty order, zero native time filters and
  bounded page number, plus the client's signing fields;
- `/x/web-interface/view/detail` with an aid explicitly admitted after a validated
  search result.

Duplicate parameters, alternate hosts, userinfo, ports, redirects, proxies and
other endpoints are rejected. TLS verification is enabled; responses are limited
to 2 MiB; requests are sequential and spaced by at least two seconds. The shared
API budget is 1 authentication + maxSearchPages + maxRecords. This is not a total
browser-resource traffic counter or an operating-system sandbox.

There is no media download, caption/transcript request, comment crawl, follower
crawl or creator graph. HTTP restrictions, negative JSON, invalid JSON and
unknown response shapes never count as normal zero results. Retry-After is
retained, with no automatic re-login, proxy rotation or challenge bypass.

## Pagination and data

A successful result list is required. A final nonempty page is processed before
stopping. Valid numPages can establish the end of the returned query pagination;
a bare total count cannot. Without end evidence, positive results are bounded.
An explicitly empty successful list ends the current query, not an assertion of
complete coverage of the platform's database. Contradictory page metadata fails.

Detail attempts, not just accepted rows, consume the record budget. Repeated aids
are not fetched twice. Later failures preserve earlier records and cannot advance
successful coverage. Authentication/verification/rate-limit states retain their
platform-pause meaning even when some observations were captured.

`video_id` is an aid, stored as an exact decimal string. A BVID alias is retained
only when returned together with the matching aid by the detail response. No
algorithmic aid/BVID conversion or title-based merge is performed. Conflicting
pairs are rejected in both collection and normalization. BVID case is preserved.

The observation is always `bili:video:<aid>` with a canonical av link and an optional
`bvid:<BVID>` alias. The excerpt is explicitly `video_description`, not a video
transcript. Timestamps are seconds, never guessed milliseconds; missing dates or
metrics remain unknown. Author identifiers are anonymized, not mapped to a real
person. Evidence remains D / discovery / unverified. Metrics and alias enrichment
do not change the content hash.

## Operator commands

The following are instructions, not a claim that these live commands were run.
Use an absolute private STATE outside both repositories, with mode 0700 on POSIX.
Create runtime.json under STATE using the frozen runtime_config contract; only
the required local platform switch should be enabled. Never commit private state.
Install the separately reviewed upstream environment and Chromium into the private
browser directory before live use; record resolved dependency versions. The source
pin does not by itself freeze all dependency ranges.

```sh
# Offline plan preview, no network:
python -m tools.social.cli plan --platform bili --state-dir "$STATE" --dry-run

# Explicitly save a local plan:
python -m tools.social.cli plan --platform bili --state-dir "$STATE" --output plans/bili.json

# Explicit manual setup, with runtime.interactiveAuthAllowed=true:
python -m tools.social.mediacrawler_cli bootstrap-session --platform bili \
  --state-dir "$STATE" --runtime-config "$STATE/runtime.json" --live --interactive

# The next query independently validates the saved session:
python -m tools.social.mediacrawler_cli run-mediacrawler --platform bili \
  --state-dir "$STATE" --runtime-config "$STATE/runtime.json" \
  --plan "$STATE/plans/bili.json" --live

# Resume only after resolving an auth/verification interruption manually:
python -m tools.social.mediacrawler_cli resume-platform --platform bili \
  --state-dir "$STATE" --runtime-config "$STATE/runtime.json" --live --confirmed
```

Closing the manual login tab finishes session setup; it does not prove that the
next API call will authenticate. The existing generic doctor keeps its legacy
implementedPlatforms registry; use the independent MediaCrawler CLI for this path.
No real session or Cookie needs to be sent through chat.

## Read-only reconciliation with existing person video discovery

`reconcile_materials()` accepts normalized Bilibili observations and the JSON list
returned by `discover_person_video_materials()`, whose records contain `url` and
`title`. It requires exact av identity or the explicit detail aid/BVID pair. A
same-title BV link with no mapping becomes only `possibleDuplicates`; it is not
merged. Different identified videos remain distinct. The report uses input
indices and signal IDs, does not infer person identity, and removes no observations.

```sh
python -m tools.social.bilibili_reconcile \
  --observations "$STATE/pending/ATTEMPT.json" \
  --materials "$STATE/existing-video-materials.json"
```

The observations input may be a list or a worker result with `observations`.
The materials input is the explicit material list, not an arbitrary nested people
snapshot. The command prints a report only. It neither edits people.json nor
invokes the production video discoverer, nor follows short links. The later
PR-07/09 integration can consume this report without losing discovery provenance.

## Acceptance and rollback

```sh
python -m unittest tests.test_social_bilibili tests.test_social_bilibili_observer \
  tests.test_social_bilibili_transport tests.test_social_bilibili_worker \
  tests.test_social_bilibili_regressions
python -m tools.social.cli validate --fixtures tests/fixtures/social/contracts
python -m tools.social.cli doctor --offline
python -m tools.social.mediacrawler_cli run-mediacrawler --help
python -m tools.social.bilibili_reconcile --help
```

Tests use synthetic callbacks, memory HTTP responses and injected process/client
objects. They exercise actual binding and CLI/checkpoint code, but do not prove
current platform availability, browser installation or real signing compatibility.
The PR conversation records exact tested commits and CI runs. No audit gate is
suppressed. The former Weibo test treating bili as unsupported is updated to a
truly unknown platform while explicitly asserting bili registration.

Disable the private bili runtime switch to stop new work. Reverting this PR does
not require a production data rollback. Do not erase private receipts during
rollback. Sealed-batch importing and persistent content storage remain PR-07,
innovation review remains PR-08 and aggregate operations remain PR-09. Until those
steps, results correctly retain batchIntegrityChecked=false.
