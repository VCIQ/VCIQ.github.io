import {
  FAVORITES_CHANGED_EVENT,
  FAVORITES_SCHEMA_VERSION,
  FAVORITES_STORAGE_KEY,
  normalizeFavorite,
  readFavoriteItems,
  type FavoriteItem,
  type FavoritePayload,
} from "@/lib/favorites";
import {
  bootstrapFavoritePreferenceHistory,
  fetchFavoritePreferenceCloudState,
  type FavoriteCloudRecord,
} from "@/lib/favorite-preference-sync";

export const FAVORITE_CLOUD_SYNC_STATUS_EVENT = "vciq:favorite-cloud-sync-status";
const CLOUD_SYNC_SUCCESS_KEY = "vciq:favorites-cloud:last-success:v1";
const CLOUD_SYNC_INTERVAL_MS = 5 * 60_000;
const MAX_FAVORITES = 300;

export type FavoriteCloudSyncStatus =
  | {
      state: "synced";
      localCount: number;
      cloudCount: number;
      restored: number;
      removed: number;
      updatedAt: string | null;
    }
  | {
      state: "auth-required" | "unavailable";
      localCount: number;
      cloudCount: 0;
      restored: 0;
      removed: 0;
      updatedAt: null;
    };

function mergedCloudItem(existing: FavoriteItem | undefined, record: FavoriteCloudRecord) {
  const cloud = record.item;
  return normalizeFavorite({
    ...(existing ?? {}),
    ...cloud,
    summary: cloud.summary || existing?.summary || "",
    channel: cloud.channel || existing?.channel,
    channelLabel: cloud.channelLabel || existing?.channelLabel,
    keywords: cloud.keywords?.length ? cloud.keywords : existing?.keywords,
    sectors: cloud.sectors?.length ? cloud.sectors : existing?.sectors,
    sources: cloud.sources?.length ? cloud.sources : existing?.sources,
    region: cloud.region || existing?.region,
    company: cloud.company || existing?.company,
    publishedAt: cloud.publishedAt || existing?.publishedAt,
    importance: cloud.importance ?? existing?.importance,
    eventType: cloud.eventType || existing?.eventType,
    savedAt: cloud.savedAt || existing?.savedAt || record.updatedAt,
  });
}

export function mergeFavoriteCloudRecords(
  localItems: FavoriteItem[],
  records: FavoriteCloudRecord[],
) {
  const next = new Map(localItems.map((item) => [item.id, item]));
  let restored = 0;
  let removed = 0;

  for (const record of records) {
    const id = record.item.id;
    if (!id) continue;
    if (record.action === "remove") {
      if (next.delete(id)) removed += 1;
      continue;
    }

    const existing = next.get(id);
    const normalized = mergedCloudItem(existing, record);
    if (!normalized) continue;
    if (!existing) restored += 1;
    next.set(id, normalized);
  }

  const items = [...next.values()]
    .sort((left, right) => right.savedAt.localeCompare(left.savedAt))
    .slice(0, MAX_FAVORITES);
  return { items, restored, removed };
}

function replaceLocalFavorites(items: FavoriteItem[]) {
  if (typeof window === "undefined") return;
  const payload: FavoritePayload = {
    schemaVersion: FAVORITES_SCHEMA_VERSION,
    items,
  };
  window.localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(payload));
  window.dispatchEvent(new CustomEvent(FAVORITES_CHANGED_EVENT));
}

function publishStatus(status: FavoriteCloudSyncStatus) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent<FavoriteCloudSyncStatus>(FAVORITE_CLOUD_SYNC_STATUS_EVENT, {
      detail: status,
    }),
  );
}

function recordSuccessfulSync() {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(CLOUD_SYNC_SUCCESS_KEY, String(Date.now()));
  } catch {}
}

export function favoriteCloudSyncIsDue() {
  if (typeof window === "undefined") return false;
  try {
    const last = Number(window.sessionStorage.getItem(CLOUD_SYNC_SUCCESS_KEY) ?? 0);
    return !Number.isFinite(last) || last <= 0 || Date.now() - last >= CLOUD_SYNC_INTERVAL_MS;
  } catch {
    return true;
  }
}

export async function reconcileFavoritesWithCloud(): Promise<FavoriteCloudSyncStatus> {
  const local = readFavoriteItems();

  // Existing browser-only collections are uploaded before the first read. The
  // server bootstrap is insert-only for IDs it has never seen, so an explicit
  // remove from another browser remains authoritative and cannot be resurrected.
  if (local.length) {
    await bootstrapFavoritePreferenceHistory(local);
  }

  const cloud = await fetchFavoritePreferenceCloudState();
  if (!cloud.available) {
    const status: FavoriteCloudSyncStatus = {
      state: cloud.authRequired ? "auth-required" : "unavailable",
      localCount: local.length,
      cloudCount: 0,
      restored: 0,
      removed: 0,
      updatedAt: null,
    };
    publishStatus(status);
    return status;
  }

  const merged = mergeFavoriteCloudRecords(local, cloud.records);
  replaceLocalFavorites(merged.items);
  recordSuccessfulSync();

  const status: FavoriteCloudSyncStatus = {
    state: "synced",
    localCount: merged.items.length,
    cloudCount: cloud.activeCount,
    restored: merged.restored,
    removed: merged.removed,
    updatedAt: cloud.updatedAt,
  };
  publishStatus(status);
  return status;
}
