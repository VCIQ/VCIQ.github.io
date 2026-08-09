import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

import { repairHistoricalCompoundTrackingEntities } from "../lib/tracking-entity-history-repair";
import type { UserTrackingConfig } from "../lib/user-tracking";

const DEFAULT_PATH = "config/user_tracking.json";

async function main(): Promise<void> {
  const write = process.argv.includes("--write");
  const pathArg = process.argv.find((arg) => !arg.startsWith("--") && arg !== process.argv[1]);
  const targetPath = resolve(process.cwd(), pathArg || DEFAULT_PATH);
  const raw = await readFile(targetPath, "utf8");
  const config = JSON.parse(raw) as UserTrackingConfig;
  const result = repairHistoricalCompoundTrackingEntities(config);

  process.stdout.write(
    `${JSON.stringify(
      {
        mode: write ? "write" : "dry-run",
        targetPath,
        ...result.audit,
      },
      null,
      2,
    )}\n`,
  );

  if (!write || result.audit.repairedOccurrences === 0) return;
  await writeFile(targetPath, `${JSON.stringify(result.config, null, 2)}\n`, "utf8");
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`[repair-tracking-compound-entities] ${message}`);
  process.exitCode = 1;
});
