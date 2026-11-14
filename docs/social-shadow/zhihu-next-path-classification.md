# Single-use Zhihu next-path classification

Three real bounded Zhihu keyword trials were correctly sealed as failures:
first a generic pagination-cursor conflict, then an authority conflict, and
finally a path mismatch. There were no accepted observations from these
trials. The saved authenticated account result, source contents, quotas,
and shadow stop must remain unchanged.

## Diagnostic, not a newly allowed endpoint

When the server returns a cursor path other than the expected
/api/v4/search_v3, the adapter emits only a static path class:
trailing-slash alias, relative path missing a slash, v2/legacy search,
v3 nested, search-family, other API v4, other API, web search, root, or unknown.
The class is selected in memory. The source URL, path text, query parameters,
tokens and response body are never persisted or printed.

These classifications do not add accepted paths. Every unexpected
path still fails closed as schema_error before any result is accepted.
There is no redirect-following or server-controlled next-page request.
Only the pinned client may construct search requests, using the unchanged
exact host/method/query allowlist and original request budget.

The classification contract is intentionally conservative. If the observed
class is unknown or implies a different API endpoint, stop, do not guess or
expand the allowed hosts. For a known trailing-slash alias, require a separate
offline test and explicit one-shot acceptance before any change to validation.

Tests exercise the fixed category mapping, rejection of arbitrary paths,
and non-disclosure of private source path content. A single future genuine
query, when explicitly authorized, must use an independent run/report ID,
one keyword, one page, one record, at most two API dispatches, and preserve
all prior failures; it cannot attest stable collection or production readiness.
