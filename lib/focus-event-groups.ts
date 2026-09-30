import links from "@/config/priority_event_links.json";
import { homepageEventIdentityKeys, homepageMaterialUrl } from "@/lib/homepage-event-identity";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

const reviewed = new Map(links.events.flatMap((event) => event.materialUrls.map(
  (url) => [homepageMaterialUrl(url), `reviewed:${event.id}`] as const,
)));

/** Exact event/material identities only. A shared company/topic is not an event. */
export function focusIdentityKeys(item: LiveIntelligenceEvent): string[] {
  const keys = homepageEventIdentityKeys(item);
  const event = reviewed.get(homepageMaterialUrl(item.source.url));
  return event ? [...keys, event] : keys;
}

/** Store one stable event veto in the existing preference store, not N repost actions. */
export function focusPreferenceIdentity(item: LiveIntelligenceEvent): string {
  return reviewed.get(homepageMaterialUrl(item.source.url)) ?? item.eventClusterId ?? item.id;
}

export function groupFocusReports(sorted: readonly LiveIntelligenceEvent[]) {
  const parent = sorted.map((_, index) => index);
  const root = (index: number): number => {
    while (parent[index] !== index) { parent[index] = parent[parent[index]]; index = parent[index]; }
    return index;
  };
  const owners = new Map<string, number>();
  sorted.forEach((item, index) => {
    for (const key of focusIdentityKeys(item)) {
      const owner = owners.get(key);
      if (owner === undefined) owners.set(key, index);
      else { const a = root(index); const b = root(owner); parent[Math.max(a, b)] = Math.min(a, b); }
    }
  });
  const grouped = new Map<number, LiveIntelligenceEvent[]>();
  sorted.forEach((item, index) => { const key = root(index); grouped.set(key, [...(grouped.get(key) ?? []), item]); });
  const groupedInto = new Map<string, string>();
  const items = [...grouped.values()].map((rows) => {
    const first = rows[0]; const seen = new Set([homepageMaterialUrl(first.source.url)]);
    const relatedSources = [...(first.relatedSources ?? [])];
    relatedSources.forEach((x) => seen.add(homepageMaterialUrl(x.url)));
    for (const row of rows.slice(1)) {
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
