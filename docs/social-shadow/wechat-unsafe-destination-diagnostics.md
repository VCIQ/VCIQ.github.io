# WeChat public-original URL rejection diagnostics

## Evidence and scope

The earlier real WeChat shadow smoke produced distinct failures:

- Bing RSS: UNSAFE_DESTINATION before any search result was counted.
- Sogou Weixin: ten index cards were seen, but one attempted original
  resolution failed UNSAFE_DESTINATION. Zero original observations were stored.

No raw URL or signed redirect target was retained in the original receipts,
so the exact rejected URL cannot be reconstructed. Neither failure is
evidence that WeChat has no matching public content.

## Safe classification without allowing new URLs

The HTTPS-only, exact-host-and-path checked_url gate remains unchanged,
as do DNS-public-address validation, TLS hostname checks, redirect budgets,
and durable request debits before requests.

At the adapter's error boundary only:

- An unsafe search/navigation destination becomes the fixed code
  WECHAT_SEARCH_DESTINATION_UNSAFE.
- An unsafe index-card URL becomes WECHAT_RESULT_URL_SCHEME,
  WECHAT_RESULT_URL_HOST, WECHAT_RESULT_URL_PATH, etc.
- A permitted search-card link that subsequently fails destination
  validation during URL resolution becomes WECHAT_RESULT_REDIRECT_UNSAFE.

These fixed codes reveal only the kind/stage of the rejection. They never
include an URL, path, query, signed token, account ID or page content.
The classifier itself never grants permission to fetch a link.

## Limits and acceptance

The synthetic tests exercise URL classes, both provider stages, upstream
redirect rejection, and no leakage. This is a *diagnostic change only*:
there is no new acceptable destination and no claim of successful original
article extraction. Real WeChat request budgets and historical quotas are
retained; there is no automatic retry or production switch. A genuine
source-specific follow-up must be separately budgeted and may not bypass the
existing quota, captcha, publisher rights or URL gate.

## Bounded WeChat-first acceptance

When an allowed Sogou HTTP redirect already returned an original article,
the adapter now reuses that response instead of debiting a second request
for the same original. A literal Sogou redirect must target an allowlisted
WeChat original. DNS lookup failures use the fixed `DNS_LOOKUP_FAILED`
receipt code. TLS, DNS destination checks and per-hop debits stay enforced.

The offline regression uses the real transport implementation with
synthetic HTTP responses. Search, the Sogou link, and the original consume
three debits. The verified original seals, imports, and reaches the private
review queue as discovery-only evidence, without exporting signed fetch
parameters.

For the first separately authorized Mac trial, use one tracking keyword,
one job, one search page and at most one original attempt. Preview the
exact plan under the private policy and confirm a new, nonoverlapping grant
with the operator. A proposed allowance is up to six shadow requests total,
including redirect hops. Account for the existing VCIQ WeChat writer before
allocating the window. Preserve old receipts and restore the stop latch
after the run. If blocked by login, verification or a request limit, record
the fixed receipt and stop for operator review.

Record whether an original was actually parsed and sealed, whether it
produced a review candidate, and whether production data was untouched.
A search card, a successful request without a usable original, and a
discovery-only candidate each have different acceptance meanings.
