import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import test from "node:test";

const repositoryRoot = process.cwd();
const scriptPath = resolve(repositoryRoot, "scripts/validate-new-tracking-entities.ts");
const tsxImport = createRequire(import.meta.url).resolve("tsx");

function trackingConfig(extraPeople: string[] = [], extraCompanies: string[] = []) {
  return {
    schemaVersion: 1,
    tracks: [
      {
        slug: "ai",
        name: "AI / AGI",
        enabled: true,
        custom: false,
        keywords: [],
        people: [
          ...Array.from({ length: 40 }, (_, index) => `Person ${index + 1}`),
          ...extraPeople,
        ],
        sampleCompanies: [
          ...Array.from({ length: 80 }, (_, index) => `Company ${index + 1}`),
          ...extraCompanies,
        ],
      },
    ],
    listedCompanies: [],
    sources: [],
  };
}

test("repository delta guard catches compounds beyond runtime normalization caps", () => {
  const directory = mkdtempSync(resolve(tmpdir(), "tracking-raw-guard-"));
  mkdirSync(resolve(directory, "config"), { recursive: true });

  execFileSync("git", ["init"], { cwd: directory, stdio: "ignore" });
  execFileSync("git", ["config", "user.name", "Test"], { cwd: directory });
  execFileSync("git", ["config", "user.email", "test@example.com"], { cwd: directory });

  const configPath = resolve(directory, "config/user_tracking.json");
  writeFileSync(configPath, `${JSON.stringify(trackingConfig(), null, 2)}\n`, "utf8");
  execFileSync("git", ["add", "config/user_tracking.json"], { cwd: directory });
  execFileSync("git", ["commit", "-m", "baseline"], { cwd: directory, stdio: "ignore" });

  writeFileSync(
    configPath,
    `${JSON.stringify(trackingConfig(["Alice、Bob"], ["Alpha / Beta"]), null, 2)}\n`,
    "utf8",
  );

  const result = spawnSync(
    process.execPath,
    ["--import", tsxImport, scriptPath, "--base-ref", "HEAD"],
    { cwd: directory, encoding: "utf8" },
  );

  assert.notEqual(result.status, 0);
  assert.match(`${result.stdout}\n${result.stderr}`, /检测到本次新增的复合追踪实体/);
  assert.match(`${result.stdout}\n${result.stderr}`, /Alice、Bob/);
  assert.match(`${result.stdout}\n${result.stderr}`, /Alpha \/ Beta/);
});
