import assert from "node:assert/strict";
import test from "node:test";
import { focusDirectMediaMatch } from "../lib/focus-direct-media";
import { buildHomepageFocusSelection } from "../lib/homepage-focus";
import type { LiveIntelligenceEvent } from "../lib/use-articles";
import type { HomepagePreferenceState } from "../lib/homepage-preferences";

const preferences: HomepagePreferenceState = { schemaVersion: 1, followedSectors: [], dismissedEventIds: [], sectorDislikes: {} };
const now = Date.parse("2026-09-30T02:00:00Z");
const base = (extra: Partial<LiveIntelligenceEvent> = {}): LiveIntelligenceEvent => ({
  id: "cls-funding", sourceId: "google-rss", title: "某硬科技公司完成Pre-IPO融资 - 财联社",
  summary: "公司完成新一轮融资，上市前资本动作取得进展。", type: "融资", region: "中国", sector: "半导体",
  company: "某公司", importance: 88, publishedAt: "2026-09-30T01:00:00Z",
  qualityScore: 33, qualityStatus: "低可信",
  source: { name: "科创资本 · Google News 中文", url: "https://news.google.com/rss/articles/example",
    level: "待交叉验证", platform: "Google News" },
  ...extra,
});

test("owner-approved Google RSS publisher label directly admits a material innovation event", () => {
  const item = base();
  assert.deepEqual(focusDirectMediaMatch(item), {
    publisherId: "cls", publisherName: "财联社／科创板日报相关栏目", attribution: "rss-publisher-label",
  });
  const result = buildHomepageFocusSelection([item], preferences, [], [], now);
  assert.deepEqual(result.items.map((x) => x.id), [item.id]);
  assert.equal(result.decisions.get(item.id)?.signal, "approved-media");
  assert.match(result.decisions.get(item.id)?.reasons.join(" ") ?? "", /重大事实仍需回到原始披露核验/u);
});

test("direct publisher host admits only material innovation/capital updates", () => {
  const material = base({ id: "pedaily", title: "硬科技企业完成战略融资", source: {
    name: "投资界", url: "https://news.pedaily.cn/202609/example.shtml", level: "媒体报道", platform: "投资界",
  }, qualityStatus: "可用", qualityScore: 70 });
  assert.equal(focusDirectMediaMatch(material)?.publisherId, "pedaily");
  const generic = base({ id: "generic", title: "创始人参加年度论坛", summary: "讨论行业趋势。", type: "公司动态",
    source: material.source, qualityStatus: "可用", qualityScore: 70 });
  assert.equal(focusDirectMediaMatch(generic), null);
});

test("publisher prose mention is not attribution and unapproved publishers stay outside direct lane", () => {
  const prose = base({ title: "某公司融资，业内人士提到财联社此前报道" });
  assert.equal(focusDirectMediaMatch(prose), null);
  const unapproved = base({ title: "某公司完成Pre-IPO融资 - 电子工程专辑" });
  assert.equal(focusDirectMediaMatch(unapproved), null);
});

test("explicit dismissal still overrides owner-approved direct media", () => {
  const item = base();
  const result = buildHomepageFocusSelection([item], { ...preferences, dismissedEventIds: [item.id] }, [], [], now);
  assert.equal(result.items.length, 0);
  assert.equal(result.decisions.get(item.id)?.exclusion, "dismissed");
});
