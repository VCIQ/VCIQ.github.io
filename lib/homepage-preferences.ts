export const HOMEPAGE_PREFERENCES_STORAGE_KEY = "vciq:homepage-preferences:v1";
export const HOMEPAGE_PREFERENCES_CHANGED_EVENT = "vciq:homepage-preferences-changed";

export type HomepagePreferenceState = {
  schemaVersion: 1;
  followedSectors: string[];
  dismissedEventIds: string[];
  sectorDislikes: Record<string, number>;
};

const MAX_FOLLOWED_SECTORS = 40;
const MAX_DISMISSED_EVENTS = 300;
const MAX_SECTOR_DISLIKES = 4;

export const EMPTY_HOMEPAGE_PREFERENCES: HomepagePreferenceState = Object.freeze({
  schemaVersion: 1,
  followedSectors: Object.freeze([]) as unknown as string[],
  dismissedEventIds: Object.freeze([]) as unknown as string[],
  sectorDislikes: Object.freeze({}) as Record<string, number>,
});

let cachedStorageRaw: string | null | undefined;
let cachedState: HomepagePreferenceState = EMPTY_HOMEPAGE_PREFERENCES;
const subscribers = new Set<() => void>();
let browserListenersAttached = false;

function cleanText(value: unknown, maxLength = 120) {
  if (typeof value !== "string") return "";
  return value.normalize("NFKC").replace(/\s+/g, " ").trim().slice(0, maxLength);
}

function uniqueStrings(value: unknown, limit: number) {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of value) {
    const item = cleanText(raw, 180);
    const key = item.toLocaleLowerCase("zh-CN");
    if (!item || seen.has(key)) continue;
    seen.add(key);
    result.push(item);
    if (result.length >= limit) break;
  }
  return result;
}

function normalizeSectorDislikes(value: unknown) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const result: Record<string, number> = {};
  for (const [rawSector, rawCount] of Object.entries(value as Record<string, unknown>)) {
    const sector = cleanText(rawSector, 120);
    const count = Math.trunc(Number(rawCount));
    if (!sector || !Number.isFinite(count) || count <= 0) continue;
    result[sector] = Math.min(MAX_SECTOR_DISLIKES, count);
    if (Object.keys(result).length >= MAX_FOLLOWED_SECTORS) break;
  }
  return result;
}

export function normalizeHomepagePreferenceState(value: unknown): HomepagePreferenceState {
  const raw = value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
  return {
    schemaVersion: 1,
    followedSectors: uniqueStrings(raw.followedSectors, MAX_FOLLOWED_SECTORS),
    dismissedEventIds: uniqueStrings(raw.dismissedEventIds, MAX_DISMISSED_EVENTS),
    sectorDislikes: normalizeSectorDislikes(raw.sectorDislikes),
  };
}

