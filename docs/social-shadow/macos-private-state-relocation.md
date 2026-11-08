# macOS shadow-state relocation: non-Desktop target

## Motivation and evidence

The isolated acceptance Mac exhibited repeated changes from owner-only
directory mode 0700 to 0755. The Desktop parent also carries an
iCloud-Desktop attribute, and .icloud placeholders are present in the
shadow state and browser install. This strongly motivates removal of the
active state from Desktop sync, but does **not** identify the process that
changed the directory permissions. The original cause remains unproven.

The existing source contains a private SQLite scheduler (including previous
quota and pause history), content and review databases, immutable run reports,
checkpoint and evidence records, Chromium profile files, and Playwright
browser binaries. The source must not be deleted, truncated, or treated as a
disposable cache during migration.

## Destination and guarantees

Use an owner-private location outside Desktop/CloudDrive, such as the user's
Library/Application Support/VCIQ/social-shadow-v1. The app-specific operator
script is run by the desktop user without sudo; it checks owner, permissions,
global stop, incomplete runs, active workers, SQLite quick-check and database
sidecars before copying. Refuse unexpected file types or escaping symbolic
links; preserve legitimate relative browser-framework links and executable
bits. Never export account profile contents or cookie values into logs.

Perform the migration as **preview -> stage -> verify -> activate**:

1. Preview reports only counts, storage size, and whether the new destination
   has enough space. It makes no writes.
2. Stage copies to an isolated partial directory, checks every file hash,
   records a private manifest and atomically publishes the destination. The
   original source is never moved or overwritten. The copied runtime has the
   new state/profile root but remains disabled, mode=shadow and publish=false.
   Original historic reports, receipts and quotas are not re-authored.
3. Verify rechecks copied contents, SQLite integrity, symlink containment,
   owner-only modes, stop marker and disabled platform switches.
4. Activate only if the original has not changed since stage, and write a
   private pointer for the local operator helpers. This **does not** clear the
   stop marker, resume scheduling, authenticate any platform, or publish data.

An interrupted or invalid copy must remain non-active; never automatically
delete partial evidence or silently select the older state as a fallback after
the new root is staged. Operator tools fail closed if the activation pointer
or manifest is missing, modified or has unsafe permissions.

## What migration proves and does not prove

Byte-for-byte transfer establishes local data integrity, **not** whether
login cookies remain usable after the Chromium profile moves. Revalidate
account state separately before any bounded live request. Do not claim
recurring collection is stable until permission drift is observed over actual
use in the new location. Never infer that desktop iCloud synchronization was
the sole root cause from metadata alone.

The public VCIQ repository already accepts explicit stateDir/profileRoot
settings; original production collectors, public data and the innovation
project pool need no changes. Mac-specific operator migration scripts,
credentials, real profiles, full browser executables and private manifests
are **not** included in this PR.
