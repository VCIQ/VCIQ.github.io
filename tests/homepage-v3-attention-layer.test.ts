import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const ROOT = process.cwd();
const read = (relativePath: string) => readFileSync(path.join(ROOT, relativePath), "utf8");

const page = read("app/page.tsx");
const layer = read("components/homepage-v3-attention-layer.tsx");
const styles = read("components/homepage-v3-attention-layer.module.css");

test("homepage v3 mounts a server-rendered recommendation layer ahead of the research desk", () => {
  assert.match(page, /<HomepageV3AttentionLayer/);
  assert.match(page, /<DashboardV2Client/);
  assert.ok(
    page.indexOf("<HomepageV3AttentionLayer") < page.indexOf("<DashboardV2Client"),
    "the attention layer should appear before the existing research desk",
  );
  assert.doesNotMatch(layer, /["']use client["']/);
});

test("homepage v3 consumes the bounded public ranked projection instead of private preference details", () => {
  assert.match(page, /parseRankedIntelligenceProjection/);
  assert.match(layer, /publicRecommendationReasons/);
  assert.match(layer, /P0 高优先级/);
  assert.match(layer, /同事件来源/);
  assert.doesNotMatch(layer, /feedbackAffinity/);
  assert.doesNotMatch(layer, /profileSampleSize/);
  assert.doesNotMatch(layer, /actor/);
});

test("homepage v3 separates personalized attention from the existing daily brief semantics", () => {
  assert.match(page, /selectDailyBriefEvents/);
  assert.match(layer, /为你推荐/);
  assert.match(layer, /今日必看/);
  assert.match(layer, /Daily Brief 的事件级去重/);
});

test("homepage v3 adds presentation-level topic and source diversity caps", () => {
  assert.match(layer, /MAX_PER_TRACK = 2/);
  assert.match(layer, /MAX_PER_SOURCE = 2/);
  assert.match(layer, /selectDiverseRecommendations/);
  assert.match(styles, /grid-template-columns: minmax\(0, 1\.65fr\) minmax\(300px, \.75fr\)/);
  assert.match(styles, /@media \(max-width: 980px\)/);
});
