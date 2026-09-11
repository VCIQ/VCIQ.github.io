import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

import { coreTechnologyEntities } from "../lib/core-research-objects";
import { intelligenceEvents, snapshotDate } from "../lib/intelligence-data";
import { eventTrackSlugs } from "../lib/tracking-snapshot";
import { normalizeTaxonomyTerm } from "../lib/tracking-taxonomy";
import { trackedSectors } from "../lib/tracked-sectors";

const OUTPUT = resolve(
  process.env.RESEARCH_AGENT_OBJECT_SNAPSHOT_PATH ||
    "work/research-agent/research_agent_objects.json",
);
const MAX_EVENTS_PER_OBJECT = 8;

function unique(values: Iterable<string>, limit = 40) {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = raw.trim();
    const key = normalizeTaxonomyTerm(value);
    if (!value || !key || seen.has(key)) continue;
    seen.add(key);
    result.push(value);
    if (result.length >= limit) break;
  }
  return result;
}

function canonicalUrl(value: string) {
  try {
    const url = new URL(value);
    url.hash = "";
    for (const key of [...url.searchParams.keys()]) {
      if (/^(?:utm_|spm$|from$|ref$|source$)/iu.test(key)) url.searchParams.delete(key);
    }
    return url.toString();
  } catch {
    return value.trim();
  }
}

const intelligenceByUrl = new Map(
  intelligenceEvents
    .filter((event) => Boolean(event.source.url))
    .map((event) => [canonicalUrl(event.source.url), event] as const),
);

function eventEvidence(event: (typeof intelligenceEvents)[number]) {
  const primary = ["官方披露", "原始材料", "监管文件"].includes(event.source.level);
  return {
    id: event.id,
    title: event.title,
    summary: event.summary,
    eventType: event.type,
    importance: event.importance,
    publishedAt: event.publishedAt,
    url: event.source.url,
    sourceName: event.source.name,
    platformName: event.source.platform ?? "",
    evidenceGrade: event.source.level,
    sourceRole: primary ? "primary" : "corroboration",
  };
}

function trackEvents(slug: string, name: string, aliases: string[]) {
  const identityKeys = new Set(
    [name, ...aliases].map(normalizeTaxonomyTerm).filter(Boolean),
  );
  return intelligenceEvents
    .filter((event) => {
      const assigned = eventTrackSlugs(event);
      if (assigned.length) return assigned.includes(slug);
      return identityKeys.has(normalizeTaxonomyTerm(event.sector));
    })
    .sort(
      (left, right) =>
        right.publishedAt.localeCompare(left.publishedAt) ||
        right.importance - left.importance ||
        left.id.localeCompare(right.id),
    )
    .slice(0, MAX_EVENTS_PER_OBJECT)
    .map(eventEvidence);
}

const tracks = Object.fromEntries(
  trackedSectors.map((sector) => [
    sector.slug,
    {
      slug: sector.slug,
      name: sector.name,
      aliases: unique(sector.aliases ?? []),
      definition: sector.definition,
      subsectors: sector.subsectors,
      researchFocus: sector.researchFocus,
      risks: sector.risks,
      profileMode: sector.profileMode,
      latestEvents: trackEvents(sector.slug, sector.name, sector.aliases ?? []),
    },
  ]),
);

const technologies = Object.fromEntries(
  coreTechnologyEntities.map((entity) => [
    entity.slug,
    {
      id: entity.id,
      slug: entity.slug,
      name: entity.name,
      aliases: unique(entity.aliases ?? []),
      trackSlugs: unique(entity.trackSlugs ?? []),
      trackNames: unique(entity.trackNames ?? []),
      state: entity.state,
      summary: entity.summary,
      priority: entity.priority,
      researchThesis: entity.researchThesis,
      latestEvents: entity.timeline
        .filter((item) => Boolean(item.url && item.title))
        .slice(0, MAX_EVENTS_PER_OBJECT)
        .map((item) => {
          const intelligence = intelligenceByUrl.get(canonicalUrl(item.url));
          if (intelligence) return eventEvidence(intelligence);
          return {
            id: item.id,
            title: item.title,
            summary: item.summary,
            eventType: item.eventType,
            importance: 50,
            eventDate: item.eventDate,
            observedAt: item.observedAt,
            publishedAt: item.eventDate || item.observedAt,
            url: item.url,
            sourceName: item.sourceName,
            evidenceGrade: item.origin === "manual-capture" ? "人工核验材料" : "媒体报道",
            sourceRole: "corroboration",
          };
        }),
    },
  ]),
);

const payload = {
  schemaVersion: 1,
  generatedAt: new Date().toISOString(),
  articleSnapshotDate: snapshotDate,
  counts: {
    track: Object.keys(tracks).length,
    technology: Object.keys(technologies).length,
  },
  tracks,
  technologies,
};

mkdirSync(dirname(OUTPUT), { recursive: true });
writeFileSync(OUTPUT, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
console.log(
  `Wrote Research Agent object snapshot: ${payload.counts.track} tracks, ${payload.counts.technology} technologies -> ${OUTPUT}`,
);
