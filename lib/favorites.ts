import { syncFavoritePreference } from "@/lib/favorite-preference-sync";

export const FAVORITES_STORAGE_KEY = "vciq:favorites:v1";
export const FAVORITES_CHANGED_EVENT = "vciq:favorites-changed";
export const FAVORITES_SCHEMA_VERSION = 1;

/**
 * `ipo` is retained only as an input compatibility alias for old DOM markers
 * and browser storage. normalizeFavorite always converts it to `companies`, so
 * persisted favorites and public groupings contain no independent IPO channel.
 */
export type FavoriteChannel =
  | "technology"
  | "companies"
  | "institutions"
  | "ipo"
  | "reports"
  | "people";

export type FavoriteStoredChannel = Exclude<FavoriteChannel, "ipo">;

export type FavoriteSource = {
  name: string;
  url: string;
  level?: string;
};

export type FavoriteInput = {
  id: string;
  href: string;
  title: string;
  summary: string;
  channel: FavoriteChannel;
  channelLabel: string;
  keywords?: string[];
  sectors?: string[];
  sources?: FavoriteSource[];
  region?: string;
  company?: string;
  publishedAt?: string;
  importance?: number;
  eventType?: string;
};

export type FavoriteItem = Omit<
  FavoriteInput,
  "channel" | "keywords" | "sectors" | "sources"
> & {
  channel: FavoriteStoredChannel;
  keywords: string[];
  sectors: string[];
  sources: FavoriteSource[];
  savedAt: string;
};

type FavoritePayload = {
  schemaVersion: 1;
  items: FavoriteItem[];
};

const MAX_FAVORITES = 300;
const MAX_KEYWORDS = 40;
const MAX_SOURCES = 20;
const EMPTY_FAVORITES: FavoriteItem[] = [];
const EMPTY_FAVORITE_IDS = new Set<string>();

let cachedStorageRaw: string | null | undefined;
let cachedFavoriteItems: FavoriteItem[] = EMPTY_FAVORITES;
let cachedFavoriteIds = EMPTY_FAVORITE_IDS;
const favoriteSubscribers = new Set<() => void>();
let browserListenersAttached = false;

function cleanText(value: unknown, maxLength: number): string {
  if (typeof value !== "string") return "";
  return value.normalize("NFKC").replace(/\s+/g, " ").trim().slice(0, maxLength);
}

function uniqueStrings(value: unknown, limit: number): string[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const result: string[] = [];
  for (const raw of value) {
    const item = cleanText(raw, 100);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    seen.add(key);
    result.push(item);
    if (result.length >= limit) break;
  }
  return result;
}

