import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function source(path: string) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("homepage labels distinguish the follow feed from explicit followed sectors", async () => {
  const feed = await source("components/homepage-news-feed.tsx");
  assert.match(feed, /label: "关注流"/u);
  assert.match(feed, /已关注赛道 \{preferences\.followedSectors\.length\}/u);
  assert.doesNotMatch(feed, /个性化：关注 \{preferences\.followedSectors\.length\}/u);
});

test("homepage utility actions offer share and do not pretend a generic jump is deep research", async () => {
  const feed = await source("components/homepage-news-feed.tsx");
  assert.match(feed, /recordArticleShare/u);
  assert.match(feed, /vciq:favorite-share-request/u);
  assert.match(feed, /分享这条情报/u);
  assert.doesNotMatch(feed, />\s*深度研究\s*</u);
});
