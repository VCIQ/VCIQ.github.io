import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

import { assertNoNewCompoundTrackingEntities } from "../lib/tracking-entity-integrity";
import {
  TRACKING_CONFIG_PATH,
  type UserTrackingConfig,
} from "../lib/user-tracking";

function argumentValue(name: string, fallback: string): string {
  const index = process.argv.indexOf(name);
  if (index < 0) return fallback;
  const value = process.argv[index + 1]?.trim();
  if (!value) throw new Error(`${name} 需要一个非空参数。`);
  return value;
}

function parseRawTrackingConfig(text: string, label: string): UserTrackingConfig {
  const parsed = JSON.parse(text) as Partial<UserTrackingConfig>;
  if (!Array.isArray(parsed.tracks)) {
    throw new Error(`${label} tracking config 缺少 tracks 数组。`);
  }
  for (const track of parsed.tracks) {
    if (
      !track ||
      typeof track.slug !== "string" ||
      typeof track.name !== "string" ||
      !Array.isArray(track.people) ||
      !Array.isArray(track.sampleCompanies)
    ) {
      throw new Error(`${label} tracking config 包含无法审计的 track 结构。`);
    }
  }
  return parsed as UserTrackingConfig;
}

const baseRef = argumentValue("--base-ref", "HEAD");
const previousText = execFileSync(
  "git",
  ["show", `${baseRef}:${TRACKING_CONFIG_PATH}`],
  { encoding: "utf8" },
);
const nextText = readFileSync(TRACKING_CONFIG_PATH, "utf8");

// Integrity checks must inspect the repository's raw arrays. Do not call
// normalizeTrackingConfig() here: its runtime caps intentionally truncate
// people/company lists and can hide compound values beyond those caps.
const previous = parseRawTrackingConfig(previousText, baseRef);
const next = parseRawTrackingConfig(nextText, "working tree");
assertNoNewCompoundTrackingEntities(previous, next);

console.log(
  `Tracking entity delta valid: ${baseRef} -> working tree introduces no compound people/companies.`,
);
