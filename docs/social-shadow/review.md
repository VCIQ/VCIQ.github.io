# PR-08 — private innovation lead review

Signals become company_discovery/funding/product/technology/listing leads via
conservative explicit text triggers. Claims quote the observed title/excerpt;
triggers do not verify that a financing, product or IPO event actually happened.
Subjects remain unresolved/ambiguous unless an explicit reviewed entity mapping
already exists. Same-name companies or masked accounts never establish identity.
Verified IDs already in the read-only production project snapshot produce an
existing-project evidence update, not a duplicate new candidate.

Fingerprint projection includes subject, claims, type and stable evidence versions,
not engagement, ordering, fetch time or number of keywords. Evidence changes create
a new revision/candidate key. Old accepted/rejected decisions remain immutable.
The request ledger enforces requestId idempotency, current fingerprint checks and
transactional pending-to-final compare-and-swap. Unrelated queue changes alone do
not reject a still-current candidate. Every referenced content revision is pinned.

Listing candidates reuse only the existing pure apply_decision function with
independent in-memory shadow payloads. Its production CLI and default paths are
never invoked. Accepted always means awaiting-primary-evidence, not formal pool
promotion; no source ID is relabelled as regulatory, official or broker evidence.

```sh
python -m tools.social.review_cli review-queue --state-dir "$STATE_DIR" --production-snapshot config/innovation_listing_watchlist.json
python -m tools.social.review_cli serve-review --state-dir "$STATE_DIR"
python -m tools.social.review_cli review --state-dir "$STATE_DIR" --decision /absolute/path/to/exported-decision.json
```

The browser workbench listens only on 127.0.0.1. It is read-only: it exports a
DecisionRequest JSON for explicit local CLI application. Host/Origin/fetch-site
checks, a strict CSP, plain text DOM rendering, no remote images/iframes, no CORS
and no write API limit malicious-page access. A reviewer label is an audit label,
not a remote authentication mechanism. The operator controls the private state
folder and must not expose this loopback service via a public proxy.

Acceptance is not a claim that live evidence has been checked. Both all platform
live checks and a real human quality sample remain separate pending gates.
Rollback disables this workbench; the private immutable ledger is retained and
nothing in the existing production queue/watchlist needs restoration.
