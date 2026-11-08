# Company-profile writer migration: offline PR-handoff gate (proposal only)

**Status: design and pure synthetic gate; not deployed, authorized, or wired to
any scheduled workflow.** Parent governance item: GitHub Issue #664.
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
4. For a new, unclaimed `automation/company-profile-refresh/run-<id>-attempt-<n>`
   branch, stage a bounded commit and propose a **Draft** PR targeting `main`.
   No automatic merge and no direct push to `main`. Any existing candidate
   branch, even from a prior run, requires operator triage / confirmed cleanup
   rather than creating another proposal or force-overwriting that branch.
5. On the resulting PR, prove actual required checks for the exact head,
   independent reviewer approval, fresh main/queue consistency, and explicit
   post-merge publication handoff before completing migration.

GitHub's currently documented behavior: a PR opened or synchronized by
`GITHUB_TOKEN` may create **approval-required** `pull_request` workflow runs.
Using a narrowly scoped GitHub App token can change this but requires separate
security review; do not assume approval happened or use a broad bypass token.
Path-filtered jobs cannot be universal required checks without a stable
always-triggered gate.

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

## Acceptance still required

- Independent review of the eventual live writer implementation, race
  handling, idempotency, permissions and duplicate PR recovery.
- A **separate, explicitly approved** bounded test of actual PR creation,
  GitHub check-run behavior, approval, merge/rollback and publication semantics.
- A migration strategy for the other direct-main writers; main branch
  protection remains disabled until this is resolved.

Do not merge the social-shadow PR, change source ingestion limits, disable
security checks, start collection or publish anything as part of this stage.
