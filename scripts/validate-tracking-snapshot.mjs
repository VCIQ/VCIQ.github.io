#!/usr/bin/env node

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const configPath = path.join(root, "config", "user_tracking.json");
const snapshotPath = path.join(root, "public", "data", "articles.json");

const DEDICATED_DISCOVERY_TRACKS = new Map([
  [
    "innovation-capital",
    [
      path.join(root, "tools", "crawl_with_innovation_listing_watchlist.py"),
      path.join(root, "config", "innovation_capital_tracking_seeds.json"),
      path.join(root, "config", "innovation_listing_watchlist.json"),
      path.join(root, "config", "innovation_listing_lifecycle.json"),
    ],
  ],
]);

function fail(messages) {
  for (const message of messages) {
    console.error(`TRACKING_SNAPSHOT_ERROR: ${message}`);
  }
  process.exit(1);
}

function clean(value, limit = 500) {
  return String(value ?? "").replace(/\s+/g, " ").trim().slice(0, limit);
}

function cleanList(value, limit = 80) {
  if (!Array.isArray(value)) return [];
  const result = [];
  const seen = new Set();
  for (const raw of value) {
    const item = clean(raw, 160);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    result.push(item);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

function canonicalTracks(config) {
  return (Array.isArray(config.tracks) ? config.tracks : [])
    .filter((track) => track && typeof track === "object" && track.enabled !== false)
    .map((track) => ({
      slug: clean(track.slug, 80),
      name: clean(track.name, 80),
      keywords: cleanList(track.keywords, 60),
      people: cleanList(track.people, 40),
      sampleCompanies: cleanList(track.sampleCompanies, 40),
    }))
    .filter((track) => track.slug && track.name);
}

if (!fs.existsSync(configPath) || !fs.existsSync(snapshotPath)) {
  fail(["missing config/user_tracking.json or public/data/articles.json"]);
}

let config;
let snapshot;
try {
  config = JSON.parse(fs.readFileSync(configPath, "utf8"));
  snapshot = JSON.parse(fs.readFileSync(snapshotPath, "utf8"));
} catch (error) {
  fail([`invalid tracking JSON: ${error.message}`]);
}

const tracks = canonicalTracks(config);
const expectedHash = crypto
  .createHash("sha256")
  .update(JSON.stringify(tracks), "utf8")
  .digest("hex");
const actualHash = clean(snapshot.trackingConfigHash, 80);
const errors = [];

if (!actualHash) {
  errors.push("article snapshot has no trackingConfigHash; crawler enrichment has not run");
} else if (actualHash !== expectedHash) {
  errors.push(
    `tracking configuration is newer than the article snapshot; wait for Refresh public intelligence (expected=${expectedHash.slice(0, 12)} actual=${actualHash.slice(0, 12)})`,
  );
}

const coverage =
  snapshot.trackCoverage && typeof snapshot.trackCoverage === "object"
    ? snapshot.trackCoverage
    : {};
for (const track of tracks) {
  const row = coverage[track.slug];
  if (!row || typeof row !== "object") {
    errors.push(`${track.name}: missing crawler coverage record`);
    continue;
  }
  const dedicatedInputs = DEDICATED_DISCOVERY_TRACKS.get(track.slug);
  if (dedicatedInputs) {
    const missingDedicatedInputs = dedicatedInputs.filter((input) => !fs.existsSync(input));
    if (missingDedicatedInputs.length) {
      errors.push(
        `${track.name}: dedicated discovery contract is incomplete (${missingDedicatedInputs
          .map((input) => path.relative(root, input))
          .join(", ")})`,
      );
    }
    continue;
  }

  const expectedSources = Number(row.expectedSources ?? 0);
  const completedSources = Number(row.completedSources ?? 0);
  if (expectedSources < 3) {
    errors.push(`${track.name}: expectedSources=${expectedSources}; three discovery routes are required`);
  }
  if (completedSources < expectedSources) {
    errors.push(
      `${track.name}: only ${completedSources}/${expectedSources} discovery routes completed`,
    );
  }
}

if (errors.length) fail(errors);
console.log(
  `Tracking snapshot valid: ${tracks.length} tracks match ${actualHash.slice(0, 12)}; generic routes and dedicated discovery contracts are complete.`,
);
