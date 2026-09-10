import { homepageMaterialUrl } from "./homepage-event-identity";
import { findHomepagePersonMaterialReview } from "./homepage-person-material-reviews";
import { normalizeHomepageEntityKey } from "@/lib/homepage-entity-channels";
import type {
  IntelligenceSource,
  LiveIntelligenceEvent,
  Region,
  RelatedArticleSource,
} from "@/lib/use-articles";

export type HomepagePersonDirectorySource = {
  name: string;
  href: string;
  title?: string;
};

export type HomepagePersonDirectoryItem = {
  id: string;
  title: string;
  summary: string;
  href: string;
  source: string;
  label: string;
  context: string;
  sortAt: string;
  region?: string;
  eventClusterId?: string;
  sources?: HomepagePersonDirectorySource[];
  sourceCount?: number;
  sourceGrade?: "A" | "B" | "C" | "D";
};

export type HomepagePersonProfile = {
  slug: string;
  name: string;
  englishName?: string;
  aliases?: string[];
  sectors?: string[];
};

function personProfileIndex(profiles: readonly HomepagePersonProfile[]) {
  const index = new Map<string, HomepagePersonProfile>();
  for (const profile of profiles) {
    for (const label of [profile.name, profile.englishName, ...(profile.aliases ?? [])]) {
      const key = normalizeHomepageEntityKey(label);
      if (key && !index.has(key)) index.set(key, profile);
    }
  }
  return index;
}

function normalizedRegion(value: string | undefined): Region {
  return value === "中国" || value === "美国" || value === "全球" ? value : "全球";
}

function personMaterialEventType(label: string): LiveIntelligenceEvent["type"] {
  return label === "论文" ? "论文" : "人物观点";
}

function personMaterialSourceLevel(
  item: HomepagePersonDirectoryItem,
): IntelligenceSource["level"] {
  if (item.sourceGrade === "D") return "待交叉验证";
  if (item.label === "官方资料") return "官方披露";
  if (["论文", "著作", "股东信", "演讲", "公开对话", "采访"].includes(item.label)) {
    return "原始材料";
  }
  return "媒体报道";
}

function personMaterialImportance(item: HomepagePersonDirectoryItem) {
  const baseByLabel: Record<string, number> = {
    官方资料: 88,
    论文: 86,
    著作: 84,
    股东信: 82,
    演讲: 79,
    公开对话: 77,
    采访: 75,
    人物资料: 72,
    人物材料: 70,
  };
  const sourceBonus = Math.min(6, Math.max(0, (item.sourceCount ?? 1) - 1) * 2);
  return Math.min(95, (baseByLabel[item.label] ?? 70) + sourceBonus);
}

function personTitleReferencesProfile(
  title: string,
  profile: HomepagePersonProfile,
) {
  const titleKey = normalizeHomepageEntityKey(title);
  if (!titleKey) return false;
  return [profile.name, profile.englishName, ...(profile.aliases ?? [])]
    .map((value) => normalizeHomepageEntityKey(value))
    .filter((value) => value.length >= 2)
    .some((value) => titleKey.includes(value));
}

function hasHomepagePersonSubjectEvidence(
  item: HomepagePersonDirectoryItem,
  profile: HomepagePersonProfile,
) {
  // Generic directory associations are intentionally broad: they can be
  // created because a tracked person appears somewhere in an article. That is
  // useful for research recall but too permissive for a user-facing person
  // feed. Require the formal person to be visible in the title before a
  // generic "人物材料/人物资料" item is projected onto the homepage.
  // Keep the existing admission of other material types. A label is not
  // independent subject evidence: source-reviewed exceptions are applied
  // separately when directory events enter the visible homepage feed.
  if (item.label !== "人物材料" && item.label !== "人物资料") return true;
  return personTitleReferencesProfile(item.title, profile);
}

