# P1 production adapter contract recovery

## Observed production fault

The deployed round-three parser fixes are in PR #584, merge
`f2ca29015be48b92784c2ce244f65d2ec154ecc4`. However, the subsequent full-refresh
snapshot at `1db687c745bbba197663b726eff6b3c7327ad65d` records repeated
`TypeError` failures on official article details. This is not evidence that the
companies have no news.

The scheduled workflow calls `tools/eastmoney_transport.py`, which installs
both the public-region and tracking wrappers around `_article_from_page`.
The base crawler now passes five arguments (including rejection counters and
exact-link publication evidence). Both wrappers still accepted only three.
Reproducing the scheduled installation chain produced:

```
TypeError: install_overrides.<locals>.article_from_page() takes 3 positional arguments but 5 were given
```

Previous direct calls to `tools/audit_listed_innovation_sources.py` bypassed
these production wrappers. Their successful observations do not establish that
the scheduled entrypoint worked. A successful overall workflow conclusion also
does not establish successful per-company crawling; retained articles can still
pass the aggregate quality gate.

## Fix and verification boundary

Both wrappers now forward positional and keyword context unchanged to the
underlying parser. Legacy three-argument callers still work. No date, identity,
quality, age, request-budget, source-domain or personal Focus gate changes.

Five new offline tests install the actual scheduled entrypoint, replacing only
network fixtures and the terminal publication writer. They cover positional and
keyword forwarding, rejection-counter propagation, legacy calls, real/future
date conflicts and complete feed-to-detail parsing through every wrapper.
Together with the related source suites, 51 selected tests passed.

`tools/audit_listed_production_sources.py` provides the corresponding repeatable
live diagnostic. It installs the same production adapters and intercepts only
the final snapshot writer. Its default scope is the 40 approved P1 identities;
`--company` accepts approved identities only. It emits source-code/configuration
hashes with the dated observations and never publishes its candidates.

## Post-fix live observation

Production-adapter audit: **2026-10-02 11:25:25–11:26:16 UTC**.

| Metric | Observed value |
| --- | ---: |
| Approved identities attempted | 40 / 40 |
| Identities with accepted parser candidates | 28 / 40 |
| Parser candidates | 95 |
| Recorded TypeError samples | 0 |
| Snapshot published by audit | false |

The article snapshot, historical listed-source receipt and P1 approval file had
identical SHA-256 hashes before and after the audit. This is a live diagnostic
using production adapters, not 95 net-new published stories, not complete filing
coverage, and not proof of deployment of this patch.

Remaining zero-yield identities: Cambricon, CXMT, Edge Medical, Hygon, Inovance,
MGI, NAURA, SMIC, SpaceX, Tesla, UBTECH and Xiaomi. SpaceX and Tesla returned
access failures; the other ten have discovery/date/entity or template problems.
Do not convert those observations to evidence of absence of company news.

## Historical receipt versus current source ledger

`public/data/listed_innovation_source_health.json` is a targeted collection
receipt from **2026-10-01 15:12:42 UTC**, showing 19/40. It is intentionally not
rewritten by normal scheduled refreshes. That number is historical, not a live
coverage rate. This patch does not overwrite it with an unpublished audit or
change its timestamp. Current production evidence must be read from the dated
official rows in `public/data/articles.json` (`sourceStatus`) and the relevant
workflow execution. Retained-article counts must not be described as newly
collected candidates.

P1 remains 40 research identities / 45 securities; P2 remains 50 pending. No
company profiles, private interests, IPO pool counts or publication rules are
modified. Browser filtering/pagination/private Focus acceptance remains separate.