function validHttpUrl(value: unknown): string {
  if (typeof value !== "string") return "";
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

function normalizeSources(value: unknown): FavoriteSource[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const result: FavoriteSource[] = [];
  for (const raw of value) {
    if (!raw || typeof raw !== "object") continue;
    const source = raw as Record<string, unknown>;
    const url = validHttpUrl(source.url);
    let host = "";
    try {
      host = new URL(url).hostname.replace(/^www\./, "").toLocaleLowerCase("en-US");
    } catch {
      continue;
    }
    if (!host || seen.has(host)) continue;
    seen.add(host);
    result.push({
      name: cleanText(source.name, 120) || host,
      url,
      ...(cleanText(source.level, 40)
        ? { level: cleanText(source.level, 40) }
        : {}),
    });
    if (result.length >= MAX_SOURCES) break;
  }
  return result;
}

function normalizeHref(value: unknown): string {
  const href = cleanText(value, 1000);
  if (!href) return "";
  if (href.startsWith("/") && !href.startsWith("//")) {
    try {
      const url = new URL(href, "https://vciq.local");
      if (url.pathname === "/read/" || url.pathname === "/read") {
        const original = validHttpUrl(url.searchParams.get("url"));
        if (original) return original;
      }
      const pathname = url.pathname.endsWith("/")
        ? url.pathname
        : `${url.pathname}/`;
      return `${pathname}${url.search}${url.hash}`;
    } catch {
      return "";
    }
  }
  return validHttpUrl(href);
}

function migrateLegacyIpoHref(href: string) {
  const match = href.match(/^\/ipo\/([^/?#]+)\/?(?:[?#].*)?$/u);
  return match ? `/companies/${match[1]}/` : href === "/ipo/" ? "/companies/" : href;
}

function normalizePublishedAt(value: unknown): string | undefined {
  const date = cleanText(value, 20);
  return /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : undefined;
}

function normalizeImportance(value: unknown): number | undefined {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) return undefined;
  return Math.max(0, Math.min(100, Math.round(number)));
}

const CHANNELS = new Set<FavoriteStoredChannel>([
  "technology",
  "companies",
  "institutions",
  "reports",
  "people",
]);

function normalizedChannelLabel(channel: FavoriteStoredChannel, value: unknown) {
  const label = cleanText(value, 40);
  if (channel === "technology" && ["新兴科技", "赛道研究"].includes(label)) {
    return "核心赛道";
  }
  if (channel === "companies" && ["创业案例", "上市跟踪"].includes(label)) {
    return "核心公司";
  }
  if (channel === "people" && label === "人物研究") {
    return "核心人物";
  }
  return label || channel;
}

export function normalizeFavorite(
  value: unknown,
  fallbackSavedAt = new Date().toISOString(),
): FavoriteItem | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const legacyIpo = raw.channel === "ipo";
  const channel: FavoriteStoredChannel | null = legacyIpo
    ? "companies"
    : typeof raw.channel === "string" && CHANNELS.has(raw.channel as FavoriteStoredChannel)
      ? (raw.channel as FavoriteStoredChannel)
      : null;
  const id = cleanText(raw.id, 180);
  const normalizedHref = normalizeHref(raw.href);
  const href = legacyIpo ? migrateLegacyIpoHref(normalizedHref) : normalizedHref;
  const title = cleanText(raw.title, 240);
  if (!channel || !id || !href || !title) return null;

  const savedAtRaw = cleanText(raw.savedAt, 40);
  const savedAt = Number.isNaN(Date.parse(savedAtRaw))
    ? fallbackSavedAt
    : savedAtRaw;
  const region = cleanText(raw.region, 80) || undefined;
  const publishedAt = normalizePublishedAt(raw.publishedAt);
  const importance = normalizeImportance(raw.importance);
  const eventType = cleanText(raw.eventType, 40);

  return {
    id,
    href,
    title,
    summary: cleanText(raw.summary, 1200),
    channel,
    channelLabel: legacyIpo
      ? "核心公司"
      : normalizedChannelLabel(channel, raw.channelLabel),
    keywords: uniqueStrings(raw.keywords, MAX_KEYWORDS),
    sectors: uniqueStrings(raw.sectors, 20),
    sources: normalizeSources(raw.sources),
    ...(region ? { region } : {}),
    ...(cleanText(raw.company, 120)
      ? { company: cleanText(raw.company, 120) }
      : {}),
    ...(publishedAt ? { publishedAt } : {}),
    ...(importance !== undefined ? { importance } : {}),
    ...(eventType ? { eventType } : {}),
    savedAt,
  };
}

export function parseFavoriteItems(value: string | null): FavoriteItem[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value) as unknown;
    const rawItems = Array.isArray(parsed)
      ? parsed
      : parsed &&
          typeof parsed === "object" &&
          Array.isArray((parsed as Record<string, unknown>).items)
        ? ((parsed as Record<string, unknown>).items as unknown[])
        : [];
    const seen = new Set<string>();
    const items: FavoriteItem[] = [];
    for (const raw of rawItems) {
      const item = normalizeFavorite(raw);
      if (!item || seen.has(item.id)) continue;
      seen.add(item.id);
      items.push(item);
      if (items.length >= MAX_FAVORITES) break;
    }
    return items.sort((left, right) => right.savedAt.localeCompare(left.savedAt));
  } catch {
    return [];
  }
}

function browserStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function setFavoriteCache(raw: string | null, items: FavoriteItem[]) {
  cachedStorageRaw = raw;
  cachedFavoriteItems = items;
  cachedFavoriteIds = new Set(items.map((item) => item.id));
}

