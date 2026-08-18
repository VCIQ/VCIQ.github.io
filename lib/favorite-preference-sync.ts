const DEFAULT_TRACKING_ADMIN = "https://vciq-tracking-console.pages.dev";
const FAVORITE_PREFERENCE_PATH = "/api/tracking-admin/v1/preferences/favorite";
const SYNC_TIMEOUT_MS = 5_000;
const BOOTSTRAP_TIMEOUT_MS = 8_000;
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
