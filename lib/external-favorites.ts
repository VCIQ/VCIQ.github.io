import type { FavoriteInput, FavoriteItem } from "@/lib/favorites";
import { buildTrackingCaptureLink } from "@/lib/tracking-admin-link";

export type ExternalFavoriteCategory =
  | "reference"
  | "technology"
  | "company"
  | "person"
  | "source";

export type ExternalFavoriteDraft = {
  url: string;
  title: string;
  summary?: string;
  sourceName?: string;
  category?: ExternalFavoriteCategory;
  keywords?: string[] | string;
  sectors?: string[] | string;
  publishedAt?: string;
};

const CATEGORY_META: Record<
  ExternalFavoriteCategory,
  Pick<FavoriteInput, "channel" | "channelLabel">
> = {
  reference: { channel: "reports", channelLabel: "外部研究资料" },
  technology: { channel: "technology", channelLabel: "技术 / 赛道线索" },
  company: { channel: "companies", channelLabel: "公司线索" },
  person: { channel: "people", channelLabel: "人物线索" },
  source: { channel: "institutions", channelLabel: "信源线索" },
};

const TRACKING_QUERY_KEYS = new Set([
  "from",
  "share",
  "share_token",
  "spm",
  "utm_campaign",
  "utm_content",
  "utm_medium",
  "utm_source",
  "utm_term",
]);

function clean(value: string | undefined, limit: number): string {
  return (value ?? "").normalize("NFKC").replace(/\s+/g, " ").trim().slice(0, limit);
}

function splitValues(value: string[] | string | undefined, limit: number): string[] {
  const raw = Array.isArray(value) ? value : (value ?? "").split(/[|｜,，、;；\n\r]+/u);
  const seen = new Set<string>();
  const result: string[] = [];
  for (const entry of raw) {
    const item = clean(String(entry), 100);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    seen.add(key);
    result.push(item);
    if (result.length >= limit) break;
  }
  return result;
}

export function canonicalExternalArticleUrl(value: string): string {
  const raw = clean(value, 1200);
  if (!raw) return "";
  try {
    const url = new URL(raw);
    if (!["http:", "https:"].includes(url.protocol)) return "";
    url.hash = "";
    for (const key of [...url.searchParams.keys()]) {
      if (TRACKING_QUERY_KEYS.has(key.toLocaleLowerCase("en-US")) || key.toLocaleLowerCase("en-US").startsWith("utm_")) {
        url.searchParams.delete(key);
      }
    }
    if (url.pathname !== "/") url.pathname = url.pathname.replace(/\/+$/, "") || "/";
    return url.href;
  } catch {
    return "";
  }
}

function stableHash(value: string): string {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(36);
}

export function externalFavoriteId(url: string): string {
  const canonical = canonicalExternalArticleUrl(url);
  if (!canonical) return "";
  const host = new URL(canonical).hostname.replace(/^www\./i, "").slice(0, 72);
  return `external:article:${host}:${stableHash(canonical)}`;
}

export function buildExternalFavoriteInput(draft: ExternalFavoriteDraft): FavoriteInput | null {
  const href = canonicalExternalArticleUrl(draft.url);
  const title = clean(draft.title, 240);
  if (!href || !title) return null;

  const category = draft.category ?? "reference";
  const categoryMeta = CATEGORY_META[category] ?? CATEGORY_META.reference;
  const host = new URL(href).hostname.replace(/^www\./i, "");
  const sourceName = clean(draft.sourceName, 120) || host;
  const keywords = splitValues(draft.keywords, 40);
  const sectors = splitValues(draft.sectors, 20);
  const publishedAt = clean(draft.publishedAt, 20);

  return {
    id: externalFavoriteId(href),
    href,
    title,
    summary: clean(draft.summary, 1200),
    channel: categoryMeta.channel,
    channelLabel: categoryMeta.channelLabel,
    keywords,
    sectors,
    sources: [{ name: sourceName, url: href, level: "外部研究资料" }],
    ...( /^\d{4}-\d{2}-\d{2}$/.test(publishedAt) ? { publishedAt } : {} ),
    eventType: "外部资料",
  };
}

export function isExternalFavorite(item: Pick<FavoriteItem, "href">): boolean {
  return /^https?:\/\//i.test(item.href);
}

export function researchLeadHrefForFavorite(
  item: Pick<FavoriteItem, "href" | "title" | "summary" | "keywords" | "sectors" | "sources" | "channelLabel">,
): string {
  return buildTrackingCaptureLink({
    url: item.href,
    title: item.title,
    summary: item.summary,
    keywords: [...new Set([...item.sectors, ...item.keywords])].slice(0, 30),
    source: item.sources[0]?.name,
    channel: `favorites:${item.channelLabel}`,
  });
}

export const externalFavoriteCategoryOptions: Array<{
  value: ExternalFavoriteCategory;
  label: string;
}> = [
  { value: "reference", label: "外部研究资料" },
  { value: "technology", label: "技术 / 赛道线索" },
  { value: "company", label: "公司线索" },
  { value: "person", label: "人物线索" },
  { value: "source", label: "信源线索" },
];
