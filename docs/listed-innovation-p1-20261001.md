# Owner-approved listed innovation coverage — 2026-10-01

## Approval and entity boundaries

The owner approved all 40 P1 candidates, while all 50 P2 candidates remain pending.
The approved groups are 14 US-market, 15 A-share and 11 Hong Kong primary-group
companies. Cross-listings are not extra issuers: the 40 research identities have
45 securities. Market filters include every recorded security, whereas the
14/15/11 counts refer only to the primary candidate groups.

`config/company_registry.json` remains the only company-profile registry. This
change adds 26 profiles to the pre-change 74 and reuses 14 existing profiles.
Seven existing stage/status values are corrected: Biren, Insilico, MiniMax,
Moore Threads, SpaceX, Unitree and Zhipu. Historical listing dates retain their
original precision and do not become publication dates for current news.

`config/listed_innovation_companies.json` records the explicit coverage approval,
issuer names, securities, original identity sources and research scope. It joins
to canonical profiles rather than copying their biographies. The existing Google
profile is preserved; GOOG/GOOGL belong to parent Alphabet, not to an independently
listed Google issuer. TSMC/ASML retain their company geography rather than being
relabeled US companies. Edge Medical's HK-listed identity links to existing
`citic-jingfeng` A-share guidance; no extra IPO project is created.

`config/listed_innovation_candidates.json` is a non-executing P2 review list. It is
not imported by the published universe, source collector or personal preferences.
Existing P2 company records and previously approved collection are unaffected.

## Shared views and event routing

- The company library publishes 100 canonical profiles, supports approved
  security codes in its search index and links to the shared listed view.
- The innovation page adds a market/role/search-filtered, paginated listed view
  alongside the existing project, lifecycle and capital-research sections.
- Approved company detail pages show securities and identity sources; obsolete
  “no listing evidence” summaries do not override an explicitly sourced identity.
- The original IPO reserve counts, six-broker coverage and lifecycle project
  configuration are unchanged.

The innovation matcher now recognizes `listed-company` and `listed-ecosystem`.
A title or primary company identity must match; a background summary mention
alone is insufficient. The listed path requires a material technology,
commercialization, listing or capital event. Generic platform businesses need
technical context for an investment story. Routine governance, share-price
stories, ordinary promotions and negated claims do not qualify through this path.
English and Chinese names follow explicit alias boundaries, including short AMD.
The persisted feed and incremental live matcher share the same admission logic.

No P1 approval creates private follows, favorites, tracking terms or new interest
signals. `lib/homepage-focus.ts` and its 7-day freshness, importance and personal
signal gates are unchanged. Admission to innovation is not admission to Focus.
Native Research keeps its existing canonical-archive readiness boundary.

The homepage disclosure projection groups only same-company, same-day,
same-named employee-plan supporting documents. It retains every source and keeps
later (or separately titled) approval/implementation milestones distinct. English
HKEX placeholder redirect notices remain in the evidence archive, but are not
promoted as financing events.

## Official sources and measured coverage

All 100 canonical companies have matching entries in the existing official-news
registry; 40 of those are this approved batch. New entries reuse the established
official-page/feed parser with entity checks and bounded article budgets. The
existing full-refresh pipeline continues to use this registry. A targeted run is:

```sh
python3 tools/crawl_official_companies.py --approved-listed
```

On the owner's current Mac Python installation, verified TLS requires its existing
system CA bundle (`SSL_CERT_FILE=/etc/ssl/cert.pem`); TLS verification is not disabled.
The standalone collector now maps detailed company geographies to the supported
public article regions without modifying the company master.

`public/data/listed_innovation_source_health.json` is a dated, targeted-run receipt,
not a continuously refreshed health endpoint. Normal scheduled refreshes retain
the existing workflow and publish current observations in `articles.sourceStatus`;
they do not create a new unstaged output or require workflow-write permission.
It separates approved count, attempted count, accepted articles, empty results and
fetch failures. Its `snapshotPublished` field refers to writing the local canonical
article snapshot, **not** a GitHub Pages deployment receipt. All-source failure or
quality-gate failure leaves the last-good article snapshot intact.

Securities identity sources and official company news are not a claim that all
40 issuers already have complete SEC/CNINFO/HKEX announcement coverage. The old
regulatory disclosure counters continue to report actual documents only. New
biographical baselines do not invent financial results, investors, relationships,
team members, or a completed deep-research profile.

## Acceptance

Focused tests cover the 40/50 approval boundary, 26 additions, exact source-registry
coverage, 45 unique securities, parent/child and cross-market identity, P2 exclusion,
positive/negative routing, lack of implicit personal signals, publication dates,
attachment grouping, regional normalization and all-source failure handling.

Production acceptance additionally requires a successful PR build, merged code,
the matching Pages deployment, and public/browser checks of the company library,
listed innovation filters, affected company profiles and homepage routing. A local
test pass, collection receipt or branch push does not satisfy production acceptance.

## Publication prerequisites found by CI

The first PR build compiled all company routes, passed public artifact/link checks,
but exceeded the existing 1,000,000-byte homepage script budget by 7,316 bytes.
The homepage now imports a generated 7 KB routing/search projection instead of the
full issuer-evidence registry. The feed builder regenerates it deterministically;
tests compare it to the approval source. The performance budget is unchanged.

The inherited Next.js 16.3.4 dependency failed GHSA-vcvr-r3jv-pc5j. Next and its
ESLint configuration are patched to official 16.3.8, with a regenerated lockfile.
The production audit then reported no high or critical findings. No security
exceptions or workflow permissions were expanded.

An existing live Seed check exposed an upstream migration from `/zh/blog` to
`/zh/research`. The adapter reads that page's `feedList` (blogs), not its separate
`article_list` (papers), retains official blog detail URLs and uses the source's
China-calendar publication date rather than the previous UTC day. The original
live acceptance requirement remains in place.
