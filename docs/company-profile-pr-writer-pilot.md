# Company-profile writer migration: isolated PR-handoff implementation

**Status: callable implementation and synthetic tests; NOT deployed,
authorized to run against GitHub, or wired to any scheduled workflow.**
Parent governance item: GitHub Issue #664.
This must remain independent of social-shadow Draft PR #662.

## Existing workflow risk

`.github/workflows/company-profile-incremental-refresh.yml` currently performs
official-source crawling, marks the queue processed, stages two public JSON
files, rebases with `-X theirs`, pushes `HEAD:main`, and explicitly dispatches
Pages. Replacing only the push command is unsafe:

- Before a PR merges, `main` still has the old processed-event queue; a later
  scheduled run can duplicate the same crawl or create a conflicting PR.
- A rebase across intervening `main` changes is not proof that the queue and
  generated profiles remain semantically consistent.
- Neither a successful PR-create response nor workflow-level green checks
  proves required checks actually ran for the new candidate commit.
- A PR merge must not silently inherit the existing direct `pages.yml`
  dispatch; publication is a separate authorized post-merge handoff.

## Candidate control flow (not executed)

1. Before the first network crawl, obtain a complete authenticated list of
   open company-profile writer PRs and known candidate branches. Fail closed
   on API failures, incomplete pagination, ambiguous state, or any existing
   open proposal. Preserve the existing single-writer concurrency group.
2. Record the actual `main` commit SHA at the start. Run the existing bounded
   pipeline unchanged inside an isolated candidate checkout; never mutate
   `main` or the active production state.
3. Revalidate output and queue semantics, ensure only
   `public/data/company_profile_refresh_queue.json` and
   `public/data/venture_profiles.json` changed, and compare the latest main
   HEAD to the recorded SHA. On drift, **abort without `-X theirs`**.
4. Obtain an atomic *one-use* reservation under the fixed branch
   `automation/company-profile-refresh/reservation` (or the separately
   namespaced smoke reservation for the explicitly allowlisted sandbox base).
   If it already exists,
   or any prior candidate branch or open proposal exists, fail closed. After
   acquiring it, refresh main/PR/branch inventories; on concurrent change,
   abort and **keep the reservation for operator triage**.
5. Create the candidate as an immutable Git tree/commit based on the recorded
   main SHA, changing *only* the two allowlisted public JSON files. Atomically
   create a new `automation/company-profile-refresh/run-<id>-attempt-<n>` ref
   from that commit. GitHub ref creation rejects an existing branch; no
   `git push --force`, rebase or `HEAD:main` are used.
6. Open a **Draft** PR targeting `main`, then re-read its metadata to verify
   the exact candidate SHA, same repository, Draft state and base branch.
   Failed or ambiguous creation/verification is **not retried**; preserve
   reservation/candidate refs until a maintainer reconciles GitHub state.
   Before attempting the PR, recheck main and the full PR/branch inventories
   again to detect a new competing proposal after candidate creation.
7. Never delete the reservation automatically, including after successful PR
   creation. A separate reviewed recovery procedure must determine whether
   to close, merge, or abandon the proposal and when to remove both refs.
8. On the resulting PR, prove actual required checks for the exact head,
   independent reviewer approval, fresh main/queue consistency, and explicit
   post-merge publication handoff before completing migration.

GitHub's currently documented behavior: a PR opened or synchronized by
`GITHUB_TOKEN` may create **approval-required** `pull_request` workflow runs.
Using a narrowly scoped GitHub App token can change this but requires separate
security review; do not assume approval happened or use a broad bypass token.
Path-filtered jobs cannot be universal required checks without a stable
always-triggered gate.
The repository must also permit Actions to create pull requests under
Settings → Actions → General; its actual setting has **not** been verified.
See https://docs.github.com/en/actions/concepts/security/github_token and
https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository .

## Prototype entrypoint and its limits

`python -m tools.company_profile_writer_pr_gate --stdin-json` accepts a
small *synthetic or externally verified* metadata record and returns a
deterministic proposal **decision**. It never calls Git, GitHub, Playwright,
company crawlers, Pages or production APIs; it cannot open a PR.
Its branch and idempotency rules are exercised in
`tests/test_company_profile_writer_pr_gate.py`.
The `simulatedOnly`, `handoffExecuted` and `approvalGateVerified`
fields intentionally prevent conflating this stage with a live end-to-end
acceptance.

