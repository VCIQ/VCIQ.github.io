import rawOverrides from "@/config/institution_identity_overrides.json";
import { institutionEntities } from "@/lib/institution-entity-registry";
import { institutionRankingSources } from "@/lib/institution-ranking-data";

type TrackingInstitution = { name: string; targetId: string };
const index = new Map<string, TrackingInstitution[]>();
const primarySources = new Set(institutionRankingSources.filter((row) => row.role === "primary-ranking-source").map((row) => row.id));

function key(value: string) {
  return value.normalize("NFKC").toLowerCase().replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}
function add(name: string, aliases: string[]) {
  const row = { name, targetId: `institution:${key(name)}` };
  for (const alias of new Set([name, ...aliases].map(key).filter(Boolean))) {
    const rows = index.get(alias) ?? [];
    if (!rows.some((existing) => existing.targetId === row.targetId)) index.set(alias, [...rows, row]);
  }
}
for (const entity of institutionEntities) {
  if (entity.directoryEntry.officialUrl || entity.directoryEntry.rankings.some((row) => primarySources.has(row.sourceId))) {
    add(entity.name, entity.aliases);
  }
}
for (const row of rawOverrides.institutions) {
  try {
    const url = new URL(row.sourceUrl);
    if (row.status === "verified" && row.evidence && ["https:", "http:"].includes(url.protocol) && !url.username && !url.password) add(row.name, row.aliases);
  } catch {
    // Invalid supplemental evidence never grants an identity.
  }
}
export function institutionTrackingMatches(name: string): readonly TrackingInstitution[] {
  return index.get(key(name)) ?? [];
}
