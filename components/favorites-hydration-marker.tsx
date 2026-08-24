"use client";

import { useEffect } from "react";

export const FAVORITES_HYDRATION_MARKER = "vciqFavoritesHydrated";
export const FAVORITES_RECOVERY_QUERY = "_vciq_reload";
export const FAVORITES_RECOVERY_SESSION_KEY = "vciq:favorites:recovery-reload:v1";

export function FavoritesHydrationMarker() {
  useEffect(() => {
    document.documentElement.dataset[FAVORITES_HYDRATION_MARKER] = "1";

    try {
      window.sessionStorage.removeItem(FAVORITES_RECOVERY_SESSION_KEY);
      const url = new URL(window.location.href);
      if (url.searchParams.has(FAVORITES_RECOVERY_QUERY)) {
        url.searchParams.delete(FAVORITES_RECOVERY_QUERY);
        window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
      }
    } catch {
      // Hydration itself is the success signal; URL/session cleanup is best effort.
    }

    return () => {
      delete document.documentElement.dataset[FAVORITES_HYDRATION_MARKER];
    };
  }, []);

  return null;
}