`tools/company_profile_writer_pr_handoff.py` adds **callable**
`DetachedWorkspace`, `GitHubCli` and `submit`. This is *not* a public
`--apply` command and it is deliberately **not referenced by the existing
scheduled job**. `submit` rejects calls lacking an explicit
`authorized=True`. The adapter requires an isolated detached Git checkout,
origin pointing to this repository, strictly allowlisted unstaged JSON
changes, a `GH_TOKEN` set by an approved operator, and a complete paginated
GitHub inventory. It uses `gh api` with bounded subprocess execution and
suppressed stderr, not `shell=True`. It only creates new refs, Git objects and
Draft PRs. It does not execute the existing crawler, rebase, merge, write
`main`, deploy Pages or manage tokens.

For the token smoke only, the adapter supports the exact sandbox base branch
`codex/writer-token-smoke-base-20261108` and a **separate** namespace
`automation/company-profile-refresh-smoke/`. It cannot select an arbitrary
base branch; smoke reservations cannot collide with production reservations.
This allowlist exists solely to prove the real adapter's API behavior without
opening a synthetic data PR against `main`.

**No live adapter acceptance has occurred.** The separate GitHub Token
permission smoke is recorded in Issue #664; it did not invoke this adapter.
All GitHub operations in
`tests/test_company_profile_writer_pr_handoff.py` use injected synthetic
GitHub behavior; real `git` tests use only a disposable temporary repository
with a synthetically configured remote URL and never contact that remote.
The CI workflow runs both the pure gate and handoff tests without credentials.
An approved follow-on pilot must independently attest token scope, effects
of GitHub push-triggered workflows on newly created refs, reservation cleanup,
complete PR/branch pagination, CI approval behavior for `GITHUB_TOKEN`,
publication handoff and recovery of ambiguous API failures.

## Acceptance still required

- Independent review of the eventual live writer implementation, race
  handling, idempotency, permissions and duplicate PR recovery.
- A **separate, explicitly approved** bounded test of actual PR creation,
  GitHub check-run behavior, approval, merge/rollback and publication semantics.
- A migration strategy for the other direct-main writers; main branch
  protection remains disabled until this is resolved.

Do not merge the social-shadow PR, change source ingestion limits, disable
security checks, start collection or publish anything as part of this stage.

## Stacked evidence-binding review (#664, after #668)

The candidate integration branch is stacked on the offline transition contract
in PR #668 and incorporates the **existing Draft** PR #665 adapter files.
It is not an additional live writer, and must not be merged together with an
overlapping copy of PR #665. Decide final merge order/retargeting in review.

`tools/company_profile_writer_evidence_handoff.py` offers
`EvidenceBoundWorkspace(DetachedWorkspace(...), pre_crawl_selection,
run_started_at, run_completed_at)` as a validated input to
`company_profile_writer_pr_handoff.submit(..., authorized=True)`.
It pins both original tracked queue/profile JSON objects to the candidate
checkout's exact Git commit SHA and reads the prospective JSON from that same
isolated checkout. The immutable pre-crawl selection is checked against the
actual base queue and the final candidate by
`check_transition(..., coverage_slugs=[])` **before any GitHub ref write**.

The bridge also pins `public/data/articles.json` and `lib/catalog-data.ts`
to the exact same Git SHA and uses the repository's own `build_queue` and
`parse_catalog` logic to independently reconstruct pre-crawl selection.
A supplied selection record that differs from that canonical computation
is rejected before any remote writes. Catalog parsing cannot fall back to
ambient local registry data: a valid company source row must be present
inside the pinned catalog blob itself.
The selection's own `generatedAt` must fall within the independently
recorded job execution window (at most 90 minutes). By contrast, the
underlying articles snapshot `generatedAt` may legitimately be older.
This prevents replaying an old selection while retaining support for stale
but valid source snapshots.

### Company registry and coverage provenance

Current production `lib/catalog-data.ts` **re-exports** `companies` from
`./company-registry`, which imports `config/company_registry.json`. The
original parser may silently fall back to an ambient on-disk registry if no
inline companies are found. That is not acceptable for a pinned Git review.
The bridge now reads `lib/company-registry.ts` and
`config/company_registry.json` at the **same verified Git SHA**, checks both
TS import/re-export links and resolves companies from the pinned JSON only.
Inline catalog fixtures remain supported for synthetic tests. This behavior
has a read-only compatibility test against the checked-in 100-company,
20-institution catalog and rejects absent, malformed or duplicate entries.

The optional `coverage_snapshot`, `coverage_report`, and
`coverage_updated_at` inputs must be supplied *together*. The bridge
recalculates the repository's existing `ensure_catalog_coverage` outcome
using the pinned catalog and pre-repair base, rejects report mismatch,
unauthorized modifications and missing institution coverage, and accepts only
bounded newly missing-company fallback profiles. A passing coverage check
is not proof of real external crawling or permission to publish; it is a
deterministic pre-crawl repair attestation.

