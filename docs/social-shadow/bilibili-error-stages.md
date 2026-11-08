# Bilibili shadow error stages

The first real account-backed bounded Bilibili shadow query returned
schema_error / UNEXPECTED_WORKER_ERROR with zero observed rows. Its genuine
query receipt, checkpoint, sealed batch, and degraded run are retained; they
must not be rewritten as successful or empty. The separate one-request nav
probe had confirmed authentication. Neither result proves successful search.

The pinned upstream client and restricted VCIQ transport completed a
three-request **synthetic** nav/search/detail replay without network or profile
access. Synthetic compatibility does not prove that the live platform returns
the same response shape, and the cause of the real error remains unconfirmed.
There is no automatic retry, account-cookie export, TLS bypass, or proxy switch.

## Diagnostics

The adapter classifies *only* known static validation messages, and otherwise
reports a stable stage code (BILI_SEARCH_CALL_UNEXPECTED,
BILI_SEARCH_RESPONSE_UNEXPECTED, BILI_DETAIL_CALL_UNEXPECTED, etc.).
No raw exception text, server body, cookie, signed URL, username, or profile
content is emitted. Previously classified authentication, throttling, and
verification errors retain their original statuses and halt behavior.

The stages distinguish an exception raised by calling the pinned search
method from an exception raised when checking a returned search document;
likewise for detail requests and projection. A failure in worker preparation
outside the collector still uses the ordinary fail-closed worker code.

Before a further real trial: recheck the private directory owner/mode, require
an existing stop marker and independently authenticated dedicated session,
ensure no unfinished batches or active workers, use a fresh one-shot run ID,
keep the original 1-page/1-detail/3-dispatch ceiling, and preserve all old
receipts. A separate operator decision is required to spend a new live query
budget; this change alone does not enable collection.
