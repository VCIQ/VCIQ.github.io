import type { HomepagePreferenceState } from "@/lib/homepage-preferences";

const DEFAULT_TRACKING_ADMIN = "https://vciq-tracking-console.pages.dev";
const HOMEPAGE_PREFERENCE_PATH = "/api/tracking-admin/v1/preferences/homepage";
const PENDING_HOMEPAGE_SYNC_KEY = "vciq:homepage-preferences-cloud:pending:v1";
const SYNC_TIMEOUT_MS = 5_000;
const READ_TIMEOUT_MS = 8_000;
const BOOTSTRAP_TIMEOUT_MS = 8_000;

export type HomepagePreferenceSyncAction = "follow" | "unfollow" | "dismiss" | "restore";

export type HomepagePreferenceSyncInput = {
  action: HomepagePreferenceSyncAction;
  sector: string;
  eventId?: string;
};

export type HomepagePreferenceCloudState = {
  available: boolean;
  followedSectors: string[];
  dismissedEventIds: string[];
  dismissedEvents: Array<{ eventId: string; sector: string }>;
  sectorDislikes: Record<string, number>;
  updatedAt: string | null;
  authRequired: boolean;
  status: number;
};

type PendingHomepageSync = HomepagePreferenceSyncInput & { token: string };

let pendingTokenCounter = 0;
let bootstrapInFlight: Promise<boolean> | null = null;

function cleanText(value: unknown, limit = 180) {
  if (typeof value !== "string") return "";
  return value.normalize("NFKC").replace(/\s+/g, " ").trim().slice(0, limit);
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
    result[sector] = Math.min(4, count);
    if (Object.keys(result).length >= 40) break;
  }
  return result;
}

function normalizeDismissedEvents(value: unknown) {
  if (!Array.isArray(value)) return [];
  const result: Array<{ eventId: string; sector: string }> = [];
  const seen = new Set<string>();
  for (const raw of value) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) continue;
    const item = raw as Record<string, unknown>;
    const eventId = cleanText(item.eventId, 180);
    const sector = cleanText(item.sector, 120);
    if (!eventId || !sector || seen.has(eventId)) continue;
    seen.add(eventId);
    result.push({ eventId, sector });
    if (result.length >= 300) break;
  }
  return result;
}

function trackingAdminBase(): string {
  return (process.env.NEXT_PUBLIC_TRACKING_ADMIN_URL || DEFAULT_TRACKING_ADMIN).replace(/\/+$/, "");
}

function browserOrigin(): string {
  return typeof window !== "undefined" && window.location?.origin ? window.location.origin : "";
}

function browserStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function pendingKey(input: HomepagePreferenceSyncInput) {
  return input.action === "follow" || input.action === "unfollow"
    ? `sector:${cleanText(input.sector, 120).toLocaleLowerCase("zh-CN")}`
    : `event:${cleanText(input.eventId, 180)}`;
}

function normalizeSyncInput(value: HomepagePreferenceSyncInput): HomepagePreferenceSyncInput | null {
  const action = cleanText(value.action, 30).toLocaleLowerCase("en-US") as HomepagePreferenceSyncAction;
  if (!["follow", "unfollow", "dismiss", "restore"].includes(action)) return null;
  const sector = cleanText(value.sector, 120);
  if (!sector) return null;
  if (action === "follow" || action === "unfollow") return { action, sector };
  const eventId = cleanText(value.eventId, 180);
  if (!eventId) return null;
  return { action, sector, eventId };
}

function validPending(value: unknown): value is PendingHomepageSync {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const raw = value as Partial<PendingHomepageSync>;
  if (typeof raw.token !== "string" || !raw.token) return false;
  return Boolean(normalizeSyncInput(raw as HomepagePreferenceSyncInput));
}

function readPending(): PendingHomepageSync[] {
  const storage = browserStorage();
  if (!storage) return [];
  try {
    const parsed = JSON.parse(storage.getItem(PENDING_HOMEPAGE_SYNC_KEY) ?? "[]") as unknown;
    return Array.isArray(parsed) ? parsed.filter(validPending) : [];
  } catch {
    return [];
  }
}

function writePending(items: PendingHomepageSync[]) {
  const storage = browserStorage();
  if (!storage) return;
  try {
    storage.setItem(PENDING_HOMEPAGE_SYNC_KEY, JSON.stringify(items));
  } catch {}
}

