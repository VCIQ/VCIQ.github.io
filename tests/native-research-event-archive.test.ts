import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import archive from "../config/native_research_event_archives.json";
import { archivedResearchEvent } from "../lib/native-research-event-archive";

const eventId = "official-xtalpi-451071ace85fb99c";

test("historical research uses the exact retained event with traceable source", () => {
  const event = archivedResearchEvent(eventId);
  assert.equal(event?.id, eventId);
  assert.match(event?.title ?? "", /超衍智能/);
  assert.equal(event?.publishedAt, "2026-09-16");
  assert.equal(event?.archiveProvenance?.sourceCommit, "5e5a3ab9e6bc3ac8a61c507f375df70ceb9e669e");
  assert.equal(archivedResearchEvent("official-xtalpi-unrelated"), null);
});

test("archive identity and provenance are mandatory, not a same-company fallback", () => {
  const changed = structuredClone(archive);
  changed.records[0].event.id = "another-xtalpi-event";
  assert.equal(archivedResearchEvent(eventId, changed), null);
  changed.records[0].event.id = eventId;
  changed.records[0].sourceCommit = "not-a-commit";
  assert.equal(archivedResearchEvent(eventId, changed), null);
});

test("rejected historical material is never eligible", () => {
  const original = archive.records[0];
  const value = { schemaVersion: 1, records: [{ ...original, event: { ...original.event, qualityStatus: "rejected" } }] };
  assert.equal(archivedResearchEvent(eventId, value), null);
});

test("investigate keeps the current event first and discloses archive scope", async () => {
  const source = await readFile(new URL("../app/research-agent/investigate/research-investigation-client.tsx", import.meta.url), "utf8");
  assert.ok(source.indexOf("if (canonicalEvent)") < source.indexOf("const archived = archivedResearchEvent(eventId)"));
  assert.match(source, /历史事件研究 · 不在当前滚动资讯窗口/);
  assert.match(source, /历史公开快照，未重新核验/);
  assert.match(source, /archiveProvenance.sourceCommit/);
});
