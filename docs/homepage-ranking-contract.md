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
