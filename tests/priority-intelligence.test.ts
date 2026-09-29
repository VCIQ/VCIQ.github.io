import assert from "node:assert/strict";
import test from "node:test";
import { parsePriorityIntelligence, mergePriorityCandidates } from "../lib/priority-intelligence";

const now = Date.parse("2026-09-29T12:00:00Z");
const fixture = () => ({ schemaVersion: 1, policyVersion: "priority-publisher-v1", generatedAt: "2026-09-29T10:00:00Z", contentHash: "a".repeat(64), sourceState: "healthy", items: [{ id: "amd-newsroom-a1", sourceId: "amd-newsroom", title: "AMD acquisition agreement", summary: "Closing remains subject to approval.", publishedAt: "2026-09-28", type: "并购", region: "美国", sector: "半导体", company: "AMD", importance: 90, source: { name: "AMD Newsroom", url: "https://newsroom.amd.com/news/example", level: "官方披露", platform: "官方网站" } }] });
test("priority feed projects only public whitelisted event fields", () => {
  const raw = fixture(); Object.assign(raw.items[0], { preferences: "private", reasons: ["private"] });
  const parsed = parsePriorityIntelligence(raw, now);
  assert.equal(parsed.items.length, 1); assert.doesNotMatch(JSON.stringify(parsed), /private|preferences|reasons/u);
});
test("priority feed rejects unknown publishers, private URLs and false evidence roles", () => {
  for (const url of ["http://127.0.0.1/", "https://newsroom.amd.com.evil.test/", "javascript:alert(1)", "https://user:password@newsroom.amd.com/"]) {
    const raw = fixture(); raw.items[0].source.url = url; assert.throws(() => parsePriorityIntelligence(raw, now));
  }
  const raw = fixture(); raw.items[0].source.level = "媒体报道"; assert.throws(() => parsePriorityIntelligence(raw, now));
});
test("priority data never overwrites reviewed canonical material", () => {
  const items = parsePriorityIntelligence(fixture(), now).items;
  const canonical = { ...items[0], id: "existing", title: "Reviewed title", curated: true };
  assert.deepEqual(mergePriorityCandidates([canonical], items), [canonical]);
});
test("priority contract rejects replayed future clocks, duplicate IDs and oversized arrays", () => {
  let raw = fixture(); raw.generatedAt = "2030-01-01"; assert.throws(() => parsePriorityIntelligence(raw, now));
  raw = fixture(); raw.items.push(raw.items[0]); assert.throws(() => parsePriorityIntelligence(raw, now));
  raw = fixture(); raw.items = Array(73).fill(raw.items[0]); assert.throws(() => parsePriorityIntelligence(raw, now));
});
