# Homepage ranking contract

The homepage has three distinct ranking intents. Keeping them separate prevents a broad personalization feature from overriding the user's explicit request for recency.

## Recommendation channel

The `推荐` channel is the only channel whose primary ordering is the personalized recommendation score. Recency is the first tie-breaker.

## Follow and topic channels

`关注流`, `快讯`, `科创`, and named topic channels (`AI / AGI`, `具身智能`, `半导体`, `商业航天`, `固态电池`, `HBM`) are recency-first views. Personalized recommendation score remains a secondary tie-breaker so similarly fresh items can still be ordered usefully, but personalization must not move older content ahead of newer content in these channels.

`科创` is not a keyword channel. Membership is supplied by the build-derived `innovation-capital-feed.json` projection. An item must be tied to the reviewed innovation-capital universe (project, lifecycle project, target broker, capital institution, mature candidate, or a dedicated innovation discovery source) and must also carry a material listing, funding/investment, technology/commercialization, or policy event signal. Within the channel, recency stays first; `innovationPriority` is only the first tie-breaker after recency.

## Guess-you-like rail

The former `今日重大信号 TOP 10` rail is a discovery surface, not a daily leaderboard. It is labeled `猜你喜欢` with the subtitle `你可能错过的重要信号`.

Candidate rules:

- trusted content only;
- within a rolling 45-day discovery window;
- not dismissed;
- not already saved for later;
- not already substantially consumed locally (two or more opens, or already shared);
- not already present in the first page of the normal recommendation ranking.

Candidates reuse the existing personalized homepage recommendation score; no new behavior weights are introduced in this change. Importance and recency are tie-breakers. This keeps the discovery surface useful while behavior-weight calibration remains a separate experiment.

## Behavior semantics

The intended explicit-behavior hierarchy is:

`Manual Tracking > Share > Favorite / Later > Read > Open`

`Ignore` remains a strong negative signal. This document defines product semantics only; exact numeric weights should be calibrated from replay / holdout evidence instead of being selected in this UI change.

## Official global investor evidence: 科创 / 重点 separation

The investor research archive contributes an additional **display-only, source-dated** set of homepage stories, not an automatic feed of all 30 institutions' navigation links. The selected events come from the canonical reviewed research evidence, restricted to official investor sources, explicit day publication dates and a 45-day window. Each original article appears at most once; an official article may include both funding disclosure and attributable investment theses without creating duplicate stories.

The 科创 topic accepts those known reviewed source events via the existing static projection annotation. Its ranking remains recency-first and its linked destination is the full investor research dossier. The 重点 tab uses the existing 7-day/material/personal-signal gates and does **not** treat a mentioned investor or project as an explicit tracking hit. A user must have an actual followed sector, saved/shared item or other existing approved personal signal; merely appearing on the 30-investor watch list does not auto-admit a story.

The daily source scout's candidate URLs, outage states, unverified negative titles and limited-window changes are **not** published as verified investment news. The canonical `articles.json` item wins by original URL when already present, and the display-only investor projection remains available after live article refresh without altering archive-writer ownership.
