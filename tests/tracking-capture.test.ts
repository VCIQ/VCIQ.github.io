import assert from "node:assert/strict";
import test from "node:test";

import {
  applyTrackingCapture,
  normalizeTrackingCaptureInbox,
  trackingCaptureId,
  type TrackingCaptureSource,
} from "../lib/tracking-capture";
import type { UserTrackingConfig } from "../lib/user-tracking";

const source: TrackingCaptureSource = {
  articleId: "article-polymarket",
  title: "预测市场平台 Polymarket 洽谈新一轮融资",
  url: "https://finance.example/polymarket",
  summary: "合成测试摘要：Polymarket 与 OpenAI 分别作为公司实体出现。",
  sourceName: "财经媒体",
  channel: "institutions",
  channelLabel: "投资机构",
  eventType: "融资",
};

function config(): UserTrackingConfig {
  return {
    schemaVersion: 1,
    tracks: [
      {
        slug: "ai-agi",
        name: "AI / AGI",
        enabled: true,
        custom: false,
        keywords: [],
        people: [],
        sampleCompanies: [],
      },
    ],
    listedCompanies: [],
    sources: [],
  };
}

test("article capture applies companies, people and topics to selected tracks", () => {
  const result = applyTrackingCapture({
    config: config(),
    inbox: normalizeTrackingCaptureInbox({}),
    entities: [
      { entityType: "company", name: "Polymarket 公司" },
      { entityType: "company", name: "OpenAI" },
      { entityType: "person", name: "Shayne Coplan" },
      { entityType: "topic", name: "预测市场" },
    ],
    selectedTrackSlugs: ["ai-agi"],
    newTrackName: "预测市场",
    source,
    capturedAt: "2026-08-05T04:00:00Z",
    capturedBy: "VCIQ",
    reasons: ["商业模式创新", "监管变化"],
    note: "重点观察牌照、融资和市场竞争。",
  });

  const predictionTrack = result.config.tracks.find((track) => track.name === "预测市场");
  assert.ok(predictionTrack);
  assert.deepEqual(predictionTrack.sampleCompanies, ["Polymarket", "OpenAI"]);
  assert.deepEqual(predictionTrack.people, ["Shayne Coplan"]);
  assert.deepEqual(predictionTrack.keywords, ["预测市场"]);
  assert.equal(result.records.length, 4);
  assert.equal(result.inbox.records.length, 4);
  assert.equal(result.records[0].capturedBy, "VCIQ");
  assert.equal(result.records[0].source.url, source.url);
  assert.equal(result.records[0].status, "applied");
  assert.deepEqual(result.records[0].reasons, ["商业模式创新", "监管变化"]);
  assert.equal(result.records[0].note, "重点观察牌照、融资和市场竞争。");
});

test("repeated capture is deduplicated in config and audit inbox", () => {
  const first = applyTrackingCapture({
    config: config(),
    inbox: normalizeTrackingCaptureInbox({}),
    entities: [{ entityType: "company", name: "Polymarket" }],
    selectedTrackSlugs: ["ai-agi"],
    source,
    capturedAt: "2026-08-05T04:00:00Z",
    capturedBy: "VCIQ",
  });
  const second = applyTrackingCapture({
    config: first.config,
    inbox: first.inbox,
    entities: [{ entityType: "company", name: "Polymarket" }],
    selectedTrackSlugs: ["ai-agi"],
    source,
    capturedAt: "2026-08-05T05:00:00Z",
    capturedBy: "VCIQ",
  });

  assert.deepEqual(second.config.tracks[0].sampleCompanies, ["Polymarket"]);
  assert.equal(second.addedCount, 0);
  assert.equal(second.duplicateCount, 1);
  assert.equal(second.inbox.records.length, 1);
  assert.equal(second.inbox.records[0].capturedAt, "2026-08-05T05:00:00Z");
});

test("capture identity is stable across track ordering", () => {
  const left = trackingCaptureId({
    entityType: "company",
    canonicalName: "Polymarket",
    sourceUrl: source.url,
    trackSlugs: ["prediction-market", "ai-agi"],
  });
  const right = trackingCaptureId({
    entityType: "company",
    canonicalName: "Polymarket",
    sourceUrl: source.url,
    trackSlugs: ["ai-agi", "prediction-market"],
  });
  assert.equal(left, right);
});

test("capture requires a target track and rejects generic topic keywords", () => {
  assert.throws(
    () =>
      applyTrackingCapture({
        config: config(),
        inbox: normalizeTrackingCaptureInbox({}),
        entities: [{ entityType: "topic", name: "技术" }],
        selectedTrackSlugs: [],
        source,
        capturedAt: "2026-08-05T04:00:00Z",
        capturedBy: "VCIQ",
      }),
    /目标赛道/,
  );
});

test("legacy inbox records receive empty research intent fields", () => {
  const inbox = normalizeTrackingCaptureInbox({
    records: [
      {
        id: "legacy",
        entityType: "company",
        canonicalName: "Polymarket",
        trackSlugs: ["ai-agi"],
        source,
        capturedAt: "2026-08-05T04:00:00Z",
        status: "applied",
      },
    ],
  });
  assert.deepEqual(inbox.records[0].reasons, []);
  assert.equal(inbox.records[0].note, "");
});

test("company suffix normalization cannot create an empty entity", () => {
  assert.throws(
    () =>
      applyTrackingCapture({
        config: config(),
        inbox: normalizeTrackingCaptureInbox({}),
        entities: [{ entityType: "company", name: "公司" }],
        selectedTrackSlugs: ["ai-agi"],
        source,
        capturedAt: "2026-08-05T04:00:00Z",
        capturedBy: "VCIQ",
      }),
    /公司名称至少需要两个有效字符/,
  );
});
