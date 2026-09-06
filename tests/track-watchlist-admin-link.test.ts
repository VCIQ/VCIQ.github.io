import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { buildTrackWatchlistLink } from "../lib/tracking-admin-link";

function read(path: string): string {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("track watchlist links preserve the selected track", () => {
  const previous = process.env.NEXT_PUBLIC_TRACKING_ADMIN_URL;
  delete process.env.NEXT_PUBLIC_TRACKING_ADMIN_URL;
  try {
    assert.equal(
      buildTrackWatchlistLink("biotech"),
      "https://vciq-tracking-console.pages.dev/tracks?track=biotech",
    );
    assert.equal(
      buildTrackWatchlistLink(),
      "https://vciq-tracking-console.pages.dev/tracks",
    );
  } finally {
    if (previous === undefined) delete process.env.NEXT_PUBLIC_TRACKING_ADMIN_URL;
    else process.env.NEXT_PUBLIC_TRACKING_ADMIN_URL = previous;
  }
});

test("both technology track routes surface the protected manager entry", () => {
  for (const path of [
    "app/technology/[slug]/layout.tsx",
    "app/technologies/tracks/[slug]/layout.tsx",
  ]) {
    const source = read(path);
    assert.match(source, /TrackWatchlistAdminEntry/);
    assert.match(source, /slug=\{slug\}/);
  }
});

test("sector detail no longer sends management to the public tracking snapshot", () => {
  const source = read("app/technology/[slug]/page.tsx");
  assert.match(source, /buildTrackWatchlistLink\(sector\.slug\)/);
  assert.match(source, /管理关注技术、人物与公司/);
  assert.doesNotMatch(source, /管理样本公司与关键词/);
});
