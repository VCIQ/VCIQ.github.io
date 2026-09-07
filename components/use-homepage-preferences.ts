"use client";

import { useEffect, useSyncExternalStore } from "react";
import { ensureHomepagePreferenceCloudHydrated } from "@/lib/homepage-preference-cloud-bootstrap";
import {
  EMPTY_HOMEPAGE_PREFERENCES,
  getHomepagePreferenceSnapshot,
  subscribeHomepagePreferences,
  type HomepagePreferenceState,
} from "@/lib/homepage-preferences";

function getServerSnapshot(): HomepagePreferenceState {
  return EMPTY_HOMEPAGE_PREFERENCES;
}

export function useHomepagePreferences(): HomepagePreferenceState {
  useEffect(() => {
    void ensureHomepagePreferenceCloudHydrated();
  }, []);

  return useSyncExternalStore(
    subscribeHomepagePreferences,
    getHomepagePreferenceSnapshot,
    getServerSnapshot,
  );
}
