import assert from "node:assert/strict";
import test from "node:test";

import { clusterPersonEventItems } from "../lib/person-event-clustering";
import { validatePersonIdentity } from "../lib/person-identity-validation";
import type { ResearchPerson } from "../lib/people-data";
import {
  assessPersonResearchCoverage,
  assessPersonViewChange,
  clusterPersonMaterials,
  getPersonResearchSnapshot,
} from "../lib/people-research";

function makePerson(overrides: Partial<ResearchPerson> = {}): ResearchPerson {
  return {
    slug: "test-person",
    name: "测试人物",
    englishName: "Test Person",
    role: "Example Labs 创始人",
    concepts: ["世界模型"],
    summary: "围绕世界模型与智能体开展研究。",
    materials: [],
    aliases: ["测试人物", "Test Person"],
    handles: [],
    sectors: ["AI / AGI"],
    background: "围绕世界模型与智能体开展研究。",
    organizations: ["Example Labs"],
    products: ["Atlas"],
    works: [],
    books: [],
    speeches: [],
    sources: [],
    status: "partial",
    updatedAt: "2026-08-22T00:00:00Z",
    tracked: true,
    ...overrides,
  };
}

test("person identity gate rejects non-people and title bleed", () => {
  assert.equal(validatePersonIdentity({ name: "混合专家模型" }).valid, false);
  assert.equal(validatePersonIdentity({ name: "C Class Presiden Thomas Sonderman" }).valid, false);
  assert.equal(validatePersonIdentity({ name: "Massachusetts Governo Chris Ballance" }).valid, false);
  assert.equal(validatePersonIdentity({ name: "王兴兴", englishName: "Wang Xingxing" }).valid, true);
  assert.equal(validatePersonIdentity({ name: "Chris Ballance" }).valid, true);
});

test("same-person coverage of one event clusters while preserving sources", () => {
  const items = [
    {
      title: "王兴兴：人形机器人量产与具身智能最新进展",
      date: "2026-08-20",
      href: "https://example.com/a",
      source: "Source A",
      context: "王兴兴",
    },
    {
      title: "专访王兴兴：谈人形机器人量产与具身智能进展",
      date: "2026-08-21",
      href: "https://example.com/b",
      source: "Source B",
      context: "王兴兴",
    },
  ];
  const clusters = clusterPersonEventItems(items, {
    referenceDate: "2026-08-22T00:00:00Z",
    scopeKey: (item) => item.context,
  });
  assert.equal(clusters.length, 1);
  assert.equal(clusters[0].sourceCount, 2);
  assert.equal(clusters[0].items.length, 2);
});

test("event clustering never merges different people or distant events", () => {
  const items = [
    {
      title: "人形机器人量产与具身智能进展",
      date: "2026-08-20",
      href: "https://example.com/a",
      source: "Source A",
      context: "王兴兴",
    },
    {
      title: "人形机器人量产与具身智能进展",
      date: "2026-08-20",
      href: "https://example.com/b",
      source: "Source B",
      context: "另一人物",
    },
    {
      title: "人形机器人量产与具身智能进展",
      date: "2026-04-01",
      href: "https://example.com/c",
      source: "Source C",
      context: "王兴兴",
    },
  ];
  const clusters = clusterPersonEventItems(items, {
    referenceDate: "2026-08-22T00:00:00Z",
    scopeKey: (item) => item.context,
  });
  assert.equal(clusters.length, 3);
});

test("cross-time direct expression supports reinforcement without inventing a shift", () => {
  const person = makePerson({
    materials: [
      {
        title: "世界模型：从预测到行动",
        date: "2025-01-10",
        type: "speech",
        url: "https://example.com/old",
        source: "Example Labs",
      },
      {
        title: "世界模型：从预测到行动的最新进展",
        date: "2026-08-01",
        type: "interview",
        url: "https://example.com/new",
        source: "Example Research Interview",
      },
    ],
  });
  const events = clusterPersonMaterials(person.materials, person.name, person.updatedAt);
  const assessment = assessPersonViewChange(person, events);
  assert.equal(assessment.kind, "reinforced");
  assert.equal(assessment.confidence, "supported");
  assert.equal(assessment.evidence.length, 2);
});

