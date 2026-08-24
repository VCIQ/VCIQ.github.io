import type { LiveIntelligenceEvent } from "./use-articles";

export const DEFAULT_DAILY_BRIEF_LIMIT = 10;

const SOURCE_LEVEL_POINTS: Record<LiveIntelligenceEvent["source"]["level"], number> = {
  官方披露: 10,
  原始材料: 9,
  监管文件: 9,
  媒体报道: 6,
  数据库记录: 5,
  待交叉验证: 2,
};

const TRACKING_PARAMS = new Set([
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_term",
  "utm_content",
  "utm_id",
  "gclid",
  "fbclid",
  "spm",
  "from",
  "source",
]);

function clampScore(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function normalizeText(value: string | undefined) {
  return (value ?? "").normalize("NFKC").trim().toLowerCase();
}

export function canonicalBriefUrl(rawUrl: string) {
  try {
    const url = new URL(rawUrl);
    url.hash = "";
    url.hostname = url.hostname.toLowerCase();
    for (const key of [...url.searchParams.keys()]) {
      if (TRACKING_PARAMS.has(key.toLowerCase()) || key.toLowerCase().startsWith("utm_")) {
        url.searchParams.delete(key);
      }
    }
    url.searchParams.sort();
    const pathname = url.pathname.replace(/\/+$/, "") || "/";
    const query = url.searchParams.toString();
    return `${url.hostname}${pathname}${query ? `?${query}` : ""}`;
  } catch {
    return normalizeText(rawUrl).replace(/#.*$/, "").replace(/\/+$/, "");
  }
}

export function normalizeBriefTitle(rawTitle: string) {
  return rawTitle
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[|｜].*$/, "")
    .replace(/[-—–]\s*[^-—–|｜]{0,24}(?:快讯|新闻|资讯|日报|周刊|观察|频道)\s*$/i, "")
    .replace(/三分之一/g, "1/3")
    .replace(/二分之一/g, "1/2")
    .replace(/四分之一/g, "1/4")
    .replace(/超过/g, "超")
    .replace(/以来/g, "")
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "");
}

function bigrams(value: string) {
  const normalized = normalizeBriefTitle(value);
  if (normalized.length < 2) return new Set(normalized ? [normalized] : []);
  const result = new Set<string>();
  for (let index = 0; index < normalized.length - 1; index += 1) {
    result.add(normalized.slice(index, index + 2));
  }
  return result;
}

export function briefTitleSimilarity(leftTitle: string, rightTitle: string) {
  const left = normalizeBriefTitle(leftTitle);
  const right = normalizeBriefTitle(rightTitle);
  if (!left || !right) return 0;
  if (left === right) return 1;
  if (left.includes(right) || right.includes(left)) {
    return Math.min(left.length, right.length) / Math.max(left.length, right.length);
  }

  const leftBigrams = bigrams(leftTitle);
  const rightBigrams = bigrams(rightTitle);
  if (!leftBigrams.size || !rightBigrams.size) return 0;

  let overlap = 0;
  for (const token of leftBigrams) {
    if (rightBigrams.has(token)) overlap += 1;
  }
  return (2 * overlap) / (leftBigrams.size + rightBigrams.size);
}

function entityKeys(item: LiveIntelligenceEvent) {
  return new Set(
    [
      item.company,
      ...(item.mentionedCompanies ?? []),
      ...(item.mentionedPeople ?? []),
      ...(item.matchedTrackingTerms ?? []),
    ]
      .map(normalizeText)
      .filter((value) => value.length >= 2),
  );
}

function sharesEntity(left: LiveIntelligenceEvent, right: LiveIntelligenceEvent) {
  const leftKeys = entityKeys(left);
  if (!leftKeys.size) return false;
  for (const key of entityKeys(right)) {
    if (leftKeys.has(key)) return true;
  }
  return false;
}

