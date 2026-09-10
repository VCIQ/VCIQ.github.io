import type { LiveIntelligenceEvent, RelatedArticleSource } from "@/lib/use-articles";

/** Material identity, not fuzzy topic similarity. Paths and identity query values retain case. */
export function homepageMaterialUrl(value: string): string {
  try {
    const url = new URL(value.trim());
    if (!/^https?:$/u.test(url.protocol) || url.username || url.password) return "";
    url.hash = "";
    for (const key of [...url.searchParams.keys()]) {
      if (key.toLowerCase().startsWith("utm_")) url.searchParams.delete(key);
    }
    url.searchParams.sort();
    return url.toString();
  } catch {
    return "";
  }
}

export function homepageEventIdentityKeys(item: LiveIntelligenceEvent): string[] {
  const result: string[] = [];
  if (item.id) result.push(`id:${item.id}`);
  if (item.eventClusterId) result.push(`cluster:${item.eventClusterId}`);
  const url = homepageMaterialUrl(item.source.url);
  if (url) result.push(`url:${url}`);
  return result;
}

/** Exclude currently displayed events and duplicates within the rail, without changing scores. */
export function excludeDisplayedHomepageEvents(
  candidates: readonly LiveIntelligenceEvent[],
  displayed: readonly LiveIntelligenceEvent[],
): LiveIntelligenceEvent[] {
  const seen = new Set(displayed.flatMap(homepageEventIdentityKeys));
  return candidates.filter((item) => {
    const keys = homepageEventIdentityKeys(item);
    if (keys.some((key) => seen.has(key))) return false;
    keys.forEach((key) => seen.add(key));
    return true;
  });
}

/** Count available distinct links, not archive duplicates and not independent corroborations. */
export function homepageSourceEvidence(item: LiveIntelligenceEvent): {
  totalLinks: number;
  additionalLinks: RelatedArticleSource[];
} {
  const primary = homepageMaterialUrl(item.source.url);
  const seen = new Set(primary ? [primary] : []);
  const additionalLinks: RelatedArticleSource[] = [];
  for (const source of item.relatedSources ?? []) {
    const key = homepageMaterialUrl(source.url);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    additionalLinks.push(source);
  }
  return { totalLinks: seen.size, additionalLinks };
}

/** A biographical directory description is not an event summary. Never invent a replacement fact. */
export function homepageEventSummary(item: LiveIntelligenceEvent): string {
  const summary = item.summary.trim();
  const isProfile = (item.mentionedPeople ?? []).some((name) =>
    summary.startsWith(`${name} ·`) || summary.startsWith(`${name}·`),
  );
  if (!summary || isProfile || /人物档案待补充|^新闻资讯$/u.test(summary)) {
    return "暂无可用的事件摘要，请查看来源。";
  }
  return summary;
}
