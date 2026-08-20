# Homepage event date overflow fix

The public Intelligence Inbox renders the date rail from `publishedAt`. Ranked intelligence now carries full ISO timestamps such as `2026-08-19T02:02:16.000Z`, while the legacy date rail assumed date-only values.

This branch adds a narrow visual guard around `.event-date` so only the intended `MM-DD` prefix can occupy the fixed date rail. The guard prevents ISO timestamp tails from overflowing into the event title without changing event ordering, freshness, or source timestamps.

A later cleanup can replace the legacy `publishedAt.slice(5)` renderer with an explicit date formatter. Until then, the CSS guard keeps both date-only and full ISO values visually safe.
