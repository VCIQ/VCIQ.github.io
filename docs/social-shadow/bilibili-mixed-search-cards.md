# Bilibili video search with mixed card types

## Motivating observed failure

The bounded, authenticated, one-page Bilibili shadow search for the literal
keyword "具身智能" produced a saved schema_error receipt with the fixed code
BILI_VIDEO_ITEM_REQUIRED. The receipt reported zero emitted observations.
It was not a platform-authentication or request-limit failure, and it must
remain a failed historical run.

The exact error arises when at least one search array item is not an object
or has a non-video type. No raw platform payload, cookie, account identity,
signed request, or unexpected category value was exported. Consequently,
the actual card-type distribution is **not** attested.

## Narrow compatibility behavior

The raw search response must still have a dict with a list in result, at most
100 raw items, and valid pagination bounds. Every item must be a JSON object
with an absent type (legacy video default), "video", or a short lower-case
type identifier matching the fixed ASCII pattern.

Only type=="video" cards may proceed to validation and detail retrieval.
Non-video presentation cards are discarded **before** detail requests:
the collector never follows them as links or treats them as candidate videos.
For video cards the AID and optional BV ID must still pass the original
identity/alias consistency validation; malformed video cards remain errors.

A result containing non-video cards but **no valid video cards** is not an
authenticated "empty" result. The collector returns
BILI_SEARCH_NO_VIDEO_COVERAGE with schema_error. Malformed type fields return
BILI_SEARCH_ITEM_TYPE_INVALID. Non-object cards remain
BILI_VIDEO_ITEM_REQUIRED. The page and detail budgets remain unchanged.

Page contentItems counts video entries only. Ignored non-video presentation
cards are not represented as skipped normalizer rows or synthesized empty
receipts. The existing frozen output contracts are not changed.

## Validation and rollout

Synthetic tests cover mixed video/unrelated cards, non-video-only pages,
malformed types, invalid video IDs, and absence of private values from
diagnostics. Full offline social regression passed 662 tests with one
pre-existing optional skip on the isolated Mac. These tests do not establish
that any particular category exists in the *live* response.

This change is safe to stage in a draft PR, not grounds for production
activation. The next real trial, if explicitly undertaken, must use a new
run and report identifier, the relocated state, a current authenticated
dedicated session, a visible stop marker and original single-query,
single-page, single-detail, three-dispatch request ceiling. All historical
failures and quotas are preserved.
