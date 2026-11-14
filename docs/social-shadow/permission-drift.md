# Permission drift: stop-only latch and fail-closed request guard

The private runtime must remain owned by its desktop operator with a 0700 state
directory. Observed 0700-to-0755 changes are still an unresolved environment
problem; this patch does not attribute them to a specific process or fix sync.

## Boundaries

Every instrumented MediaCrawler API dispatch rechecks the state directory's
owner and private mode, before reading its runtime configuration. A changed mode
or owner cancels the request with `SHADOW_CONTROL_PERMISSIONS`. This does not
retroactively cancel an in-flight request or Chromium's internal traffic.

`read_private` and `write_private` now recheck the private state root on entry.
This narrows the gap between an earlier successful preflight and later I/O; it
is not an OS sandbox or a guarantee against adversarial concurrent filesystem
mutation. The existing path, link, size and file-mode checks remain enabled.

`request_stop` may create only the non-secret `shadow.stop` latch after an
owner-only state directory becomes readable/traversable by others (for example
0755). It does not read configuration, modify modes, reset quota, resume work,
or write private content. Group/other-writable directories, unexpected owners,
linked ancestors and repository overlap are refused. An open directory file
descriptor anchors exclusive 0600 creation, and an existing marker is not
followed or overwritten. Partial stop-file creation also remains a stop.

All resume and normal data paths still require the original private boundary.
Restoring 0700 does not remove an existing stop marker or authorize collection.
The high-level CLI's normal settings preflight is not bypassed; this change
specifically makes the already-scoped coordinator/runner cleanup latch usable.

## Operational status

Keep collection stopped until the directory-mutation source is identified or a
separately verified stable runtime location is configured. Do not disable Git
ownership checks, broaden filesystem permissions, clear authentication/rate-limit
pauses, reset counters or repeatedly run live searches as a filesystem probe.
Private paths, account data and real platform payloads do not belong in commits.
