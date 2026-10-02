# P1 acceptance follow-up — 2026-10-01

## Scope

Keep the approved 40 P1 research identities, 45 securities and 50 pending P2
candidates unchanged. This follow-up corrects one material's company attribution,
closes a company-card quality-gate omission and adds bounded source diagnostics.
It does not grant personal follows, widen Focus admission or relax source gates.

## Resonac / NVIDIA attribution

The production article `user-track-wechat-icbank-semiconductor-897f06420892e22f`
is titled `日本大厂，推出12英寸SiC衬底`. Its archived summary identifies Resonac
Holdings, while `company`, `mentionedCompanies`, `companySlug`, `companySlugs`
and stored resolver matches incorrectly identify NVIDIA. The record also carries
`qualityScore: 25` and `qualityStatus: 低可信`.

Resonac's own release, dated 2026-09-15, describes 300 mm SiC single-crystal growth
and substrate processing, not NVIDIA's product launch or mass production:
https://prtimes.jp/main/html/rd/p/000000203.000102176.html

The shared metadata manifest now supports a company correction only with exact
article/source/title/URL identity, supporting summary text and explicit rejected
entity IDs. The reader and Python publication gate remove only the rejected
NVIDIA bindings, preserving other entities and original date, source, importance
and quality. No Resonac company profile is created. Reapplication is idempotent;
different or subsequently reviewed metadata is not overwritten.

Static intelligence consumers apply the same manifest as the live reader.
Company latest-change selection now passes the existing quality fields to the
actionable-event gate and rejects low-confidence or below-50 records. An action
word alone cannot override those quality flags.

## Read-only source observation

Command: `python3 tools/audit_listed_innovation_sources.py --only-empty`.
The existing Mac CA bundle was used; TLS verification remained enabled.
Observed from **2026-10-01T23:52:29.919089Z** through
**2026-10-01T23:53:46.466084Z**: 21 previously zero-yield P1 sources attempted,
zero accepted article candidates. Three source statuses were `error` and 18 were
`empty`. These are bounded-parser outcomes, not evidence that the companies had
no news. The canonical article snapshot was not written.

| Source | Observed rejection / access evidence |
| --- | --- |
| Alibaba | 10 candidate pages without a recognized valid publication date |
| Amazon | No candidate article URLs found from the configured index |
| ASML | 8 missing-date and 3 index/title rejections; 4 article HTTP 404s |
| Cambricon | 7 missing-date rejections |
| CXMT | 7 missing-date, 3 index/title and 2 outside-window rejections |
| Edge Medical | No candidate article URLs found |
| Horizon Robotics | 14 missing-date and 1 index/title rejection |
| Hygon | No candidate article URLs found |
| Inovance | No candidate article URLs found |
| Intuitive Surgical | 3 entity-evidence and 1 index/title rejection |
| MetaX | 6 missing-date, 1 index/title rejection; 7 HTTP 502 article failures |
| MGI | Homepage URLError; source status error |
| NAURA | 4 index/title rejections |
| SMIC | 5 missing-date, 1 index/title and 4 outside-window rejections |
| SpaceX | Both configured indexes HTTP 403; 2 fallback pages lack dates |
| Tencent | Configured articles index HTTP 404; 14 index/title rejections; one Unicode URL encoding error |
| Tesla | Configured IR index HTTP 403; source status error |
| UBTECH | 1 entity-evidence rejection and one video URL HTTP 403 |
| Unitree | 15 index/title rejections |
| Xiaomi | 2 missing-date and 1 index/title rejection |
| ZTE | 3 missing-date, 4 index/title and 5 outside-window rejections |

The collector now emits rejection counts, successful indexes and at most 12
sanitized failure examples per company. Failure examples omit query strings;
sitemap failures remain in aggregate counts and are not a complete trace.
No source endpoint, entity gate, date window, request budget or retention policy
has been relaxed in this follow-up. This instrumentation diagnoses the remaining
coverage work; it does not claim an increase in collected articles.

## Validation boundaries

Local focused JavaScript regression: 18 passed, zero failed or skipped.
Expanded Python regression: 31 passed. TypeScript `tsc --noEmit` passed.
Legacy metadata tests now supply each review's required summary evidence and use
the correct query delimiter; exact-identity and newer-correction guards remain.

Browser automation attempted `/companies/`, `/innovation-capital/` and `/` but
navigation returned `net::ERR_BLOCKED_BY_ADMINISTRATOR`. No proxy or bypass was
used. Actual browser filtering, pagination and private Focus acceptance therefore
remain unverified. HTTP/HTML checks and unit tests are not browser acceptance.

These local results do not assert that this follow-up has been merged or deployed.
Repository CI, the resulting Pages deployment and a matching production readback
are separate acceptance receipts.
