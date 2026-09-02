import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const workflowUrl = new URL(
  "../.github/workflows/company-candidate-onboarding.yml",
  import.meta.url,
);

async function workflow() {
  return readFile(workflowUrl, "utf8");
}

test("terminal publication survives an isolated onboarding failure without weakening onboarding", async () => {
  const text = await workflow();

  assert.match(text, /terminal-publication-fallback:/);
  assert.match(text, /needs:\s*onboard/);
  assert.match(
    text,
    /needs\.onboard\.result == 'failure'[\s\S]*inputs\.post_onboarding_handoff == 'publish-with-research'/,
  );
  assert.match(
    text,
    /gh workflow run pages\.yml --ref main[\s\S]*-f run_research_after_deploy=true/,
  );

  const fallbackStart = text.indexOf("terminal-publication-fallback:");
  assert.ok(fallbackStart >= 0, "terminal fallback job must exist");
  const fallback = text.slice(fallbackStart);
  assert.doesNotMatch(fallback, /frequent-intelligence-refresh\.yml/);
  assert.doesNotMatch(fallback, /onboard_company_candidates\.py/);
  assert.match(
    text,
    /python tools\/onboard_company_candidates\.py[\s\S]*--report \"\$ONBOARDING_STATE\"/,
    "candidate onboarding remains authoritative and fail-closed",
  );
});

test("non-terminal onboarding failures do not trigger the Pages fallback", async () => {
  const text = await workflow();
  const fallbackStart = text.indexOf("terminal-publication-fallback:");
  const fallback = text.slice(fallbackStart);

  assert.match(fallback, /inputs\.post_onboarding_handoff == 'publish-with-research'/);
  assert.doesNotMatch(fallback, /post_onboarding_handoff == 'refresh'/);
  assert.doesNotMatch(fallback, /post_onboarding_handoff == 'none'/);
});
