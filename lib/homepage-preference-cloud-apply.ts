import {
  HOMEPAGE_PREFERENCES_CHANGED_EVENT,
  HOMEPAGE_PREFERENCES_STORAGE_KEY,
  normalizeHomepagePreferenceState,
  type HomepagePreferenceState,
} from "@/lib/homepage-preferences";
import type { HomepagePreferenceCloudState } from "@/lib/homepage-preference-sync";

function browserStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function homepagePreferenceFingerprint(state: HomepagePreferenceState): string {
  return JSON.stringify(normalizeHomepagePreferenceState(state));
}

export function applyHomepagePreferenceCloudState(
  cloud: HomepagePreferenceCloudState,
): boolean {
  if (!cloud.available || typeof window === "undefined") return false;
  const storage = browserStorage();
  if (!storage) return false;
  const next = normalizeHomepagePreferenceState({
    followedSectors: cloud.followedSectors,
    dismissedEventIds: cloud.dismissedEventIds,
    sectorDislikes: cloud.sectorDislikes,
  });
  const serialized = JSON.stringify(next);
  try {
    storage.setItem(HOMEPAGE_PREFERENCES_STORAGE_KEY, serialized);
    window.dispatchEvent(new CustomEvent(HOMEPAGE_PREFERENCES_CHANGED_EVENT));
    return true;
  } catch {
    return false;
  }
}
