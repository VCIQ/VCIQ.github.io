import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../components/site-header.tsx", import.meta.url), "utf8");

test("settings gear opens the protected tracking admin directly", () => {
  assert.match(source, /const TRACKING_ADMIN_URL = "https:\/\/vciq-tracking-console\.pages\.dev\/";/);
  assert.match(source, /<a className="icon-button" href=\{TRACKING_ADMIN_URL\} aria-label="追踪管理台" title="追踪管理台">/);
  assert.doesNotMatch(source, /href="\/tracking"[^>]*>\s*<Settings/);
});