export function isDailyBriefDuplicate(
  left: LiveIntelligenceEvent,
  right: LiveIntelligenceEvent,
) {
  if (canonicalBriefUrl(left.source.url) === canonicalBriefUrl(right.source.url)) return true;
  if (
    left.eventClusterId &&
    right.eventClusterId &&
    left.eventClusterId === right.eventClusterId
  ) {
    return true;
  }

  const leftTitle = normalizeBriefTitle(left.title);
  const rightTitle = normalizeBriefTitle(right.title);
  if (leftTitle && leftTitle === rightTitle) return true;

  const similarity = briefTitleSimilarity(left.title, right.title);
  const sameDay = left.publishedAt === right.publishedAt;
  const sameTaxonomy = left.type === right.type && left.sector === right.sector;

  if (similarity >= 0.72) return true;
  return similarity >= 0.48 && sameDay && (sharesEntity(left, right) || sameTaxonomy);
}

export function dailyBriefScore(item: LiveIntelligenceEvent) {
  const quality = item.qualityScore ?? Math.max(60, item.importance - 10);
  const corroboration = Math.min(Math.max((item.duplicateCount ?? 1) - 1, 0), 4);
  const curatedBonus = item.curated ? 2 : 0;
  return clampScore(
    item.importance * 0.62 +
      quality * 0.2 +
      SOURCE_LEVEL_POINTS[item.source.level] +
      corroboration +
      curatedBonus,
  );
}

function compareDailyBriefCandidates(
  left: LiveIntelligenceEvent,
  right: LiveIntelligenceEvent,
) {
  return (
    dailyBriefScore(right) - dailyBriefScore(left) ||
    right.importance - left.importance ||
    (right.qualityScore ?? 0) - (left.qualityScore ?? 0) ||
    (right.duplicateCount ?? 1) - (left.duplicateCount ?? 1) ||
    right.publishedAt.localeCompare(left.publishedAt) ||
    left.title.localeCompare(right.title, "zh-CN")
  );
}

function primaryEntityKey(item: LiveIntelligenceEvent) {
  return normalizeText(
    item.company || item.mentionedCompanies?.[0] || item.mentionedPeople?.[0] || "",
  );
}

function sourceKey(item: LiveIntelligenceEvent) {
  return normalizeText(item.source.name || item.source.platform || canonicalBriefUrl(item.source.url));
}

function wouldDuplicate(
  candidate: LiveIntelligenceEvent,
  selected: LiveIntelligenceEvent[],
) {
  return selected.some((item) => isDailyBriefDuplicate(candidate, item));
}

export function selectDailyBriefEvents(
  candidates: LiveIntelligenceEvent[],
  limit = DEFAULT_DAILY_BRIEF_LIMIT,
) {
  if (limit <= 0 || !candidates.length) return [];

  const ranked = [...candidates].sort(compareDailyBriefCandidates);
  const selected: LiveIntelligenceEvent[] = [];
  const sourceCounts = new Map<string, number>();
  const entityCounts = new Map<string, number>();
  const sectorCounts = new Map<string, number>();

  const add = (item: LiveIntelligenceEvent) => {
    selected.push(item);
    const source = sourceKey(item);
    const entity = primaryEntityKey(item);
    sourceCounts.set(source, (sourceCounts.get(source) ?? 0) + 1);
    if (entity) entityCounts.set(entity, (entityCounts.get(entity) ?? 0) + 1);
    sectorCounts.set(item.sector, (sectorCounts.get(item.sector) ?? 0) + 1);
  };

  for (const item of ranked) {
    if (selected.length >= limit) break;
    if (wouldDuplicate(item, selected)) continue;

    const source = sourceKey(item);
    const entity = primaryEntityKey(item);
    if ((sourceCounts.get(source) ?? 0) >= 2) continue;
    if (entity && (entityCounts.get(entity) ?? 0) >= 2) continue;
    if ((sectorCounts.get(item.sector) ?? 0) >= 4) continue;
    add(item);
  }

  // Diversity is a ranking preference, not a reason to leave the brief half-empty.
  // The second pass relaxes concentration caps while preserving event-level dedupe.
  if (selected.length < limit) {
    for (const item of ranked) {
      if (selected.length >= limit) break;
      if (selected.some((selectedItem) => selectedItem.id === item.id)) continue;
      if (wouldDuplicate(item, selected)) continue;
      add(item);
    }
  }

  return selected;
}
