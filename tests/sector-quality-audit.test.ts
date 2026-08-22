import assert from "node:assert/strict";
import test from "node:test";
import {
  assessSectorQuality,
  buildSectorQualityReviewQueue,
} from "../lib/sector-quality-audit";

function item(overrides: Record<string, unknown>) {
  return {
    id: "sample",
    title: "Sample event",
    summary: "",
    track: "AI / AGI",
    topicSlugs: [],
    sourceGrade: "B" as const,
    ...overrides,
  };
}

test("direct title evidence outside the assigned track becomes a high-confidence correction candidate", () => {
  const finding = assessSectorQuality(
    item({
      id: "gemini-space",
      title: "Google Gemini Notebook expands into AI Mode Search",
      track: "商业航天",
      topicSlugs: ["large-models"],
    }),
  );

  assert.ok(finding);
  assert.equal(finding.category, "high-confidence-misclassification");
  assert.deepEqual(finding.recommendedTracks, ["AI / AGI"]);
  assert.deepEqual(finding.incompatibleTopics, ["大模型"]);
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
