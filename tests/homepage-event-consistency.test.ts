import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { applyArticleMetadataReview } from "../lib/article-metadata-reviews";
import {
  excludeDisplayedHomepageEvents,
  homepageEventSummary,
  homepageMaterialUrl,
  homepageSourceEvidence,
} from "../lib/homepage-event-identity";
import { mergeHomepagePersonChannelEvents } from "../lib/homepage-person-channel-events";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

function event(overrides: Partial<LiveIntelligenceEvent> = {}): LiveIntelligenceEvent {
  return {
    id: "event-1",
    title: "Example event",
    summary: "Example summary",
    type: "公司动态",
    region: "全球",
    sector: "AI / AGI",
    company: "Example",
    sourceId: "example-source",
    publishedAt: "2026-09-10T00:00:00.000Z",
    importance: 80,
    source: {
      name: "Example",
      url: "https://example.com/event",
      level: "媒体报道",
    },
    ...overrides,
  };
}

test("bounded article reviews correct only the five reviewed metadata fields", () => {
  const cases: Array<{
    articleId: string;
    sourceId: string;
    url: string;
    title: string;
    input: Partial<LiveIntelligenceEvent> & { trackSlugs?: string[] };
    expected: Partial<LiveIntelligenceEvent> & { trackSlugs?: string[] };
  }> = [
    {
      articleId: "professional-media-computerworld-f1366913d70c811b",
      sourceId: "professional-media-computerworld",
      url: "https://www.computerworld.com/article/4220493/anthropic-maps-three-ai-futures-for-2030-the-most-extreme-could-upend-the-economy.html",
      title: "Anthropic maps three AI futures for 2030; the most extreme could upend the economy",
      input: { sector: "新能源", trackSlugs: ["energy", "other"] },
      expected: { sector: "AI / AGI", trackSlugs: ["other", "ai"] },
    },
    {
      articleId: "professional-media-tom-s-hardware-f0484c85e0f50275",
      sourceId: "professional-media-tom-s-hardware",
      url: "https://www.tomshardware.com/tech-industry/artificial-intelligence/openai-says-its-next-generation-processors-could-be-made-at-samsung-double-sourcing-with-tsmc-hints-at-massive-volume-requirements",
      title: "OpenAI says its next-generation processors could be made at Samsung — double-sourcing with TSMC hints at massive volume requirements",
      input: { sector: "机器人", trackSlugs: ["robotics", "other"] },
      expected: { sector: "半导体", trackSlugs: ["other", "semiconductor"] },
    },
    {
      articleId: "x-openai-129bdd50d2dc5f99",
      sourceId: "x-openai",
      url: "https://x.com/OpenAI/status/2097741659509584091",
      title: "OpenAI：Paul Christiano, founder of the Alignment Research Center, is joining the OpenAI Foundation Board and its Safety and Security Committee, which provide",
      input: { type: "技术突破" },
      expected: { type: "公司动态" },
    },
    {
      articleId: "official-form-energy-7f5377b6174512b9",
      sourceId: "official-form-energy",
      url: "https://formenergy.com/form-energy-launches-technician-hiring-sprint-in-weirton-wv",
      title: "Form Energy Launches Technician Hiring Sprint In Weirton, WV",
      input: { type: "产品发布" },
      expected: { type: "公司动态" },
    },
    {
      articleId: "official-user-东方财富-半导体信源-d29f97496d3075ea",
      sourceId: "official-user-东方财富",
      url: "https://finance.eastmoney.com/a/202609073866203674.html",
      title: "华为更新韬定律论文 最新机构解读来了 后道测试设备环节直接受益？",
      input: { type: "公司动态" },
      expected: { type: "论文" },
    },
  ];

  for (const current of cases) {
    const original = {
      ...event({
        id: current.articleId,
        title: current.title,
        sourceId: current.sourceId,
        source: { name: "source", url: current.url, level: "媒体报道" },
        ...current.input,
      }),
      trackSlugs: current.input.trackSlugs,
    } as LiveIntelligenceEvent & { trackSlugs?: string[] };
    const corrected = applyArticleMetadataReview(original);
    assert.equal(corrected.id, original.id);
    assert.equal(corrected.importance, 80);
    if (current.expected.sector) assert.equal(corrected.sector, current.expected.sector);
    if (current.expected.type) assert.equal(corrected.type, current.expected.type);
    if (current.expected.trackSlugs) assert.deepEqual(corrected.trackSlugs, current.expected.trackSlugs);

    const wrongId = { ...original, id: `${original.id}-different` };
    assert.strictEqual(applyArticleMetadataReview(wrongId), wrongId);
  }
});

test("review identity keeps material query values but ignores tracking parameters", () => {
  assert.equal(
    homepageMaterialUrl("https://example.com/Path/?article=A&utm_source=x&fbclid=1#top"),
    "https://example.com/Path?article=A",
  );
  assert.notEqual(
    homepageMaterialUrl("https://example.com/Path?article=A"),
    homepageMaterialUrl("https://example.com/Path?article=B"),
  );
});

