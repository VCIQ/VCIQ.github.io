# Source collection and homepage publication audit

## Scope and evidence

This audit distinguishes source entities, configured endpoints, observed runtime
channels, accepted articles, homepage selection and deployed publication.
They are not interchangeable success metrics.

The inspected public deployment contained 831 articles in the snapshot dated
2026-09-29T19:33:26+00:00. Two English reports about AMD's agreement to acquire
World Labs were already present (ITPro and InfoWorld), first observed at
2026-09-29T19:26:47+00:00. They were not in the separately published 36-item ranked
projection dated 2026-09-29T13:26:01.290Z. This does not establish that they were
absent from every other homepage component or search surface.

The public sources page displayed 112 source entities. The health snapshot dated
2026-09-29T19:33:31+00:00 retained 904 runtime identities, including historical
records. Those totals have different denominators. The page previously omitted
the professional-media and owner-added source registries from its entity builders.
The new coverage diagnostic maps exact runtime IDs and reports the unmapped count;
it does not manufacture health evidence or automatically approve sources as Core.

## Implemented in this change

1. Add AMD Newsroom's verified RSS endpoint to the existing feed collector.
   The release announces an agreement to acquire World Labs; agreement and closing
   must not be conflated. Announcement: https://newsroom.amd.com/news/amd-acquire-world-labs/
   RSS: https://newsroom.amd.com/rss.xml
2. Add the Chinese Technology Review public news API used by its own frontend.
   The HTML homepage, article URL and apparent sitemap return a JavaScript shell,
   so treating them as a feed is incorrect. The bounded list reader accepts only
   valid publisher IDs and dates, builds fixed-host article links, rejects API or
   schema errors, and stores media attribution rather than first-party evidence.
   The reported regression is https://www.mittrchina.com/news/detail/17028 .
3. Add the ranked-homepage writer to the existing successful-main workflow observer.
   This provides an explicit Pages handoff for GITHUB_TOKEN-created data commits,
   without creating a second competing dispatch inside the writer itself.
4. Add a public coverage diagnostic that separates collection time from build time,
   historical from current channel records, and empty results from transport errors.
   It exposes no private RSS URLs, credentials or private preference records.

## Verification

Focused Python and Node tests cover feed acceptance, fixed-host URL identity,
API/schema rejection, publication listener guards, exact-ID directory coverage,
missing observations, and bounded public output. Live read-only probes confirmed
the two new configured readers return the World Labs event.

## Not established by this change

- This is not a five-minute collector or a guaranteed latency service.
- The separate RSS full-finalization resource-limit incident remains under investigation.
- Adding a source does not prove all of its new articles will be retained or selected.
- The full professional-media/user-source entity directory is not rebuilt here;
  omissions are made visible rather than silently relabeled as complete coverage.
- Homepage data is still deployed through Pages. A separately versioned live public
  feed, atomic publication receipts and per-event latency diagnostics remain follow-up work.
- Passing tests or merging this PR does not prove deployed browser freshness.

Production acceptance must inspect the collected target event, its publication
decision, the matching data commit, successful Pages deployment and the actual
live artifact. Preserve user dismissals, manual editorial slots and Core approval
requirements throughout remediation.
