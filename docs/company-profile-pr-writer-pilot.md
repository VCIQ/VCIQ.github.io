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

The bridge intentionally refuses all additional coverage-only company
mutations. The real workflow currently runs coverage reconciliation before
selection; a separate pre-crawl coverage provenance/attestation contract is
needed before the bridge could be used in production. The bridge does **not**
attest the truth of source articles, that a crawler request succeeded, that
coverage changes are authorized, or that all downstream publication validators
ran. Those are independent, outstanding gates.

The `EvidenceBoundWorkspace` API has no CLI, does not handle credentials,
and is not referenced by any scheduled job. Real-Git tests use a temporary
detached repository and a synthetic remote URL. Other tests inject fake
GitHub API objects; no actual GitHub candidate PR is created in this stage.
Even a successful synthetic submission reports `ciChecksVerified=false`,
`merged=false`, and `published=false`.
