import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ledger from "../public/data/research_event_ledger.json";
import {
  parseResearchLedgerEvent,
  RESEARCH_EVENT_LEDGER_PATH,
} from "../lib/research-event-ledger";

const rankedId = "ranked-intelligence:intel-event-35084a5f95caa665";

test("Research Event Ledger restores exact ranked homepage IDs", () => {
  const result = parseResearchLedgerEvent(ledger, rankedId);
  assert.equal(result?.id, rankedId);
  assert.match(result?.title ?? "", /数据中心/);
  assert.equal(result?.researchLedgerProvenance.sourceDataset, "public/data/ranked-intelligence.json");
  assert.match(result?.researchLedgerProvenance.sourceCommit ?? "", /^[a-f0-9]{40}$/);
  assert.equal(RESEARCH_EVENT_LEDGER_PATH, "/data/research_event_ledger.json");
});

test("Research Event Ledger never substitutes another event ID", () => {
  assert.equal(parseResearchLedgerEvent(ledger, "ranked-intelligence:not-this-event"), null);
});

test("rejected records fail closed", () => {
  const clone = structuredClone(ledger) as unknown as { events: Record<string, { status: string }> };
  clone.events[rankedId].status = "rejected";
  assert.equal(parseResearchLedgerEvent(clone, rankedId), null);
});

test("investigate lookup order is current snapshot, ledger, explicit archive", async () => {
  const source = await readFile(
    new URL("../app/research-agent/investigate/research-investigation-client.tsx", import.meta.url),
    "utf8",
  );
  const current = source.indexOf("if (canonicalEvent)");
  const retained = source.indexOf("await loadResearchLedgerEvent(eventId)");
  const archive = source.indexOf("archivedResearchEvent(eventId)");
  assert.ok(current >= 0 && retained > current && archive > retained);
  assert.match(source, /Research Event Ledger · 历史事件研究/u);
  assert.match(source, /exact event ID 保留 180 天/u);
});
