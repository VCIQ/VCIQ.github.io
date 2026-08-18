# Ranked Intelligence → Homepage Projection

## Purpose

The public homepage now accepts a small, public-safe projection of the private
VCIQ Intelligence Inbox. The bridge is deliberately one-way and display-only:
it can raise homepage attention for high-relevance public articles, but it
cannot create tracking objects or mutate the tracking catalog.

```text
tracking-admin /alerts/inbox
  → Google Alerts RSS + canonical dedupe
  → Entity/Event/Track Resolver
  → feedback-aware Relevance Score
  → public-safe projection (max 24)
  → workflow_dispatch
  → strict public validator
  → public/data/ranked-intelligence.json
  → homepage key events / latest headlines
```

## Public contract

Only these fields may enter the public repository:

- public article title, summary, publisher URL/source and publication time;
- coarse P0/P1/P2 priority and 0–100 relevance score;
- coarse Event Type;
- resolved public company/person/technology names;
- resolved public VCIQ track names.

The validator rejects extra keys. In particular, Google Alert query text,
private feed URLs/IDs, user email, feedback action, scoring reasons, database
identifiers and credentials are not accepted by the public workflow.

## Homepage behavior

The projection is merged with `articles.json` by publisher URL. If the crawler
already has the same article, no duplicate card is created; the personalized
score can raise its importance and resolver terms are merged. New projected
items use `Google Alerts RSS` as the platform and `待交叉验证` as source level.

Projected items are eligible for the primary ranked event stream and Latest
Headlines. Items without a resolved track use the display-only fallback sector
`跨赛道精选`. This keeps them visible without creating a new tracking taxonomy
entry.

## Failure behavior

The bridge is fail-open for the public site and fail-closed for publication:

- missing/malformed optional projection → homepage continues with canonical
  `articles.json`;
- all Google Alert feeds degraded → the last good projection is preserved;
- resolver degraded → no replacement projection is published;
- unchanged content hash → no GitHub commit is created;
- concurrent main writers → the consumer retries from the newest main head and
  never force-pushes.

## Merge order

The public consumer/workflow must reach `VCIQ.github.io/main` before the private
tracking-admin producer is enabled, because GitHub workflow dispatch can only
target a workflow present on the target repository's default branch.
