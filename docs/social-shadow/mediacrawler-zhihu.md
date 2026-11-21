# PR-06: Zhihu typed keyword search

## Scope and release boundary

Depends on PR-05 / #640. This adds Zhihu to the isolated MediaCrawler execution
path, not to the original production crawler. All committed switches remain off.
No production configuration, Article snapshot, people data, innovation project
pool, previous review decision, workflow or npm dependency is changed here.
Real Zhihu login, browser, server response and JS-signing acceptance are
`live_pending`. Offline test success is not a platform-availability claim.

The reviewed MediaCrawler source commit remains
`8f583999006d5b692272c608440e193ca282e73b`.
The following pinned files inform this adapter: `media_platform/zhihu/client.py`,
`help.py`, `field.py`, `core.py`, and `model/m_zhihu.py`.
No upstream checkout is modified and no automatic update or installation runs.

## Architecture

The shared Worker registers `zhihu -> bootstrap_zhihu.py`; it uses
`profiles/zhihu`, `locks/zhihu.lock`, a separate Python interpreter, an external
private state directory, and the existing POSIX process-group cleanup. CLI
platform choices come from this registry, so `--platform zhihu` works without
changing the production command or the old generic doctor's compatibility list.
Native Windows is not claimed to support the POSIX cleanup path.

The child loads the pinned ZhiHuClient, its native keyword/offset construction,
its signer, and upstream author-anonymization helpers. It does not invoke
crawler main/start, automatic login, comments, creator history or detail download.
The request retry decorator is removed only in this private child; it cannot
retry a verification or authentication failure. The upstream projection normally
returns only a content list and loses paging. A child-local RawSearch extractor
keeps the raw search response instead; our typed projection preserves missing
values rather than inheriting model defaults of zero.

Zhihu's upstream signer lazily opens `libs/zhihu.js` relative to cwd, whereas the
isolated child deliberately runs in private state. `prepare_signer()` therefore
reads the verified upstream's absolute JS path and fills the upstream compiler
cache. It does not change cwd or implement a new signature algorithm. Missing,
linked or oversized resources fail closed. A separately installed compatible
ExecJS JavaScript runtime is required; actual JS execution and platform signature
compatibility have not been verified by the injected offline tests.

## Request restrictions

Only HTTPS GET to `www.zhihu.com` is admitted:

- `/api/v4/me`, without an include query: authentication only, not email/phone
  profile enrichment. The response stays in memory and is not exported.
- `/api/v4/search_v3` with the exact current keyword, page size 20, matching offset
  and lc_idx, and the fixed upstream default search parameters.

The stored session must have the signing cookie and the authentication response
must contain a usable identity/name. Neither is exported. There is no automated
login, challenge solving, Cookie refresh loop, proxy rotation or redirect follow.
Duplicate parameters, extra hosts/ports, arbitrary include fields, detail/comment
endpoints, repeated pages and search-before-auth requests are rejected.

The request budget is one authentication plus at most maxSearchPages. Requests
are sequential and at least two seconds apart. TLS verification is required and
a JSON response is bounded to 2 MiB. Retry-After is retained. HTML with status
200, negative JSON, duplicate JSON keys and nonfinite values are errors, not zero
results. This budget is not a counter for all Chromium resource traffic and the
process/path checks are not an operating-system sandbox.

## Paging and content identity

The adapter reads `data` and `paging.is_end` from each successful search response.
A final nonempty page is processed before stopping. Missing end evidence makes a
positive result bounded, not exhausted. A supplied next URL is never followed:
its host, keyword and expected next offset are checked, while the pinned client
constructs the next request independently. A contradiction stops the query.

Only answer/article/zvideo contents are collected. Known question/topic/person/
column search results are explicitly counted as non-target rows. Unknown wrappers
or unknown content types stop with a schema error rather than disappearing. A
page containing only non-target rows is not reported as a proven zero-result
keyword search. Earlier successful pages survive a later failure.

IDs remain exact decimal strings. The stable identity is
`zhihu:<answer|article|zvideo>:<content-id>`; identical numbers across different
types do not collide. A question ID is parent context, never an answer ID or alias.
Two answers under one question remain independent. Conflicting question parents
for the same answer fail validation. Missing question ID yields a null answer URL,
not an invented parent. Canonical article and video links are reconstructed from
their own content IDs, never from a raw media/redirect URL.

