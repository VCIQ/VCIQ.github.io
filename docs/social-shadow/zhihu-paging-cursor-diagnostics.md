# Zhihu pagination cursor: evidence, constraints, and blocked acceptance

## Actual Mac8888 shadow evidence (2026-11-08)

The dedicated migrated Zhihu Chromium session completed manual login and
passed one genuine authenticated GET to the allowlisted /api/v4/me endpoint:
authenticationVerified=true, apiDispatches=1, keywordSearches=0.

The following **separate** bounded shadow search trials each used the fixed
literal "具身智能", one page, up to one content record and at most two API
dispatches. All failures were checkpointed/sealed with no new observations,
stop restored, no production promotion, and no quota reset:

1. Original receipt: schema_error / ZHIHU_PAGING_CURSOR_CONFLICT,
   run 9dd9579a-02dc-481a-888d-64acca011cff.
2. Read-only-safe error classification receipt:
   schema_error / ZHIHU_PAGING_CURSOR_AUTHORITY,
   run 28a7411e-2d1d-429f-b376-4819b584f9fa.
3. After allowing a fixed API host or a path-only cursor as metadata:
   schema_error / ZHIHU_PAGING_CURSOR_PATH,
   run 7b1c65af-f65c-495f-881c-fe5617e65467.

This narrows the contract mismatch to the **returned paging.next path**.
It does not establish which path the server supplied, and a path mismatch
is not evidence of authentication failure or zero search results.

## Current diagnostics and safe handling

The adapter emits only fixed diagnostic codes, never raw server pagination
URLs, query strings, cookies, signatures, or account identifiers. It accepts
only strictly structured HTTPS cursors from www.zhihu.com or api.zhihu.com,
or a relative path-only cursor. Regardless of the apparent host, the actual
next URL is **never followed**; any subsequent page would be reconstructed
by the pinned client and exact API transport allowlist.

All accepted cursor forms must still use precisely /api/v4/search_v3,
offset=pageNo*20 and, when supplied, the matching query keyword. Unknown
paths, different domains, schemes, redirects, malformed offsets and keyword
conflicts remain schema errors. This must not be loosened just to force a
single sample to pass.

## Status and next acceptance gate

**Zhihu keyword shadow collection is not accepted.** No further live
search retries are authorized by this diagnostic commit.

For a future limited diagnostic, use a privacy-preserving, explicitly
approved inspection of returned cursor structure: record *only* a fixed
enumerated path class (e.g. exact search path, trailing-slash alias,
unrelated endpoint, unknown), not the URL or raw contents. Confirm the
category against current platform behavior, then add a narrowly scoped
contract and synthetic regression before any new genuine query.

The existing three failures and the authenticated account receipt remain
historical evidence. The account profile, original tracking database,
quota, and global shadow stop are not modified by this PR. No merge,
automatic polling, or production roll-out is justified by these tests.
