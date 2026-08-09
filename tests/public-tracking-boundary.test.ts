import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");
const read = (relativePath: string) =>
  fs.readFileSync(path.join(root, relativePath), "utf8");

test("public tracking landing is build-based and contains no admin loader", () => {
  const source = read("app/tracking/page.tsx");
  assert.match(source, /coreResearchObjectStats/u);
  assert.match(source, /FOUR RESEARCH OBJECTS/u);
  assert.match(source, /PRIVATE REVIEW BOUNDARY/u);
  assert.doesNotMatch(source, /UserTrackingLoader/u);
  assert.doesNotMatch(source, /fetch\s*\(/u);
  assert.doesNotMatch(source, /tracking-capture-inbox-github/u);
});

test("public source tree has no tracking capture route or browser admin stack", () => {
  const retired = [
    "app/tracking/capture/page.tsx",
    "components/user-tracking-loader.tsx",
    "components/user-tracking-panel.tsx",
    "components/tracking-admin-session-guard.tsx",
    "components/tracking-admin-conflict-guard.tsx",
    "components/tracking-company-candidate-review.tsx",
    "components/tracking-entity-resolution-review.tsx",
    "components/tracking-capture-inbox.tsx",
    "components/tracking-recommendations-bridge.tsx",
    "components/intelligence-tracking-capture-controls.tsx",
    "components/external-tracking-capture-page.tsx",
  ];
  for (const relativePath of retired) {
    assert.equal(
      fs.existsSync(path.join(root, relativePath)),
      false,
      `${relativePath} must stay outside the public source tree`,
    );
  }
});

test("global public client controls remain read only", () => {
  const source = read("components/site-client-controls.tsx");
  assert.match(source, /IntelligenceFavoriteControls/u);
  assert.match(source, /IntelligenceHotnessControls/u);
  assert.match(source, /WechatShareCompat/u);
  assert.doesNotMatch(source, /IntelligenceTrackingCaptureControls/u);
  assert.doesNotMatch(source, /tracking-capture-github/u);
  assert.doesNotMatch(source, /tracking-admin-token/u);
});

test("public research detail compatibility component contains no write client", () => {
  const source = read("components/tracking-entity-research-editor.tsx");
  assert.doesNotMatch(source, /["']use client["']/u);
  assert.doesNotMatch(source, /GitHub Token/u);
  assert.doesNotMatch(source, /commitTrackingEntityRecordManifest/u);
  assert.doesNotMatch(source, /sessionStorage/u);
  assert.match(source, /return null/u);
});

test("public companies page contains formal profiles only", () => {
  const page = read("app/companies/page.tsx");
  assert.match(page, /CompanyDirectory/u);
  assert.match(page, /CompanyProfileRefreshStatus/u);
  assert.doesNotMatch(page, /CompanyCandidateDirectory/u);
  assert.equal(
    fs.existsSync(path.join(root, "components/company-candidate-directory.tsx")),
    false,
  );
});

test("company review queue is repository-only and not statically bundled", () => {
  assert.equal(
    fs.existsSync(path.join(root, "public/data/company_candidates.json")),
    false,
  );
  assert.equal(
    fs.existsSync(path.join(root, "public/data/company_candidate_onboarding.json")),
    false,
  );
  assert.equal(
    fs.existsSync(path.join(root, "config/company_candidate_review_queue.json")),
    true,
  );
  assert.equal(
    fs.existsSync(path.join(root, "config/company_candidate_onboarding_state.json")),
    true,
  );

  const dataBoundary = read("lib/company-candidate-data.ts");
  assert.doesNotMatch(dataBoundary, /public\/data\/company_candidates\.json/u);
  assert.match(dataBoundary, /candidates:\s*\[\]/u);

  assert.equal(
    fs.existsSync(path.join(root, "components/tracking-company-onboarding.tsx")),
    false,
  );
});

test("public update directories contain no browser-side repository writer", () => {
  assert.equal(
    fs.existsSync(path.join(root, "components/channel-document-import.tsx")),
    false,
  );
  assert.equal(
    fs.existsSync(path.join(root, "components/channel-document-import.module.css")),
    false,
  );

  const directoryClient = read("components/channel-update-directory-client.tsx");
  assert.doesNotMatch(directoryClient, /ChannelDocumentImport/u);
  assert.doesNotMatch(directoryClient, /tracking-admin-token/u);
  assert.doesNotMatch(directoryClient, /onDrop=/u);
  assert.doesNotMatch(directoryClient, /导入文档信源/u);
});

test("tracking snapshot coverage has no environment bypass", () => {
  const validator = read("scripts/validate-tracking-snapshot.mjs");
  assert.doesNotMatch(validator, /ALLOW_INCOMPLETE_TRACKING_COVERAGE/u);
  assert.doesNotMatch(validator, /TRACKING_SNAPSHOT_WARNING/u);
  assert.match(validator, /completedSources < expectedSources/u);
  assert.match(validator, /errors\.push/u);
});

test("Pages build audits the final public artifact and rejects private review files", () => {
  const packageJson = JSON.parse(read("package.json")) as {
    scripts: Record<string, string>;
  };
  assert.equal(
    packageJson.scripts["audit:public-artifact"],
    "node scripts/audit-public-artifact.mjs",
  );
  assert.match(packageJson.scripts["build:pages"], /audit:public-artifact/u);

  const audit = read("scripts/audit-public-artifact.mjs");
  assert.match(audit, /tracking\/capture/u);
  assert.match(audit, /GitHub Token/u);
  assert.match(audit, /totalBytes/u);
  assert.match(audit, /data\/company_candidates\.json/u);
  assert.match(audit, /data\/company_candidate_onboarding\.json/u);
  assert.match(audit, /company_candidate_review_queue\.json/u);
  assert.match(audit, /company_candidate_onboarding_state\.json/u);
});
