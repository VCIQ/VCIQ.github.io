# Pinned MediaCrawler source relocation on macOS

## Why it was needed

The isolated acceptance Mac repeatedly found the tracked MediaCrawler file
docs/STZHONGS.TTF evicted from its Desktop checkout, with a corresponding
.icloud placeholder. This caused the pinned Git integrity check to fail
before a platform request. The observed eviction is not evidence that the
WeChat publisher or account authentication failed.

The pinned source had to be copied outside Desktop sync rather than weakening
Git checks or restoring files indefinitely before each job.

## Staged and activated local operator source

The fixed commit is 8f583999006d5b692272c608440e193ca282e73b.
The protected copy contains 10,024 files and three known Python virtualenv
symlinks (approximately 679 MB of file contents). The copy was verified
with per-file SHA256, permitted symlink targets, owner-only permissions and
a clean pinned Git checkout. The original Desktop checkout remains intact.

An owner-private activation pointer selects the non-Desktop source for the
local operator helpers. The pointer does not alter the disabled production
runtime configuration, saved browser profiles, collection stop, existing
WeChat budget or previously sealed attempts.

Git status can update the internal .git/index cache without changing tracked
files. Only that exact Git cache file is exempt from post-copy byte equality;
its type, owner, size and permission mode remain checked, and activation
separately requires pinned HEAD and a clean tracked worktree. All other
source files must still match their saved hashes. The old Desktop source is
permitted to show only the already-observed single font eviction when the
matching iCloud placeholder exists. Any other old-source change refuses
activation.

## Checks performed

- A copied Python 3.12 virtual environment starts from the new path, resolves
  its new sys.prefix, and imports httpx, playwright and tenacity.
- VCIQ Worker preflight accepts the copied source and its fixed Git commit.
- Local operator source selection uses a private location pointer and
  never accepts arbitrary environment paths.
- The four dedicated platform login helper preflights succeed against the
  new source without browser, network, search or producer writes.
- The source original is not moved or deleted. The default production
  runtime remains disabled; no fresh account or keyword requests were made.

## Residual risks and rollout boundary

The virtualenv's Python executable symlink still points to a separately
installed interpreter under the original Desktop tools directory. Thus the
MediaCrawler SOURCE is no longer on Desktop, but its base interpreter is not
yet completely independent from Desktop/iCloud. Do not claim long-running
stability until that runtime dependency is migrated and observed.

The source pointer is for private Mac acceptance helpers only. This work
does not merge social PRs, enable scheduled collection, bypass platform
controls, raise existing WeChat quotas, or authorize full-text copying.
The WeChat original-article path remains unverified. Private manifests,
Python binaries, cookies and account profiles are not included in GitHub.
