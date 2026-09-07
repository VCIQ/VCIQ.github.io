import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  buildResearchContextUrl,
  buildResearchInvestigationHref,
  buildResearchWorkspaceLaunchUrl,
  buildResearchWorkspacePrompt,
} from "../lib/research-workspace-handoff";

async function source(path: string) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

const handoff = {
  eventId: "event:hbm/123",
  title: "HBM4 supply update",
  url: "https://example.com/story",
  summary: "A supplier changed its HBM4 production plan.",
  sector: "HBM",
  company: "Example Memory",
  people: ["Jane Doe"],
  companies: ["Example GPU"],
  relatedSources: [
    {
      name: "Official filing",
      url: "https://example.com/filing",
      level: "官方披露",
      title: "Capacity filing",
    },
  ],
  importance: 93,
  publishedAt: "2026-09-07T01:00:00Z",
  sourceName: "Example News",
  sourceLevel: "媒体报道",
  matchedTrackingTerms: ["HBM4"],
  curated: true,
  sectorFollowed: true,
  savedForLater: true,
};

test("research investigation links carry only the event identity", () => {
  assert.equal(
    buildResearchInvestigationHref(handoff.eventId),
    "/research-agent/investigate/?event=event%3Ahbm%2F123",
  );
  assert.equal(
    buildResearchContextUrl(handoff.eventId),
    "https://vciq.github.io/research-agent/investigate/?event=event%3Ahbm%2F123",
  );
});

test("workspace launch URL carries a bounded public context contract", () => {
  const value = buildResearchWorkspaceLaunchUrl(
    "https://research.example.com/app?existing=1",
    handoff.eventId,
  );
  const url = new URL(value);
  assert.equal(url.origin, "https://research.example.com");
  assert.equal(url.searchParams.get("existing"), "1");
  assert.equal(url.searchParams.get("vciq_handoff"), "1");
  assert.equal(url.searchParams.get("vciq_event"), handoff.eventId);
  assert.match(url.searchParams.get("vciq_context") ?? "", /research-agent\/investigate/u);
  assert.equal(url.searchParams.get("vciq_articles"), "https://vciq.github.io/data/articles.json");
  assert.equal(url.searchParams.get("vciq_ranked"), "https://vciq.github.io/data/ranked-intelligence.json");
  assert.equal(url.searchParams.has("summary"), false);
});

test("research prompt preserves evidence boundaries and the current event context", () => {
  const prompt = buildResearchWorkspacePrompt(handoff);
  assert.match(prompt, /区分【事实】【推断】【待验证】/u);
  assert.match(prompt, /HBM4 supply update/u);
  assert.match(prompt, /Example Memory/u);
  assert.match(prompt, /Jane Doe/u);
  assert.match(prompt, /已显式关注赛道「HBM」/u);
  assert.match(prompt, /已加入稍后读/u);
  assert.match(prompt, /命中追踪词「HBM4」/u);
  assert.match(prompt, /Capacity filing/u);
  assert.match(prompt, /过去 30 天 \/ 90 天/u);
  assert.match(prompt, /bull case、bear case/u);
});

test("contextual research page resolves public data and does not fabricate a workspace when unconfigured", async () => {
  const client = await source("app/research-agent/investigate/research-investigation-client.tsx");
  assert.match(client, /fetch\("\/data\/articles\.json"/u);
  assert.match(client, /fetch\("\/data\/ranked-intelligence\.json"/u);
  assert.match(client, /buildResearchWorkspaceLaunchUrl/u);
  assert.match(client, /Research Workspace 尚未发布/u);
  assert.match(client, /复制上下文并进入工作台/u);
});
