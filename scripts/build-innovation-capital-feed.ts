import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildInnovationCapitalFeedProjection } from "../lib/homepage-innovation-capital-channel";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");

function readJson(relativePath: string): unknown {
  return JSON.parse(fs.readFileSync(path.join(root, relativePath), "utf8"));
}

const projection = buildInnovationCapitalFeedProjection({
  articlesPayload: readJson("public/data/articles.json"),
  rankedPayload: readJson("public/data/ranked-intelligence.json"),
  watchlistPayload: readJson("config/innovation_listing_watchlist.json"),
  lifecyclePayload: readJson("config/innovation_listing_lifecycle.json"),
  maturePayload: readJson("config/innovation_capital_mature_candidates.json"),
  trackingSeedsPayload: readJson("config/innovation_capital_tracking_seeds.json"),
});

const output = path.join(root, "public/data/innovation-capital-feed.json");
fs.writeFileSync(output, `${JSON.stringify(projection, null, 2)}\n`, "utf8");

console.log(JSON.stringify({
  output: "public/data/innovation-capital-feed.json",
  generatedAt: projection.generatedAt,
  universeAsOf: projection.universeAsOf,
  eventCount: projection.eventCount,
}));
