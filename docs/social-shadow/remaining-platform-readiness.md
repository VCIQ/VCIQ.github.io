# Remaining platform browser readiness

This change extends the already-validated XHS browser selection to Weibo,
Bilibili and Zhihu: `launch_persistent_context(channel="chromium")` uses the
Playwright-bundled full Chromium in both manual/headed and collection/headless
paths. It does not select the user's daily Chrome installation, connect over
CDP, transfer cookies between profiles, alter request signing, disable TLS
verification, or increase query budgets.

Playwright documents its separate default headless shell and the opt-in full
Chromium mode at https://playwright.dev/python/docs/browsers#chromium-new-headless-mode.

## Acceptance levels must remain distinct

1. Offline launch contracts: platform guard, import origin, binary and profile.
2. Actual disposable browser: the real worker reaches the collection boundary
   with all page traffic denied and no platform/account profile used.
3. Public homepage probe: one bounded navigation in a disposable profile.
   Login redirects, HTTP access restrictions and timeouts are reported, not
   silently reclassified as a usable account session.
4. Manual session: the operator logs in in that platform's dedicated profile.
   Closing a window or confirming the terminal only prepares the session.
5. Real API authentication and a bounded query: must independently succeed
   before any platform is declared ready for collection.

The shipped Bilibili, Weibo and Zhihu bindings require their existing genuine
authentication checks. A reachable homepage does not authorize bypassing them.
This PR does not enable any platform by default or attest production readiness.

## Local environment boundary

The acceptance machine has recurring private-directory permission drift. That
root cause is not established by browser tests. Keep the global stop and all
unused runtime switches disabled. Any explicit precondition repair must retain
controls, receipts, quota, and all existing sessions, narrow permissions only,
and refuse unexpected ownership or links. It is not a background repair loop.

Platform responses, account profiles and authentication material must not be
committed with the test fixtures.
