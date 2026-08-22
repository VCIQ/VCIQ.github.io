import assert from "node:assert/strict";
import test from "node:test";
import type { ChannelUpdateItem } from "../lib/channel-updates";
import { analysisEligibilityForFinding } from "../lib/analysis-eligibility";
import type { CanonicalSectorResolution } from "../lib/analysis-eligibility";
import type { CanonicalSectorAssignmentRecord } from "../lib/canonical-sector-assignment";
import type { SectorQualityFinding } from "../lib/sector-quality-audit";

function item(overrides: Partial<ChannelUpdateItem> = {}): ChannelUpdateItem {
  return {
    id: "event-1",
    title: "DeepSeek API pricing update",
    summary: "DeepSeek updates model API pricing.",
    href: "https://example.com/deepseek",
    source: "Example",
    label: "产品发布",
    context: "生物科技 · 全球",
    date: "2026-08-22",
    dateOriginal: "2026-08-22",
    datePrecision: "exact",
    sortAt: "2026-08-22T00:00:00.000Z",
    keywords: ["产品发布"],
    track: "生物科技",
    region: "全球",
    topicSlugs: ["large-models"],
    topicNames: ["大模型"],
    ...overrides,
  };
}

function finding(): SectorQualityFinding {
  return {
    id: "event-1",
    title: "DeepSeek API pricing update",
    currentTrack: "生物科技",
    category: "high-confidence-misclassification",
    recommendedTracks: ["AI / AGI"],
    evidenceTopics: [],
    compatibleTopics: [],
    incompatibleTopics: ["大模型"],
    currentTrackTitleTerms: [],
    currentTrackSummaryTerms: [],
    currentTrackSourceTerms: [],
    reason: "test",
  };
}

function assignment(mode: "replace" | "augment" = "replace"): CanonicalSectorAssignmentRecord {
  return {
    id: "event-1",
    expectedObservedTrack: "生物科技",
    canonicalTracks: ["AI / AGI"],
    mode,
    reviewedAt: "2026-08-22",
    reason: "人工复核确认该事件属于 AI / AGI，而非生物科技。",
    evidence: ["标题与摘要均为 DeepSeek 模型 API 事件。"],
  };
}

function resolution(record: CanonicalSectorAssignmentRecord): CanonicalSectorResolution {
  return {
    assignment: record,
    observedTrack: "生物科技",
    canonicalTracks:
      record.mode === "augment" ? ["生物科技", "AI / AGI"] : ["AI / AGI"],
    applied: true,
  };
}

test("confirmed replace assignment overrides the analysis track without mutating the observed track", () => {
  const source = item();
  const entry = analysisEligibilityForFinding(source, finding(), resolution(assignment("replace")));

  assert.equal(entry.status, "canonical-corrected");
  assert.equal(entry.sectorWeight, 1);
  assert.equal(entry.topicWeight, 1);
  assert.deepEqual(entry.analysisTracks, ["AI / AGI"]);
  assert.equal(entry.observedTrack, "生物科技");
  assert.equal(entry.item.track, "生物科技");
  assert.equal(entry.canonicalAssignment?.mode, "replace");
});

test("confirmed augment assignment retains provenance track and adds the reviewed adjacent track", () => {
  const entry = analysisEligibilityForFinding(
    item(),
    finding(),
    resolution(assignment("augment")),
  );

  assert.equal(entry.status, "canonical-corrected");
  assert.deepEqual(entry.analysisTracks, ["生物科技", "AI / AGI"]);
  assert.equal(entry.sectorWeight, 1);
});

test("an unapplied registry entry cannot bypass the high-confidence exclusion gate", () => {
  const record = assignment("replace");
  const entry = analysisEligibilityForFinding(item(), finding(), {
    assignment: record,
    observedTrack: "生物科技",
    canonicalTracks: ["生物科技"],
    applied: false,
  });

  assert.equal(entry.status, "sector-excluded");
  assert.equal(entry.sectorWeight, 0);
  assert.deepEqual(entry.analysisTracks, []);
});
