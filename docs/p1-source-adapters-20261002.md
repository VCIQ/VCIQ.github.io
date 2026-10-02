# P1 official-source adapter follow-up — 2026-10-02

## Scope and production boundary

P1 remains 40 approved research identities / 45 securities. All 50 P2 candidates
remain pending. No canonical company profiles, IPO reserve counts, private
interests, Focus thresholds or workflow permissions are changed here.

The earlier attribution fix #581 was deployed as b818a05c, Pages run 36949056729.
A later run 36949749718 failed with homepage script bytes 1,000,307 against the
unchanged 1,000,000-byte limit. Failure retained the last-good deployment.
This follow-up is not itself a deployment receipt.

## Source adapters

Ten existing official-source entries are adjusted: ASML, Intuitive, Amazon,
MetaX, ZTE, MGI, Tencent, Alibaba, Xiaomi and Horizon Robotics. Existing entity
IDs are reused. Company-specific aliases such as Intuitive and AWS stay in the
official-source registry, not in unrestricted global entity matching.

ASML and Intuitive use their official IR news indexes. MetaX uses its corporate
news index and exact /ndetail/<id>.html paths. ZTE's reviewed, anchored article
path may override only the generic /about exclusion; attachments and other
excluded paths remain excluded. MGI uses its current official site. Tencent
uses the newsroom overview and its exact tencent-prefixed story path rather
than treating the JavaScript all-news shell as a successful news list.

Configured RSS/Atom endpoints are parsed directly and every candidate still
requires a fetched detail page. Publication evidence from a feed or HTML index
is usable only for the exact destination and matching fetched title, with one
unambiguous date. Feed updated, collection, copyright and sitemap modification
times are not publication evidence. Invalid, future, conflicting or old detail
dates cannot be replaced by a newer index date. The accepted record retains the
index/feed evidence source when that fallback is used.

MetaX's literal title suffix '新闻中心' and Horizon's '-地平线HorizonRobotics'
are stripped only in their configured adapters. The latter now requires entity
evidence after suffix stripping: another robotics company's standalone financing
story on Horizon's site must not become Horizon's own financing event.

No approval is inferred for the whole shared WeChat domain. Unresolved dynamic
indexes, access failures and old articles remain diagnostic outcomes rather than
manufactured successful collection. These adapters collect official news; they
do not establish complete regulatory-filings coverage or certify every claim.

## Dated observations (read-only, not publication)

The 21 previously zero-yield sources were observed at
2026-10-02T01:48:09.228343Z–01:48:47.048811Z. Five supplied 18 parser candidates:
ASML 4, Intuitive 4, MetaX 4, Horizon 4 and ZTE 2. Fourteen were empty and two
reported error. The canonical article snapshot was not written.

A separate Tencent-only observation after its final endpoint correction ran at
2026-10-02T01:51:13.923130Z–01:51:23.908522Z: 4 accepted candidates, zero failures.
This is a separate observation, not a contemporaneous remeasurement of all 40.
Neither count means net-new articles or public homepage exposure.

Final six-company confirmation after the JSON publication-date guard ran at
2026-10-02T01:55:21.933741Z–01:55:31.301892Z: all six returned status ok with zero
fetch failures and 22 total parser candidates (ASML 4, Intuitive 4, MetaX 4,
Horizon 4, Tencent 4, ZTE 2). This selected-source receipt is not an all-40 audit.

| Source(s) still unresolved | Last bounded observation |
| --- | --- |
| Alibaba, Cambricon | Candidate details lack a recognized publication date |
| Amazon, Hygon, Inovance, Edge Medical | No usable article candidates from configured inputs |
| CXMT, SMIC | Missing-date or index rejections; some legitimate old-date exclusions |
| MGI | Missing-date / entity rejections and old material; old T1+ release is not new news |
| NAURA, Unitree | Index or boilerplate titles, not accepted detail articles |
| UBTECH | Entity evidence missing |
| Xiaomi | Date/title/canonical-host rejection |
| SpaceX, Tesla | Access errors; do not bypass restrictions |

Commands:

```sh
SSL_CERT_FILE=/etc/ssl/cert.pem python3 tools/audit_listed_innovation_sources.py --only-empty
SSL_CERT_FILE=/etc/ssl/cert.pem python3 tools/audit_listed_innovation_sources.py --company tencent
```

The optional repeatable --company selector rejects non-P1 companies before
collection. It prints a diagnostic receipt and never writes the article archive.

## Homepage payload

The full article_metadata_reviews.json remains authoritative and retains all
audit prose and evidence links. The reader imports article_metadata_runtime.json,
a deterministic projection containing every matching and correction field but
not unused audit prose. The projection is checked against the full manifest in
Python regression tests; stale projections fail rather than silently diverge.
No filtering threshold, build budget, review or evidence requirement is relaxed.

```sh
python3 tools/project_article_review_runtime.py --check
```

Without --check the command prints the current projection for review. It does
not edit either manifest. Full build output must verify actual bundle savings;
JSON-size savings alone are not a successful Pages publication.

## Acceptance still required

The focused regression suite covers RSS/detail binding, exact aliases and paths,
title suffixes, date conflict/future/age gates, P1-only audit scope, and runtime
projection parity. The final targeted Python suite passed 46 tests; the frontend
targeted suite passed 18, and TypeScript checking passed. The additional final
JSON future-date regression is included in the same 46-test Python suite.
Full repository CI, build byte budgets and actual deployment remain separate.

Real browser filtering/pagination and private Focus acceptance remain unverified.
Earlier browser attempts reported ERR_BLOCKED_BY_ADMINISTRATOR; no bypass is
authorized by this work. Unit tests, HTTP inspection, PR merge and build receipts
must remain separate from a successful interactive production browser check.
