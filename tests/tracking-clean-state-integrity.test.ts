import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import test from "node:test";

const repositoryRoot = process.cwd();
const scriptPath = resolve(repositoryRoot, "scripts/validate-zero-tracking-compounds.ts");
const tsxImport = createRequire(import.meta.url).resolve("tsx");

function runValidator(worktree?: string) {
  const args = ["--import", tsxImport, scriptPath];
  if (worktree) args.push("--worktree", worktree);
  return spawnSync(process.execPath, args, {
    cwd: repositoryRoot,
    encoding: "utf8",
  });
}

function writeTrackingConfig(
  people: unknown[],
  sampleCompanies: unknown[],
): string {
  const directory = mkdtempSync(resolve(tmpdir(), "tracking-clean-state-"));
  mkdirSync(resolve(directory, "config"), { recursive: true });
  writeFileSync(
    resolve(directory, "config/user_tracking.json"),
    `${JSON.stringify(
      {
        schemaVersion: 1,
        tracks: [
          {
            slug: "ai",
            name: "AI / AGI",
            enabled: true,
            custom: false,
            keywords: [],
            people,
            sampleCompanies,
          },
        ],
        listedCompanies: [],
        sources: [],
      },
      null,
      2,
    )}\n`,
    "utf8",
  );
  return directory;
}

// Diagnostic baseline only: current main is intentionally known-dirty while PR #295
// repairs it. Skip the repository-state assertion here so this throwaway PR can reach
// static-page generation and measure /people/ without altering page code or data.
test.skip("current raw repository tracking config has zero compound people and companies", () => {
  const result = runValidator();
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  assert.match(result.stdout, /zero compound people\/companies/);
});

test("clean-state gate catches compounds beyond runtime normalization caps", () => {
  const people = [
    ...Array.from({ length: 40 }, (_, index) => `Person ${index + 1}`),
    "Alice、Bob",
  ];
  const companies = [
    ...Array.from({ length: 80 }, (_, index) => `Company ${index + 1}`),
    "Alpha / Beta",
  ];
  const result = runValidator(writeTrackingConfig(people, companies));
  const output = `${result.stdout}\n${result.stderr}`;

  assert.notEqual(result.status, 0);
  assert.match(output, /raw user_tracking\.json 必须保持零复合状态/);
  assert.match(output, /Alice、Bob/);
  assert.match(output, /Alpha \/ Beta/);
});

test("legal single-entity punctuation remains allowed", () => {
  const result = runValidator(
    writeTrackingConfig(
      ["Alice Smith"],
      ["OpenAI, Inc.", "Pony.ai, Inc.", "Procter & Gamble", "A/B Test Labs"],
    ),
  );

  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
});

test("malformed raw entity arrays fail closed", () => {
  const result = runValidator(writeTrackingConfig(["Alice", { name: "Bob" }], ["OpenAI"]));
  const output = `${result.stdout}\n${result.stderr}`;

  assert.notEqual(result.status, 0);
  assert.match(output, /不是字符串，无法进行实体完整性审计/);
});
