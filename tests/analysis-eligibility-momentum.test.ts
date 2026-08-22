import assert from "node:assert/strict";
import test from "node:test";
import type { ChannelUpdateDirectory, ChannelUpdateItem } from "../lib/channel-updates";
import { analysisEligibilityForFinding } from "../lib/analysis-eligibility";
import type { SectorQualityFinding } from "../lib/sector-quality-audit";
import { buildTechnologyAnalysisSnapshot } from "../lib/technology-momentum";

function updateItem(overrides: Partial<ChannelUpdateItem>): ChannelUpdateItem {
  return {
    id: "event",
    title: "Sample event",
    summary: "",
    href: "https://example.com/event",
    source: "Example",
    label: "产品发布",
    context: "AI / AGI · 全球",
    date: "2026-08-20",
    dateOriginal: "2026-08-20",
    datePrecision: "exact",
    sortAt: "2026-08-20T00:00:00.000Z",
    firstSeenAt: "2026-06-01T00:00:00.000Z",
    firstSeenEstimated: false,
    keywords: ["产品发布"],
    track: "AI / AGI",
    region: "全球",
    topicSlugs: ["large-models"],
    topicNames: ["大模型"],
    ...overrides,
  };
}

function finding(
  category: SectorQualityFinding["category"],
  recommendedTracks: string[] = ["AI / AGI"],
): SectorQualityFinding {
  return {
    id: "event",
    title: "Sample event",
    currentTrack: "生物科技",
    category,
    recommendedTracks,
    evidenceTopics: [],
    compatibleTopics: [],
    incompatibleTopics: ["大模型"],
    currentTrackTitleTerms: [],
    currentTrackSummaryTerms: [],
    currentTrackSourceTerms: [],
    reason: "test",
  };
}

test("analysis eligibility keeps topic evidence while excluding strong sector misclassification", () => {
  const item = updateItem({ track: "生物科技" });
  const entry = analysisEligibilityForFinding(
    item,
    finding("high-confidence-misclassification"),
  );

  assert.equal(entry.status, "sector-excluded");
  assert.equal(entry.sectorWeight, 0);
  assert.equal(entry.topicWeight, 1);
  assert.deepEqual(entry.analysisTracks, []);
  assert.deepEqual(entry.analysisTopicSlugs, ["large-models"]);
});

test("reasonable cross-sector events contribute fully to each relevant track", () => {
  const item = updateItem({ track: "机器人" });
  const entry = analysisEligibilityForFinding(
    item,
    finding("reasonable-cross-sector", ["AI / AGI"]),
  );

  assert.equal(entry.status, "cross-sector");
  assert.equal(entry.sectorWeight, 1);
  assert.deepEqual(entry.analysisTracks, ["机器人", "AI / AGI"]);
});

test("needs-review events are retained with conservative weights", () => {
  const item = updateItem({ track: "半导体", topicSlugs: ["ai-agent"] });
  const entry = analysisEligibilityForFinding(
    item,
    finding("needs-review", ["AI / AGI"]),
  );

  assert.equal(entry.status, "downweighted");
  assert.equal(entry.sectorWeight, 0.5);
  assert.equal(entry.topicWeight, 0.75);
  assert.deepEqual(entry.analysisTracks, ["半导体"]);
});

