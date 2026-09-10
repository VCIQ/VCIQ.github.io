import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  isHomepagePersonDirectoryEvent,
  mergeHomepagePersonChannelEvents,
  projectHomepagePersonDirectoryEvents,
  type HomepagePersonDirectoryItem,
  type HomepagePersonProfile,
} from "../lib/homepage-person-channel-events";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

const profile: HomepagePersonProfile = {
  slug: "jensen-huang",
  name: "黄仁勋",
  englishName: "Jensen Huang",
  aliases: ["Jensen H. Huang"],
  role: "NVIDIA 创始人兼首席执行官",
  organizations: ["NVIDIA", "英伟达"],
  sectors: ["AI算力与基础设施"],
};

function directoryItem(
  overrides: Partial<HomepagePersonDirectoryItem> = {},
): HomepagePersonDirectoryItem {
  return {
    id: "person-material-1",
    title: "黄仁勋谈 AI 基础设施的新阶段",
    summary: "黄仁勋 · NVIDIA 创始人兼 CEO",
    href: "https://example.com/interview?utm_source=test",
    source: "Example Media",
    label: "采访",
    context: "Jensen H. Huang",
    sortAt: "2026-09-09T08:00:00.000Z",
    eventClusterId: "person-cluster-1",
    sourceCount: 2,
    sources: [
      {
        name: "Second Source",
        href: "https://example.org/second",
        title: "Second report",
      },
    ],
    ...overrides,
  };
}

function articleEvent(
  overrides: Partial<LiveIntelligenceEvent> = {},
): LiveIntelligenceEvent {
  return {
    id: "article-1",
    title: "已有正式人物事件",
    summary: "summary",
    type: "人物观点",
    region: "全球",
    sector: "AI算力与基础设施",
    company: "",
    personSlug: "jensen-huang",
    publishedAt: "2026-09-09T07:00:00.000Z",
    importance: 80,
    source: {
      name: "Canonical",
      url: "https://example.net/canonical",
      level: "媒体报道",
    },
    mentionedPeople: ["黄仁勋"],
    ...overrides,
  };
}

test("person directory projection only admits published person profiles", () => {
  const accepted = projectHomepagePersonDirectoryEvents([directoryItem()], [profile]);
  assert.equal(accepted.length, 1);
  assert.equal(accepted[0]?.personSlug, "jensen-huang");
  assert.deepEqual(accepted[0]?.mentionedPeople, ["黄仁勋"]);
  assert.equal(accepted[0]?.sector, "AI算力与基础设施");
  assert.equal(accepted[0]?.type, "人物观点");
  assert.equal(accepted[0]?.qualityStatus, "可用");
  assert.ok(accepted[0]?.qualitySignals?.includes("首页人物事件中心性"));

  const rejected = projectHomepagePersonDirectoryEvents(
    [directoryItem({ context: "未收录的人物" })],
    [profile],
  );
  assert.deepEqual(rejected, []);
});

test("homepage person gate excludes durable references, undated records and roundup headlines", () => {
  for (const label of ["官方资料", "人物资料", "公开材料"]) {
    assert.equal(
      isHomepagePersonDirectoryEvent(directoryItem({ label }), profile),
      false,
      `${label} should stay in the person library`,
    );
  }
  assert.equal(
    isHomepagePersonDirectoryEvent(
      directoryItem({ sortAt: "0000-01-01T00:00:00.000Z" }),
      profile,
    ),
    false,
  );
  assert.equal(
    isHomepagePersonDirectoryEvent(
      directoryItem({
        title:
          "科技早报：黄仁勋谈 AI；OpenAI 发布新品；多家公司公布融资进展",
        label: "人物材料",
      }),
      profile,
    ),
    false,
  );
  assert.equal(
    isHomepagePersonDirectoryEvent(
      directoryItem({
        title:
          "黄仁勋谈 AI；OpenAI 发布新品；Anthropic 更新模型；多家公司公布融资进展",
        label: "人物材料",
      }),
      profile,
    ),
    false,
  );
});

test("generic person material must make the person central in the headline", () => {
  assert.equal(
    isHomepagePersonDirectoryEvent(
      directoryItem({
        title: "OpenAI 推出新一代推理模型",
        summary: "报道同时提到黄仁勋对 AI 基础设施的看法",
        label: "人物材料",
      }),
      profile,
    ),
    false,
  );
  assert.equal(
    isHomepagePersonDirectoryEvent(
      directoryItem({
        title: "黄仁勋回应 OpenAI 自研芯片：竞争会推动产业进步",
        label: "人物材料",
      }),
      profile,
    ),
    true,
  );
});

