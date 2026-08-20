import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

import { assertNoNewCompoundTrackingEntities } from "../lib/tracking-entity-integrity";
import {
  TRACKING_CONFIG_PATH,
  normalizeTrackingConfig,
} from "../lib/user-tracking";

function argumentValue(name: string, fallback: string): string {
  const index = process.argv.indexOf(name);
  if (index < 0) return fallback;
  const value = process.argv[index + 1]?.trim();
  if (!value) throw new Error(`${name} 需要一个非空参数。`);
  return value;
}

const baseRef = argumentValue("--base-ref", "HEAD");
const previousText = execFileSync(
  "git",
  ["show", `${baseRef}:${TRACKING_CONFIG_PATH}`],
  { encoding: "utf8" },
);
const nextText = readFileSync(TRACKING_CONFIG_PATH, "utf8");

const previous = normalizeTrackingConfig(JSON.parse(previousText));
const next = normalizeTrackingConfig(JSON.parse(nextText));
assertNoNewCompoundTrackingEntities(previous, next);

console.log(
  `Tracking entity delta valid: ${baseRef} -> working tree introduces no compound people/companies.`,
);
