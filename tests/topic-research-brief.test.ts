import assert from "node:assert/strict";
import test from "node:test";

import type { IntelligenceEvent } from "../lib/intelligence-data";
import type { ReportContent } from "../lib/research-content";
import {
  buildTopicResearchBrief,
  resolveTopicEvidence,
} from "../lib/topic-research-brief";

const content: ReportContent = {
  thesis: "人形机器人研究判断",
  points: [],
  companySlugs: ["figure-ai", "unitree", "fourier-intelligence"],
  eventSectors: ["机器人"],
  watchlist: ["累计作业小时", "量产节奏"],
};

function event(
  overrides: Partial<IntelligenceEvent> & Pick<IntelligenceEvent, "id" | "title">,
): IntelligenceEvent {
  return {
    id: overrides.id,
    title: overrides.title,
    summary: overrides.summary ?? "测试摘要",
    type: overrides.type ?? "公司动态",
    region: overrides.region ?? "全球",
    sector: overrides.sector ?? "机器人",
    company: overrides.company ?? "测试公司",
    companySlug: overrides.companySlug,
    publishedAt: overrides.publishedAt ?? "2026-08-20",
    importance: overrides.importance ?? 70,
    source: overrides.source ?? {
      name: "测试来源",
      url: `https://example.com/${overrides.id}`,
      level: "媒体报道",
    },
  };
}

test("humanoid topic excludes unrelated robotics sector events", () => {
  const result = resolveTopicEvidence({
    slug: "humanoid-robotics",
    content,
    events: [
      event({
        id: "robotaxi",
        title: "Robotaxi service expands to a new city",
        summary: "Autonomous driving fleet adds commercial rides.",
      }),
      event({
        id: "humanoid",
        title: "Humanoid robot starts a factory trial",
        summary: "The biped system performs material handling tasks.",
      }),
    ],
  });

  assert.deepEqual(
    result.evidence.map(({ event: item }) => item.id),
    ["humanoid"],
  );
  assert.equal(result.evidence[0]?.matchKind, "keyword");
});

test("dedicated humanoid company events remain eligible without broad sector matching", () => {
  const result = resolveTopicEvidence({
    slug: "humanoid-robotics",
    content,
    events: [
      event({
        id: "figure-index",
        title: "Introducing Index",
        summary: "A large physical dataset for general robotics training.",
        company: "Figure AI",
        companySlug: "figure-ai",
      }),
    ],
  });

  assert.equal(result.evidence.length, 1);
  assert.equal(result.evidence[0]?.matchKind, "company");
  assert.equal(result.evidence[0]?.evidenceId, "E01");
});

test("diversified robot companies require humanoid-specific evidence", () => {
  const result = resolveTopicEvidence({
    slug: "humanoid-robotics",
    content,
    events: [
      event({
        id: "unitree-quadruped",
        title: "Unitree updates its quadruped robot",
        company: "Unitree",
        companySlug: "unitree",
      }),
      event({
        id: "unitree-g1",
        title: "Unitree G1 humanoid enters a new deployment",
        company: "Unitree",
        companySlug: "unitree",
      }),
    ],
  });

  assert.deepEqual(
    result.evidence.map(({ event: item }) => item.id),
    ["unitree-g1"],
  );
});

test("core brief excludes sources still awaiting cross-validation", () => {
  const result = resolveTopicEvidence({
    slug: "humanoid-robotics",
    content,
    events: [
      event({
        id: "pending-source",
        title: "Humanoid robot reaches a deployment milestone",
        source: {
          name: "待核验来源",
          url: "https://example.com/pending",
          level: "待交叉验证",
        },
      }),
      event({
        id: "traceable-source",
        title: "Humanoid robot expands factory deployment",
        source: {
          name: "公开媒体",
          url: "https://example.com/traceable",
          level: "媒体报道",
        },
      }),
    ],
  });

  assert.deepEqual(
    result.evidence.map(({ event: item }) => item.id),
    ["traceable-source"],
  );
});

test("duplicate headlines collapse to one traceable evidence item", () => {
  const result = resolveTopicEvidence({
    slug: "humanoid-robotics",
    content,
    events: [
      event({
        id: "media-copy",
        title: "Humanoid robot begins factory deployment",
        source: {
          name: "媒体",
          url: "https://example.com/media",
          level: "媒体报道",
        },
      }),
      event({
        id: "official-copy",
        title: "Humanoid robot begins factory deployment",
        source: {
          name: "官方",
          url: "https://example.com/official",
          level: "官方披露",
        },
      }),
    ],
  });

  assert.equal(result.evidence.length, 1);
  assert.equal(result.evidence[0]?.event.source.level, "官方披露");
});

test("AI capital report requires capital evidence even for tracked companies", () => {
  const capitalContent: ReportContent = {
    thesis: "AI 资本开支与融资研究",
    points: [],
    companySlugs: ["openai"],
    eventSectors: ["AI / AGI"],
    watchlist: ["资本开支"],
  };
  const result = resolveTopicEvidence({
    slug: "ai-capital-2026",
    content: capitalContent,
    events: [
      event({
        id: "product",
        title: "OpenAI launches a new model",
        sector: "AI / AGI",
        company: "OpenAI",
        companySlug: "openai",
      }),
      event({
        id: "capex",
        title: "OpenAI announces new data center investment",
        sector: "AI / AGI",
        company: "OpenAI",
        companySlug: "openai",
      }),
    ],
  });

  assert.deepEqual(
    result.evidence.map(({ event: item }) => item.id),
    ["capex"],
  );
});

test("brief exposes reproducible coverage statistics", () => {
  const brief = buildTopicResearchBrief({
    slug: "humanoid-robotics",
    content,
    snapshotDate: "2026-08-29",
    events: [
      event({
        id: "recent",
        title: "Humanoid robot reaches a new production milestone",
        publishedAt: "2026-08-20",
        company: "Figure AI",
        companySlug: "figure-ai",
        type: "商业进展",
      }),
      event({
        id: "old",
        title: "Humanoid robot prototype is announced",
        publishedAt: "2026-06-01",
        type: "产品发布",
      }),
    ],
  });

  assert.equal(brief.readMinutes, 3);
  assert.equal(brief.totalMatches, 2);
  assert.equal(brief.recent30Count, 1);
  assert.equal(brief.evidence[0]?.evidenceId, "E01");
  assert.match(brief.coverageSummary, /专题规则共筛出 2 条相关事件/);
});

test("reports without a dedicated rule keep legacy sector fallback", () => {
  const result = resolveTopicEvidence({
    slug: "future-report",
    content: { ...content, companySlugs: [] },
    events: [event({ id: "sector-only", title: "Generic robotics update" })],
  });

  assert.equal(result.evidence.length, 1);
  assert.equal(result.evidence[0]?.matchKind, "sector");
});