test("explicit shift wording remains a candidate until original context is verified", () => {
  const person = makePerson({
    materials: [
      {
        title: "世界模型：从预测到行动",
        date: "2025-01-10",
        type: "speech",
        url: "https://example.com/old",
        source: "Example Labs",
      },
      {
        title: "从世界模型转向端到端智能体：新的研究重心",
        date: "2026-08-01",
        type: "interview",
        url: "https://example.com/new",
        source: "Example Research Interview",
      },
    ],
  });
  const events = clusterPersonMaterials(person.materials, person.name, person.updatedAt);
  const assessment = assessPersonViewChange(person, events);
  assert.equal(assessment.kind, "shift");
  assert.equal(assessment.confidence, "candidate");
});

test("third-party publication timing alone never becomes a viewpoint change", () => {
  const person = makePerson({
    materials: [
      {
        title: "媒体解读测试人物的世界模型路线",
        date: "2025-01-10",
        type: "commentary",
        url: "https://example.com/media-old",
        source: "Media A",
      },
      {
        title: "媒体再次解读测试人物的世界模型路线",
        date: "2026-08-01",
        type: "commentary",
        url: "https://example.com/media-new",
        source: "Media B",
      },
    ],
  });
  const events = clusterPersonMaterials(person.materials, person.name, person.updatedAt);
  const assessment = assessPersonViewChange(person, events);
  assert.equal(assessment.kind, "unchanged");
  assert.equal(assessment.confidence, "insufficient");
});

test("research coverage reports missing identity evidence instead of hiding the gap", () => {
  const person = makePerson({
    role: "待补充",
    organizations: [],
    concepts: [],
    sectors: [],
    products: [],
    materials: [
      {
        title: "第三方人物介绍",
        date: "2026-08-01",
        type: "commentary",
        url: "https://example.com/profile",
        source: "Media",
      },
    ],
  });
  const events = clusterPersonMaterials(person.materials, person.name, person.updatedAt);
  const coverage = assessPersonResearchCoverage(person, events);
  assert.ok(coverage.score < 60);
  assert.ok(coverage.gaps.includes("身份或任职仍需核验"));
  assert.ok(coverage.gaps.includes("缺少可核验的公司或机构关联"));
  assert.ok(coverage.gaps.includes("缺少两条以上一手表达、论文或公开文件"));
});

test("latest event implications separate organization, technology and evidence semantics", () => {
  const person = makePerson({
    materials: [
      {
        title: "Example Labs 发布 Atlas 世界模型研究进展",
        date: "2026-08-20",
        type: "research_paper",
        url: "https://example.com/atlas",
        source: "Example Labs Research",
      },
    ],
  });
  const snapshot = getPersonResearchSnapshot(person);
  const dimensions = new Set(snapshot.latestImplications.map((item) => item.dimension));
  assert.ok(dimensions.has("组织"));
  assert.ok(dimensions.has("技术 / 产品"));
  assert.ok(dimensions.has("证据性质"));
});

test("latest change skips clickbait when a nearby research-relevant event exists", () => {
  const person = makePerson({
    materials: [
      {
        title: "Test Person Leaves Audience Speechless (MUST WATCH)",
        date: "2026-08-22",
        type: "commentary",
        url: "https://example.com/clickbait",
        source: "Video Channel",
      },
      {
        title: "Example Labs 发布 Atlas 世界模型研究进展",
        date: "2026-08-21",
        type: "research_paper",
        url: "https://example.com/research",
        source: "Example Labs Research",
      },
    ],
  });

  const snapshot = getPersonResearchSnapshot(person);
  assert.equal(snapshot.latestChange?.url, "https://example.com/research");
});