The bridge remains fail-closed for coverage changes without the full attested
snapshot and report. It does **not** attest the truth of source articles,
that a crawler request succeeded, that institution onboarding changes are
safe, or that all downstream publication validators ran. Those are
independent, outstanding gates.

The `EvidenceBoundWorkspace` API has no CLI, does not handle credentials,
and is not referenced by any scheduled job. Real-Git tests use a temporary
detached repository and a synthetic remote URL. Other tests inject fake
GitHub API objects; no actual GitHub candidate PR is created in this stage.
Even a successful synthetic submission reports `ciChecksVerified=false`,
`merged=false`, and `published=false`.


## Selected-company crawl receipt contract (pre-production only)

The currently deployed company-refresh workflow runs
`crawl_venture_profiles.py --kind company --slug ...`, then marks every
selected event processed when the command exits with status 0. Its global
quality gate can also pass while historical profiles are retained, or
fallback profiles are kept after failed page retrieval. **Zero subprocess
exit status alone is therefore not enough to mark events processed.**

`tools/company_profile_writer_crawl_receipt.py` defines a **pure, offline**
`check_selected_crawl_receipts(...)` contract for the *immediate post-crawl*
snapshot. For each selected company, a future reviewed orchestrator must
capture the command exit code, capture timestamp, status/profile JSON SHA-256,
the observed status row and immediate post-crawl profile. The validator
requires fresh `ok` or sufficiently evidenced `partial` status, at least
two new fetched pages, appropriate accepted-section counts, a new
`updatedAt` within the run window, no retained/fallback/error/warning state,
and a matching official-domain evidence source from the **pinned catalog**.
A strong partial crawl must additionally have an evidence score of at least
70, two distinct official URLs and core technical/product sections.

The status/profile digests prevent accidental mismatch between supplied
capture records and the claimed snapshot, but **do not cryptographically
authenticate an actual HTTP fetch, GitHub runner identity or process exit
code**. Those facts require the separate orchestrator to produce and
preserve trusted execution receipts, with provenance anchored to the same
run ID and selected-slug set. This checker intentionally returns
`markProcessedAuthorized=false`, `mergeAuthorized=false` and
`publicationAuthorized=false` even on success.

No scheduled job invokes this module today. It is **not** permission to
modify `--mark-processed`, bypass the existing quality gates, run a live
crawler, open a production data PR, merge or deploy. Future production
integration requires a separate approved pipeline change and direct
verification of exact-head CI and reviewer status.

## Observed crawl subprocess capture (Draft-only, not deployed)

`tools/company_profile_writer_crawl_observer.py` is a callable **opt-in**
observer that takes the job's pinned selection, pinned official URLs,
base SHA, run ID, a bounded clock, and an **externally supplied** command
runner. It has no CLI, no scheduled trigger, no GitHub client and no
default executable runner. The caller must explicitly set
`authorized=True`; simply importing this module does nothing.

On explicit invocation, the observer sends the runner a fixed, shell-free
argument tuple for each selected company's existing crawler command. It
checks the returned `subprocess.CompletedProcess` against that tuple,
reads the current `venture_profiles.json` after **each** result,
and captures the status/profile SHA-256 pair. A zero exit code with
unchanged profile, malformed/duplicate-key JSON, a symlinked snapshot,
missing selected-company status, stale run time or unexpected process result
fails closed. After the last selected company, it calls the existing
`check_selected_crawl_receipts` gate against the *final* snapshot,
so an intervening change to an earlier company's profile is detected.

The observer returns `markProcessedAuthorized=false`,
`mergeAuthorized=false` and `publicationAuthorized=false` even when all
checks pass. The capture results and hashes **do not prove** a real HTTP
fetch, trustworthy subprocess execution, GitHub runner identity, or
truthfulness of supplied selection/catalog evidence. Future production
integration requires an independently reviewed runner/orchestrator that
pins the checkout and source catalog to one `main` SHA, captures real
process-level evidence, retains immutable run receipts, isolates secrets,
enforces queuing/recovery, and performs separate exact-head CI, reviewer,
merge and publication checks.

`tests/test_company_profile_writer_crawl_observer.py` uses only synthetic
subprocess results and disposable snapshots. The read-only PR check runs it
alongside the prior receipt, transition and PR-handoff suites. No existing
`company-profile-incremental-refresh.yml` schedule, `--mark-processed`
invocation, direct-main writer or social collection switch was modified.
