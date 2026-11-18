import { homepageEventIdentityKeys, homepageMaterialUrl, reviewedHomepageEvent } from "@/lib/homepage-event-identity";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

/** Store one stable event veto in the existing preference store, not N repost actions. */
export function focusPreferenceIdentity(item: LiveIntelligenceEvent): string {
  const reviewed = reviewedHomepageEvent(item);
  return reviewed ? `reviewed:${reviewed.id}` : item.eventClusterId ?? item.id;
}

export function groupFocusReports(sorted: readonly LiveIntelligenceEvent[], preserveRanking = false) {
  const parent = sorted.map((_, index) => index);
  const root = (index: number): number => {
    while (parent[index] !== index) { parent[index] = parent[parent[index]]; index = parent[index]; }
    return index;
  };
  const owners = new Map<string, number>();
  sorted.forEach((item, index) => {
    for (const key of homepageEventIdentityKeys(item)) {
      const owner = owners.get(key);
      if (owner === undefined) owners.set(key, index);
      else { const a = root(index); const b = root(owner); parent[Math.max(a, b)] = Math.min(a, b); }
    }
  });
  const grouped = new Map<number, LiveIntelligenceEvent[]>();
  sorted.forEach((item, index) => { const key = root(index); grouped.set(key, [...(grouped.get(key) ?? []), item]); });
  const groupedInto = new Map<string, string>();
  const items = [...grouped.values()].map((rows) => {
    const reviewedOriginal = rows.find((row) => {
      const event = reviewedHomepageEvent(row);
      return event && homepageMaterialUrl(event.evidenceUrl) === homepageMaterialUrl(row.source.url);
    });
    const reviewedPublisher = rows.find((row) =>
      reviewedHomepageEvent(row) && ["官方披露", "监管文件"].includes(row.source.level),
    );
    const original = preserveRanking ? rows[0] : rows.reduce((earliest, row) =>
      Date.parse(row.publishedAt) < Date.parse(earliest.publishedAt) ? row : earliest,
    );
    const first = reviewedOriginal ?? reviewedPublisher ?? original;
    const seen = new Set([homepageMaterialUrl(first.source.url)]);
    const relatedSources = [...(first.relatedSources ?? [])];
    relatedSources.forEach((x) => seen.add(homepageMaterialUrl(x.url)));
    for (const row of rows) {
      if (row === first) continue;
      groupedInto.set(row.id, first.id);
      for (const source of [{ ...row.source, platform: row.source.platform ?? "", title: row.title, publishedAt: row.publishedAt }, ...(row.relatedSources ?? [])]) {
        const key = homepageMaterialUrl(source.url);
        if (key && !seen.has(key)) { relatedSources.push(source); seen.add(key); }
      }
    }
    // Representative keeps its original publication date and source attribution.
    return { ...first, relatedSources, duplicateCount: seen.size };
  });
  return { items, groupedInto };
}
