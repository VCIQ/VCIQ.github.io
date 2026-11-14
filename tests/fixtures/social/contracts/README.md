# Synthetic PR-01 contract fixtures

`valid.jsonl` contains 21 independent documents covering all nine top-level
contract kinds and five platforms. No URL or event is claimed to be real or
reachable. `invalid.jsonl` contains ten `{caseId,errorCode,document}` wrappers;
every wrapped document must be rejected with its expected sanitized error code.
Credential markers are intentionally fake negative-test data, not live secrets.

The manifest is a shape/semantic fixture, not a sealed on-disk import batch.
Cross-file integrity and raw HTTP response replay are explicitly later PR work.