function nextToken() {
  pendingTokenCounter += 1;
  return `${Date.now().toString(36)}-${pendingTokenCounter.toString(36)}`;
}

function queuePending(input: HomepagePreferenceSyncInput) {
  const normalized = normalizeSyncInput(input);
  if (!normalized) return null;
  const pending: PendingHomepageSync = { ...normalized, token: nextToken() };
  const target = pendingKey(normalized);
  const current = readPending().filter((entry) => pendingKey(entry) !== target);
  writePending([pending, ...current]);
  return pending;
}

function clearPendingIfCurrent(pending: PendingHomepageSync) {
  const current = readPending();
  const next = current.filter((entry) => entry.token !== pending.token);
  if (next.length !== current.length) writePending(next);
}

async function postPayload(payload: unknown, timeoutMs: number, keepalive: boolean) {
  if (typeof fetch !== "function" || !browserOrigin()) return false;
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${trackingAdminBase()}${HOMEPAGE_PREFERENCE_PATH}`, {
      method: "POST",
      credentials: "include",
      mode: "cors",
      keepalive,
      headers: {
        accept: "application/json",
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

export function normalizeHomepagePreferenceCloudState(
  value: unknown,
  status = 200,
): HomepagePreferenceCloudState {
  const body = value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
  return {
    available: body.available === true,
    followedSectors: uniqueStrings(body.followedSectors, 40),
    dismissedEventIds: uniqueStrings(body.dismissedEventIds, 300),
    dismissedEvents: normalizeDismissedEvents(body.dismissedEvents),
    sectorDislikes: normalizeSectorDislikes(body.sectorDislikes),
    updatedAt: typeof body.updatedAt === "string" ? body.updatedAt : null,
    authRequired: status === 401 || status === 403,
    status,
  };
}

export async function fetchHomepagePreferenceCloudState(): Promise<HomepagePreferenceCloudState> {
  const empty = (status = 0) => normalizeHomepagePreferenceCloudState({}, status);
  if (typeof fetch !== "function" || !browserOrigin()) return empty();

  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), READ_TIMEOUT_MS);
  try {
    const response = await fetch(`${trackingAdminBase()}${HOMEPAGE_PREFERENCE_PATH}`, {
      method: "GET",
      credentials: "include",
      mode: "cors",
      cache: "no-store",
      headers: { accept: "application/json" },
      signal: controller.signal,
    });
    if (!response.ok) return empty(response.status);
    return normalizeHomepagePreferenceCloudState(await response.json(), response.status);
  } catch {
    return empty();
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

export async function syncHomepagePreference(input: HomepagePreferenceSyncInput): Promise<boolean> {
  const pending = queuePending(input);
  if (!pending) return false;
  const normalized = normalizeSyncInput(pending);
  if (!normalized) return false;
  const synced = await postPayload(normalized, SYNC_TIMEOUT_MS, true);
  if (synced) clearPendingIfCurrent(pending);
  return synced;
}

export async function flushPendingHomepagePreferences(): Promise<number> {
  const pending = readPending();
  let synced = 0;
  for (const entry of pending) {
    const normalized = normalizeSyncInput(entry);
    if (!normalized) continue;
    if (await postPayload(normalized, SYNC_TIMEOUT_MS, false)) {
      clearPendingIfCurrent(entry);
      synced += 1;
    }
  }
  return synced;
}

export async function bootstrapHomepagePreferenceHistory(
  state: HomepagePreferenceState,
  dismissedEvents: Array<{ eventId: string; sector: string }>,
): Promise<boolean> {
  if (bootstrapInFlight) return bootstrapInFlight;
  const origin = browserOrigin();
  if (!origin) return false;
  const payload = {
    bootstrap: true,
    state: {
      followedSectors: state.followedSectors,
      dismissedEvents,
      sectorDislikes: state.sectorDislikes,
    },
  };
  if (!state.followedSectors.length && !state.dismissedEventIds.length && !Object.keys(state.sectorDislikes).length) {
    return true;
  }

  const request = postPayload(payload, BOOTSTRAP_TIMEOUT_MS, false);
  bootstrapInFlight = request;
  try {
    return await request;
  } finally {
    if (bootstrapInFlight === request) bootstrapInFlight = null;
  }
}

export function pendingHomepagePreferenceCount(): number {
  return readPending().length;
}
