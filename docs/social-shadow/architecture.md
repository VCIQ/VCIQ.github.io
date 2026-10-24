# Social discovery shadow pipeline — PR-01

Status: contract and offline-guard infrastructure only. There is no collector,
worker, database, review server, scheduler or production publisher in this PR.
It implements PR-01 of the 2026-10-23 VCIQ/MediaCrawler taskbook. PR-02–09 remain
separate work. The code baseline is VCIQ commit
`ca0977e213918ab043713711ee2d89b7d53afe05`; no production entrypoint is changed.

## Boundary

`config/social_discovery.json` is disabled, shadow-only and publication-forbidden.
All five platforms (`wechat`, `xhs`, `wb`, `bili`, `zhihu`) default to disabled.
An eventual operator runtime must live outside both worktrees. Enabling local
configuration will additionally require an implemented collector and an explicit
live opt-in. PR-01 has no implemented collectors or live subcommand at all.

Future flow: complete query registry → budgeted tasks → independent WeChat or
MediaCrawler process → sanitized observations/receipts → sealed batch → local
store → shadow review. None of these future arrows is activated by merging this
PR. Do not import MediaCrawler's `tools` or `config` into VCIQ's Python process.
The upstream metadata lock is inert: no checkout, install or browser launch occurs.

No changes to production collectors, scheduled/Pages workflows, existing source
configuration, `public/data`, original review decisions, the formal watchlist or
`config/automation_jobs.json` are included. Production lineage is not finalized by
shadow commands. Review acceptance never establishes the underlying claim or
permission to publish.

## Contracts

`schemas/social/contracts-v1.schema.json` preserves the taskbook v1 structure.
It covers nine top-level kinds: discovery policy, local runtime, job plan, crawl
job, query receipt, signal observation, run manifest, review item and decision
request. It rejects unknown fields/platforms/states, non-shadow modes and
publication=true. The fixture corpus contains only synthetic companies, queries,
IDs and test-only credential markers; it is not real collection evidence.

`tools.social.contracts` uses the standard library so existing dependency-free
crawler tests can import it. Its interpreter supports only the vocabulary used
by this bundled schema, rejecting unknown keywords/formats and every nonlocal
reference. It is not a general-purpose JSON Schema validator. The optional exact
pins in `requirements-social-dev.txt` provide a reference-validator parity test;
no production installation step is changed. RFC3339 checks require an explicit
timezone; leap-second strings are intentionally not accepted.

Single-record semantic checks additionally cover query/job/content hashes,
platform/content-type constraints, publication precision, bounded/exhausted
receipt semantics, count conservation, review promotion status, canonical URL
allowlists and manifest filename uniqueness. `publishedAt=null` remains null;
`observedAt` is not a substitute. Search terms are not established claims. An
author's masked display name or creator key is not a verified person identity.

`validate` does **not** validate an actual crawl, cross-file references, manifest
file bytes, full review fingerprints/CAS or store integrity. Those are PR-07/08
responsibilities. `batchIntegrityChecked=false` is reported explicitly. Neither
valid JSON nor an exit code establishes that any platform query succeeded.

## Secrets and URLs

Contracts are output allowlists, augmented by sensitive-key, URL-parameter and
credential-assignment scanning (including encoded text). Unknown extras are not
silently stripped. Errors expose stable codes and schema-owned locations, never
raw values or input filenames. Canonical URLs have exact platform hosts and
bounded content paths; credentials, access signatures, unexpected query keys,
ports and userinfo are rejected. This offline check does not prove a URL is
reachable and is not a future network redirect/SSRF policy. Raw responses and
credential-bearing locator URLs must remain private in later PRs.

## Paths and writes

`state_path` requires an explicit absolute directory that neither contains nor is
contained by either worktree. Existing path components must not be symlinks.
`output_path` additionally rejects traversal, cross-platform separators, linked
outputs and existing hardlinked targets. `runtime_paths` requires the dedicated
`<state>/profiles` path and a runtime file under that external state directory.
These functions never create or chmod anything. Doctor may check nonexistent
future state directories; it does not initialize them or authenticate.

These checks assume a trusted local operator and are not an OS sandbox against
concurrent malicious filesystem changes. Future writers must revalidate at the
write boundary and perform bounded atomic writes. Symlinks are deliberately
rejected, including benign ones; use an explicit resolved path on such systems.
`protected_snapshot`/`assert_unchanged` fingerprint config, production data,
workflows, top-level tool modules and `.gitignore`, detecting changes/additions/
deletions without following protected symlink contents or invoking Git.

## Offline usage

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest tests.test_social_contracts tests.test_social_guard
PYTHONDONTWRITEBYTECODE=1 python -m tools.social.cli validate --fixtures tests/fixtures/social/contracts
PYTHONDONTWRITEBYTECODE=1 python -m tools.social.cli doctor --offline
# Optional: install only into a separate development environment, then rerun tests.
python -m pip install -r requirements-social-dev.txt
```

`validate --file <path>` accepts a single contract. The fixture command reads
`valid.jsonl` and `invalid.jsonl`; the latter wraps synthetic documents with an
expected error code. Neither command writes. `doctor --offline --state-dir
/absolute/external/state` checks a future path without creating it. `--runtime`
may point to an explicitly prepared external file, but doctor remains offline.
Python's own bytecode caching is suppressed above, independently of application
side effects. No `publish`, `run`, `commit`, `push` or online-doctor command exists.
Exit 0 means offline checks passed; exit 2 means invalid input or an unsupported
command, not a platform failure/success.

## Test evidence and remaining scope

The initial implementation passed 39 offline tests in an isolated Python 3.13
harness. That harness contained these new modules and a test-only empty `tools`
parent; this is **not** a claim that the entire production repository passed.
The repository's existing Frontend checks workflow also runs `test:crawler`,
which exercises these tests with the actual package parent on Python 3.12. Its
result must be read from this PR's checks, not inferred from the isolated run.
The optional reference-validator test skips transparently when the development
dependency is absent; all application security/contract tests remain active.

Acceptance coverage: C01 all kinds/platforms and invalid modes; C02 unknown dates
and no timestamp substitution; C03 credential keys/URLs/logs; G01 both worktrees,
symlinks/hardlinks and traversal; G02 fresh imports/default-off/no application
writes; G03 version/enum/extra-field/length/duplicate-key/nonfinite errors.
Actual platform traffic, accounts, browser auth and live fixtures: **not run**.

Rollback: revert the new files and appended ignore block. No production snapshot
or runtime data needs rollback. Do not delete an operator's external state folder.
