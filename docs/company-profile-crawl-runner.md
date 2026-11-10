# Reviewed candidate crawl execution — not deployed

Parent: Issue #664. Implementation remains inside stacked Draft PR #670,
depending on #669 and #668. Do not merge the overlapping #665 separately.

## What is implemented

`BoundedCrawlRunner` is an explicitly opted-in callable adapter for
`observe_selected_company_crawls`. Unlike an injected synthetic
`CompletedProcess`, this adapter actually starts and waits for a subprocess.
It has no CLI, import-time execution, scheduled trigger or production wiring.
Instantiating it requires `authorized=True`; that flag is an API guard, not
an independent authorization service.

Before and after every command, the runner verifies an isolated standalone
Git directory, detached HEAD, the expected commit SHA, expected repository
origin, unchanged tracked code and absence of untracked or ignored files.
Only the two existing public JSON outputs may be dirty before execution.
The queue must be byte-identical after execution: the crawler must not mark
events processed. Outputs must be regular single-link files, not symlinks.

The command is fixed to the current Python executable and existing company
crawler module, with `-E -s -B`, one selected slug, one worker and six pages.
It cannot substitute a shell, another module, another slug or another cwd.
The environment is built from an allowlist rather than copied from the
operator: no `GH_TOKEN`, cloud credentials, proxy authentication, `PYTHONPATH`
or dynamic-loader variables are inherited. Each command gets a disposable
HOME/TMPDIR, closed inherited file descriptors and null standard streams.
Timeouts terminate the new POSIX process group; a failed runner cannot retry,
and a successful slug cannot be run twice by the same runner.

The observer now freezes the selection and official URLs, verifies the time
budget before each command, clamps command timeout to the remaining budget,
and checks each company's fresh receipt before starting the next company.
Freshness is measured against that command's start, not just the job start.
Snapshot reads use nonblocking open so a FIFO is rejected without blocking
before the regular-file check. Returned evidence includes selection/source
digests, but those are consistency links, not signatures.

## What the tests prove

The tests create disposable local Git repositories containing a deliberately
synthetic program at the crawler module path. Some tests run that actual
program in a real subprocess and exercise the observer/runner integration,
timeout termination, environment isolation, dirty code, ignored imports,
unexpected origins, SHA drift, staged changes, queue mutation and duplicate
execution. No test invokes the production crawler or makes HTTP requests.
The fixture's origin URL is only configured locally and is not evidence of
an authenticated remote checkout.

## Remaining production gates

This adapter is **not an operating-system sandbox**. An explicitly trusted
runtime and exclusively owned checkout remain necessary; it does not prevent
malicious reviewed code from reading arbitrary files accessible to its OS
user or initiating network requests. Concurrent filesystem/index tampering,
authentication of source repositories and trust in the system Python/runtime
are outside its protection. The deployment must enforce those boundaries.

Production integration must still authenticate the expected main SHA,
reconstruct selection/catalog evidence from that same SHA, retain immutable
run receipts, recover failed or interrupted runs, check the final queue and
postprocessed profiles, and obtain independent review. No caller in the
current scheduled workflow instantiates this runner. A successful observer
result still sets `markProcessedAuthorized`, `mergeAuthorized` and
`publicationAuthorized` to false. It is not evidence that an official website
was successfully fetched or its factual content is correct.

The existing company-refresh schedule, production crawler, `--mark-processed`
step, main branch, Pages publication and social collection stop switches are
not modified by this Draft. Enabling the runner in production is a separate
reviewed change, not a consequence of green unit tests.
