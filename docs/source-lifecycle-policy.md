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

## Evidence reuse

The gate reads existing persisted `public/data/source_health.json` rolling `performance` samples produced by `tools/update_source_health.py`. It reuses the existing manual quality sample metrics from `config/source_quality_reviews.json`; it does not create a parallel performance history.

When historical evidence is absent or malformed, the source remains `Tracked` with `evidence_pending`. Homepage-only official-company entries without a continuous collection endpoint remain `Candidate`.