Answer/article excerpts are marked answer_excerpt/article_excerpt. Zvideo uses
only its supplied title/description and is always video_description, even when
empty. No video transcript, subtitle, media or full-text retrieval is claimed.
An answer title borrowed from its question is marked derived, not original.

Publication and update fields remain separate. Answer timestamps use
created_time/updated_time; article created_time/created and updated_time/updated
are aliases and must agree when both are present. For videos an explicit
published_at takes priority over created_at (upload creation); updated_at remains
the update. All are seconds, never guessed milliseconds. Unknown dates/metrics
stay null; relative date text is not filled with the collection time. Native date
filters are unsupported; explicit post-filtering uses known UTC publication dates.

Only anonymized author keys and masked nicknames are retained. No real-person,
company or investment relationship is inferred from the author or parent question.
All observations enter as D / discovery / unverified. Content hashes ignore
engagement and observation timestamps. Query terms and visible matches are distinct.

## Operator commands

These are instructions, not commands executed during this PR. STATE must be an
absolute path outside both worktrees, private mode 0700. Keep runtime.json inside
STATE. Use the frozen runtime_config contract; enable only the required local
platform, never committed production switches. Install the separately reviewed
upstream Python environment, a compatible JavaScript runtime, and Playwright's
Chromium under STATE/browsers first; record resolved dependency versions.
Pinned source is not a transitive dependency lock.

```sh
# Offline preview; no directory creation or network:
python -m tools.social.cli plan --platform zhihu --state-dir "$STATE" --dry-run

# Explicitly save a private plan:
python -m tools.social.cli plan --platform zhihu --state-dir "$STATE" --output plans/zhihu.json

# Manual website session setup only; runtime.interactiveAuthAllowed=true:
python -m tools.social.mediacrawler_cli bootstrap-session --platform zhihu \
  --state-dir "$STATE" --runtime-config "$STATE/runtime.json" --live --interactive

# Saved session is independently checked by the query:
python -m tools.social.mediacrawler_cli run-mediacrawler --platform zhihu \
  --state-dir "$STATE" --runtime-config "$STATE/runtime.json" \
  --plan "$STATE/plans/zhihu.json" --live

# Only after resolving an interruption; Retry-After cannot be bypassed:
python -m tools.social.mediacrawler_cli resume-platform --platform zhihu \
  --state-dir "$STATE" --runtime-config "$STATE/runtime.json" --live --confirmed
```

Closing the setup tab ends setup, not proof of authentication. No Cookie/password
belongs in chat, committed files or public CI. The parent keeps job requests,
receipts and pending results in private state. The old generic doctor intentionally
retains its compatibility implementedPlatforms list; it is not a live-readiness
report for the separate MediaCrawler entrypoint.

## Offline acceptance and rollback

```sh
python -m unittest tests.test_social_zhihu_observer tests.test_social_zhihu \
  tests.test_social_zhihu_transport tests.test_social_zhihu_worker \
  tests.test_social_zhihu_session
python -m tools.social.cli validate --fixtures tests/fixtures/social/contracts
python -m tools.social.cli doctor --offline
python -m tools.social.mediacrawler_cli run-mediacrawler --help
```

The tests inject callback, HTTP, client, compiler and process stand-ins. They
exercise the actual binding and CLI/checkpoint functions without a browser or
network. Exact tested commits and Actions runs are recorded in PR #641. They do
not establish real login, current API shape, JS runtime compatibility or coverage.
No prior failure test is skipped: the legacy Weibo unsupported-platform test now
asserts Zhihu registration and still rejects genuinely unknown/path-traversal input.

Disable the private zhihu switch and stop new tasks to roll back. Reverting this
PR requires no production-data rollback and should not delete private receipts.
The sealed importer/content database is PR-07, innovation review is PR-08, and
aggregate shadow operation/benefit evaluation is PR-09. Until then results retain
batchIntegrityChecked=false and cannot promote themselves into the production pool.
