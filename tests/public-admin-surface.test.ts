import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const ROOT = path.resolve(import.meta.dirname, "..");
const PUBLIC_SOURCE_ROOTS = ["app", "components"].map((segment) => path.join(ROOT, segment));
const LEGACY_ADMIN_FILES = [
  "components/tracking-company-onboarding.tsx",
  "components/tracking-company-onboarding.module.css",
  "components/channel-document-import.tsx",
  "components/channel-document-import.module.css",
  "components/user-tracking-loader.tsx",
  "components/user-tracking-panel.tsx",
  "components/user-tracking-panel.module.css",
  "components/tracking-admin-session-guard.tsx",
  "components/tracking-admin-conflict-guard.tsx",
  "components/tracking-company-candidate-review.tsx",
  "components/tracking-company-candidate-review.module.css",
  "components/tracking-entity-resolution-review.tsx",
  "components/tracking-entity-resolution-review.module.css",
  "components/tracking-capture-inbox.tsx",
  "components/tracking-capture-inbox.module.css",
  "components/tracking-people-scope-enhancer.tsx",
  "components/tracking-admin-module-recommendations.tsx",
  "components/tracking-admin-recommendation.tsx",
  "components/tracking-recommendations-bridge.tsx",
  "components/tracking-recommendations.tsx",
  "components/tracking-recommendations.module.css",
  "components/intelligence-tracking-capture-controls.tsx",
  "components/intelligence-tracking-capture-controls.module.css",
  "components/external-tracking-capture-page.tsx",
  "components/external-tracking-capture-page.module.css",
];

function sourceFiles(root: string): string[] {
  if (!existsSync(root)) return [];
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = path.join(root, entry.name);
    if (entry.isDirectory()) return sourceFiles(fullPath);
    if (!entry.isFile() || !/\.(?:ts|tsx)$/u.test(entry.name)) return [];
    return [fullPath];
  });
}

test("legacy browser-based repository admin clients stay removed", () => {
  for (const relativePath of LEGACY_ADMIN_FILES) {
    assert.equal(
      existsSync(path.join(ROOT, relativePath)),
      false,
      `${relativePath} must not return to the public source tree`,
    );
  }
});

test("public app and component sources do not bundle private review state or a GitHub write client", () => {
  const forbidden = [
    '@/config/company_candidate_decisions.json',
    '@/config/company_candidate_review_queue.json',
    '@/config/company_candidate_onboarding_state.json',
    '@/config/entity_resolution_decisions.json',
    '@/config/tracking_capture_inbox.json',
    '@/lib/tracking-capture-github',
    'TRACKING_ADMIN_TOKEN_SESSION_KEY',
    'no1lize:tracking-admin-token',
    'Authorization: `Bearer ${token}`',
  ];

  for (const filePath of PUBLIC_SOURCE_ROOTS.flatMap(sourceFiles)) {
    const text = readFileSync(filePath, "utf8");
    for (const marker of forbidden) {
      assert.equal(
        text.includes(marker),
        false,
        `${path.relative(ROOT, filePath)} contains forbidden public admin marker ${marker}`,
      );
    }
  }
});
