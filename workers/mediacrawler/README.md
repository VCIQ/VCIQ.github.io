# MediaCrawler shadow worker (PR-03)

This is executable integration code, not a live-platform acceptance claim.
The default remains disabled. Do not merge this stacked branch into production
independently of PR-01/02. No production sources, data or review decisions change.

## Isolation

Prepare a separate MediaCrawler checkout at the commit in `upstream.lock.json`
and its own `.venv`. The worker checks HEAD, tracked modifications and unexpected
untracked importable files; it never installs dependencies, pulls or updates the
checkout while collecting. Run the pinned project's supported dependency setup
manually once in that separate directory. Its browser installation also belongs
to that environment, not the VCIQ web build.

`python -I -B workers/mediacrawler/bootstrap.py <private-input>` is started by the
parent using the upstream `.venv` interpreter and cwd. VCIQ modules are NOT put
on the subprocess import path. Both `tools` and `config` origins are checked.
The environment is allowlisted; stdout/stderr are discarded, not forwarded into
Actions or the public repository. Structured raw reports are mode 0600 under the
private state directory. This is isolation for a trusted local operator, not an
OS sandbox against hostile local code or filesystem races.

A dedicated persistent browser context uses `<state>/profiles/xhs`. It does not
connect to an existing Chrome/CDP instance. Proxy rotation, SSL bypass, comments,
media downloads and creator crawling are disabled after native CLI parsing.
Only bounded search and detail client methods are invoked. The convenience
upstream `start()` and its automatic login/fallback paths are not called.

## Last-page compatibility

At upstream `8f583999006d5b692272c608440e193ca282e73b`, XHS search checks
`has_more` before processing the current items. The shadow observer instead
processes the page and then ends pagination. This is a tested runtime search-loop
replacement, not a source patch; `patches=[]` remains truthful. Missing `has_more`
is a schema error. The upstream client and `update_xhs_note` store mapping are
reused unchanged. Search/normalization failures are never inferred from exit code.

## Operator commands

A valid private RuntimeConfig points to absolute, non-overlapping checkout/state
paths, enables the desired platform and contains no credential values. Use
`plan --platform xhs --output plan.json` to create a plan, then save one of its
`jobs` as a private job JSON. Runtime/plan files stay outside both repositories.

```sh
python -m tools.social.cli worker-doctor --runtime-config "$STATE_DIR/runtime.json" --state-dir "$STATE_DIR"
python -m tools.social.cli bootstrap-session --platform xhs --interactive --live --runtime-config "$STATE_DIR/runtime.json" --state-dir "$STATE_DIR"
python -m tools.social.cli run --platform xhs --job "$STATE_DIR/job.json" --live --runtime-config "$STATE_DIR/runtime.json" --state-dir "$STATE_DIR"
```

Interactive bootstrap additionally requires `interactiveAuthAllowed=true`.
Complete normal platform login in the dedicated visible browser; do not send
cookies/passwords to chat or GitHub. Login readiness never counts as query
coverage. Unattended collection returns `auth_required` instead of prompting.
Resume after a manual check with `resume-platform --confirmed`; active Retry-After
windows cannot be overridden. The browser and worker have wall-clock limits.

## Acceptance and rollback

Offline fixtures cover final-page handling, unknown schemas, explicit empty,
masked authors, dates, credentials, subprocess namespace, profile locks, default-off
activation and timeouts. They do not prove login readiness or live availability.
`live_pending` remains until a genuine private query is reviewed by its operator.
Stop by disabling the private runtime and stopping local scheduling; original
production needs no rollback. Preserve private results, never force-delete profiles.
