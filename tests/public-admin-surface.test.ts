import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const ROOT = path.resolve(import.meta.dirname, "..");
const PUBLIC_SOURCE_ROOTS = ["app", "components"].map((segment) => path.join(ROOT, segment));
const LEGACY_ADMIN_FILES = [
  "components/tracking-company-onboarding.tsx",
  "components/tracking-company-onboarding.module.css",
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

test("legacy browser-based company onboarding admin client stays removed", () => {
  for (const relativePath of LEGACY_ADMIN_FILES) {
    assert.equal(
      existsSync(path.join(ROOT, relativePath)),
      false,
      `${relativePath} must not return to the public source tree`,
    );
  }
});

test("public app and component sources do not bundle private company review state or a GitHub write token client", () => {
  const forbidden = [
    '@/config/company_candidate_decisions.json',
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