function syncFavoriteCache(): boolean {
  const storage = browserStorage();
  if (!storage) return false;
  const raw = storage.getItem(FAVORITES_STORAGE_KEY);
  if (raw === cachedStorageRaw) return false;
  setFavoriteCache(raw, parseFavoriteItems(raw));
  return true;
}

function notifyFavoriteSubscribers() {
  for (const subscriber of favoriteSubscribers) subscriber();
}

function onFavoritesChanged() {
  if (syncFavoriteCache()) notifyFavoriteSubscribers();
}

function onFavoriteStorage(event: StorageEvent) {
  if (event.key !== FAVORITES_STORAGE_KEY) return;
  if (syncFavoriteCache()) notifyFavoriteSubscribers();
}

function ensureFavoriteBrowserListeners() {
  if (
    browserListenersAttached ||
    typeof window === "undefined" ||
    typeof window.addEventListener !== "function"
  ) {
    return;
  }
  window.addEventListener(FAVORITES_CHANGED_EVENT, onFavoritesChanged);
  window.addEventListener("storage", onFavoriteStorage);
  browserListenersAttached = true;
}

function releaseFavoriteBrowserListeners() {
  if (
    !browserListenersAttached ||
    typeof window === "undefined" ||
    typeof window.removeEventListener !== "function"
  ) {
    return;
  }
  window.removeEventListener(FAVORITES_CHANGED_EVENT, onFavoritesChanged);
  window.removeEventListener("storage", onFavoriteStorage);
  browserListenersAttached = false;
}

export function subscribeFavorites(subscriber: () => void): () => void {
  ensureFavoriteBrowserListeners();
  favoriteSubscribers.add(subscriber);
  return () => {
    favoriteSubscribers.delete(subscriber);
    if (!favoriteSubscribers.size) releaseFavoriteBrowserListeners();
  };
}

export function readFavoriteItems(): FavoriteItem[] {
  const storage = browserStorage();
  if (!storage) return EMPTY_FAVORITES;
  syncFavoriteCache();
  return cachedFavoriteItems;
}

export function getFavoriteSnapshot(): FavoriteItem[] {
  return readFavoriteItems();
}

export function getFavoriteIdSnapshot(): Set<string> {
  const storage = browserStorage();
  if (!storage) return EMPTY_FAVORITE_IDS;
  syncFavoriteCache();
  return cachedFavoriteIds;
}

function writeFavoriteItems(items: FavoriteItem[]): void {
  const storage = browserStorage();
  if (!storage) return;
  const nextItems = items.slice(0, MAX_FAVORITES);
  const payload: FavoritePayload = {
    schemaVersion: FAVORITES_SCHEMA_VERSION,
    items: nextItems,
  };
  const serialized = JSON.stringify(payload);
  storage.setItem(FAVORITES_STORAGE_KEY, serialized);
  setFavoriteCache(serialized, nextItems);
  notifyFavoriteSubscribers();
  window.dispatchEvent(new CustomEvent(FAVORITES_CHANGED_EVENT));
}

export function isFavorite(id: string): boolean {
  getFavoriteIdSnapshot();
  return cachedFavoriteIds.has(id);
}

export function toggleFavorite(input: FavoriteInput): boolean {
  const current = readFavoriteItems();
  const existingItem = current.find((item) => item.id === input.id);
  if (existingItem) {
    // Local favorite state remains authoritative for UX. Preference sync is
    // additive and deliberately cannot make an un-favorite operation fail.
    writeFavoriteItems(current.filter((item) => item.id !== input.id));
    void syncFavoritePreference("remove", existingItem);
    return false;
  }
  const item = normalizeFavorite({
    ...input,
    savedAt: new Date().toISOString(),
  });
  if (!item) return false;
  writeFavoriteItems([item, ...current.filter((entry) => entry.id !== item.id)]);
  void syncFavoritePreference("save", item);
  return true;
}

export function removeFavorite(id: string): void {
  const current = readFavoriteItems();
  const existingItem = current.find((item) => item.id === id);
  writeFavoriteItems(current.filter((item) => item.id !== id));
  if (existingItem) void syncFavoritePreference("remove", existingItem);
}
