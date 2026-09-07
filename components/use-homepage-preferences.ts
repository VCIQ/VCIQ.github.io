"use client";

import { useSyncExternalStore } from "react";
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
  return useSyncExternalStore(
    subscribeHomepagePreferences,
    getHomepagePreferenceSnapshot,
    getServerSnapshot,
  );
}
