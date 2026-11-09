# People professional identity review — 2026-11-09

Scope: the 186 published /people/ records at source commit 5d34686c066a0e4a379991888a4d682d4bd8fd52, plus the outstanding innovation-investor attributions.

## Directory outcomes

| Outcome | Records |
| --- | ---: |
| Public profile identity cross-checked against a first-party source | 25 |
| Same-name candidates, insufficient corroboration | 84 |
| No match returned in this bounded search | 56 |
| Source name malformed, organizational, or ambiguous | 21 |
| Total | 186 |

The machine-readable register is config/people_professional_profiles.json. Each record contains the review date, search terms, an explicit outcome, and (for bindings) the public LinkedIn profile, a first-party source, and the matching reason. Search-result counts are not identity confidence. Unresolved candidate URLs are deliberately not presented as the subject's profile.

Notable disambiguations:
- Shunyu Yao: Princeton/OpenAI history matches /shunyu-yao-099a41115; the Stanford-background namesake was not selected.
- Gavin Baker: Atreides matches /gavinbaker-portfoliomanager.
- David Kirtley: Helion matches /david-kirtley-490b8230 after public-web corroboration.
- Andrew Ng: English-name follow-up connects the Chinese directory name to the public profile and personal website.
- Demis Hassabis: Google author biography supports the chair/chief-scientist context; older company pages may still use CEO.
- Historical employment supports identity disambiguation; it is not automatically asserted as current employment.

## Innovation relationships

30 people now map to the existing reviewed investment evidence. The former 23 missing attribution labels are covered. One label contains five coauthors: Ben Horowitz, Martin Casado, Raghu Raghuram, David Ulevitch, and David George. Their mapping is explicit and scoped to the Machine Age Fund source URL; there is no generic string-splitting or fuzzy matching.

LinkedIn outcomes in this separate network: 26 cross-checked, 2 still candidate-only (Josh Wolfe and 周志峰), 2 unbound (Marc Andreessen and George Robson). No candidate was selected solely by rank.

Original sources checked include a16z's Machine Age Fund, TypeSafe and Westmag articles; Lightspeed's Ricursive and Harvey articles; DCVC's Prineha Narang and Jason Pontin articles; Eclipse's compute-ownership article; IQ Capital's Nyobolt announcement; Earlybird's Neuracore article; Sequoia's Catalyst and TypeSafe articles; Index's Oratomic article. The source URLs and dates remain attached to each identity and relationship.

## Boundaries

Cross-checked means a website editorial identity match, not LinkedIn platform verification, account-owner authorization, contact synchronization, personal investment responsibility, or a friendship claim. No LinkedIn feed or contact-network synchronization is enabled. Future directory additions receive an explicit unreviewed state.

## Validation

10 focused regression tests passed locally using Node's TypeScript loader, covering unsafe links, unsupported identity claims, duplicates, future directory entries, and source-scoped coauthor mappings. Full lint, unit, crawler and Pages checks run through the repository's existing PR workflow.
