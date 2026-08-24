const DEFAULT_TRACKING_ADMIN = "https://vciq-tracking-console.pages.dev";
const FAVORITE_PREFERENCE_PATH = "/api/tracking-admin/v1/preferences/favorite";
const PENDING_FAVORITE_SYNC_KEY = "vciq:favorites-cloud:pending:v1";
const SYNC_TIMEOUT_MS = 5_000;
const BOOTSTRAP_TIMEOUT_MS = 8_000;
const READ_TIMEOUT_MS = 8_000;
const MAX_BOOTSTRAP_FAVORITES = 200;
const MAX_PENDING_FAVORITES = 300;

export type FavoritePreferenceSyncAction = "save" | "remove";

export interface FavoritePreferenceSyncItem {
  id: string;
  href: string;
  title: string;
  summary?: string;
  channel: string;
  channelLabel: string;
  keywords?: string[];
  sectors?: string[];
  sources?: Array<{ name: string; url: string; level?: string }>;
  region?: string;
  company?: string;
  publishedAt?: string;
  importance?: number;
  eventType?: string;
  savedAt?: string;
}

export type FavoriteCloudRecord = {
  action: FavoritePreferenceSyncAction;
  updatedAt: string;
  item: FavoritePreferenceSyncItem & { savedAt?: string };
};

export type FavoriteCloudState = {
  available: boolean;
  records: FavoriteCloudRecord[];
  activeCount: number;
  tombstoneCount: number;
  updatedAt: string | null;
  authRequired: boolean;
  status: number;
};

type PendingFavoriteSync = {
  action: FavoritePreferenceSyncAction;
  item: FavoritePreferenceSyncItem;
  token: string;
};

let bootstrapInFlight: Promise<boolean> | null = null;
let pendingTokenCounter = 0;

