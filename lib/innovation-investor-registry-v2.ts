import source from "@/config/innovation_investor_registry_v2.json";

export type InvestorRegistryRelationship = {
  type: "historical-lineage";
  targetId: string;
  note: string;
};

export type InvestorRegistryV2Entry = {
  id: string;
  canonicalName: string;
  aliases: string[];
  cohorts: string[];
  regionGroup: string;
  focusAreas: string[];
  officialSources: {
    homepage: string | null;
    discovery: string | null;
    portfolio: string | null;
    people: string | null;
  };
  sourceStatus: string;
  sourceReferences: string[];
  relationships: InvestorRegistryRelationship[];
};

export const innovationInvestorRegistryV2 =
  source.institutions as readonly InvestorRegistryV2Entry[];

/** Equality only: do not use fuzzy, substring, or family/network-name joins. */
export function normalizeInvestorAlias(value: string): string {
  return value.normalize("NFKC").toLocaleLowerCase("en-US").replace(/\s+/gu, "").trim();
}

export function investorRegistryV2Errors(
  institutions: readonly InvestorRegistryV2Entry[] = innovationInvestorRegistryV2,
): string[] {
  const errors: string[] = [];
  const byId = new Map(institutions.map((entry) => [entry.id, entry]));
  const aliases = new Map<string, string>();
  if (byId.size !== institutions.length) errors.push("duplicate canonical id");
  const validUrl = (value: string | null) => {
    if (value === null) return true;
    try {
      const url = new URL(value);
      return url.protocol === "https:" && !url.username && !url.password &&
        Boolean(url.hostname) && !url.hostname.endsWith(".local");
    } catch {
      return false;
    }
  };
  for (const entry of institutions) {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(entry.id)) errors.push(`invalid canonical ID: ${entry.id}`);
    if (!entry.canonicalName.trim() || !entry.aliases.includes(entry.canonicalName)) {
      errors.push(`canonicalName missing from aliases: ${entry.id}`);
    }
    if (!entry.cohorts.length || !entry.cohorts.every((x) => ["global-core", "china-focus"].includes(x))) {
      errors.push(`invalid cohort: ${entry.id}`);
    }
    if (entry.sourceStatus === "pending-official-source" && entry.officialSources.homepage !== null) {
      errors.push(`pending official source should not fabricate a homepage: ${entry.id}`);
    }
    if (!Object.values(entry.officialSources).every(validUrl)) {
      errors.push(`unsafe official source: ${entry.id}`);
    }
    for (const alias of entry.aliases) {
      const key = normalizeInvestorAlias(alias);
      if (!key) errors.push(`blank alias: ${entry.id}`);
      const previous = aliases.get(key);
      if (previous && previous !== entry.id) errors.push(`alias collision: ${alias} (${previous}, ${entry.id})`);
      else aliases.set(key, entry.id);
    }
    for (const rel of entry.relationships) {
      if (rel.type !== "historical-lineage" || !byId.has(rel.targetId) || rel.targetId === entry.id) {
        errors.push(`invalid investor relationship: ${entry.id} -> ${rel.targetId}`);
      }
    }
  }
  return errors;
}

export function resolveInvestorRegistryV2(
  label: string,
  institutions: readonly InvestorRegistryV2Entry[] = innovationInvestorRegistryV2,
): string | null {
  const key = normalizeInvestorAlias(label);
  if (!key) return null;
  const matches = institutions.filter((row) => row.aliases.some((alias) => normalizeInvestorAlias(alias) === key));
  return matches.length === 1 ? matches[0].id : null;
}
