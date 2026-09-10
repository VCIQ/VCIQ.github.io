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
  // Explicitly person-centric material types (interview, speech, dialogue,
  // paper, book, shareholder letter, official material) keep their existing
  // curated admission because the directory label itself carries subject
  // semantics.
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

    events.push({
      id: `person-directory:${item.eventClusterId || item.id}`,
      title,
      summary: item.summary.trim() || `${profile.name} · 人物材料`,
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
        level: personMaterialSourceLevel(item),
        platform: item.source || undefined,
      },
      curated: true,
      qualityStatus: "可用",
      qualitySignals: ["人物库正式实体", "人物材料目录"],
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

function normalizedEventUrl(value: string) {
  const candidate = value.trim();
  if (!candidate) return "";
  try {
    const url = new URL(candidate, "https://vciq.github.io");
    url.hash = "";
    for (const key of [...url.searchParams.keys()]) {
      if (key.toLowerCase().startsWith("utm_")) url.searchParams.delete(key);
    }
    return url.toString().replace(/\/$/u, "").toLocaleLowerCase("en-US");
  } catch {
    return candidate.toLocaleLowerCase("en-US");
  }
}

/**
 * Article-derived person events remain canonical when the same material is
 * already present in the main intelligence archive. The directory contributes
 * only person-library material that would otherwise disappear from the new
 * homepage-only event architecture.
 */
export function mergeHomepagePersonChannelEvents(
  articleEvents: readonly LiveIntelligenceEvent[],
  directoryEvents: readonly LiveIntelligenceEvent[],
): LiveIntelligenceEvent[] {
  const merged = [...articleEvents];
  const seenUrls = new Set(
    articleEvents.map((item) => normalizedEventUrl(item.source.url)).filter(Boolean),
  );
  const seenTitles = new Set(
    articleEvents.map((item) => normalizedEventTitle(item.title)).filter(Boolean),
  );

  for (const event of directoryEvents) {
    const urlKey = normalizedEventUrl(event.source.url);
    const titleKey = normalizedEventTitle(event.title);
    if ((urlKey && seenUrls.has(urlKey)) || (titleKey && seenTitles.has(titleKey))) continue;
    merged.push(event);
    if (urlKey) seenUrls.add(urlKey);
    if (titleKey) seenTitles.add(titleKey);
  }

  return merged;
}
