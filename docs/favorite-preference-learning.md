# Favorite → Preference learning bridge

VCIQ Favorites remain a browser-local feature first. Saving or removing a Favorite immediately updates `vciq:favorites:v1` in localStorage exactly as before. After the local write succeeds, the public site makes a best-effort request to the private tracking-admin preference endpoint.

The request carries only the research metadata already present in the Favorite card: ID, public link, title/summary, channel, keywords, sectors, public sources, company, event type, publication date, importance and saved timestamp. It does not contain a user email, Cloudflare token, GitHub credential, database credential, Google Alert query, or feedback ledger details.

The private endpoint is protected by the existing Cloudflare Access session. The browser request uses credentials but no embedded secret. A missing/expired Access session, CORS failure, network error, timeout, or preference-database error is intentionally ignored by the public Favorite UX.

Existing localStorage history is not discarded. The first time a page runtime reads non-empty Favorites, it sends at most 200 existing entries in one bounded cold-start request rather than issuing one network request per bookmark. The private ledger only inserts favorite IDs it has never seen before, and uses each entry's original `savedAt` as the preference timestamp. This keeps the import idempotent and prevents an old browser snapshot from overwriting a newer server-side save/remove decision.

This gives the system one additive learning path:

`Favorite history + future save/remove → private tracking_events → Unified Preference Profile → Ranked Intelligence`

It does not create companies, people, technologies, tracks, memberships, or source-catalog entries. Those mutations remain behind the authenticated Capture / Manual Tracking validation and apply flow.

## Integration validation

The repository-wide `/search/` route budget issue that previously blocked this PR is intentionally fixed outside this bridge. PR #279 landed on `main` as commit `5deeb7fa56a6c0fc230993eeb4e37a68ba4dbbe0`; its validated `/search/` output is 78,377 bytes against the 100,000-byte HTML budget. This branch does not copy or modify the search-route implementation. The purpose of this note is to force a fresh merge-result validation against the repaired `main` while keeping the Favorite / Ranked Intelligence changes isolated.

A separate production-browser acceptance check is still required for the authenticated cross-origin Favorite write: local Favorite persistence must remain immediate, the private request must succeed only with a valid tracking-admin Access session, and blocking or signing out of that private request must never roll back the browser Favorite.
