# PR-08: private innovation lead review

## Scope and safety boundary

This change depends on PR-07 / #642. It consumes the private `signals.sqlite3`
content database, not raw crawler files. It never invokes a platform crawler,
changes a scheduler pause, publishes articles or edits the formal innovation pool.
The existing production review configuration, decisions, public data and workflows
remain unchanged. All committed platform switches remain disabled.

`accepted` means the reviewer considers a lead worth following. It does not mean
that a claim is true, that a company/person was identified, or that a candidate is
approved for publication. Accepted leads remain `awaiting-primary-evidence`.
`rejected` is an immutable final action for that exact evidence revision. Changes
to material evidence create a new revision rather than overwrite a prior decision.

## Lead construction

The builder reads latest normalized observations and the existing
`config/company_registry.json` names, slugs, English names and explicit aliases.
An alternative company snapshot must be an explicit file under private STATE.
No fuzzy entity match, author-to-company attribution or relationship inference is
performed. Even a unique company-name mention remains unresolved with companyId
null; multiple candidate matches are ambiguous. Candidate suggestions are shown
separately from any factual claim.

Funding, product, technology and listing labels use visible literal keywords.
They are navigational heuristics, not event classification proofs. Otherwise,
relevant material becomes a company-discovery lead. Original negations and
qualifications are retained in the quoted excerpt. One content item may generate
multiple lead types; same-title or cross-platform posts are not silently merged
into one verified event. A maximum of 5,000 signals / 2,000 active candidates is
currently accepted; larger collections fail explicitly rather than truncate.

Lead IDs are stable per signal and lead type. Candidate revisions bind material
content, evidence, subject and suggestions; engagement or observation-time-only
updates do not reopen review. The first snapshot of a revision is retained, so its
metrics/observedAt can intentionally be older than the latest crawler snapshot.
The queue displays the actual snapshot time, not an invented freshness claim.

## Evidence and immutable decisions

`reviews.sqlite3` is independent of `signals.sqlite3` and `state.sqlite3`. It
checks its application ID, version, table set and migration fingerprint and will
not overwrite an unrelated database. Candidates, decisions and request IDs are
kept separately, with SQLite transactions for each final change.

Evidence is pinned by exact signalId/contentHash before a candidate becomes
visible. A crash between pinning and queue publication may leave a safe orphan
pin, but never a visible reference to unprotected evidence. A final source check
is made while holding the content lock before publishing the queue. Content and
review locks are always taken in that order. The two databases are not represented
as one distributed atomic transaction; retained orphan pins are an intentional
fail-safe and are not automatically removed.

A decision must identify the candidate key, fingerprint and queue version the
reviewer saw. Current stored evidence is checked again even before the next queue
rebuild. Stale evidence, changed subject suggestions, missing pins, conflicting
request IDs and opposite terminal decisions fail closed. Exact replay is
idempotent and does not change the original actor, note or timestamp. Exact replay
of a previously recorded request can acknowledge the historical decision without
applying it to a newer revision.

Only listing leads call the existing `innovation_listing_candidate_review` pure
`apply_decision` function with a constructed, discovery-only shadow payload. Its
CLI and file writers are never called. Other lead types are not disguised as IPO
candidates; no regulator/broker source prefixes or primary-backed flags are forged.

## Operator commands

Use an existing absolute private STATE outside both repositories and a valid
runtime_config file inside it. The runtime can stay disabled: these commands are
explicit offline operations, not authorization to collect data. POSIX state and
files must have private permissions. On macOS, use a resolved path such as
`/private/tmp/...` rather than the symlink `/tmp/...`; do not relax the symlink guard.

```sh
# Read-only preview; no review DB or evidence pins are created.
python -m tools.social.review_cli sync \
  --state-dir "$STATE" --runtime-config "$STATE/runtime.json"

# Explicitly pin evidence and publish/rebuild the private queue.
python -m tools.social.review_cli sync --apply \
  --state-dir "$STATE" --runtime-config "$STATE/runtime.json"

# Read current or historical revisions, with bounded pagination.
python -m tools.social.review_cli list --limit 25 \
  --state-dir "$STATE" --runtime-config "$STATE/runtime.json"
python -m tools.social.review_cli list --history --offset 0 --limit 25 \
  --state-dir "$STATE" --runtime-config "$STATE/runtime.json"

# Start only the loopback read-only workbench; Ctrl-C stops it.
python -m tools.social.review_web --port 8767 \
  --state-dir "$STATE" --runtime-config "$STATE/runtime.json"
```

