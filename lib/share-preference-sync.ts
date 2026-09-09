const DEFAULT_TRACKING_ADMIN = "https://vciq-tracking-console.pages.dev";
const SHARE_PREFERENCE_PATH = "/api/tracking-admin/v1/preferences/share";
const PENDING_SHARE_SYNC_KEY = "vciq:share-preference:pending:v1";
const SYNC_TIMEOUT_MS = 5_000;

export interface SharePreferenceSyncItem {
  id: string;
  href: string;
  title: string;
  summary?: string;
  channel?: string;
  channelLabel?: string;
  keywords?: string[];
  sectors?: string[];
  sources?: Array<{ name: string; url: string; level?: string }>;
  region?: string;
  company?: string;
  publishedAt?: string;
  importance?: number;
  eventType?: string;
  sharedAt?: string;
}

type PendingShareSync = {
  item: SharePreferenceSyncItem;
  token: string;
};

let pendingTokenCounter = 0;

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

function absolutePublicUrl(value: string, publicOrigin: string): string {
  try {
    const url = new URL(value, publicOrigin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

export function buildSharePreferencePayload(
  item: SharePreferenceSyncItem,
  publicOrigin = "https://vciq.github.io",
) {
  const href = absolutePublicUrl(item.href, publicOrigin);
  if (!href || !item.id || !item.title) return null;
  return {
    item: {
      id: item.id,
      href,
      title: item.title,
      summary: item.summary ?? "",
      channel: item.channel ?? "",
      channelLabel: item.channelLabel ?? "",
      keywords: item.keywords ?? [],
      sectors: item.sectors ?? [],
      sources: item.sources ?? [],
      region: item.region ?? "",
      company: item.company ?? "",
      publishedAt: item.publishedAt ?? "",
      importance: item.importance,
      eventType: item.eventType ?? "",
      sharedAt: item.sharedAt ?? "",
    },
  };
}

function validPendingShareSync(value: unknown): value is PendingShareSync {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const pending = value as Partial<PendingShareSync>;
  if (typeof pending.token !== "string" || !pending.token) return false;
  if (!pending.item || typeof pending.item !== "object") return false;
  return Boolean(buildSharePreferencePayload(pending.item));
}

function readPendingShareSyncs(): PendingShareSync[] {
  const storage = browserStorage();
  if (!storage) return [];
  try {
    const parsed = JSON.parse(storage.getItem(PENDING_SHARE_SYNC_KEY) ?? "[]") as unknown;
    return Array.isArray(parsed) ? parsed.filter(validPendingShareSync) : [];
  } catch {
    return [];
  }
}

function writePendingShareSyncs(items: PendingShareSync[]) {
  const storage = browserStorage();
  if (!storage) return;
  try {
    storage.setItem(PENDING_SHARE_SYNC_KEY, JSON.stringify(items.slice(0, 100)));
  } catch {}
}

function nextPendingToken() {
  pendingTokenCounter += 1;
  return `${Date.now().toString(36)}-${pendingTokenCounter.toString(36)}`;
}

function queuePendingShareSync(item: SharePreferenceSyncItem): PendingShareSync {
  const pending = { item, token: nextPendingToken() };
  const current = readPendingShareSyncs().filter((entry) => entry.item.id !== item.id);
  writePendingShareSyncs([pending, ...current]);
  return pending;
}

function clearPendingShareSyncIfCurrent(pending: PendingShareSync) {
  const current = readPendingShareSyncs();
  const next = current.filter(
    (entry) => !(entry.item.id === pending.item.id && entry.token === pending.token),
  );
  if (next.length !== current.length) writePendingShareSyncs(next);
}

async function postSharePreference(item: SharePreferenceSyncItem, keepalive: boolean): Promise<boolean> {
  const origin = browserOrigin();
  const payload = buildSharePreferencePayload(item, origin || "https://vciq.github.io");
  if (!origin || !payload || typeof fetch !== "function") return false;

  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), SYNC_TIMEOUT_MS);
  try {
    const response = await fetch(`${trackingAdminBase()}${SHARE_PREFERENCE_PATH}`, {
      method: "POST",
      credentials: "include",
      mode: "cors",
      keepalive,
      headers: {
        accept: "application/json",
        // Keep the normal browser path CORS-simple, matching Favorite sync.
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

export async function syncSharePreference(item: SharePreferenceSyncItem): Promise<boolean> {
  const normalizedItem = {
    ...item,
    sharedAt: item.sharedAt || new Date().toISOString(),
  };
  const pending = queuePendingShareSync(normalizedItem);
  const synced = await postSharePreference(normalizedItem, true);
  if (synced) clearPendingShareSyncIfCurrent(pending);
  return synced;
}

export async function flushPendingSharePreferences(): Promise<number> {
  const pending = readPendingShareSyncs();
  if (!pending.length) return 0;

  let synced = 0;
  for (const entry of pending) {
    if (await postSharePreference(entry.item, false)) {
      clearPendingShareSyncIfCurrent(entry);
      synced += 1;
    }
  }
  return synced;
}