test("attributed surname and owned primary-source formats remain publishable", () => {
  const musk: HomepagePersonProfile = {
    slug: "elon-musk",
    name: "埃隆·马斯克",
    englishName: "Elon Musk",
    role: "企业家、工程与产品负责人",
    organizations: ["SpaceX", "Tesla", "xAI"],
    sectors: ["AI / AGI", "商业航天"],
  };
  assert.equal(
    isHomepagePersonDirectoryEvent(
      directoryItem({
        context: "埃隆·马斯克",
        title: "马斯克称 Starship 下一阶段将提高发射频率",
        label: "人物材料",
      }),
      musk,
    ),
    true,
  );

  assert.equal(
    isHomepagePersonDirectoryEvent(
      directoryItem({
        title: "GTC 2026 Opening Keynote",
        source: "NVIDIA",
        href: "https://www.nvidia.com/gtc/keynote",
        label: "演讲",
      }),
      profile,
    ),
    true,
  );
});

test("sparse auto-discovered identities need explicit research-domain evidence and reject Latin homonyms", () => {
  const rahul: HomepagePersonProfile = {
    slug: "rahul-patil",
    name: "Rahul Patil",
    role: "人物档案待补充",
    organizations: [],
    sectors: ["半导体"],
  };
  assert.equal(
    isHomepagePersonDirectoryEvent(
      directoryItem({
        context: "Rahul Patil",
        title: "BJP–MIM Secret Deal Exposed? | Asif Shaikh Interview | Rahul Patil Podcast",
        source: "YouTube · Hotseat With Rahul Patil",
        href: "https://www.youtube.com/watch?v=example",
        label: "采访",
      }),
      rahul,
    ),
    false,
  );

  const sparseChineseProfile: HomepagePersonProfile = {
    slug: "yang-hongxin",
    name: "杨红新",
    role: "人物档案待补充",
    organizations: [],
    sectors: ["新能源"],
  };
  assert.equal(
    isHomepagePersonDirectoryEvent(
      directoryItem({
        context: "杨红新",
        title: "蜂巢能源杨红新：混合固液电池的低成本量产路径",
        label: "人物材料",
      }),
      sparseChineseProfile,
    ),
    true,
  );
  assert.equal(
    isHomepagePersonDirectoryEvent(
      directoryItem({
        context: "杨红新",
        title: "杨红新谈个人旅行与生活方式",
        label: "采访",
      }),
      sparseChineseProfile,
    ),
    false,
  );
});

test("person directory projection preserves research semantics and related sources", () => {
  const [event] = projectHomepagePersonDirectoryEvents(
    [directoryItem({ label: "论文" })],
    [profile],
  );
  assert.ok(event);
  assert.equal(event.type, "论文");
  assert.equal(event.source.level, "原始材料");
  assert.equal(event.relatedSources?.length, 1);
  assert.equal(event.duplicateCount, 2);
  assert.equal(event.id, "person-directory:person-cluster-1");
});

test("person channel merge keeps canonical article events and adds only unique directory material", () => {
  const canonical = articleEvent();
  const duplicateByUrl = articleEvent({
    id: "directory-duplicate-url",
    title: "different title",
    source: { ...canonical.source, url: "https://example.net/canonical?utm_source=homepage" },
  });
  const duplicateByTitle = articleEvent({
    id: "directory-duplicate-title",
    source: { ...canonical.source, url: "https://example.net/other" },
  });
  const uniqueDirectory = articleEvent({
    id: "directory-unique",
    title: "新的正式人物材料",
    source: { ...canonical.source, url: "https://example.net/unique" },
  });

  const merged = mergeHomepagePersonChannelEvents(
    [canonical],
    [duplicateByUrl, duplicateByTitle, uniqueDirectory],
  );
  assert.deepEqual(merged.map((event) => event.id), ["article-1", "directory-unique"]);
});

test("homepage and deep-research routes consume the published person directory bridge", async () => {
  const [homepage, feed, investigation] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/homepage-news-feed.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/research-agent/investigate/research-investigation-client.tsx", import.meta.url),
      "utf8",
    ),
  ]);

  assert.match(homepage, /aggregatePeopleUpdateDirectory\(getChannelUpdateDirectory\("people"\)\)/u);
  assert.match(homepage, /projectHomepagePersonDirectoryEvents/u);
  assert.match(homepage, /peopleChannelEvents=\{peopleChannelEvents\}/u);
  assert.match(feed, /mergeHomepagePersonChannelEvents/u);
  assert.match(feed, /channel === "people"/u);
  assert.match(investigation, /channel_update_directories\.json/u);
  assert.match(investigation, /eventId\.startsWith\("person-directory:"\)/u);
});
