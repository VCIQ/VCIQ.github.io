import assert from "node:assert/strict";
import test from "node:test";
import {
  assessSectorQuality,
  buildSectorQualityReviewQueue,
} from "../lib/sector-quality-audit";

type AuditInput = Parameters<typeof assessSectorQuality>[0];

function item(overrides: Partial<AuditInput>): AuditInput {
  return {
    id: "sample",
    title: "Sample event",
    summary: "",
    source: "",
    href: "https://example.com/item",
    track: "AI / AGI",
    topicSlugs: [],
    sourceGrade: "B",
    ...overrides,
  };
}

test("direct title evidence outside the assigned track becomes a high-confidence correction candidate", () => {
  const finding = assessSectorQuality(
    item({
      id: "gemini-space",
      title: "Google Gemini Notebook expands into AI Mode Search",
      source: "DEV Community",
      track: "商业航天",
      topicSlugs: ["large-models"],
    }),
  );

  assert.ok(finding);
  assert.equal(finding.category, "high-confidence-misclassification");
  assert.deepEqual(finding.recommendedTracks, ["AI / AGI"]);
  assert.deepEqual(finding.incompatibleTopics, ["大模型"]);
  assert.deepEqual(finding.currentTrackTitleTerms, []);
  assert.deepEqual(finding.currentTrackSourceTerms, []);
});

test("current-sector title anchors retain hardware-company model releases as cross-sector", () => {
  const finding = assessSectorQuality(
    item({
      id: "cerebras-multimodal",
      title: "Gemma 4 on Cerebras: Fast Multimodal AI",
      source: "Cerebras",
      href: "https://www.cerebras.ai/blog/gemma-4",
      track: "半导体",
      topicSlugs: ["multimodal-models"],
    }),
  );

  assert.ok(finding);
  assert.equal(finding.category, "reasonable-cross-sector");
  assert.ok(finding.currentTrackTitleTerms.includes("Cerebras"));
  assert.deepEqual(finding.recommendedTracks, ["AI / AGI"]);
});

test("current-sector source anchors retain original company releases as cross-sector", () => {
  const finding = assessSectorQuality(
    item({
      id: "cerebras-gpt",
      title: "Accelerating GPT-5.6 Sol Ultrafast with OpenAI",
      source: "Official",
      href: "https://www.cerebras.ai/blog/gpt-5-6",
      track: "半导体",
      topicSlugs: ["large-models"],
    }),
  );

  assert.ok(finding);
  assert.equal(finding.category, "reasonable-cross-sector");
  assert.deepEqual(finding.currentTrackTitleTerms, []);
  assert.ok(finding.currentTrackSourceTerms.includes("Cerebras"));
});

test("summary anchors prevent a strong automatic correction", () => {
  const finding = assessSectorQuality(
    item({
      id: "hardware-summary",
      title: "New GPT inference service launches",
      summary: "The service runs on a new wafer-scale semiconductor platform.",
      source: "Industry News",
      track: "半导体",
      topicSlugs: ["large-models"],
    }),
  );

  assert.ok(finding);
  assert.equal(finding.category, "needs-review");
  assert.ok(finding.currentTrackSummaryTerms.includes("semiconductor"));
});

test("sector ASCII anchors use token boundaries rather than substrings", () => {
  const finding = assessSectorQuality(
    item({
      id: "workspace-not-space",
      title: "Google Workspace adds Gemini AI controls",
      source: "ZDNET",
      track: "商业航天",
      topicSlugs: ["large-models"],
    }),
  );

  assert.ok(finding);
  assert.equal(finding.category, "high-confidence-misclassification");
  assert.deepEqual(finding.currentTrackTitleTerms, []);
});

test("an event with both current-track and adjacent-track topics is retained as cross-sector", () => {
  const finding = assessSectorQuality(
    item({
      id: "robot-cross-sector",
      title: "Humanoid robot adds a large language model planning stack",
      track: "机器人",
      topicSlugs: ["humanoid-robots", "large-models"],
    }),
  );

  assert.ok(finding);
  assert.equal(finding.category, "reasonable-cross-sector");
  assert.ok(finding.compatibleTopics.includes("人形机器人"));
  assert.ok(finding.incompatibleTopics.includes("大模型"));
});

test("summary-only cross-track evidence stays in manual review", () => {
  const finding = assessSectorQuality(
    item({
      id: "weak-agent-semiconductor",
      title: "New data center deployment enters service",
      summary: "The operator says AI Agent workloads may be supported later.",
      source: "ITPro",
      track: "半导体",
      topicSlugs: ["ai-agent"],
    }),
  );

  assert.ok(finding);
  assert.equal(finding.category, "needs-review");
  assert.deepEqual(finding.recommendedTracks, ["AI / AGI"]);
});

test("fully compatible topic assignments do not enter the sector review queue", () => {
  const finding = assessSectorQuality(
    item({
      id: "chip-semiconductor",
      title: "New AI chip accelerator enters production",
      track: "半导体",
      topicSlugs: ["ai-chips"],
    }),
  );

  assert.equal(finding, null);
});

test("review queue sorts actionable corrections before cross-sector and weak-evidence cases", () => {
  const queue = buildSectorQualityReviewQueue([
    item({
      id: "weak",
      title: "New deployment enters service",
      summary: "AI Agent workloads may be supported later.",
      track: "半导体",
      topicSlugs: ["ai-agent"],
    }),
    item({
      id: "cross",
      title: "Humanoid robot adds a large language model planning stack",
      track: "机器人",
      topicSlugs: ["humanoid-robots", "large-models"],
    }),
    item({
      id: "strong",
      title: "Microsoft launches new reasoning model family",
      track: "新材料",
      topicSlugs: ["reasoning-models"],
    }),
  ]);

  assert.deepEqual(
    queue.map((finding) => finding.category),
    [
      "high-confidence-misclassification",
      "reasonable-cross-sector",
      "needs-review",
    ],
  );
});
