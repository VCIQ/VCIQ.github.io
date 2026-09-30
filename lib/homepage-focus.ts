import type { FavoriteItem } from "@/lib/favorites";
import type { HomepagePreferenceState } from "@/lib/homepage-preferences";
import { homepageEventIdentityKeys, homepageMaterialUrl } from "@/lib/homepage-event-identity";
import type { HotnessItem } from "@/lib/hotness";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

/** A versioned editorial rule, not a learned/calibrated prediction of interest. */
export const HOMEPAGE_FOCUS_POLICY = Object.freeze({
  version: "personal-focus-v1",
  maxItems: 24,
  freshnessDays: 7,
  behaviorWindowDays: 90,
  minimumImportance: 75,
  broadTrackMinimumImportance: 85,
});
const DAY = 86_400_000;
const GENERIC = new Set([
  "", "ai", "agi", "ai / agi", "人工智能", "芯片", "半导体", "机器人", "科技产业",
  "科技公司", "公司", "中国", "美国", "全球", "未知", "未明确", "未分类", "并购",
  "融资", "产业投资", "公司动态", "产品发布", "技术突破", "风险投资", "商业进展",
]);
const MATERIAL_EVENT = /收购|并购|签署|融资|量产|订单|发布|突破|获批|监管|上市|IPO|acquir|acquisition|merger|funding|launch|release|breakthrough|approval|world model|世界模型/iu;

function normalized(value: string | undefined): string {
  return (value ?? "").normalize("NFKC").replace(/\s+/gu, " ").trim().toLowerCase();
}
function meaningful(value: string): boolean {
  const key = normalized(value);
  return key.length >= 2 && key.length <= 100 && !GENERIC.has(key);
}
function searchable(item: LiveIntelligenceEvent): string {
  return normalized([item.title, item.summary, item.company, item.sector,
    ...(item.mentionedCompanies ?? []), ...(item.mentionedPeople ?? []),
    ...(item.matchedTrackingTerms ?? [])].join(" "));
}
function contains(haystack: string, needle: string): boolean {
  const key = normalized(needle);
  if (!meaningful(key)) return false;
  if (/^[a-z0-9 ._-]+$/u.test(key)) {
    const escaped = key.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
    return new RegExp(`(^|[^a-z0-9])${escaped}($|[^a-z0-9])`, "u").test(haystack);
  }
  return haystack.includes(key);
}
function evidenceAnchors(item: LiveIntelligenceEvent): string[] {
  return [...new Set([item.company, ...(item.mentionedCompanies ?? []),
    ...(item.mentionedPeople ?? []), ...(item.matchedTrackingTerms ?? [])]
    .filter((x): x is string => typeof x === "string" && meaningful(x)).map(normalized))].slice(0, 12);
}
function recent(value: string | undefined, now: number, days: number): boolean {
  const date = Date.parse(value ?? "");
  return Number.isFinite(date) && date <= now + DAY && now - date <= days * DAY;
}
function identityKeys(item: LiveIntelligenceEvent): string[] {
  // Background references are not proof of identical events. A later closing
  // announcement may cite an earlier agreement without inheriting its veto.
  return homepageEventIdentityKeys(item);
}

export type HomepageFocusDecision = {
  eligible: boolean;
  signal: "tracking" | "share" | "favorite" | "none";
  signalTier: number;
  readTieBreak: number;
  reasons: string[];
  exclusion?: "dismissed" | "low-quality" | "stale" | "low-impact" | "no-personal-signal";
};
export type HomepageFocusSelection = {
  items: LiveIntelligenceEvent[];
  decisions: Map<string, HomepageFocusDecision>;
  profileScope: "this-browser";
  policyVersion: string;
  distinctSharedTargets: number;
};

