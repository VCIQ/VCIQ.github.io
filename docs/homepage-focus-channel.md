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
material and cluster identities. These are versioned bootstrap rules, **not**\+learned weights or a claim that Share calibration has passed the existing replay
protocol. No private samples or browsing records are invented or published.

Each focus card exposes its admission reasons. An empty profile or an empty
qualified set remains empty; unrelated high-scoring stories are not substituted.
Source multiplicity is not asserted to be independent fact verification.

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
