import { getHomepagePreferenceSnapshot } from "@/lib/homepage-preferences";
import {
  applyHomepagePreferenceCloudState,
  homepagePreferenceFingerprint,
} from "@/lib/homepage-preference-cloud-apply";
import {
  bootstrapHomepagePreferenceHistory,
  fetchHomepagePreferenceCloudState,
  flushPendingHomepagePreferences,
  pendingHomepagePreferenceCount,
} from "@/lib/homepage-preference-sync";

const LEGACY_DISMISSED_SECTOR = "__legacy__";
let initialization: Promise<boolean> | null = null;

async function initializeHomepagePreferenceCloud(): Promise<boolean> {
  const local = getHomepagePreferenceSnapshot();
  // Pre-cloud local storage did not remember the sector for each exact hidden
  // event. Preserve those event tombstones across devices under an inert
  // migration-only sector while the existing aggregate sectorDislikes values
  // retain the actual recommendation penalty.
  const legacyDismissedEvents = local.dismissedEventIds.map((eventId) => ({
    eventId,
    sector: LEGACY_DISMISSED_SECTOR,
  }));

  await bootstrapHomepagePreferenceHistory(local, legacyDismissedEvents);
  await flushPendingHomepagePreferences();

  let beforeFetch = homepagePreferenceFingerprint(getHomepagePreferenceSnapshot());
  let cloud = await fetchHomepagePreferenceCloudState();
  if (!cloud.available) return false;

  const afterFetch = homepagePreferenceFingerprint(getHomepagePreferenceSnapshot());
  if (afterFetch !== beforeFetch || pendingHomepagePreferenceCount() > 0) {
    await flushPendingHomepagePreferences();
    beforeFetch = homepagePreferenceFingerprint(getHomepagePreferenceSnapshot());
    cloud = await fetchHomepagePreferenceCloudState();
    if (!cloud.available) return false;
    const finalLocal = homepagePreferenceFingerprint(getHomepagePreferenceSnapshot());
    if (finalLocal !== beforeFetch || pendingHomepagePreferenceCount() > 0) {
      // A user action is still racing the hydration read. Keep the local state
      // authoritative for this render; the queued action will be retried on the
      // next mount rather than replacing it with an older cloud snapshot.
      return false;
    }
  }

  return applyHomepagePreferenceCloudState(cloud);
}

export function ensureHomepagePreferenceCloudHydrated(): Promise<boolean> {
  if (initialization) return initialization;
  const request = initializeHomepagePreferenceCloud();
  initialization = request;
  void request.finally(() => {
    if (initialization === request) initialization = null;
  });
  return request;
}
