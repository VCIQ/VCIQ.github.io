# Homepage ranking contract

The homepage has three distinct ranking intents. Keeping them separate prevents a broad personalization feature from overriding the user's explicit request for recency.

## Recommendation channel

The `推荐` channel is the only channel whose primary ordering is the personalized recommendation score. Recency is the first tie-breaker.

## Follow, topic, and entity channels

`关注流`, `快讯`, named topic channels (`AI / AGI`, `具身智能`, `半导体`, `商业航天`, `固态电池`, `HBM`), and entity channels (`人物`, `公司`) are recency-first views. Personalized recommendation score remains a secondary tie-breaker so similarly fresh items can still be ordered usefully, but personalization must not move older content ahead of newer content in these channels.

The two entity channels reuse the same feed cards and ranking semantics as topic channels, but their membership is entity-linked rather than keyword-only:

- `人物`: an event has a canonical `personSlug`, is explicitly typed as `人物观点`, or contains resolved `mentionedPeople` links;
- `公司`: an event has a canonical `companySlug` or resolved `mentionedCompanies` links.

This keeps `人物` and `公司` as event-stream views on the homepage while `/people` and `/companies` remain structured research directories rather than duplicate news feeds.

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
