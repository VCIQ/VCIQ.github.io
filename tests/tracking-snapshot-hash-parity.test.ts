import assert from "node:assert/strict";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import test from "node:test";

type RawTrack = Record<string, unknown> & { enabled?: unknown };
type RawConfig = { tracks?: unknown };
type CanonicalTrack = {
  slug: string;
  name: string;
  keywords: string[];
  people: string[];
  sampleCompanies: string[];
};

type PythonParity = {
  canonical: string;
  beforeHash: string;
  afterRuntimeHelpersHash: string;
  enrichedHash: string;
};

function clean(value: unknown, limit = 500): string {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function cleanList(value: unknown, limit = 80): string[] {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
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

function nodeCanonicalTracks(config: RawConfig): CanonicalTrack[] {
  const tracks = Array.isArray(config.tracks) ? config.tracks : [];
  return tracks
    .filter(
      (track): track is RawTrack =>
        Boolean(track) && typeof track === "object" && (track as RawTrack).enabled !== false,
    )
    .map((track) => ({
      slug: clean(track.slug, 80),
      name: clean(track.name, 80),
      keywords: cleanList(track.keywords, 60),
      people: cleanList(track.people, 40),
      sampleCompanies: cleanList(track.sampleCompanies, 40),
    }))
    .filter((track) => Boolean(track.slug && track.name));
}

function hash(value: string | Buffer): string {
  return crypto.createHash("sha256").update(value).digest("hex");
}

test("Python enrichment and Node snapshot validator share one stable tracking hash", () => {
  const rawConfig = fs.readFileSync("config/user_tracking.json");
  const config = JSON.parse(rawConfig.toString("utf8")) as RawConfig;
  const nodeTracks = nodeCanonicalTracks(config);
  const nodeJson = JSON.stringify(nodeTracks);
  const nodeHash = hash(nodeJson);

  const pythonJson = execFileSync(
    "python3",
    [
      "-c",
      [
        "import json",
        "from tools.enrich_tracking_snapshot import enabled_tracks, canonical_tracks, tracking_config_hash, assign_track_slugs, enrich",
        "config=json.load(open('config/user_tracking.json', encoding='utf-8'))",
        "tracks=enabled_tracks(config)",
        "canonical=canonical_tracks(tracks)",
        "before=tracking_config_hash(tracks)",
        "assign_track_slugs([], tracks)",
        "after=tracking_config_hash(tracks)",
        "payload={'articles': [], 'sourceStatus': [], 'generatedAt': '2026-08-21T00:00:00+00:00'}",
        "enriched=enrich(payload, config)",
        "print(json.dumps({'canonical': canonical, 'beforeHash': before, 'afterRuntimeHelpersHash': after, 'enrichedHash': enriched.get('trackingConfigHash')}, ensure_ascii=False))",
      ].join(";"),
    ],
    { encoding: "utf8" },
  ).trim();
  const python = JSON.parse(pythonJson) as PythonParity;

  console.log(
    `TRACKING_HASH_PARITY=${JSON.stringify({
      rawConfigSha256: hash(rawConfig),
      nodeHash,
      pythonBeforeHash: python.beforeHash,
      pythonAfterRuntimeHelpersHash: python.afterRuntimeHelpersHash,
      pythonEnrichedHash: python.enrichedHash,
      trackCount: nodeTracks.length,
    })}`,
  );

  if (python.canonical !== nodeJson) {
    const pythonTracks = JSON.parse(python.canonical) as CanonicalTrack[];
    const maxTracks = Math.max(nodeTracks.length, pythonTracks.length);
    const differences: unknown[] = [];
    for (let index = 0; index < maxTracks; index += 1) {
      const nodeTrack = nodeTracks[index];
      const pythonTrack = pythonTracks[index];
      if (JSON.stringify(nodeTrack) === JSON.stringify(pythonTrack)) continue;
      const fields = [
        "slug",
        "name",
        "keywords",
        "people",
        "sampleCompanies",
      ] as const;
      const fieldDiffs: Record<string, unknown> = {};
      for (const field of fields) {
        if (
          JSON.stringify(nodeTrack?.[field]) === JSON.stringify(pythonTrack?.[field])
        ) {
          continue;
        }
        fieldDiffs[field] = {
          node: nodeTrack?.[field],
          python: pythonTrack?.[field],
        };
      }
      differences.push({
        index,
        nodeSlug: nodeTrack?.slug,
        pythonSlug: pythonTrack?.slug,
        fields: fieldDiffs,
      });
      if (differences.length >= 5) break;
    }
    assert.fail(
      `tracking canonicalization differs across Node/Python; nodeHash=${nodeHash}; differences=${JSON.stringify(differences)}`,
    );
  }

  assert.equal(python.beforeHash, nodeHash);
  assert.equal(
    python.afterRuntimeHelpersHash,
    nodeHash,
    "runtime-only personSearchTerms must not alter the persisted tracking config hash",
  );
  assert.equal(
    python.enrichedHash,
    nodeHash,
    "the real enrichment path must write the same tracking hash the Node validator expects",
  );
});
