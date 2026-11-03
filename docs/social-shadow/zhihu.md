# PR-06 — Zhihu typed search

The upstream convenience method discards raw response pagination before returning
model objects. This adapter observes and validates `data` and `paging.is_end`
before extraction, checks that recognized content identities were not silently
dropped, and then reuses the native store. Missing end evidence never becomes an
exhausted or empty success merely because the returned Python list is empty.

Content identity includes type and ID: answer/article/zvideo never collide.
A parent question is not an answer ID. Publication and update times are separate;
unknown publication dates remain unknown. Empty video bodies remain title_only,
not generated transcripts. Script/style text is removed before the native parser.

The browser visits a fixed Zhihu search endpoint with the literal job query to
prepare the cookies required by the pinned client. No arbitrary source URLs are
executed. Operator commands use `--platform zhihu`; defaults remain disabled.

Fixtures cover three content types and pagination/error branches. Real login,
search and review remain live_pending. Disable the private zhihu flag to stop;
no production source, formal pool, or original review decisions are changed.