test("person channel reuses a same-URL canonical article and keeps canonical importance", () => {
  const canonical = event({
    id: "official-user-东方财富-半导体信源-d29f97496d3075ea",
    title: "华为更新韬定律论文 最新机构解读来了 后道测试设备环节直接受益？",
    summary: "旧的文章摘要",
    type: "论文",
    region: "中国",
    sector: "半导体",
    company: "华为",
    sourceId: "official-user-东方财富",
    source: {
      name: "东方财富",
      url: "https://finance.eastmoney.com/a/202609073866203674.html",
      level: "媒体报道",
    },
    importance: 80,
  });
  const directory = event({
    id: "person-directory:person-event-1higdg5",
    title: canonical.title,
    summary: "财联社报道何庭波更新韬定律相关论文，并解读产业影响；当前链接为东方财富转载的新闻报道，非论文原文。",
    type: "论文",
    region: "中国",
    sector: "AI / AGI",
    company: "",
    personSlug: "person-918f5d53a8",
    sourceId: "person-update-directory",
    source: canonical.source,
    importance: 86,
    qualityStatus: "可用",
    qualitySignals: ["人物库正式实体", "人物材料目录", "已核实：论文更新行为的新闻报道"],
    mentionedPeople: ["何庭波"],
  });

  const merged = mergeHomepagePersonChannelEvents([], [directory], [canonical]);
  assert.equal(merged.length, 1);
  assert.equal(merged[0]?.id, canonical.id);
  assert.equal(merged[0]?.importance, 80);
  assert.equal(merged[0]?.sector, "半导体");
  assert.equal(merged[0]?.type, "论文");
  assert.equal(merged[0]?.personSlug, "person-918f5d53a8");
  assert.deepEqual(merged[0]?.mentionedPeople, ["何庭波"]);
  assert.match(merged[0]?.summary ?? "", /非论文原文/u);
  assert.equal(merged[0]?.source.level, "媒体报道");
});

test("a context-only person review is not reintroduced through the canonical article pool", () => {
  const canonical = event({
    id: "leiphone-article",
    title: "对话 IDEA 张磊：「不以动作为输入条件，就不叫世界模型」",
    source: {
      name: "雷峰网",
      url: "https://www.leiphone.com/category/academic/wQny8Cer4EJz0RAU.html",
      level: "媒体报道",
    },
  });
  const directory = event({
    id: "person-directory:person-event-4bmdge",
    title: canonical.title,
    personSlug: "fei-fei-li",
    sourceId: "person-update-directory",
    source: canonical.source,
    mentionedPeople: ["李飞飞"],
  });
  assert.deepEqual(mergeHomepagePersonChannelEvents([], [directory], [canonical]), []);
});

test("right-rail identity filtering removes visible material and internal duplicates", () => {
  const displayed = event({
    id: "left",
    source: { name: "A", url: "https://example.com/a?utm_source=homepage", level: "媒体报道" },
  });
  const duplicate = event({
    id: "right-duplicate",
    source: { name: "A", url: "https://example.com/a", level: "媒体报道" },
  });
  const unique = event({
    id: "right-unique",
    source: { name: "B", url: "https://example.com/b", level: "媒体报道" },
  });
  const duplicateUnique = event({
    id: "right-unique-2",
    source: { name: "B2", url: "https://example.com/b?gclid=tracking", level: "媒体报道" },
  });

  assert.deepEqual(
    excludeDisplayedHomepageEvents([duplicate, unique, duplicateUnique], [displayed]).map((item) => item.id),
    ["right-unique"],
  );
});

test("profile placeholders are not rendered or propagated as event summaries", () => {
  const item = event({
    summary: "杨红新 · 人物档案待补充",
    sourceId: "person-update-directory",
    mentionedPeople: ["杨红新"],
  });
  assert.equal(homepageEventSummary(item), "暂无可用的事件摘要，请查看来源。");
  assert.equal(homepageEventSummary(event({ summary: "杨红新介绍了新的电池量产计划。" })), "杨红新介绍了新的电池量产计划。");
  assert.equal(
    homepageEventSummary(event({ summary: "杨红新 · 新电池量产计划正式启动", mentionedPeople: ["杨红新"] })),
    "杨红新 · 新电池量产计划正式启动",
  );
});

test("source evidence counts distinct links instead of archive duplicateCount", () => {
  const item = event({
    duplicateCount: 9,
    source: { name: "A", url: "https://example.com/a", level: "媒体报道" },
    relatedSources: [
      {
        name: "same",
        url: "https://example.com/a?utm_source=x",
        level: "媒体报道",
        platform: "same",
        title: "same",
        publishedAt: "2026-09-10T00:00:00.000Z",
      },
      {
        name: "other",
        url: "https://example.com/b",
        level: "媒体报道",
        platform: "other",
        title: "other",
        publishedAt: "2026-09-10T00:00:00.000Z",
      },
      {
        name: "other duplicate",
        url: "https://example.com/b?fbclid=1",
        level: "媒体报道",
        platform: "other",
        title: "other duplicate",
        publishedAt: "2026-09-10T00:00:00.000Z",
      },
    ],
  });
  const evidence = homepageSourceEvidence(item);
  assert.equal(evidence.totalLinks, 2);
  assert.equal(evidence.additionalLinks.length, 1);
});

test("homepage server, live refresh, feed and quality UI are wired to the consistency helpers", async () => {
  const [homepage, live, feed, quality] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../lib/use-articles.ts", import.meta.url), "utf8"),
    readFile(new URL("../components/homepage-news-feed.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/event-quality-indicator.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(homepage, /applyArticleMetadataReviews/u);
  assert.match(live, /return applyArticleMetadataReviews\(merged\)/u);
  assert.match(feed, /mergeHomepagePersonChannelEvents\([\s\S]*?peopleChannelEvents,[\s\S]*?articleBase/u);
  assert.match(feed, /excludeDisplayedHomepageEvents/u);
  assert.match(feed, /homepageEventSummary/u);
  assert.match(feed, /猜你喜欢 · 全站推荐/u);
  assert.match(quality, /来源链接/u);
  assert.match(quality, /其他来源链接/u);
  assert.doesNotMatch(quality, /关联来源 \{/u);
});
