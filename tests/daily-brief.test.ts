import assert from "node:assert/strict";
import test from "node:test";

import {
  briefTitleSimilarity,
  dailyBriefScore,
  isDailyBriefDuplicate,
  selectDailyBriefEvents,
} from "../lib/daily-brief";
import type { LiveIntelligenceEvent } from "../lib/use-articles";

function event(
  id: string,
  title: string,
  overrides: Partial<LiveIntelligenceEvent> = {},
): LiveIntelligenceEvent {
  return {
    id,
    title,
    summary: title,
    type: "论文",
    region: "全球",
    sector: "AI / AGI",
    company: "OpenAI",
    publishedAt: "2026-08-24",
    importance: 100,
    qualityScore: 92,
    qualityStatus: "高可信",
    source: {
      name: `Source ${id}`,
      url: `https://example.com/${id}`,
      level: "媒体报道",
      platform: "Web",
    },
    ...overrides,
  };
}

test("Daily Brief recognizes the two Pew headlines as the same event", () => {
  const left = event(
    "pew-a",
    "皮尤研究中心：ChatGPT 问世以来的新闻页中，三分之一存在AI痕迹",
  );
  const right = event(
    "pew-b",
    "皮尤研究：ChatGPT 问世后超1/3新增网页含AI生成痕迹-DoNews快讯",
  );

  assert.ok(briefTitleSimilarity(left.title, right.title) >= 0.48);
  assert.equal(isDailyBriefDuplicate(left, right), true);
});

test("Daily Brief strips publisher suffixes before duplicate comparison", () => {
  const left = event(
    "teen-a",
    "风波不断！ChatGPT 推出青少年专属版，背后可不只是保护学生",
    { type: "产品发布" },
  );
  const right = event(
    "teen-b",
    "风波不断！ChatGPT 推出青少年专属版，背后可不只是保护学生|OpenAI家长",
    { type: "产品发布" },
  );

  assert.equal(isDailyBriefDuplicate(left, right), true);
});

test("Daily Brief honors canonical URLs and upstream event clusters", () => {
  const urlA = event("url-a", "事件 A", {
    source: {
      name: "A",
      url: "https://example.com/story?utm_source=alerts&id=7",
      level: "媒体报道",
    },
  });
  const urlB = event("url-b", "完全不同标题", {
    source: {
      name: "B",
      url: "https://example.com/story?id=7&utm_medium=email",
      level: "媒体报道",
    },
  });
  const clusterA = event("cluster-a", "事件 B", { eventClusterId: "cluster-42" });
  const clusterB = event("cluster-b", "事件 B 的另一种写法", {
    eventClusterId: "cluster-42",
  });

  assert.equal(isDailyBriefDuplicate(urlA, urlB), true);
  assert.equal(isDailyBriefDuplicate(clusterA, clusterB), true);
});

test("Daily Brief keeps similar same-company stories separate when the event meaning differs", () => {
  const enterprise = event(
    "enterprise",
    "OpenAI 发布 ChatGPT 企业版全新安全控制功能",
    { type: "产品发布" },
  );
  const teen = event(
    "teen",
    "OpenAI 发布 ChatGPT 青少年版全新家长控制功能",
    { type: "产品发布" },
  );
  const gpt6 = event("gpt6", "OpenAI 发布 GPT-6 模型，性能提升显著", {
    type: "产品发布",
  });
  const gpt7 = event("gpt7", "OpenAI 发布 GPT-7 模型，性能提升显著", {
    type: "产品发布",
  });

  assert.equal(isDailyBriefDuplicate(enterprise, teen), false);
  assert.ok(briefTitleSimilarity(gpt6.title, gpt7.title) >= 0.86);
  assert.equal(isDailyBriefDuplicate(gpt6, gpt7), false);
});

test("Daily Brief expands to ten unique events and backfills after dedupe", () => {
  const unique = Array.from({ length: 11 }, (_, index) =>
    event(`unique-${index}`, `独立事件 ${index}：${"甲乙丙丁戊己庚辛壬癸"[index % 10]} 技术进展`, {
      company: `Company ${index}`,
      source: {
        name: `Publisher ${index % 4}`,
        url: `https://example.com/unique-${index}`,
        level: index % 3 === 0 ? "官方披露" : "媒体报道",
      },
    }),
  );
  const duplicate = event(
    "duplicate",
    "独立事件 0：甲 技术进展|转载",
    {
      company: "Company 0",
      source: {
        name: "Another publisher",
        url: "https://another.example/duplicate",
        level: "媒体报道",
      },
    },
  );

  const result = selectDailyBriefEvents([...unique, duplicate], 10);

  assert.equal(result.length, 10);
  assert.equal(
    result.filter((item) => item.id === "unique-0" || item.id === "duplicate").length,
    1,
  );
});

test("Daily Brief composite score breaks saturated importance ties", () => {
  const official = event("official", "官方事件", {
    source: {
      name: "Official",
      url: "https://example.com/official",
      level: "官方披露",
    },
  });
  const pending = event("pending", "待核验事件", {
    source: {
      name: "Pending",
      url: "https://example.com/pending",
      level: "待交叉验证",
    },
  });

  assert.ok(dailyBriefScore(official) > dailyBriefScore(pending));
  assert.ok(dailyBriefScore(official) < 100);
});

test("Daily Brief keeps diversity caps soft so the list can still fill", () => {
  const sameSource = Array.from({ length: 12 }, (_, index) =>
    event(`same-${index}`, `同一来源但不同事件 ${index}：主题 ${String.fromCharCode(65 + index)}`, {
      company: `Company ${index}`,
      sector: index % 2 === 0 ? "AI / AGI" : "机器人",
      type: index % 2 === 0 ? "论文" : "产品发布",
      source: {
        name: "Only Publisher",
        url: `https://example.com/same-${index}`,
        level: "媒体报道",
      },
    }),
  );

  assert.equal(selectDailyBriefEvents(sameSource, 10).length, 10);
});
