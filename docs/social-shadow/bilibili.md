# PR-05 — Bilibili video metadata discovery

Adds only video keyword search through the pinned MediaCrawler client and
anonymizing store. It uses normal mode and zero native date bounds; optional date
windows are explicit parent-side post-filters, not historical completeness.

The stable key is aid, displayed as an av URL. An optional BVID alias is attached
only from the same validated detail response that contains the same aid. A shared
title does not establish a duplicate. PR-07 persists these alias mappings without
merging independent original signals. The existing person_video_discovery.py and
people.json remain untouched and can be read as comparison baselines.

The excerpt is the upstream description, not a transcript or a claim that the
video was watched. No media, captions, comments, dynamics, fans or following lists
are collected. Use the private worker commands with `--platform bili`.

Offline replay tests do not establish that the account is logged in or the live
platform is available. Live acceptance remains pending. Disable the private bili
runtime flag for rollback; no production migration is involved.