test("7D trend and 30D Momentum are computed from eligibility-weighted equal windows", () => {
  const directory: ChannelUpdateDirectory = {
    title: "test",
    description: "test",
    generatedAt: "2026-08-21T12:00:00.000Z",
    items: [
      updateItem({
        id: "ai-now-1",
        title: "DeepSeek releases a new large language model",
        sortAt: "2026-08-20T00:00:00.000Z",
        date: "2026-08-20",
        dateOriginal: "2026-08-20",
      }),
      updateItem({
        id: "ai-now-2",
        title: "Qwen large language model update",
        sortAt: "2026-08-18T00:00:00.000Z",
        date: "2026-08-18",
        dateOriginal: "2026-08-18",
      }),
      updateItem({
        id: "ai-prev",
        title: "Claude large language model update",
        sortAt: "2026-08-10T00:00:00.000Z",
        date: "2026-08-10",
        dateOriginal: "2026-08-10",
      }),
      updateItem({
        id: "wrong-sector-topic-valid",
        title: "Google Gemini Notebook expands into AI Mode Search",
        track: "商业航天",
        context: "商业航天 · 全球",
        sortAt: "2026-08-19T00:00:00.000Z",
        date: "2026-08-19",
        dateOriginal: "2026-08-19",
      }),
      updateItem({
        id: "cross-robot-ai",
        title: "Humanoid robot adds a large language model planning stack",
        track: "机器人",
        context: "机器人 · 全球",
        topicSlugs: ["humanoid-robots", "large-models"],
        topicNames: ["人形机器人", "大模型"],
        sortAt: "2026-08-20T00:00:00.000Z",
        date: "2026-08-20",
        dateOriginal: "2026-08-20",
      }),
    ],
  };

  const snapshot = buildTechnologyAnalysisSnapshot(directory);
  const ai = snapshot.tracks.find((track) => track.name === "AI / AGI");
  const space = snapshot.tracks.find((track) => track.name === "商业航天");
  const largeModels = snapshot.topics.find((topic) => topic.slug === "large-models");

  assert.ok(ai);
  assert.ok(space);
  assert.ok(largeModels);
  assert.equal(snapshot.coverage.sevenDayComparisonReady, true);
  assert.equal(snapshot.coverage.thirtyDayComparisonReady, true);
  assert.equal(ai.sevenDayTrend.currentWeightedEvents, 3);
  assert.equal(ai.sevenDayTrend.previousWeightedEvents, 1);
  assert.equal(ai.sevenDayTrend.direction, "up");
  assert.equal(space.sevenDayTrend.currentWeightedEvents, 0);
  assert.equal(largeModels.sevenDayTrend.currentWeightedEvents, 4);
  assert.equal(largeModels.sevenDayTrend.previousWeightedEvents, 1);
  assert.equal(largeModels.thirtyDayMomentum.currentWeightedEvents, 5);
});

test("approximate dates contribute at reduced temporal weight and undated rows do not affect trends", () => {
  const directory: ChannelUpdateDirectory = {
    title: "test",
    description: "test",
    generatedAt: "2026-08-21T12:00:00.000Z",
    items: [
      updateItem({
        id: "approx",
        title: "DeepSeek large language model update",
        datePrecision: "approximate",
        sortAt: "2026-08-20T00:00:00.000Z",
      }),
      updateItem({
        id: "undated",
        title: "Qwen large language model update",
        datePrecision: "undated",
        sortAt: "0000-01-01T00:00:00.000Z",
      }),
    ],
  };

  const snapshot = buildTechnologyAnalysisSnapshot(directory);
  const topic = snapshot.topics.find((item) => item.slug === "large-models");
  assert.ok(topic);
  assert.equal(topic.sevenDayTrend.currentWeightedEvents, 0.8);
  assert.equal(snapshot.population.datedForTrend, 1);
});

test("Momentum comparisons stay suppressed until the monitoring history covers both windows", () => {
  const directory: ChannelUpdateDirectory = {
    title: "test",
    description: "test",
    generatedAt: "2026-08-21T12:00:00.000Z",
    items: [
      updateItem({
        id: "recent-monitoring",
        title: "DeepSeek large language model update",
        firstSeenAt: "2026-08-15T00:00:00.000Z",
        sortAt: "2026-08-20T00:00:00.000Z",
      }),
    ],
  };

  const snapshot = buildTechnologyAnalysisSnapshot(directory);
  const topic = snapshot.topics.find((item) => item.slug === "large-models");
  assert.ok(topic);
  assert.equal(snapshot.coverage.sevenDayComparisonReady, false);
  assert.equal(snapshot.coverage.thirtyDayComparisonReady, false);
  assert.equal(topic.sevenDayTrend.comparisonReady, false);
  assert.equal(topic.sevenDayTrend.direction, "insufficient");
  assert.equal(topic.sevenDayTrend.growthPct, null);
  assert.equal(topic.thirtyDayMomentum.direction, "insufficient");
});
