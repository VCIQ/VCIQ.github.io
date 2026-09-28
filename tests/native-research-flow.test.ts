import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { parseNativeResearchReports, researchLaunchUrl, researchResultHref, RESEARCH_SECTIONS, safeResearchUrl, validResearchEventId } from "../lib/native-research-contract";
import { buildNativeResearchWorkflowCommand } from "../lib/research-workspace-handoff";

const requestId = "00000000-0000-4000-8000-000000000001";
const nonce = "00000000-0000-4000-8000-000000000002";
const eventId = "official-xtalpi-test";
const source = (path: string) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

function fixture() {
  return { schemaVersion: 2, results: [{
    schemaVersion: 2, eventId, requestId, title: "Event report", sector: "生物科技", sourceUrl: "https://example.com/event",
    status: "completed-draft", modelUsed: true, reviewStatus: "automated_unreviewed", requestedAt: "2026-09-27T00:00:00Z", completedAt: "2026-09-27T00:01:00Z",
    evidence: [{ id: "N001", url: "https://example.com/event", excerpt: "Source statement", title: "Primary material" }],
    analysis: { executiveSummary: { text: "Event-specific summary", kind: "inference", evidenceIds: ["N001"] }, sections: Object.fromEntries(Object.keys(RESEARCH_SECTIONS).map((key) => [key, [{ text: "Statement within the evidence scope", kind: key === "facts" ? "source_statement" : "unknown", evidenceIds: ["N001"] }]])) },
  }] };
}

test("normalized ranked-intelligence event IDs remain accepted up to the published ID budget", () => {
  const longRanked = `ranked-intelligence:${"a".repeat(240)}`;
  assert.equal(validResearchEventId(longRanked), true);
  assert.doesNotThrow(() => researchLaunchUrl(longRanked, requestId, nonce));
  assert.equal(validResearchEventId("a".repeat(321)), false);
});

test("research launch carries only event/request identity with a nonce in the fragment", () => {
  const url = new URL(researchLaunchUrl(eventId, requestId, nonce));
  assert.equal(url.origin, "https://vciq-tracking-console.pages.dev");
  assert.deepEqual([...url.searchParams.keys()].sort(), ["event", "request"]);
  assert.equal(url.searchParams.get("event"), eventId);
  assert.equal(new URLSearchParams(url.hash.slice(1)).get("nonce"), nonce);
  assert.throws(() => researchLaunchUrl("x;$(curl injected)", requestId, nonce));
  assert.equal(new URL(researchResultHref(eventId, requestId, 12), "https://vciq.github.io").searchParams.get("request"), requestId);
});

test("manual export commands cannot interpolate shell metacharacters", () => {
  assert.match(buildNativeResearchWorkflowCommand(eventId, requestId), /native-event-research\.yml/);
  assert.match(buildNativeResearchWorkflowCommand(eventId, requestId), /request_id=/);
  assert.doesNotMatch(buildNativeResearchWorkflowCommand("$(touch injected)", requestId), /gh workflow/);
  assert.equal(safeResearchUrl("javascript:alert(1)"), "");
  assert.equal(safeResearchUrl("https://user:secret@example.com"), "");
});

test("report reader accepts real draft contracts but rejects arbitrary summaries and foreign evidence", () => {
  assert.equal(parseNativeResearchReports(fixture())[0].status, "completed-draft");
  const badId = fixture();
  badId.results[0].analysis.executiveSummary.evidenceIds = ["FAKE"];
  assert.throws(() => parseNativeResearchReports(badId));
  const badFacts = fixture();
  badFacts.results[0].analysis.sections.facts[0].kind = "verified_fact";
  assert.throws(() => parseNativeResearchReports(badFacts));
  const selfApproval = fixture();
  selfApproval.results[0].reviewStatus = "approved";
  assert.throws(() => parseNativeResearchReports(selfApproval));
  assert.throws(() => parseNativeResearchReports({ schemaVersion: 1, results: [] }));
});

test("submitted request identity cannot select a different event attempt", () => {
  const reports = parseNativeResearchReports(fixture());
  assert.equal(reports.find((row) => row.eventId === eventId && row.requestId === nonce), undefined);
});

test("investigate uses protected automatic submission rather than opening Actions alone", async () => {
  const client = await source("app/research-agent/investigate/research-investigation-client.tsx");
  const submit = await source("app/research-agent/investigate/native-research-submission.tsx");
  assert.match(client, /NativeResearchSubmission/);
  assert.match(client, /静态站不保存 GitHub 写凭据/);
  assert.match(client, /导出研究包/);
  assert.match(client, /查看研究结果/);
  assert.doesNotMatch(submit, /GITHUB_WORKFLOW_TOKEN|clipboard/);
  assert.match(submit, /event\.origin !== NATIVE_RESEARCH_ADMIN_ORIGIN/);
  assert.match(submit, /event\.source !== popup/);
  assert.match(submit, /body\.nonce === nonce/);
});

test("event workflow has its own writer and quality gate rather than relabeling daily output", async () => {
  const workflow = await source(".github/workflows/native-event-research.yml");
  assert.match(workflow, /request_id:/);
  assert.match(workflow, /native_event_research_workflow\.py/);
  assert.match(workflow, /validate_native_research_reports\.py/);
  assert.match(workflow, /run_pipeline\.py finalize native-event-research/);
  assert.match(workflow, /gh workflow run pages\.yml --ref main/);
  assert.doesNotMatch(workflow, /git push.*--force|git rebase/);
  const result = await source("app/research-agent/investigate/result/native-research-result-client.tsx");
  assert.match(result, /row\.requestId === requestId/);
  assert.match(result, /不会用通用日报替代/);
});

test("native reports have an independent channel section and artifact ownership", async () => {
  const panel = await source("app/research-agent/native-research-reports-panel.tsx");
  const registry = JSON.parse(await source("config/automation_jobs.json"));
  assert.match(panel, /专题深研报告/);
  assert.match(panel, /completed-draft/);
  const job = registry.jobs.find((row: { id: string }) => row.id === "native-event-research");
  assert.ok(job.outputs.some((row: { path: string }) => row.path === "public/data/native_research_reports.json"));
});
