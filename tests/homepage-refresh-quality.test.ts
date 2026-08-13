import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const dashboard = readFileSync("components/dashboard-client.tsx", "utf8");
const page = readFileSync("app/page.tsx", "utf8");
const headlines = readFileSync("components/daily-headlines.tsx", "utf8");
const updates = readFileSync("components/homepage-channel-updates.tsx", "utf8");
const feed = readFileSync("components/homepage-sortable-feed.tsx", "utf8");

test("homepage defaults key events to trusted evidence", () => {
  assert.match(dashboard, /qualityScope === "all" \|\| item\.qualityStatus !== "低可信"/);
  assert.match(dashboard, /<option value="trusted">可信优先<\/option>/);
  assert.match(page, /\.filter\(\(item\) => item\.qualityStatus !== "低可信"\)/);
});

test("homepage distinguishes today's events from current-crawl additions", () => {
  assert.match(dashboard, /今日事件 \$\{todayArticleCount\} 条/);
  assert.match(dashboard, /本轮新收录/);
  assert.match(dashboard, /refreshAudit\?\.todayArticleCount \?\? bootstrap\.todayArticleCount/);
  assert.match(dashboard, /refreshAudit\?\.newArticleCount \?\? "待刷新"/);
});

test("rolling 200-item column is labeled as latest headlines", () => {
  assert.match(headlines, /03 \/ LATEST HEADLINES/);
  assert.match(headlines, /<h2>最新头条<\/h2>/);
  assert.doesNotMatch(headlines, /<h2>今日头条<\/h2>/);
});

test("homepage starts from bounded, object-first research entry points", () => {
  assert.match(page, /INITIAL_KEY_EVENTS_LIMIT = 20/);
  assert.match(dashboard, /以公开证据组织可复核的科技研究/);
  assert.match(dashboard, /id="research-objects"/);
  assert.match(dashboard, /浏览四类对象/);
  assert.match(dashboard, /搜索公开证据/);
  assert.match(dashboard, /<nav className=\{styles\.heroActions\} aria-label="首页研究入口">/);
  assert.ok(
    dashboard.indexOf('id="research-objects"') <
      dashboard.indexOf('className="market-strip"'),
    "research object directory should follow the hero before market/event streams",
  );
});

test("homepage event controls describe local filtering and load the archive explicitly", () => {
  assert.match(dashboard, /useArticles\(initialPayload, \{ enabled: false \}\)/);
  assert.match(dashboard, /function ensureFullArchive\(\)/);
  assert.match(dashboard, /placeholder="筛选当前事件列表"/);
  assert.doesNotMatch(dashboard, /placeholder="搜索技术、赛道、人物、公司或事件"/);
  assert.match(dashboard, /KEY_EVENTS_INITIAL_LIMIT = 20/);
  assert.match(dashboard, /加载更多事件/);
  assert.match(dashboard, /role="group" aria-label="地区筛选"/);
  assert.match(dashboard, /aria-pressed=\{region === item\}/);
  assert.match(dashboard, /完整事件档案暂时读取失败/);
});

test("homepage secondary feeds are deduplicated, bounded, and link to fuller views", () => {
  assert.match(page, /excludeHrefs=\{initialEventHrefs\}/);
  assert.match(page, /\.\.\.initialHeadlineHrefs/);
  assert.match(headlines, /HOMEPAGE_HEADLINE_LIMIT = 10/);
  assert.match(updates, /HOMEPAGE_OBJECT_UPDATE_LIMIT = 10/);
  assert.match(headlines, /const seen = new Set<string>\(\)/);
  assert.match(headlines, /excluded\.has\(key\) \|\| seen\.has\(key\)/);
  assert.match(updates, /const key = canonicalHref\(item\.href\)/);
  assert.match(updates, /excludeHrefs\.map\(canonicalHref\)/);
  assert.match(feed, /INITIAL_FEED_RENDER_LIMIT = 10/);
  assert.match(feed, /archiveHref/);
});

test("curated company panel does not claim an unverified weekly ranking", () => {
  assert.match(dashboard, /<h2>公开公司样本<\/h2>/);
  assert.doesNotMatch(dashboard, /本周重点公司/);
});

test("homepage labels metrics conservatively and remains a read-only surface", () => {
  assert.match(dashboard, /事件档案/);
  assert.match(dashboard, /唯一原文链接/);
  assert.match(dashboard, /档案最多赛道/);
  assert.doesNotMatch(dashboard, /原始来源/);
  assert.doesNotMatch(dashboard, /高活跃赛道/);
  assert.match(dashboard, /PUBLICATION STRUCTURE GATE/);
  assert.match(dashboard, /"UNKNOWN"/);
  assert.match(dashboard, /不代表每条语义均经人工核验/);
  assert.match(dashboard, /buildTrackingCaptureLink/);
  assert.match(dashboard, /验证并加入追踪/);
  assert.doesNotMatch(page, /HomepageTrackingActions/);
  assert.doesNotMatch(feed, /buildTrackingCaptureLink/);
  assert.doesNotMatch(feed, /加入追踪/);
});
