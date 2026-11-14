# Zhihu one-page metadata-only pagination exception

## Evidence

A genuine, authenticated, bounded Zhihu search reported the fixed path class
ZHIHU_CURSOR_PATH_OTHER_WEB_SEARCH. This establishes only that the returned
paging.next path begins with /search but differs from the exact allowlisted
/api/v4/search_v3 endpoint. The original URL and query were not stored.
Previous runs remain failed, not empty and not rewritten as successful.

## Narrow rule

For a task with maxSearchPages == 1 on page 1, and only if the current
response has a nonempty data array, a paging.next from an official accepted
authority whose path class is OTHER_WEB_SEARCH is treated as an untrusted
pagination hint. We NEVER follow this link, do not trust it as evidence
of further pages, and report hasMore=unknown. The current response still
must pass the original wrapper/type/identity/normalization validation.
No new account, source, search endpoint, or request scheme is accepted.

A page containing only excluded non-target cards still fails coverage.
An empty first page with this unexpected cursor remains schema_error,
never an empty success. Multi-page tasks, cross-host next URLs, arbitrary
unknown paths and invalid paging metadata continue to fail closed.

The pinned MediaCrawler client still creates all actual page requests,
and the restricted VCIQ HTTP transport controls method, hostname, path,
parameters, TLS validation, platform authentication and request budget.
The 1-page/1-record trial has at most one search API request after the
account check and cannot fetch page 2.

## Acceptance and limitations

Offline tests demonstrate metadata-only behavior for a one-page query,
that no second search call occurs, that invalid data remains rejected,
and that cross-host and multi-page cases still fail. A separate, explicitly
bounded genuine shadow run is needed to confirm the current content shape.
Even a successful run would establish only a one-page discovery path, not
verified investment leads, full-text extraction, pagination completeness,
continuous collection stability or production readiness.
