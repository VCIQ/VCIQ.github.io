# Canonical Sector Assignment

This layer preserves the original event sector as provenance and applies only explicit, reviewed sector decisions to the analysis population.

- `replace`: use reviewed canonical tracks for analysis while preserving the observed/raw sector in source data.
- `augment`: retain the observed track and add reviewed adjacent tracks for analysis.
- No automatic sector-quality finding is promoted into this registry without an explicit reviewed record.
- A present registry record must still match its `expectedObservedTrack`; drift is a build failure rather than a silent rewrite.
- Missing historical events are warnings, not failures, so the registry can retain provenance after an event leaves the current public window.

The registry lives at `config/canonical_sector_assignments.json`.