function absolutePublicUrl(value: string, publicOrigin: string): string {
  try {
    const url = new URL(value, publicOrigin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

function trackingAdminBase(): string {
  return (process.env.NEXT_PUBLIC_TRACKING_ADMIN_URL || DEFAULT_TRACKING_ADMIN).replace(/\/+$/, "");
}

function browserOrigin(): string {
  return typeof window !== "undefined" && window.location?.origin
    ? window.location.origin
    : "";
}

function browserStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function buildFavoritePreferenceSyncPayload(
  action: FavoritePreferenceSyncAction,
  item: FavoritePreferenceSyncItem,
  publicOrigin = "https://vciq.github.io",
) {
  const href = absolutePublicUrl(item.href, publicOrigin);
  if (!href || !item.id || !item.title) return null;
  return {
    action,
    item: {
      id: item.id,
      href,
      title: item.title,
      summary: item.summary ?? "",
      channel: item.channel,
      channelLabel: item.channelLabel,
      keywords: item.keywords ?? [],
      sectors: item.sectors ?? [],
      sources: item.sources ?? [],
      region: item.region ?? "",
      company: item.company ?? "",
      publishedAt: item.publishedAt ?? "",
      importance: item.importance,
      eventType: item.eventType ?? "",
      savedAt: item.savedAt ?? "",
    },
  };
}

function validPendingFavoriteSync(value: unknown): value is PendingFavoriteSync {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const pending = value as Partial<PendingFavoriteSync>;
  if (pending.action !== "save" && pending.action !== "remove") return false;
  if (typeof pending.token !== "string" || !pending.token) return false;
  if (!pending.item || typeof pending.item !== "object") return false;
  return Boolean(buildFavoritePreferenceSyncPayload(pending.action, pending.item));
}

function readPendingFavoriteSyncs(): PendingFavoriteSync[] {
  const storage = browserStorage();
  if (!storage) return [];
  try {
    const parsed = JSON.parse(storage.getItem(PENDING_FAVORITE_SYNC_KEY) ?? "[]") as unknown;
    return Array.isArray(parsed)
      ? parsed.filter(validPendingFavoriteSync).slice(0, MAX_PENDING_FAVORITES)
      : [];
  } catch {
    return [];
  }
}

function writePendingFavoriteSyncs(items: PendingFavoriteSync[]) {
  const storage = browserStorage();
  if (!storage) return;
  try {
    storage.setItem(PENDING_FAVORITE_SYNC_KEY, JSON.stringify(items.slice(0, MAX_PENDING_FAVORITES)));
  } catch {}
}

function nextPendingToken() {
  pendingTokenCounter += 1;
  return `${Date.now().toString(36)}-${pendingTokenCounter.toString(36)}`;
}

function queuePendingFavoriteSync(
  action: FavoritePreferenceSyncAction,
  item: FavoritePreferenceSyncItem,
): PendingFavoriteSync {
  const pending: PendingFavoriteSync = { action, item, token: nextPendingToken() };
  const current = readPendingFavoriteSyncs().filter((entry) => entry.item.id !== item.id);
  writePendingFavoriteSyncs([pending, ...current]);
  return pending;
}

function clearPendingFavoriteSyncIfCurrent(pending: PendingFavoriteSync) {
  const current = readPendingFavoriteSyncs();
  const next = current.filter(
    (entry) => !(entry.item.id === pending.item.id && entry.token === pending.token),
  );
  if (next.length !== current.length) writePendingFavoriteSyncs(next);
}

async function postPreferencePayload(
  payload: unknown,
  timeoutMs: number,
  keepalive: boolean,
): Promise<boolean> {
  if (typeof fetch !== "function" || !browserOrigin()) return false;
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${trackingAdminBase()}${FAVORITE_PREFERENCE_PATH}`, {
      method: "POST",
      credentials: "include",
      mode: "cors",
      keepalive,
      headers: {
        accept: "application/json",
        // text/plain is CORS-safelisted and lets the private endpoint parse the
        // JSON body without requiring a browser preflight in the common path.
        "content-type": "text/plain;charset=UTF-8",
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    return response.ok;
  } catch {
    return false;
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

function validCloudRecord(value: unknown): value is FavoriteCloudRecord {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const record = value as Partial<FavoriteCloudRecord>;
  if (record.action !== "save" && record.action !== "remove") return false;
  if (typeof record.updatedAt !== "string") return false;
  if (!record.item || typeof record.item !== "object") return false;
  return (
    typeof record.item.id === "string" &&
    typeof record.item.href === "string" &&
    typeof record.item.title === "string"
  );
}

export async function fetchFavoritePreferenceCloudState(): Promise<FavoriteCloudState> {
  const empty = (status = 0, authRequired = false): FavoriteCloudState => ({
    available: false,
    records: [],
    activeCount: 0,
    tombstoneCount: 0,
    updatedAt: null,
    authRequired,
    status,
  });
  if (typeof fetch !== "function" || !browserOrigin()) return empty();

  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), READ_TIMEOUT_MS);
  try {
    const response = await fetch(`${trackingAdminBase()}${FAVORITE_PREFERENCE_PATH}`, {
      method: "GET",
      credentials: "include",
      mode: "cors",
      cache: "no-store",
      headers: { accept: "application/json" },
      signal: controller.signal,
    });
    if (response.status === 401 || response.status === 403) {
      return empty(response.status, true);
    }
    if (!response.ok) return empty(response.status);

    const body = await response.json() as Record<string, unknown>;
    const records = Array.isArray(body.records)
      ? body.records.filter(validCloudRecord)
      : [];
    return {
      available: body.available === true,
      records,
      activeCount: Number.isFinite(Number(body.activeCount))
        ? Math.max(0, Math.trunc(Number(body.activeCount)))
        : records.filter((record) => record.action === "save").length,
      tombstoneCount: Number.isFinite(Number(body.tombstoneCount))
        ? Math.max(0, Math.trunc(Number(body.tombstoneCount)))
        : records.filter((record) => record.action === "remove").length,
      updatedAt: typeof body.updatedAt === "string" ? body.updatedAt : null,
      authRequired: false,
      status: response.status,
    };
  } catch {
    return empty();
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

export async function syncFavoritePreference(
  action: FavoritePreferenceSyncAction,
  item: FavoritePreferenceSyncItem,
): Promise<boolean> {
  const origin = browserOrigin();
  if (!origin) return false;
  const payload = buildFavoritePreferenceSyncPayload(action, item, origin);
  if (!payload) return false;

  // Queue before the network call so a newer local action cannot be erased by
  // an older request that happens to finish later.
  const pending = queuePendingFavoriteSync(action, item);
  const synced = await postPreferencePayload(payload, SYNC_TIMEOUT_MS, true);
  if (synced) clearPendingFavoriteSyncIfCurrent(pending);
  return synced;
}

export async function flushPendingFavoritePreferences(): Promise<number> {
  const pending = readPendingFavoriteSyncs();
  if (!pending.length) return 0;

  let synced = 0;
  for (const entry of pending) {
    const payload = buildFavoritePreferenceSyncPayload(entry.action, entry.item, browserOrigin());
    if (!payload) continue;
    if (await postPreferencePayload(payload, SYNC_TIMEOUT_MS, false)) {
      clearPendingFavoriteSyncIfCurrent(entry);
      synced += 1;
    }
  }
  return synced;
}

export async function bootstrapFavoritePreferenceHistory(
  items: FavoritePreferenceSyncItem[],
): Promise<boolean> {
  if (bootstrapInFlight) return bootstrapInFlight;

  const origin = browserOrigin();
  if (!origin || !Array.isArray(items) || items.length === 0) return false;
  const normalizedItems = items
    .slice(0, MAX_BOOTSTRAP_FAVORITES)
    .map((item) => buildFavoritePreferenceSyncPayload("save", item, origin)?.item ?? null)
    .filter((item): item is NonNullable<typeof item> => Boolean(item));
  if (!normalizedItems.length) return false;

  // A historical import can exceed the browser keepalive body budget, so it is
  // sent once per concurrent page bootstrap. Individual future Favorite actions
  // continue to use the small keepalive request above.
  const request = postPreferencePayload(
    { bootstrap: true, items: normalizedItems },
    BOOTSTRAP_TIMEOUT_MS,
    false,
  );
  bootstrapInFlight = request;
  try {
    return await request;
  } finally {
    if (bootstrapInFlight === request) bootstrapInFlight = null;
  }
}