export function buildHomepageFocusSelection(
  candidates: readonly LiveIntelligenceEvent[],
  preferences: HomepagePreferenceState,
  favorites: readonly FavoriteItem[],
  history: readonly HotnessItem[],
  nowMs: number,
): HomepageFocusSelection {
  const now = Number.isFinite(nowMs) ? nowMs : 0;
  const dismissed = new Set(preferences.dismissedEventIds);
  // Expand the existing event/item veto through exact material/cluster identities.
  // A second feed or a repost must not resurrect a dismissed event.
  const vetoKeys = new Set<string>();
  const keyOwners = new Map<string, number[]>();
  candidates.forEach((item, index) => identityKeys(item).forEach((key) => {
    const owners = keyOwners.get(key) ?? []; owners.push(index); keyOwners.set(key, owners);
  }));
  const blocked = new Set<number>(); const queue: number[] = [];
  candidates.forEach((item, index) => {
    if (dismissed.has(item.id) || dismissed.has(item.eventClusterId ?? "")) {
      blocked.add(index); queue.push(index);
    }
  });
  for (let head = 0; head < queue.length; head++) {
    for (const key of identityKeys(candidates[queue[head]])) {
      if (vetoKeys.has(key)) continue;
      vetoKeys.add(key);
      for (const index of keyOwners.get(key) ?? []) if (!blocked.has(index)) {
        blocked.add(index); queue.push(index);
      }
    }
  }
  const byUrl = new Map(candidates.map((item) => [homepageMaterialUrl(item.source.url), item]));
  const universe = [...new Set(candidates.flatMap(evidenceAnchors))].slice(0, 256);
  const sharedUrls = new Set<string>();
  const sharedAnchors = new Set<string>();
  const readUrls = new Set<string>();
  for (const row of history.slice(0, 500)) {
    const key = homepageMaterialUrl(row.href);
    if (!key) continue;
    if (row.opens > 0 && recent(row.lastOpenedAt, now, 30)) readUrls.add(key);
    if (!(row.shares > 0) || !recent(row.lastSharedAt, now, HOMEPAGE_FOCUS_POLICY.behaviorWindowDays)) continue;
    if (sharedUrls.has(key)) continue; // Frequency is not independent evidence.
    sharedUrls.add(key);
    const item = byUrl.get(key);
    const text = normalized(`${row.title} ${row.summary}`);
    for (const anchor of item ? evidenceAnchors(item) : universe.filter((x) => contains(text, x))) {
      sharedAnchors.add(anchor);
    }
  }
  const favoriteUrls = new Set<string>();
  const favoriteAnchors = new Set<string>();
  for (const row of favorites.slice(0, 500)) {
    // Only current favorites are supplied: an unsave removes its contribution.
    if (!recent(row.savedAt, now, HOMEPAGE_FOCUS_POLICY.behaviorWindowDays)) continue;
    const url = homepageMaterialUrl(row.href);
    if (url) favoriteUrls.add(url);
    for (const term of [row.company, ...row.keywords]) {
      if (typeof term === "string" && meaningful(term)) favoriteAnchors.add(normalized(term));
    }
  }
  const followed = new Set(preferences.followedSectors.map(normalized));
  const decisions = new Map<string, HomepageFocusDecision>();
  for (const item of candidates) {
    const result: HomepageFocusDecision = { eligible: false, signal: "none", signalTier: 0, readTieBreak: 0, reasons: [] };
    decisions.set(item.id, result);
    if (dismissed.has(item.id) || dismissed.has(item.eventClusterId ?? "") || identityKeys(item).some((key) => vetoKeys.has(key))) {
      result.exclusion = "dismissed"; continue;
    }
    if (item.qualityStatus === "低可信" || (typeof item.qualityScore === "number" && item.qualityScore < 50)) {
      result.exclusion = "low-quality"; continue;
    }
    if (!recent(item.publishedAt, now, HOMEPAGE_FOCUS_POLICY.freshnessDays)) {
      result.exclusion = "stale"; continue;
    }
    if (!Number.isFinite(item.importance) || item.importance < HOMEPAGE_FOCUS_POLICY.minimumImportance ||
      !MATERIAL_EVENT.test(`${item.type} ${item.title}`)) {
      result.exclusion = "low-impact"; continue;
    }
    const text = searchable(item);
    const url = homepageMaterialUrl(item.source.url);
    const trackedTerms = (item.matchedTrackingTerms ?? []).filter(meaningful);
    const exactTracking = trackedTerms.length > 0;
    const followedTrack = followed.has(normalized(item.sector)) && item.importance >= HOMEPAGE_FOCUS_POLICY.broadTrackMinimumImportance;
    const shareAnchor = [...sharedAnchors].find((key) => contains(text, key));
    const favoriteAnchor = [...favoriteAnchors].find((key) => contains(text, key));
    if (exactTracking || followedTrack) {
      result.signal = "tracking"; result.signalTier = 3;
      result.reasons.push(exactTracking ? `命中站点追踪词：${trackedTerms.slice(0, 2).join("、")}` : `你关注的「${item.sector}」出现重要更新`);
    } else if (sharedUrls.has(url) || shareAnchor) {
      result.signal = "share"; result.signalTier = 2;
      result.reasons.push(sharedUrls.has(url) ? "你分享过这条信息" : `与你分享内容中的「${shareAnchor}」有关`);
    } else if (favoriteUrls.has(url) || favoriteAnchor) {
      result.signal = "favorite"; result.signalTier = 1;
      result.reasons.push(favoriteUrls.has(url) ? "这条信息在你的收藏／稍后读中" : `与你收藏内容中的「${favoriteAnchor}」有关`);
    } else {
      result.exclusion = "no-personal-signal"; continue;
    }
    result.eligible = true;
    result.readTieBreak = readUrls.has(url) ? 1 : 0;
    result.reasons.push(`重要度 ${item.importance} · 最近 ${HOMEPAGE_FOCUS_POLICY.freshnessDays} 天的实质更新`);
    if (item.source.level === "媒体报道" || item.source.level === "待交叉验证") result.reasons.push("媒体陈述不等于事实已核实");
  }
  const sorted = candidates.filter((item) => decisions.get(item.id)?.eligible).sort((left, right) => {
    const a = decisions.get(left.id)!; const b = decisions.get(right.id)!;
    return b.signalTier - a.signalTier || Date.parse(right.publishedAt) - Date.parse(left.publishedAt) ||
      right.importance - left.importance || b.readTieBreak - a.readTieBreak || left.id.localeCompare(right.id);
  });
  const seen = new Set<string>();
  const items = sorted.filter((item) => {
    const keys = identityKeys(item);
    if (keys.some((key) => seen.has(key))) return false;
    keys.forEach((key) => seen.add(key)); return true;
  }).slice(0, HOMEPAGE_FOCUS_POLICY.maxItems);
  return { items, decisions, profileScope: "this-browser", policyVersion: HOMEPAGE_FOCUS_POLICY.version, distinctSharedTargets: sharedUrls.size };
}
