# Source lifecycle promotion

`Candidate -> Tracked -> Core` is a Publisher-level lifecycle and is independent from evidence role and current collector health.

## Fail-closed Core gate

A Publisher can become `Core` only when all configured quantitative conditions pass and an explicit human `approve_core` decision exists in `config/source_core_reviews.json`.

The current policy requires:

- at least 5 rolling collection runs;
- observations spanning at least 7 distinct calendar days;
- at least 20 scanned candidates;
- rolling availability rate >= 0.90;
- rolling valid-yield rate >= 0.50;
- at least 20 manually reviewed records;
- manual misattribution rate <= 0.05;
- an active collection state;
- publication eligibility;
- no outstanding performance-review flag;
- explicit Publisher-level Core approval.

Approval never bypasses missing or failing quantitative evidence. Passing quantitative evidence without approval produces `review_pending`, not `Core`.

## Default evidence-role governance

The versioned default governance in `lib/source-governance.ts` separates evidence use from collector health and Core readiness:

- `primary`: official company sources, regulatory / exchange disclosures, papers and other original research are default Core candidates;
- `corroboration`: professional media and independent research sources are default cross-checking sources and may become Core after the same fail-closed gate;
- `discovery`: WeChat accounts and X profiles remain `Discovery-only` by default. They may still be tracked and quality-reviewed for discovery value, but they do not enter the Core promotion or Core QA queue. Important claims must be traced back to Primary or Corroboration evidence.

This role policy does not weaken any lifecycle threshold and does not convert a Discovery source into a factual authority.

## Operational action versus governance action

The Sources dashboard must not collapse unrelated states into one generic “needs action” bucket.

- operational collection action: collector `error`, `partial`, stale successful observation, or no reliable observation;
- governance decision: no sustainable endpoint (`Candidate`) or an explicit blocked Core decision;
- evidence accumulation: a Core-eligible source remains `evidence_pending`;
- human approval: quantitative gates pass and the source is `review_pending`;
- Discovery-only: the source is retained for discovery but is outside the Core queue.

## Pause and deprecation guardrails

An unstable endpoint does not immediately invalidate its Source Entity.

1. Retain the entity and look for a publisher-owned website, RSS, regulatory endpoint, paper API, or other stable alternative.
2. After three consecutive scheduled collection cycles without a stable endpoint, a low-value source may be recommended for `Pause`.
3. `Deprecated` is reserved for duplicates, permanent failure, or explicitly confirmed lack of research value.
4. Bulk disable or deletion must not occur before a fresh health snapshot is available.
5. Pause / Deprecated remain explicit governance changes; they are not inferred automatically from one failed run.

## Evidence reuse

The gate reads existing persisted `public/data/source_health.json` rolling `performance` samples produced by `tools/update_source_health.py`. It reuses the existing manual quality sample metrics from `config/source_quality_reviews.json`; it does not create a parallel performance history.

When historical evidence is absent or malformed, a Core-eligible source remains `Tracked` with `evidence_pending`. Homepage-only official-company entries without a continuous collection endpoint remain `Candidate`.
