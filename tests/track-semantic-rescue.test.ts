import assert from "node:assert/strict";
import test from "node:test";
import { trackSemanticRescueForEvidence } from "../lib/track-semantic-rescue";

test("weak new-materials evidence with a direct title anchor is partially rescued", () => {
  const result = trackSemanticRescueForEvidence({
    track: "新材料",
    title: "AI材料翻身戰：台灣缺材料的材料，往上游挖技術缺口",
    summary: "产业链正在补齐关键原料与先进材料能力。",
    topicCount: 0,
    contentStatus: "weak-evidence",
  });
  assert.equal(result.status, "title-rescue");
  assert.equal(result.multiplier, 2);
  assert.ok(result.titleAnchors.includes("材料"));
});

test("summary rescue requires multiple current-track semantic anchors", () => {
  const rescued = trackSemanticRescueForEvidence({
    track: "半导体",
    title: "New capacity project enters construction",
    summary: "The wafer project adds foundry capacity for advanced chip manufacturing.",
    topicCount: 0,
    contentStatus: "weak-evidence",
  });
  assert.equal(rescued.status, "summary-rescue");
  assert.equal(rescued.multiplier, 1.5);

  const notRescued = trackSemanticRescueForEvidence({
    track: "半导体",
    title: "New capacity project enters construction",
    summary: "The project mentions a single chip-related detail.",
    topicCount: 0,
    contentStatus: "weak-evidence",
  });
  assert.equal(notRescued.status, "none");
  assert.equal(notRescued.multiplier, 1);
});

test("priority topics and non-weak content never receive semantic rescue", () => {
  assert.equal(
    trackSemanticRescueForEvidence({
      track: "新材料",
      title: "先进材料项目投产",
      summary: "",
      topicCount: 1,
      contentStatus: "priority-topic",
    }).multiplier,
    1,
  );
  assert.equal(
    trackSemanticRescueForEvidence({
      track: "新材料",
      title: "先进材料项目投产",
      summary: "",
      topicCount: 0,
      contentStatus: "usable",
    }).multiplier,
    1,
  );
});

test("AI slash AGI is intentionally not rescued by generic AI wording", () => {
  const result = trackSemanticRescueForEvidence({
    track: "AI / AGI",
    title: "AI is changing how consumers shop",
    summary: "A broad consumer trend story about artificial intelligence.",
    topicCount: 0,
    contentStatus: "weak-evidence",
  });
  assert.equal(result.status, "none");
  assert.equal(result.multiplier, 1);
});

test("ASCII rescue terms use token boundaries", () => {
  const result = trackSemanticRescueForEvidence({
    track: "机器人",
    title: "A roboticist discusses resilient systems",
    summary: "No robot deployment is described.",
    topicCount: 0,
    contentStatus: "weak-evidence",
  });
  assert.equal(result.status, "summary-rescue");
  assert.equal(result.titleAnchors.includes("robot"), false);
  assert.ok(result.summaryAnchors.includes("robot"));
});
