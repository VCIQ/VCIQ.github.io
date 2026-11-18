import links from "@/config/priority_event_links.json";
import type { LiveIntelligenceEvent, RelatedArticleSource } from "@/lib/use-articles";
import { isNonDurableWeChatArticleUrl } from "@/lib/wechat-link-policy";

const NON_IDENTITY_QUERY_KEYS = new Set([
  "gclid",
  "fbclid",
  "mc_cid",
  "mc_eid",
  "igshid",
]);

/** Material identity, not fuzzy topic similarity. Paths and identity query values retain case. */
export function homepageMaterialUrl(value: string): string {
  try {
    const url = new URL(value.trim());
    if (!/^https?:$/u.test(url.protocol) || url.username || url.password) return "";
    url.hash = "";
    for (const key of [...url.searchParams.keys()]) {
      const lowered = key.toLowerCase();
      if (lowered.startsWith("utm_") || NON_IDENTITY_QUERY_KEYS.has(lowered)) {
        url.searchParams.delete(key);
      }
    }
    url.searchParams.sort();
    if (url.pathname.length > 1) url.pathname = url.pathname.replace(/\/+$/u, "");
    return url.toString();
  } catch {
    return "";
  }
}

const reviewedByMaterial = new Map(links.events.flatMap((event) => event.materialUrls.map(
  (url) => [homepageMaterialUrl(url), event] as const,
)));

export function reviewedHomepageMaterial(url: string) {
  return reviewedByMaterial.get(homepageMaterialUrl(url));
}

export function reviewedHomepageEvent(item: LiveIntelligenceEvent) {
  return reviewedHomepageMaterial(item.source.url);
}

export function homepageEventPublishedAt(item: LiveIntelligenceEvent): string {
  const reviewedDate = reviewedHomepageEvent(item)?.publishedAt;
  return !reviewedDate || item.publishedAt.slice(0, 10) === reviewedDate
    ? item.publishedAt
    : reviewedDate;
}

export function homepageEventIdentityKeys(item: LiveIntelligenceEvent): string[] {
  const result: string[] = [];
  if (item.id) result.push(`id:${item.id}`);
  const reviewed = reviewedHomepageEvent(item);
  if (reviewed) result.push(`reviewed:${reviewed.id}`);
  else if (item.eventClusterId) result.push(`cluster:${item.eventClusterId}`);
  const url = homepageMaterialUrl(item.source.url);
  if (url) result.push(`url:${url}`);
  return result;
}

export function homepageEarlierMilestones(item: LiveIntelligenceEvent) {
  const current = reviewedHomepageEvent(item);
  if (!current?.storyId) return [];
  return links.events.filter(
    (event) => event.storyId === current.storyId && event.stageLabel &&
      event.publishedAt < current.publishedAt,
  ).sort((left, right) => right.publishedAt.localeCompare(left.publishedAt));
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
  const primary = isNonDurableWeChatArticleUrl(item.source.url)
    ? "" : homepageMaterialUrl(item.source.url);
  const seen = new Set(primary ? [primary] : []);
  const additionalLinks: RelatedArticleSource[] = [];
  for (const source of item.relatedSources ?? []) {
    if (isNonDurableWeChatArticleUrl(source.url)) continue;
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
  const isDirectoryProfile = item.sourceId === "person-update-directory" &&
    (item.mentionedPeople ?? []).some((name) =>
      summary.startsWith(`${name} ·`) || summary.startsWith(`${name}·`),
    );
  if (!summary || isDirectoryProfile || /人物档案待补充|^新闻资讯$/u.test(summary)) {
    return "暂无可用的事件摘要，请查看来源。";
  }
  return summary;
}
