import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function source(path: string) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("investigate page exposes a QM-independent native research flow", async () => {
  const client = await source("app/research-agent/investigate/research-investigation-client.tsx");
  assert.match(client, /VCIQ Native Research Flow/u);
  assert.match(client, /提交深研/u);
  assert.match(client, /导出研究包/u);
  assert.match(client, /查看研究结果/u);
  assert.match(client, /静态站不保存 GitHub 写凭据/u);
  assert.match(client, /NATIVE_RESEARCH_WORKFLOW_URL/u);
  assert.match(client, /buildNativeResearchMarkdown/u);
  assert.match(client, /buildNativeResearchResultHref/u);
});

test("native handoff creates markdown, result URLs and an operator workflow command", async () => {
  const handoff = await source("lib/research-workspace-handoff.ts");
  assert.match(handoff, /buildNativeResearchMarkdown/u);
  assert.match(handoff, /buildNativeResearchResultHref/u);
  assert.match(handoff, /buildNativeResearchWorkflowCommand/u);
  assert.match(handoff, /research-agent-v1\.yml/u);
  assert.match(handoff, /-f event_id=/u);
});

test("Research Agent workflow accepts an optional event-specific request without changing scheduled runs", async () => {
  const workflow = await source(".github/workflows/research-agent-v1.yml");
  const runtime = await source("tools/research_agent_runtime.py");
  assert.match(workflow, /event_id:/u);
  assert.match(workflow, /build-native-research-request\.ts/u);
  assert.match(workflow, /RESEARCH_AGENT_NATIVE_REQUEST_PATH/u);
  assert.match(workflow, /build-native-research-result\.ts/u);
  assert.match(runtime, /nativeResearchRequest/u);
  assert.match(runtime, /研究任务上下文，不是已验证证据/u);
});

test("native result publication refuses to substitute the generic daily brief", async () => {
  const builder = await source("scripts/build-native-research-result.ts");
  const resultClient = await source("app/research-agent/investigate/result/native-research-result-client.tsx");
  assert.match(builder, /no-event-specific-evidence/u);
  assert.match(builder, /不把通用日报冒充为专属研究结果/u);
  assert.match(resultClient, /NO EVENT-SPECIFIC EVIDENCE/u);
  assert.match(resultClient, /不会用通用日报替代/u);
  assert.match(resultClient, /native_research_results\.json/u);
});

test("native result artifact is registered as a public Research Agent output", async () => {
  const registry = JSON.parse(await source("config/automation_jobs.json"));
  const job = registry.jobs.find((row: { id: string }) => row.id === "research-agent-daily");
  assert.ok(job);
  const output = job.outputs.find((row: { path: string }) => row.path === "public/data/native_research_results.json");
  assert.ok(output);
  assert.equal(output.public, true);
  assert.equal(output.required, false);
});