Open `http://127.0.0.1:8767`. The workbench shows the evidence excerpt, source,
publication/snapshot times, content scope, candidate company matches, hashes and
prior decisions. It can export a DecisionRequest JSON file, but cannot submit or
apply it. Move the exported file into the private STATE directory with private
permissions. Then validate and explicitly apply it:

```sh
python -m tools.social.review_cli decide --request decision-UUID.json \
  --state-dir "$STATE" --runtime-config "$STATE/runtime.json"
python -m tools.social.review_cli decide --request decision-UUID.json --apply \
  --state-dir "$STATE" --runtime-config "$STATE/runtime.json"
```

The examples use a placeholder file name; use the actual exported UUID. Validation
alone does not record a decision. Do not edit fingerprints to force a stale request
through. Rebuild the queue and review the new evidence instead. The reviewer label
is a local audit label, not an authenticated identity or electronic signature.

The optional `--companies companies.json` input is accepted by sync/decide only
and must stay under STATE. Use the same intended registry for both operations;
changed relevant mappings can require a fresh queue revision. Default registry
reads are read-only. List and browser reads do not need the registry or create it.

## Browser and HTTP boundary

The server binds only `127.0.0.1`, validates the exact Host/port and Origin, and
rejects cross-site fetches. No LAN/public bind option, CORS permission, HTTP write
route, arbitrary-file route or directory listing is supplied. POST/PUT/PATCH/
DELETE and other non-read methods are rejected. Assets are an exact allowlist;
only `/api/queue` can read a bounded page. Databases open read-only for each API
request. Error responses do not include raw exceptions, inputs or filesystem paths.

All assets are local, with no third-party fonts, telemetry or remote scripts.
Evidence uses DOM text nodes rather than HTML injection. External source links
have an explicit allowlist, noopener/noreferrer and no-referrer policy. CSP denies
inline scripts, embedded objects, frames and form submissions. Responses use
no-store and nosniff headers. Decision downloads contain no credentials and do not
include the entire observation snapshot.

Loopback/Host checks are not protection against a malicious process already
running as the same local user. This is a trusted single-operator workstation,
not a remotely authenticated review service. Do not expose it through a reverse
proxy, tunnel or port forward. A browser download outside STATE is not an ingested
decision until an operator deliberately places and applies it inside STATE.

## Verification and limitations

```sh
python -m unittest tests.test_social_lead_builder tests.test_social_review \
  tests.test_social_review_cli tests.test_social_review_web
node --test tests/social-review-ui.test.cjs
# Explicit loopback integration, separate from network-denied offline CI:
python -m tests.social_review_loopback_smoke
```

The Python suite exercises real SQLite/CLI operations with synthetic evidence;
network and subprocess calls are blocked where appropriate. Node tests evaluate
the unchanged classic browser asset in a VM because the parent package is ESM.
The loopback smoke script starts a temporary synthetic server, checks actual local
HTTP behavior and shuts it down, leaving no permanent process or real decision.
It must be run explicitly and does not contact social platforms.

No real source login, platform traffic or real human acceptance/rejection is part
of these tests. Automated JS/HTTP tests are not a claim of visual browser review
unless a separate browser test is recorded in the PR. The PR discussion identifies
the exact tested commit, environment, results and remaining CI failures.

This PR does not provide cross-source truth verification, automatic promotion,
remote users, bulk review, unpinning, periodic execution or a production UI route.
PR-09 still owns aggregate shadow orchestration, health checks and measured yield.

## Rollback

Stop the local workbench and stop invoking review commands. No production data
rollback is necessary. Keep the private review ledger, original decisions,
source batches and evidence pins for audit. Do not automatically delete pinned
versions merely because the workbench code was disabled. Never commit private
runtime configuration, state databases or decision files to the public repository.