function relatedPersonMaterialSources(
  item: HomepagePersonDirectoryItem,
): RelatedArticleSource[] | undefined {
  const primary = item.href.trim();
  const seen = new Set<string>(primary ? [primary] : []);
  const related: RelatedArticleSource[] = [];
  for (const source of item.sources ?? []) {
    const href = source.href.trim();
    if (!href || seen.has(href)) continue;
    seen.add(href);
    related.push({
      name: source.name || item.source,
      url: href,
      level: personMaterialSourceLevel(item),
      platform: source.name || item.source,
      title: source.title || item.title,
      publishedAt: item.sortAt,
    });
    if (related.length >= 3) break;
  }
  return related.length ? related : undefined;
}

export function projectHomepagePersonDirectoryEvents(
  items: readonly HomepagePersonDirectoryItem[],
  profiles: readonly HomepagePersonProfile[],
): LiveIntelligenceEvent[] {
  const profilesByKey = personProfileIndex(profiles);
  const events: LiveIntelligenceEvent[] = [];

  for (const item of items) {
    const profile = profilesByKey.get(normalizeHomepageEntityKey(item.context));
    const title = item.title.trim();
    const href = item.href.trim();
    const publishedAt = item.sortAt.trim();
    if (!profile || !title || !href || !publishedAt) continue;
    if (!hasHomepagePersonSubjectEvidence(item, profile)) continue;
    const review = findHomepagePersonMaterialReview(profile.slug, href, title);

    events.push({
      id: `person-directory:${item.eventClusterId || item.id}`,
      title,
      summary: review?.summary ?? (item.summary.trim() || `${profile.name} · 人物材料`),
      type: personMaterialEventType(item.label),
      region: normalizedRegion(item.region),
      sector: profile.sectors?.[0]?.trim() || "人物",
      company: "",
      personSlug: profile.slug,
      sourceId: "person-update-directory",
      publishedAt,
      importance: personMaterialImportance(item),
      source: {
        name: item.source || "人物资料",
        url: href,
        level: item.sourceGrade === "D"
          ? "待交叉验证"
          : review?.sourceLevel ?? personMaterialSourceLevel(item),
        platform: item.source || undefined,
      },
      curated: true,
      qualityStatus: "可用",
      qualitySignals: ["人物库正式实体", "人物材料目录", ...(review ? [review.signal] : [])],
      relatedSources: relatedPersonMaterialSources(item),
      duplicateCount: Math.max(1, item.sourceCount ?? 1),
      eventClusterId: item.eventClusterId,
      mentionedPeople: [profile.name],
      matchedTrackingTerms: [profile.name, item.label],
    });
  }

  return events;
}

function normalizedEventTitle(value: string) {
  return normalizeHomepageEntityKey(value);
}

function uniqueStrings(values: readonly (string | undefined)[]) {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = String(raw ?? "").trim();
    const key = value.normalize("NFKC").toLocaleLowerCase("zh-CN");
    if (!value || seen.has(key)) continue;
    seen.add(key);
    result.push(value);
  }
  return result;
}

function mergeRelatedSources(
  canonical: LiveIntelligenceEvent,
  directory: LiveIntelligenceEvent,
): RelatedArticleSource[] | undefined {
  const primary = homepageMaterialUrl(canonical.source.url);
  const seen = new Set(primary ? [primary] : []);
  const merged: RelatedArticleSource[] = [];
  for (const source of [...(canonical.relatedSources ?? []), ...(directory.relatedSources ?? [])]) {
    const key = homepageMaterialUrl(source.url);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    merged.push(source);
    if (merged.length >= 3) break;
  }
  return merged.length ? merged : undefined;
}

