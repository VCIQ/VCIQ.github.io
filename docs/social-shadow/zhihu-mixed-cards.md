# Zhihu mixed search-card handling

## Evidence

After the single-page pagination-metadata fix, an authenticated genuine
Zhihu shadow search for "具身智能" moved beyond paging validation but failed
with schema_error / ZHIHU_SEARCH_CARD_UNKNOWN. The trial emitted zero
observations, was fully checkpointed and sealed, and restored global stop.
This fixed code indicates an unexpected search card wrapper, not a failed
login or proof of no matching content. Original API response contents and
unknown card type values were not exported.

## Strict non-content filtering

The bounded search adapter accepts only wrapper types search_result and
zvideo for projection. Each accepted object must still have a recognized
answer, article or zvideo identity with valid IDs and parent relationship.

An unexpected card is excluded solely as non-content presentation metadata
when its wrapper is a JSON object and its type is a short ASCII category name
(lower-case alphanumeric, underscore or hyphen). Its links, object data,
author, metrics and raw payload are never used or printed. Malformed or
missing wrapper types remain schema errors.

If all cards are excluded or lack valid target content, the collector
returns ZHIHU_EMPTY_COVERAGE_UNPROVEN, never empty or exhausted. The page
limit, content limit, trusted platform transport, auth and identity checks
do not change. A one-page search treats the known web-search-style next
link only as an untrusted hint and never visits it. Multi-page unknown
cursor paths remain rejected.

## Acceptance boundary

Synthetic regression tests cover mixed valid/non-content cards, malformed
categories, all-excluded pages, no raw information leakage, and no extra
search calls. This is not confirmation that the real page contains a
particular presentation type. A later live trial may be run only once,
on a new report/run ID, after natural scheduler eligibility, limited to
one keyword, one search page, one content record and two API requests.
No automated collection or production merge is authorized by this fix.