export function parseHomepagePreferenceState(value: string | null): HomepagePreferenceState {
  if (!value) return EMPTY_HOMEPAGE_PREFERENCES;
  try {
    return normalizeHomepagePreferenceState(JSON.parse(value) as unknown);
  } catch {
    return EMPTY_HOMEPAGE_PREFERENCES;
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

function setCache(raw: string | null, state: HomepagePreferenceState) {
  cachedStorageRaw = raw;
  cachedState = state;
}

function syncCache() {
  const storage = browserStorage();
  if (!storage) return false;
  const raw = storage.getItem(HOMEPAGE_PREFERENCES_STORAGE_KEY);
  if (raw === cachedStorageRaw) return false;
  setCache(raw, parseHomepagePreferenceState(raw));
  return true;
}

function notifySubscribers() {
  for (const subscriber of subscribers) subscriber();
}

function onPreferenceStorage(event: StorageEvent) {
  if (event.key !== HOMEPAGE_PREFERENCES_STORAGE_KEY) return;
  if (syncCache()) notifySubscribers();
}

function onPreferenceChanged() {
  if (syncCache()) notifySubscribers();
}

function ensureBrowserListeners() {
  if (browserListenersAttached || typeof window === "undefined") return;
  window.addEventListener("storage", onPreferenceStorage);
  window.addEventListener(HOMEPAGE_PREFERENCES_CHANGED_EVENT, onPreferenceChanged);
  browserListenersAttached = true;
}

function releaseBrowserListeners() {
  if (!browserListenersAttached || typeof window === "undefined") return;
  window.removeEventListener("storage", onPreferenceStorage);
  window.removeEventListener(HOMEPAGE_PREFERENCES_CHANGED_EVENT, onPreferenceChanged);
  browserListenersAttached = false;
}

function writeState(next: HomepagePreferenceState) {
  const storage = browserStorage();
  if (!storage) return;
  const normalized = normalizeHomepagePreferenceState(next);
  const serialized = JSON.stringify(normalized);
  storage.setItem(HOMEPAGE_PREFERENCES_STORAGE_KEY, serialized);
  setCache(serialized, normalized);
  notifySubscribers();
  window.dispatchEvent(new CustomEvent(HOMEPAGE_PREFERENCES_CHANGED_EVENT));
}

export function subscribeHomepagePreferences(subscriber: () => void) {
  ensureBrowserListeners();
  subscribers.add(subscriber);
  return () => {
    subscribers.delete(subscriber);
    if (!subscribers.size) releaseBrowserListeners();
  };
}

export function getHomepagePreferenceSnapshot(): HomepagePreferenceState {
  const storage = browserStorage();
  if (!storage) return EMPTY_HOMEPAGE_PREFERENCES;
  syncCache();
  return cachedState;
}

export function toggleHomepageSectorFollow(sectorValue: string) {
  const sector = cleanText(sectorValue, 120);
  if (!sector) return false;
  const current = getHomepagePreferenceSnapshot();
  const exists = current.followedSectors.some(
    (item) => item.toLocaleLowerCase("zh-CN") === sector.toLocaleLowerCase("zh-CN"),
  );
  writeState({
    ...current,
    followedSectors: exists
      ? current.followedSectors.filter(
          (item) => item.toLocaleLowerCase("zh-CN") !== sector.toLocaleLowerCase("zh-CN"),
        )
      : [sector, ...current.followedSectors],
  });
  return !exists;
}

export function dismissHomepageEvent(eventIdValue: string, sectorValue: string) {
  const eventId = cleanText(eventIdValue, 180);
  const sector = cleanText(sectorValue, 120);
  if (!eventId) return false;
  const current = getHomepagePreferenceSnapshot();
  const dismissedEventIds = [
    eventId,
    ...current.dismissedEventIds.filter((item) => item !== eventId),
  ].slice(0, MAX_DISMISSED_EVENTS);
  const sectorDislikes = { ...current.sectorDislikes };
  if (sector) {
    sectorDislikes[sector] = Math.min(
      MAX_SECTOR_DISLIKES,
      (sectorDislikes[sector] ?? 0) + 1,
    );
  }
  writeState({ ...current, dismissedEventIds, sectorDislikes });
  return true;
}

export function undoDismissHomepageEvent(eventIdValue: string, sectorValue: string) {
  const eventId = cleanText(eventIdValue, 180);
  const sector = cleanText(sectorValue, 120);
  if (!eventId) return false;
  const current = getHomepagePreferenceSnapshot();
  const sectorDislikes = { ...current.sectorDislikes };
  if (sector && sectorDislikes[sector]) {
    const nextCount = sectorDislikes[sector] - 1;
    if (nextCount > 0) sectorDislikes[sector] = nextCount;
    else delete sectorDislikes[sector];
  }
  writeState({
    ...current,
    dismissedEventIds: current.dismissedEventIds.filter((item) => item !== eventId),
    sectorDislikes,
  });
  return true;
}
