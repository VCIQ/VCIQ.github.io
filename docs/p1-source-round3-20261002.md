# P1 source round 3 — AMD, TSMC and Unitree

## Scope

This round addresses two parser regressions and one client-rendered official
source. It does not add companies, expand P2, relax source identity, widen the
publication age window, or change personal Focus admission.

P1 remains 40 research identities / 45 securities. P2 remains 50 pending.

## AMD false publication-date conflict

The AMD press-release detail page exposes the real publication timestamp in a
detail `<time datetime="2026-09-28T16:05:00">` element, but its footer also uses
`<time datetime="2026">2026</time>` for the copyright year. The generic date
normalizer interprets an all-digit string as an epoch timestamp, so the bare
copyright year became a false 1970-era date and caused a conflict.

The official-source conflict checker now ignores a bare four-digit 20xx year as
non-publication boilerplate. Two distinct real detail dates still fail closed.

## TSMC CMS epoch placeholders

TSMC news details expose a real `Issued on` `<time>` value, for example
`2026-09-10T12:00:00Z`. The same page's JSON-LD also contains CMS placeholder
values around the Unix epoch (`1969-12-31` / `1970-01-01`). Those placeholders
previously conflicted with the visible issue date.

The checker ignores those epoch placeholders only when the same detail page also
contains at least one valid explicit publication date. A detail containing only
an epoch placeholder remains rejected, even if an index/feed claims a recent
date. Future dates and genuine conflicting dates continue to fail closed.

## Unitree official API

Unitree `/news/<id>` pages are client-rendered and their static HTML does not
contain the article title or publication timestamp. The site's own client code
calls the fixed official endpoint:

`https://api.unitree.com/website/news/info?id=<page-id>`

The adapter is restricted to the `unitree` registry slug and an exact numeric
`unitree.com/(cn/)?news/<id>` page. The API response must have `code=100`, the
response page ID must equal the URL ID, and its `article.publishTime` must pass
the existing date and age gates. The canonical public source remains the Unitree
news page; the API URL is retained only as publication-date evidence.

## Live read-only evidence

A targeted post-change audit produced:

- AMD: `status=ok`, 4 accepted parser candidates, 0 fetch failures.
- TSMC: `status=ok`, 2 accepted parser candidates, 0 fetch failures.
- Unitree: `status=ok`, 4 accepted parser candidates, 0 fetch failures.
- Combined: 3 attempted, 3 with accepted candidates, 10 parser candidates,
  `snapshotPublished=false`.

A subsequent read-only audit of all 40 approved P1 identities produced:

- attempted: 40 / 40
- companies with accepted parser candidates: **28 / 40**
- accepted parser candidates: **94**
- snapshot published: false
- remaining zero-yield identities: Cambricon, CXMT, Edge Medical, Hygon,
  Inovance, MGI, NAURA, SMIC, SpaceX, Tesla, UBTECH and Xiaomi.

These counts describe parser candidates, not net-new public stories and not
complete regulatory-disclosure coverage. No canonical article snapshot was
written by either audit.

## Validation

52 selected source/parser regressions passed after the final change, including
new tests for AMD copyright-year handling, TSMC placeholder behavior, genuine
date conflicts, Unitree response status/ID binding and Unitree future/old-date
rejection. `git diff --check` passed before the all-40 read-only audit.

