# Favorite → Preference learning bridge

VCIQ Favorites remain a browser-local feature first. Saving or removing a Favorite immediately updates `vciq:favorites:v1` in localStorage exactly as before. After the local write succeeds, the public site makes a best-effort request to the private tracking-admin preference endpoint.

The request carries only the research metadata already present in the Favorite card: ID, public link, title/summary, channel, keywords, sectors, public sources, company, event type, publication date, importance and saved timestamp. It does not contain a user email, Cloudflare token, GitHub credential, database credential, Google Alert query, or feedback ledger details.

The private endpoint is protected by the existing Cloudflare Access session. The browser request uses credentials but no embedded secret. A missing/expired Access session, CORS failure, network error, timeout, or preference-database error is intentionally ignored by the public Favorite UX.

Existing localStorage history is not discarded. The first time a page runtime reads non-empty Favorites, it sends at most 200 existing entries in one bounded cold-start request rather than issuing one network request per bookmark. The private ledger only inserts favorite IDs it has never seen before, and uses each entry's original `savedAt` as the preference timestamp. This keeps the import idempotent and prevents an old browser snapshot from overwriting a newer server-side save/remove decision.

This gives the system one additive learning path:

`Favorite history + future save/remove → private tracking_events → Unified Preference Profile → Ranked Intelligence`

It does not create companies, people, technologies, tracks, memberships, or source-catalog entries. Those mutations remain behind the authenticated Capture / Manual Tracking validation and apply flow.
