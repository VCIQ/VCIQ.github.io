import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { buildInnovationCapitalResearchModel } from "../lib/innovation-capital-research";
import { buildInnovationCapitalThesisMemory } from "../lib/innovation-capital-thesis-memory";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const output = path.join(root, "public/data/innovation_capital_thesis_memory.json");

let previous: unknown = {};
if (fs.existsSync(output)) {
  try {
    previous = JSON.parse(fs.readFileSync(output, "utf8"));
  } catch {
    previous = {};
  }
}

const model = buildInnovationCapitalResearchModel();
const generatedAt = new Date().toISOString();
// `asOf` tracks the evidence horizon. `generatedAt` tracks the most recent
// successful rebuild/validation, even when the thesis content is unchanged.
// Keeping those clocks separate prevents a healthy daily rebuild from being
// reported as stale merely because no material thesis revision occurred.
const memory = {
  ...buildInnovationCapitalThesisMemory(previous, model, generatedAt),
  generatedAt,
};
const serialized = `${JSON.stringify(memory, null, 2)}\n`;
const before = fs.existsSync(output) ? fs.readFileSync(output, "utf8") : "";

if (before === serialized) {
  console.log(`Innovation Capital thesis memory already current at ${model.asOf || "unknown"}.`);
} else {
  fs.writeFileSync(output, serialized, "utf8");
  console.log(
    `Updated Innovation Capital thesis memory: ${memory.currentObservationIds.length} current / ${memory.observationCount} historical observations.`,
  );
}
