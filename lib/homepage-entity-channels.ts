import type { LiveIntelligenceEvent } from "@/lib/use-articles";

export type HomepageEntityChannelIndex = {
  people: {
    slugs: string[];
    keys: string[];
  };
  companies: {
    slugs: string[];
    keys: string[];
  };
};

export type HomepageEntityChannelSets = {
  people: {
    slugs: ReadonlySet<string>;
    keys: ReadonlySet<string>;
  };
  companies: {
    slugs: ReadonlySet<string>;
    keys: ReadonlySet<string>;
  };
};

export function normalizeHomepageEntityKey(value: string | undefined) {
  return String(value ?? "")
    .normalize("NFKC")
    .trim()
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

export function uniqueHomepageEntityKeys(values: readonly (string | undefined)[]) {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const key = normalizeHomepageEntityKey(value);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    result.push(key);
  }
  return result;
}

export function uniqueHomepageEntitySlugs(values: readonly (string | undefined)[]) {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const slug = String(value ?? "").trim();
    if (!slug || seen.has(slug)) continue;
    seen.add(slug);
    result.push(slug);
  }
  return result;
}

export function buildHomepageEntityChannelSets(
  index: HomepageEntityChannelIndex,
): HomepageEntityChannelSets {
  return {
    people: {
      slugs: new Set(index.people.slugs),
      keys: new Set(index.people.keys),
    },
    companies: {
      slugs: new Set(index.companies.slugs),
      keys: new Set(index.companies.keys),
    },
  };
}

function hasFormalEntityMention(
  values: readonly string[] | undefined,
  keys: ReadonlySet<string>,
) {
  return (values ?? []).some((value) => keys.has(normalizeHomepageEntityKey(value)));
}

export function matchesHomepagePersonEntityChannel(
  item: LiveIntelligenceEvent,
  index: HomepageEntityChannelSets,
) {
  const slug = String(item.personSlug ?? "").trim();
  if (slug && index.people.slugs.has(slug)) return true;
  return hasFormalEntityMention(item.mentionedPeople, index.people.keys);
}

export function matchesHomepageCompanyEntityChannel(
  item: LiveIntelligenceEvent,
  index: HomepageEntityChannelSets,
) {
  const slug = String(item.companySlug ?? "").trim();
  if (slug && index.companies.slugs.has(slug)) return true;
  return hasFormalEntityMention(item.mentionedCompanies, index.companies.keys);
}
