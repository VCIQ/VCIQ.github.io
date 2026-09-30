import assert from "node:assert/strict";
import test from "node:test";
import policy from "../config/priority_source_policy.json";
import { parsePriorityIntelligence, PRIORITY_FEED_SOURCE_HOSTS } from "../lib/priority-intelligence";

test("producer and reader share precisely the eight approved publishers", () => {
  assert.equal(policy.sources.length, 8);
  assert.equal(policy.autoPromoteCore, false);
  assert.equal(Object.keys(PRIORITY_FEED_SOURCE_HOSTS).length, 8);
  const value = { schemaVersion: 1, policyVersion: "priority-publisher-v1", generatedAt: "2026-09-30T01:00:00Z",
    contentHash: "a".repeat(64), sourceState: "healthy", items: policy.sources.map((s) => ({
      id: s.id + "-example", sourceId: s.id, title: "AI launch", summary: "Public source statement",
      type: "产品发布", region: "全球", sector: "AI / AGI", company: "", importance: 85,
      publishedAt: "2026-09-29", source: { name: s.id, url: `https://${s.articleHost}/news/test`, level: s.level },
    })) };
  const read = parsePriorityIntelligence(value, Date.parse("2026-09-30T02:00:00Z"));
  assert.equal(read.items.length, 8);
  const media = value.items.find((x) => x.sourceId === "leiphone")!;
  media.source.level = "官方披露";
  assert.throws(() => parsePriorityIntelligence(value, Date.parse("2026-09-30T02:00:00Z")));
});
