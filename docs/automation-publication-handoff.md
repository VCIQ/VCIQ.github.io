# Automation publication handoff

VCIQ public data publication follows a fail-closed handoff:

1. Reconcile tracked entities to a fixed point.
2. Run `Refresh public intelligence` when tracking scope changes.
3. Require the refreshed article snapshot to match the canonical tracking configuration and pass coverage/quality gates.
4. Re-run entity reconciliation against the refreshed snapshot.
5. Dispatch `Build and deploy GitHub Pages` only after the tracking scope is stable.

## GitHub Actions recursion constraint

Repository writes performed with the workflow `GITHUB_TOKEN` do not recursively trigger ordinary push/workflow-run chains in every downstream case. Production automation therefore must use an explicit `workflow_dispatch` handoff whenever one bot-driven workflow depends on another workflow running next.

Do not weaken `validate-tracking-snapshot.mjs` to compensate for a missing handoff. A stale snapshot must remain non-deployable.

## Lightweight refresh publication

A successful two-hour intelligence refresh commits its checked article snapshot, then explicitly dispatches `company-candidate-discovery.yml` with `publish_after_reconciliation=true`. Entity reconciliation remains the publication gate: if tracking inputs changed, the chain first rebuilds the public snapshot; otherwise it dispatches Pages only after reconciliation reaches a fixed point. The lightweight crawler must not rely on its bot-authored push to trigger Pages implicitly.

## Full-refresh reservation fail-open

The daily full refresh owns the 06:00-08:59 Asia/Taipei reservation window. Lightweight scheduled refreshes wait during that window when the current day's full refresh has not completed. At 09:00 the reservation expires and lightweight refreshes fail open to the normal age threshold, so a failed or delayed full refresh cannot freeze public intelligence updates for the rest of the day.

## Recovery invariant

If a full or lightweight refresh completed successfully and committed a new `public/data/articles.json`, but no later Pages run exists for the resulting terminal `main`, create an explicit publication handoff rather than rebuilding or editing the data by hand.
