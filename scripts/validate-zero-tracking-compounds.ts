import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { splitCompoundTrackingEntityName } from "../lib/tracking-entity-integrity";

const TRACKING_CONFIG_PATH = "config/user_tracking.json";

type RawTrackingTrack = {
  slug: string;
  name: string;
  people: string[];
  sampleCompanies: string[];
};

type RawTrackingConfig = {
  tracks: RawTrackingTrack[];
};

type CompoundIssue = {
  trackSlug: string;
  trackName: string;
  entityType: "person" | "company";
  value: string;
  parts: string[];
};

function argumentValue(name: string, fallback: string): string {
  const index = process.argv.indexOf(name);
  if (index < 0) return fallback;
  const value = process.argv[index + 1]?.trim();
  if (!value) throw new Error(`${name} 需要一个非空参数。`);
  return value;
}

function parseRawTrackingConfig(text: string): RawTrackingConfig {
  const parsed = JSON.parse(text) as { tracks?: unknown };
  if (!Array.isArray(parsed.tracks)) {
    throw new Error("raw tracking config 缺少 tracks 数组。");
  }

  const tracks: RawTrackingTrack[] = parsed.tracks.map((track, index) => {
    if (!track || typeof track !== "object") {
      throw new Error(`raw tracking config 第 ${index + 1} 个 track 结构无效。`);
    }
    const row = track as Record<string, unknown>;
    if (
      typeof row.slug !== "string" ||
      typeof row.name !== "string" ||
      !Array.isArray(row.people) ||
      !Array.isArray(row.sampleCompanies)
    ) {
      throw new Error(`raw tracking config 第 ${index + 1} 个 track 无法进行实体完整性审计。`);
    }

    for (const [field, values] of [
      ["people", row.people],
      ["sampleCompanies", row.sampleCompanies],
    ] as const) {
      const invalidIndex = values.findIndex((value) => typeof value !== "string");
      if (invalidIndex >= 0) {
        throw new Error(
          `${row.slug}/${field} 第 ${invalidIndex + 1} 项不是字符串，无法进行实体完整性审计。`,
        );
      }
    }

    return {
      slug: row.slug,
      name: row.name,
      people: row.people as string[],
      sampleCompanies: row.sampleCompanies as string[],
    };
  });

  return { tracks };
}

function findCompoundIssues(config: RawTrackingConfig): CompoundIssue[] {
  const issues: CompoundIssue[] = [];

  for (const track of config.tracks) {
    for (const [field, entityType] of [
      ["people", "person"],
      ["sampleCompanies", "company"],
    ] as const) {
      for (const value of track[field]) {
        const parts = splitCompoundTrackingEntityName(value);
        if (parts.length < 2) continue;
        issues.push({
          trackSlug: track.slug,
          trackName: track.name,
          entityType,
          value,
          parts,
        });
      }
    }
  }

  return issues;
}

const worktree = resolve(argumentValue("--worktree", "."));
const configPath = resolve(worktree, TRACKING_CONFIG_PATH);
const config = parseRawTrackingConfig(readFileSync(configPath, "utf8"));
const issues = findCompoundIssues(config);

if (issues.length) {
  const preview = issues
    .slice(0, 5)
    .map((issue) => {
      const label = issue.entityType === "person" ? "人物" : "公司";
      return `${issue.trackName}/${label}“${issue.value}” → ${issue.parts.join("、")}`;
    })
    .join("；");
  const remainder = issues.length > 5 ? `；另有 ${issues.length - 5} 项` : "";
  throw new Error(
    `检测到复合追踪实体，raw user_tracking.json 必须保持零复合状态：${preview}${remainder}。`,
  );
}

console.log(
  "Tracking entity clean state valid: raw user_tracking.json contains zero compound people/companies.",
);
