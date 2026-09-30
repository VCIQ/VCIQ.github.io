# Homepage Focus channel and isolated publisher updates

## Product contract

The homepage order is **关注流 → 重点 → 推荐 → 快讯 → 科创** followed by
the existing topic and entity channels. Focus is a personal-interest view, not
a renamed P0 list, and it does not replace the existing recommendation channel.

The first version reuses existing browser Favorite, Hotness/share and Homepage
Preference stores plus already-published tracking matches. It writes no new
feedback ledger and sends no behavior records to the public feed endpoint.
Its explicit profile scope is `this-browser`: it does **not** claim to have read
all devices' private Unified Preference Profile or the admin's entire manual
tracking history. Existing private preference synchronization remains unchanged.
Adding authenticated, cross-device focus decisions needs a separate reviewed
bridge that respects the existing actor-scoped profile and explicit exclusions.

Admission requires a recent material event, sufficient importance and an actual
positive signal. Signal classes are ordered tracking > share > favorite. Opens
are only a weak tie-breaker and cannot create admission. Repeated shares of one
URL count once, a removed Favorite stops contributing, generic country/type/source
host matches are insufficient, and exact event dismissals propagate through
material and cluster identities. Background references do not make two events
identical. These are versioned bootstrap rules, **not** learned weights or a
claim that Share calibration has passed the existing replay
protocol. No private samples or browsing records are invented or published.

Each focus card exposes its admission reasons. An empty profile or an empty
qualified set remains empty; unrelated high-scoring stories are not substituted.
Source multiplicity is not asserted to be independent fact verification.

### Chronological display (personal-focus-v2-chronological)

Interest evidence still determines admission with the existing quality, age and
explicit-dismissal gates. After admission, order by the original `publishedAt`
instant descending, before exact-material deduplication and the existing 24-item
cap. Tracking/share/favorite tier, importance, reads and stable ID only break
equal-time ties; older tracking hits must not precede newer eligible favorites.
Missing dates remain ineligible. Date-only publisher inputs retain day precision:
neither collection time, data-branch commit time nor a page-read timestamp is
substituted for a missing publication time. Same-day items with no time-of-day
therefore have a deterministic tie order, not a claimed minute-level chronology.
The public feed source budget, admission thresholds and behavior stores are
unchanged by this display-order update.

## Independent update lane

The existing source configuration supplies two initially verified publishers:
AMD Newsroom RSS and MIT Technology Review China's public JSON news list.
`priority-intelligence-refresh.yml` requests a five-minute schedule, while the
active, visible Focus tab checks the bounded public snapshot once per minute.
GitHub scheduling/queues/network/cache are best-effort: neither interval is an
end-to-end freshness guarantee. Further publishers require their own endpoint
verification and explicit allowlist/contract updates.

Collection uses a read-only job; publication uses a separate write-permission
job. Public source fetches never receive a GitHub token. Per-source failures are
reported as degraded and retain last-good data, all-source failure does not
advance the successful snapshot, and old/config-mismatched artifacts are rejected.
The publisher validates fields and size, then atomically replaces one data file
using its current content SHA on the dedicated `intelligence-live` branch.

The homepage reads `public/data/priority_intelligence.json` directly from that
public branch. It omits credentials/referrers and does not send a personal profile.
This deliberately avoids both the main repository-writer queue and a full Pages
build for each data update. The initial UI deployment still requires Pages.
The raw GitHub host is an initial delivery backend, not a new authenticated API
or a guaranteed low-latency CDN. A future dedicated read-only delivery endpoint
can preserve this bounded snapshot contract.

Existing reviewed archive metadata wins when an increment has the same material.
An increment-only event can immediately be read, tracked, shared and saved, but
Native Research remains gated until that event is in the canonical article
archive. The UI says `增量待归档后可深研` rather than opening a broken event link.

## Entity, diagnostics and pagination revision

Focus v3 retains all eligible event groups from the bounded candidate window.
24 is the first page and subsequent page size, not an admission cap. Admission
remains separate from reverse publication-time order. Exact reviewed material
links and existing cluster IDs group reports; a common company name, a topic or
a background reference alone never establishes event equivalence. A new approval
or closing is not automatically grouped with an earlier agreement announcement.
Reviewed event dismissals use one stable identity in the existing preference
store; no duplicate share samples, feedback ledger or private public projection
is created.

The publisher derives company/person mentions from existing public registries
and an explicitly sourced supplementary alias list. Each mention records the
actual matching alias and title/summary field. Ambiguous aliases stay ambiguous.
This is mention attribution, not automatic company-profile approval, employment
verification or permission to create companySlug/personSlug. Generic company
placeholders are replaced in new feed records, while reviewed archive attribution
is preserved and only missing mention evidence is supplemented.

The browser's diagnostic view separates admission failures, event grouping,
current search/region filters, and not-yet-rendered pages. Absent records are
reported as outside the current candidate window, not falsely as never collected.
The public trace covers only observed bounded source responses and the retained
window; it has a 120-row cap, explicit truncation and aggregate counters. No
private browsing or feedback payload is sent with a diagnostic query. Recall and
irrelevance metrics require an explicitly judged sample; without one they remain
unavailable. Render elapsed time is not called first exposure or reading time.

MITTR collection now always checks page 1 and at most two catch-up pages, with a
frozen previous-window checkpoint and a resumed page overlap. Incomplete/failed
pages never falsely advance the completed checkpoint. RSS uses its available
feed window and reports unbridgeable history gaps; it does not invent a next-page
URL. Each source remains bounded to 60 observed candidates per run; the public
snapshot still holds at most 72 recent records and 300,000 bytes. Records withheld
by this safety window are diagnosed separately from the 24-event display page.
The snapshot is not an unlimited historical archive. Source API timestamps are
retained with their precision; feed midnight/date-only values remain day precision.
Only actual instrumented observations become firstSeenAt; this does not recover
unknown history before instrumentation.

Read-only integration probe during this revision: 89 response rows inspected,
23 final recent records, MITTR pages 1/2/3, AMD feed page 1. Article 17028 retained
2026-09-29T01:30:54Z and identified AMD, World Labs, 李飞飞; the AMD original retained
its date-only timestamp and identified AMD and World Labs. No production data was
written by that probe. New candidate publishers remain disabled pending owner
selection and source-specific verification.

## Acceptance and remaining boundaries

Tests cover channel order, behavior signal hierarchy, cold start, exact vetoes,
repost identity, expiry, URL/evidence schema, optimistic publication boundaries,
partial/all failures and read-only producer versus writer permissions.

Production acceptance needs: all PR checks; merged UI; a real priority collector
and publisher receipt; the matching raw-branch artifact; deployed Focus UI;
and a browser check using real existing follows/shares/favorites. A green CI or a
data-branch commit is not itself that browser acceptance.

The independent full RSS finalize `503/1102` is not repaired by this new lane.
The legacy negative-feedback policy and private Unified Preference Profile are
not replaced. No Core source is auto-approved, no existing manual editorial slot
is removed, and no financial transaction claim is promoted from agreement to
completed acquisition.