function enrichCanonicalPersonEvent(
  canonical: LiveIntelligenceEvent,
  directory: LiveIntelligenceEvent,
): LiveIntelligenceEvent {
  const review = findHomepagePersonMaterialReview(
    directory.personSlug,
    directory.source.url,
    directory.title,
  );
  const relatedSources = mergeRelatedSources(canonical, directory);
  const mentionedPeople = uniqueStrings([
    ...(canonical.mentionedPeople ?? []),
    ...(directory.mentionedPeople ?? []),
  ]);
  const qualitySignals = uniqueStrings([
    ...(canonical.qualitySignals ?? []),
    ...(directory.qualitySignals ?? []),
  ]);
  const matchedTrackingTerms = uniqueStrings([
    ...(canonical.matchedTrackingTerms ?? []),
    ...(directory.matchedTrackingTerms ?? []),
  ]);
  const source = review && canonical.source.level !== "待交叉验证"
    ? { ...canonical.source, level: review.sourceLevel }
    : canonical.source;

  return {
    ...canonical,
    summary: review?.summary ?? canonical.summary,
    personSlug: directory.personSlug ?? canonical.personSlug,
    source,
    qualityStatus: canonical.qualityStatus ?? directory.qualityStatus,
    qualitySignals: qualitySignals.length ? qualitySignals : undefined,
    relatedSources,
    duplicateCount: Math.max(
      canonical.duplicateCount ?? 1,
      directory.duplicateCount ?? 1,
      (relatedSources?.length ?? 0) + 1,
    ),
    eventClusterId: canonical.eventClusterId ?? directory.eventClusterId,
    mentionedPeople: mentionedPeople.length ? mentionedPeople : undefined,
    matchedTrackingTerms: matchedTrackingTerms.length ? matchedTrackingTerms : undefined,
  };
}

/**
 * Article-derived events stay canonical. The third argument is the complete
 * quality-scoped article pool, allowing a person-directory relationship to
 * attach to an existing article even when that article did not already carry
 * person metadata. Historical directory IDs remain independently recoverable.
 */
export function mergeHomepagePersonChannelEvents(
  articleEvents: readonly LiveIntelligenceEvent[],
  directoryEvents: readonly LiveIntelligenceEvent[],
  canonicalArticleEvents: readonly LiveIntelligenceEvent[] = articleEvents,
): LiveIntelligenceEvent[] {
  const merged = [...articleEvents];
  const canonicalByUrl = new Map<string, LiveIntelligenceEvent>();
  for (const article of canonicalArticleEvents) {
    const key = homepageMaterialUrl(article.source.url);
    if (key && !canonicalByUrl.has(key)) canonicalByUrl.set(key, article);
  }
  const seenUrls = new Set(
    articleEvents.map((item) => homepageMaterialUrl(item.source.url)).filter(Boolean),
  );
  const seenTitles = new Set(
    articleEvents.map((item) => normalizedEventTitle(item.title)).filter(Boolean),
  );

  for (const event of directoryEvents) {
    // Keep context-only records resolvable by historical deep-research links,
    // but never surface them as that person's visible news.
    const review = event.sourceId === "person-update-directory"
      ? findHomepagePersonMaterialReview(event.personSlug, event.source.url, event.title)
      : undefined;
    if (review?.relation === "context-only") continue;

    const urlKey = homepageMaterialUrl(event.source.url);
    const titleKey = normalizedEventTitle(event.title);
    const canonical = urlKey ? canonicalByUrl.get(urlKey) : undefined;
    if (canonical) {
      const enriched = enrichCanonicalPersonEvent(canonical, event);
      const existingIndex = merged.findIndex((item) =>
        item.id === canonical.id ||
        (urlKey && homepageMaterialUrl(item.source.url) === urlKey),
      );
      if (existingIndex >= 0) merged[existingIndex] = enriched;
      else merged.push(enriched);
      if (urlKey) seenUrls.add(urlKey);
      const enrichedTitle = normalizedEventTitle(enriched.title);
      if (enrichedTitle) seenTitles.add(enrichedTitle);
      continue;
    }

    if ((urlKey && seenUrls.has(urlKey)) || (titleKey && seenTitles.has(titleKey))) continue;
    merged.push(event);
    if (urlKey) seenUrls.add(urlKey);
    if (titleKey) seenTitles.add(titleKey);
  }

  return merged;
}
