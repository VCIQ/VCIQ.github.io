const DEFAULT_TRACKING_ADMIN = "https://vciq-tracking-console.pages.dev";
const FAVORITE_PREFERENCE_PATH = "/api/tracking-admin/v1/preferences/favorite";
const SYNC_TIMEOUT_MS = 5_000;

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

export async function syncFavoritePreference(
  action: FavoritePreferenceSyncAction,
  item: FavoritePreferenceSyncItem,
): Promise<boolean> {
  if (typeof window === "undefined" || typeof fetch !== "function") return false;
  const payload = buildFavoritePreferenceSyncPayload(action, item, window.location.origin);
  if (!payload) return false;

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), SYNC_TIMEOUT_MS);
  try {
    const response = await fetch(`${trackingAdminBase()}${FAVORITE_PREFERENCE_PATH}`, {
      method: "POST",
      // Favorite persistence is local-first. The private preference event is a
      // best-effort learning signal authenticated by the existing Cloudflare
      // Access session; no GitHub or database credential is exposed here.
      credentials: "include",
      mode: "cors",
      keepalive: true,
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
    window.clearTimeout(timeout);
  }
}
