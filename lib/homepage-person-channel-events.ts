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
  handles?: string[];
  role?: string;
  organizations?: string[];
  sectors?: string[];
};

const STATIC_PERSON_REFERENCE_LABELS = new Set([
  "官方资料",
  "人物资料",
  "公开材料",
]);

const STRONG_PERSON_MATERIAL_LABELS = new Set([
  "演讲",
  "采访",
  "公开对话",
  "著作",
  "股东信",
]);

const PERSON_ROUNDUP_TITLE_RE =
  /(?:早报|晨报|晚报|日报|周报|月报|要闻|盘点|速览|一览|汇总|热点|简报|roundup|daily briefing|weekly briefing)/iu;

const PERSON_ATTRIBUTION_RE =
  /(?:表示|称|说|谈|认为|指出|回应|警告|预测|呼吁|宣布|披露|透露|祝贺|批评|解释|强调|分享|直言|发声|\bsays?\b|\bsaid\b|\btalks?\b|\bargues?\b|\bwarns?\b|\bpredicts?\b|\bannounc(?:es|ed)\b|\bresponds?\b|\bcomments?\b|\bexplains?\b|\bdiscusses?\b)/iu;

const PERSON_RESEARCH_DOMAIN_RE =
  /(?:人工智能|大模型|模型|机器人|具身|芯片|半导体|晶圆|算力|数据中心|云计算|软件|开源|电池|储能|新能源|航天|火箭|卫星|量子|生物科技|药物|医药|医疗|融资|募资|投资|收购|并购|上市|监管|政策|技术|研发|论文|创业|初创|自动驾驶|材料|核聚变|风投|风险投资)|(?:\b(?:AI|AGI|LLM|GPU|HBM|IPO|startup|venture|funding|investment|acquisition|merger|research|paper|model|robot|robotics|chip|semiconductor|battery|space|rocket|satellite|quantum|biotech|drug|medical|software|cloud|datacenter|autonomous)\b)/iu;

const PERSON_PLACEHOLDER_ROLE_RE =
  /(?:待补充|待核验|pending|unknown|tbd)/iu;

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

function personIdentityLabels(profile: HomepagePersonProfile) {
  return [profile.name, profile.englishName, ...(profile.aliases ?? [])]
    .filter((value): value is string => Boolean(value?.trim()));
}

function personIdentityKeys(profile: HomepagePersonProfile) {
  return personIdentityLabels(profile)
    .map(normalizeHomepageEntityKey)
    .filter((key) => key.length >= 3);
}

function personAttributionKeys(profile: HomepagePersonProfile) {
  const keys = new Set<string>();
  for (const label of personIdentityLabels(profile)) {
    const middleDotParts = label.split(/[·•]/u);
    if (middleDotParts.length > 1) {
      const tail = normalizeHomepageEntityKey(middleDotParts.at(-1));
      if (tail.length >= 2) keys.add(tail);
    }

    const latinParts = label.match(/[A-Za-z]{4,}/gu) ?? [];
    const lastName = latinParts.at(-1)?.toLocaleLowerCase("en-US") ?? "";
    if (lastName.length >= 4) keys.add(lastName);
  }
  return [...keys];
}

function titleHasFullPersonIdentity(title: string, profile: HomepagePersonProfile) {
  const normalizedTitle = normalizeHomepageEntityKey(title);
  return personIdentityKeys(profile).some((key) => normalizedTitle.includes(key));
}

function titleHasAttributedPersonIdentity(
  title: string,
  profile: HomepagePersonProfile,
) {
  if (!PERSON_ATTRIBUTION_RE.test(title)) return false;
  const normalizedTitle = normalizeHomepageEntityKey(title);
  return personAttributionKeys(profile).some((key) => normalizedTitle.includes(key));
}

function sourceOwnedByPersonProfile(
  item: HomepagePersonDirectoryItem,
  profile: HomepagePersonProfile,
) {
  const sourceText = normalizeHomepageEntityKey(
    [
      item.source,
      item.href,
      ...(item.sources ?? []).flatMap((source) => [source.name, source.href]),
    ].join(" "),
  );
  const ownershipKeys = [
    ...personIdentityLabels(profile),
    ...(profile.handles ?? []),
    ...(profile.organizations ?? []),
  ]
    .map(normalizeHomepageEntityKey)
    .filter((key) => key.length >= 3);
  return ownershipKeys.some((key) => sourceText.includes(key));
}

function profileHasSparseIdentity(profile: HomepagePersonProfile) {
  const hasOrganization = (profile.organizations ?? []).some((value) => value.trim());
  const role = profile.role?.trim() ?? "";
  return !hasOrganization && (!role || PERSON_PLACEHOLDER_ROLE_RE.test(role));
}

function profileUsesLatinPrimaryIdentity(profile: HomepagePersonProfile) {
  return /^[A-Za-z\s.'’\-]+$/u.test(profile.name.trim());
}

function looksLikeRoundupTitle(title: string) {
  if (PERSON_ROUNDUP_TITLE_RE.test(title)) return true;
  const separators = title.match(/[；;]/gu)?.length ?? 0;
  return title.length >= 60 && separators >= 2;
}

/**
 * The people library is intentionally broader than the homepage event stream.
 * This second gate keeps durable profile/reference material and incidental NER
 * associations in the library while requiring homepage items to be dated,
 * person-central research/news signals.
 */
export function isHomepagePersonDirectoryEvent(
  item: HomepagePersonDirectoryItem,
  profile: HomepagePersonProfile,
) {
  const title = item.title.trim();
  if (!title || !item.href.trim() || !item.sortAt.trim()) return false;
  if (item.sourceGrade === "D") return false;
  if (STATIC_PERSON_REFERENCE_LABELS.has(item.label)) return false;
  if (item.sortAt.startsWith("0000-")) return false;
  if (looksLikeRoundupTitle(title)) return false;

  const hasFullIdentity = titleHasFullPersonIdentity(title, profile);
  const hasAttributedIdentity = titleHasAttributedPersonIdentity(title, profile);
  const ownedSource = sourceOwnedByPersonProfile(item, profile);

  // Auto-discovered profiles without an organization or verified role have a
  // higher homonym risk. Do not let a same-name podcast or lifestyle interview
  // become a research event. Latin-only sparse names are held back entirely
  // until identity context is enriched; CJK names still need an explicit name
  // in the title plus a technology/business/research-domain signal.
  if (profileHasSparseIdentity(profile)) {
    if (profileUsesLatinPrimaryIdentity(profile)) return false;
    return hasFullIdentity && PERSON_RESEARCH_DOMAIN_RE.test(title);
  }

  // Generic article-derived material and papers must make the person central
  // in the headline. A surname/short-form anchor is acceptable only when the
  // headline explicitly attributes a statement/action to that person.
  if (item.label === "人物材料" || item.label === "论文") {
    return hasFullIdentity || hasAttributedIdentity;
  }

  // First-person/primary-source formats can omit the speaker from the title if
  // the source itself is owned by the person or one of their organizations.
  if (STRONG_PERSON_MATERIAL_LABELS.has(item.label)) {
    return hasFullIdentity || hasAttributedIdentity || ownedSource;
  }

  return hasFullIdentity || hasAttributedIdentity;
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
    if (!profile || !isHomepagePersonDirectoryEvent(item, profile)) continue;

    const title = item.title.trim();
    const href = item.href.trim();
    const publishedAt = item.sortAt.trim();
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
      qualitySignals: ["人物库正式实体", "首页人物事件中心性", "人物材料目录"],
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
