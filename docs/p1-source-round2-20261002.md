# P1 source follow-up: CI and configuration checkpoint

## Release state observed

PR #582 was rebased onto the then-latest `main`, reran all required checks,
and was squash-merged as `48e9da73cb2ecd9a7710c82dfe2a26bbd35c72bb`.
Pages run `36963098954` completed both build and deploy successfully. A later
successful Pages deployment at `3330db1e34d8ea92b2bc8d3dccc97899a2af75a6`
is nine commits ahead of the #582 merge, so production still contains #582.

The visible company page has 100 published profiles and 40 approved listed
identities. The incorrect 12-inch SiC story is absent from visible company-card
text; NVIDIA's latest-change card uses a NVIDIA-titled article. These are
HTTP/HTML observations, not interactive-browser acceptance.

## Two configuration-only corrections, separate from #582

Local branch: `fix/p1-source-round2-20261002`.

1. Amazon: the configured AWS RSS response contains dated article paths under
   `/about-aws/whats-new/YYYY/MM/slug/`. With no reviewed article pattern, the
   generic `/about` exclusion drops them before detail parsing. Add one fully
   anchored HTTPS path pattern for this host, numeric year, valid month and
   one article slug. General About pages, directories, attachments, extra path
   components and invalid months are not included in the exception.
2. Alibaba: change the news index to `/en-US/news-press-releases`, which visibly
   contains release links such as `/en-US/document-2041385426245124096`. Add one
   anchored numeric document path pattern. No extra host or company is added.

Observed primary entries:
- https://aws.amazon.com/new/ links to the official RSS endpoint.
- https://aws.amazon.com/about-aws/whats-new/recent/feed/
- https://www.alibabagroup.com/en-US/news-press-releases

The publication parser, source/identity gates, 90-day age window, per-company
four-item limit, ten-candidate budget and private Focus rules are unchanged.
An index link becoming discoverable does not make it a published article.
P1 remains 40 research identities / 45 securities; P2 remains 50 pending.

## Post-change live collection receipt

On 2026-10-02 the two configuration-only corrections were rerun with the
read-only approved-company audit. No canonical article snapshot was written.

- Amazon/AWS: `status=ok`, 4 accepted parser candidates, 0 fetch failures.
  Accepted URLs are four `aws.amazon.com/about-aws/whats-new/2026/10/...`
  article details discovered from the official AWS feed.
- Alibaba: `status=ok`, 3 accepted parser candidates, 0 fetch failures.
  Accepted URLs are three numeric `alibabagroup.com/en-US/document-*` release
  details from the official press-release index.
- Combined: 2 attempted companies, 2 with accepted candidates, 7 parser
  candidates, `snapshotPublished=false`.

This receipt establishes parser recovery for these two sources only. It does
not mean seven net-new public stories, does not expand regulatory coverage, and
does not change Focus admission.

## Validation and limits

53 offline Python regression tests passed, including seven new path, host,
detail/date and scope regressions. The compact review manifest parity check and
`git diff --check` passed. The fixture source is synthetic and is not a new
company or live source.

The post-change live audit now supports counting Amazon and Alibaba as recovered
parser sources in addition to the previously confirmed six. No canonical article
snapshot was written, and no browser interaction result was obtained. These
local changes remain separate from the already deployed #582 tree until this
round-two configuration is reviewed and merged.
