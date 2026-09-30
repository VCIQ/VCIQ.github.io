import assert from "node:assert/strict";
import test from "node:test";
import { parseBatch6Priority } from "../lib/batch6-priority-candidates";

const now = Date.parse("2026-09-30T03:00:00Z");
const base = {
  schemaVersion: 1,
  policyVersion: "batch6-priority-v1",
  generatedAt: "2026-09-30T02:59:00Z",
  contentHash: "a".repeat(64),
  sourceState: "healthy",
  items: [{
    id: "batch6-rss-0123456789abcdef01234567",
    sourceId: "batch6-google-alerts",
    title: "硬科技企业完成Pre-IPO融资",
    summary: "公司披露新一轮融资进展。",
    publishedAt: "2026-09-30T02:00:00Z",
    type: "融资",
    region: "全球",
    sector: "科创资本",
    company: "",
    importance: 92,
    firstSeenAt: "2026-09-30T02:30:00Z",
    source: { name: "证券时报", url: "https://www.stcn.com/article/detail/example.html",
      level: "待交叉验证", platform: "Google Alerts RSS" },
  }],
} as const;

test("Batch-6 browser contract accepts bounded public discovery evidence", () => {
  const result = parseBatch6Priority(base, now);
  assert.equal(result.items.length, 1);
  assert.equal(result.items[0].source.name, "证券时报");
  assert.equal(result.items[0].qualityStatus, undefined);
});

test("Batch-6 browser contract rejects private URLs and forged evidence roles", () => {
  const privateUrl = { ...base, items: [{ ...base.items[0],
    source: { ...base.items[0].source, url: "https://127.0.0.1/private" } }] };
  assert.throws(() => parseBatch6Priority(privateUrl, now));
  const forged = { ...base, items: [{ ...base.items[0],
    source: { ...base.items[0].source, level: "官方披露" } }] };
  assert.throws(() => parseBatch6Priority(forged, now));
});
