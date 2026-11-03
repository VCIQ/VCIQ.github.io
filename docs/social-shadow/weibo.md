# PR-04 — Weibo shadow search

Depends on PR-03. Uses the same subprocess, profile lock, opt-in gates, timeout,
normalization and checkpoint framework. Default remains disabled.

The pinned client returns a `cards` list. Only validated card_type=9 content is
mapped, including nested card_group entries. An explicitly empty cards response
can end this accessible query; a nonempty result is bounded, not proof of full
platform coverage. No retweet-parent relationship is invented from text.

Python integers/strings are converted directly to stable string note IDs. Titles
are derived and labelled accordingly. Both epoch and source local publication
fields are cross-checked (the latter is China time when it has no offset). A
conflict rejects the row, rather than changing it to the observation time.
HTML script/style content is removed before the upstream store's tag stripping.

Read `workers/mediacrawler/README.md` for private runtime and login setup; use
`--platform wb`. No comments, media, creators or relation graphs are collected.
Offline tests are synthetic; genuine search/login and evidence review remain
`live_pending`. Disable wb to roll back, without touching production data.
