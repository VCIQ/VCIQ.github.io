import assert from "node:assert/strict";
import test from "node:test";

import {
  ALL_CHANNEL_UPDATE_KEYWORDS,
  collectChannelUpdateTracks,
  filterAndSortChannelUpdates,
} from "../lib/channel-update-filter";
import type { ChannelUpdateItem } from "../lib/channel-updates";

function reviewedTrackFixture(): ChannelUpdateItem {
  return {
    id: "fixture-reviewed-public-tracks",
    title: "Reviewed cross-track technology event",
    summary: "A stable fixture that verifies public track filtering independently of rolling news retention.",
    href: "https://example.com/reviewed-cross-track-event",
    source: "Test source",
    label: "公司动态",
    context: "Regression fixture",
    date: "2026-08-24",
    dateOriginal: "2026-08-24",
    datePrecision: "exact",
    sortAt: "2026-08-24T00:00:00.000Z",
    keywords: ["公司动态"],
    track: "Web3",
    publicTracks: ["AI / AGI", "AI安全"],
    region: "全球",
    topicNames: ["AI Agent"],
  };
}

test("reviewed public tracks drive filter options without erasing observed provenance", () => {
  const item = reviewedTrackFixture();

  const options = collectChannelUpdateTracks([item]);
  assert.deepEqual(options, [
    { keyword: "AI / AGI", count: 1 },
    { keyword: "AI安全", count: 1 },
  ]);

  const filtered = filterAndSortChannelUpdates({
    items: [item],
    keyword: ALL_CHANNEL_UPDATE_KEYWORDS,
    track: "AI / AGI",
    sortOrder: "newest",
  });
  assert.equal(filtered.length, 1);
  assert.equal(filtered[0].track, "Web3");
  assert.deepEqual(filtered[0].publicTracks, ["AI / AGI", "AI安全"]);
});

test("observed provenance alone does not override reviewed public track filters", () => {
  const item = reviewedTrackFixture();
  const filtered = filterAndSortChannelUpdates({
    items: [item],
    keyword: ALL_CHANNEL_UPDATE_KEYWORDS,
    track: "Web3",
    sortOrder: "newest",
  });

  assert.equal(filtered.length, 0);
});
