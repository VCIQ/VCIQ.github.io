const DEFAULT_TRACKING_ADMIN = "https://vciq-tracking-console.pages.dev";
const FAVORITE_PREFERENCE_PATH = "/api/tracking-admin/v1/preferences/favorite";
const SYNC_TIMEOUT_MS = 5_000;
const BOOTSTRAP_TIMEOUT_MS = 8_000;
const READ_TIMEOUT_MS = 8_000;
const MAX_BOOTSTRAP_FAVORITES = 200;

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

  // Favorite persistence is local-first. The private preference event is a
  // best-effort learning signal authenticated by the existing Cloudflare
  // Access session; no GitHub or database credential is exposed here.
  return postPreferencePayload(payload, SYNC_TIMEOUT_MS, true);
}

export async function bootstrapFavoritePreferenceHistory(
  items: FavoritePreferenceSyncItem[],
): Promise<boolean> {
  const origin = browserOrigin();
  if (!origin || !Array.isArray(items) || items.length === 0) return false;
  const normalizedItems = items
    .slice(0, MAX_BOOTSTRAP_FAVORITES)
    .map((item) => buildFavoritePreferenceSyncPayload("save", item, origin)?.item ?? null)
    .filter((item): item is NonNullable<typeof item> => Boolean(item));
  if (!normalizedItems.length) return false;

  // A historical import can exceed the browser keepalive body budget, so it is
  // sent once per page runtime without keepalive. Individual future Favorite
  // actions continue to use the small keepalive request above.
  return postPreferencePayload(
    { bootstrap: true, items: normalizedItems },
    BOOTSTRAP_TIMEOUT_MS,
    false,
  );
}
