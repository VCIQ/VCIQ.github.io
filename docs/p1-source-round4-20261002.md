# P1 round four: CXMT entry and SMIC publication-field recovery

## Verified production baseline after #585

PR #585 merged as `612d8b441c5d16e7ff579a2c9b2d1dd3e7eecee4`.
Pages run `37002156027` completed build and deploy successfully; deploy finished
at 2026-10-02 11:48:51 UTC. Full refresh `37002155971` completed successfully
at 12:03:29 UTC, including official-source collection and public-data commit.

Direct production readback returned source `b8251a987ffaadd92322cb8876d986d610e08e90`,
Pages run `37006015140` and provenance generated at 12:27:23 UTC. The published
source ledger contains all 40 P1 source rows, 25 sources with newly accepted
article URLs, 85 such URLs, and zero recorded TypeError samples. This is not a
count of 85 net-new news stories. Source attempts are stamped 12:02:03 UTC.

The preceding local production-adapter audit (28 sources) is not substituted for
this production observation (25 sources). Unitree returned HTTP 567 in GitHub
Actions; Enflame returned HTTP 403; XtalPi returned URL errors. Retained articles
must not turn those failed attempts into fresh source successes.

The October 1 `listed_innovation_source_health.json` remains a historical one-off
receipt. It is not overwritten by this patch or used as a live 19/40 metric.

## Narrow source fixes

### CXMT

Use the existing official news index `https://www.cxmt.com/news.html` instead
of the homepage. The index binds each `/news/info_<id>.html` detail to a title
and date. The existing exact-title, exact-link evidence checks still fetch the
detail and require its matching title; an index item alone is not an article.
The source domain, aliases, four-item cap, request budget and 90-day window are
unchanged. Old reports found on the index stay old and remain outside the window.

### SMIC

The observed news detail `https://www.smics.com/site/news_read/3722` puts its
publication date inside `div.date.clearfix > div > p`; the surrounding body
contains different quarterly reporting dates. Read only this field, and only
for the `smic` slug and an exact HTTPS numeric `/site/news_read/<id>` URL.

The named date participates in the same explicit-date conflict checks. Reject
invalid/future values, conflicting dates, malformed fields and a different
canonical article URL. Do not scan fiscal dates from prose, visit counts or
footer timestamps. A matched field is retained as `official-detail-field`
publication evidence, with the source URL and selector, for auditability.

## Tests and measured two-source observation

67 selected source and production-adapter regressions passed, including ten new
round-four cases. The new cases cover nested field/class order, host/path/slug
boundaries, footer exclusion, invalid/future/old dates, genuine conflicts,
canonical-article binding, CXMT index/detail matching and the actual scheduled
adapter chain. No publication writer is used in these fixtures.

Live read-only scheduled-adapter observation, 12:53:37–12:53:45 UTC:

| Source | Parsed candidates | Status | Fetch failures |
| --- | ---: | --- | ---: |
| CXMT | 2 | ok | 0 |
| SMIC | 1 | partial | 1 |

Accepted detail URLs: CXMT `/news/info_97.html` and `/news/info_96.html`; SMIC
`/site/news_read/3722`. These are three parser candidates, not three net-new
published news stories. `snapshotPublished=false`; partial success is retained.

Subsequent all-40 production-adapter audit, 12:54:13–12:55:04 UTC:
40/40 attempted, **30/40 with candidates**, **98 parser candidates**, zero
TypeError samples, `snapshotPublished=false`. Remaining zero-yield: Cambricon,
Edge Medical, Hygon, Inovance, MGI, NAURA, SpaceX, Tesla, UBTECH and Xiaomi.
The source configuration and code hashes are in the generated local audit
`.p1-round4-all40-audit.json`; it is not a replacement for the public receipt.

Article-snapshot, historical-receipt and P1-approval SHA-256 values were identical
before/after the all-40 audit:

- articles: `27c31923feb265e846c993542f3e934cfc08d38fcfe364d2a668b7186702b3dd`
- historic receipt: `127475294805c8ce034f5a4343298d1378b610bf5bf927275028789076f24df1`
- P1 approval: `9f1983d55b360b3c36069107d62b51f815fd21161b3efd330eb3d8045428264f`

The 30-source Mac observation is distinct from the earlier 25-source Actions
production result. It must not be described as 30 sources already succeeding in
the published production refresh, nor as 98 net-new public news stories.

## Scope and outstanding acceptance

P1 remains 40 research identities / 45 securities; P2 remains 50 pending. No
company profiles, regulatory source coverage, personal interests, IPO-pool
counts or homepage Focus gates change. This source patch needs its own complete
CI, merge and production collection validation; local observations are not
production deployment receipts. Real browser filtering, pagination and private
Focus interaction remain a separate unverified gate.

NAURA's observed company-news index currently points to official WeChat links.
This patch does not widen a generic official-company allowlist to the entire
WeChat host. That requires separately bound account/link evidence rather than
treating every article on the shared host as NAURA's own news.
