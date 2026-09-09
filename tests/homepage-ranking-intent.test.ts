import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(
  new URL("../components/homepage-news-feed.tsx", import.meta.url),
  "utf8",
);

const contract = await readFile(
  new URL("../docs/homepage-ranking-contract.md", import.meta.url),
  "utf8",
);

test("only the recommendation channel is personalization-first", () => {
  assert.match(source, /if \(channel === "recommend"\)/u);
  assert.match(source, /right\.publishedAt\.localeCompare\(left\.publishedAt\)[\s\S]*personalizedHomepageRecommendationScore/u);
  assert.match(contract, /Recommendation channel/u);
  assert.match(contract, /recency-first views/u);
});

test("guess-you-like is a missed-discovery rail instead of a daily leaderboard", () => {
  assert.match(source, /DISCOVERY_WINDOW_DAYS = 45/u);
  assert.match(source, /YOU MAY HAVE MISSED/u);
  assert.match(source, /猜你喜欢/u);
  assert.doesNotMatch(source, /今日重大信号 TOP 10/u);
  assert.match(source, /recommendationFirstPageIds/u);
  assert.match(source, /metrics\.opens < 2 && metrics\.shares === 0/u);
  assert.match(contract, /not already present in the first page of the normal recommendation ranking/u);
});

test("behavior hierarchy is documented without inventing new UI weights", () => {
  assert.match(contract, /Manual Tracking > Share > Favorite \/ Later > Read > Open/u);
  assert.match(contract, /exact numeric weights should be calibrated/u);
});
