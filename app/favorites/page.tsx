import type { Metadata } from "next";
import { ExternalFavoriteCapture } from "@/components/external-favorite-capture";
import { FavoritesHydrationMarker } from "@/components/favorites-hydration-marker";
import { FavoritesPage } from "@/components/favorites-page";
import "./favorites.css";

export const metadata: Metadata = {
  title: "收藏",
  description: "集中查看收藏内容，支持保存站外高价值文章，并以收藏信号提高相关关键词与信息源的推荐权重。",
};

const favoritesHydrationWatchdog = `
(() => {
  const marker = "vciqFavoritesHydrated";
  const recoveryQuery = "_vciq_reload";
  const recoverySessionKey = "vciq:favorites:recovery-reload:v1";
  window.setTimeout(() => {
    if (document.documentElement.dataset[marker] === "1") return;
    try {
      if (window.sessionStorage.getItem(recoverySessionKey) === "1") return;
      window.sessionStorage.setItem(recoverySessionKey, "1");
      const url = new URL(window.location.href);
      url.searchParams.set(recoveryQuery, String(Date.now()));
      window.location.replace(url.toString());
    } catch {
      // A blocked storage API should not create a reload loop.
    }
  }, 8000);
})();
`;

export default function FavoriteChannelPage() {
  return (
    <main className="page-shell subpage">
      <script dangerouslySetInnerHTML={{ __html: favoritesHydrationWatchdog }} />
      <FavoritesHydrationMarker />
      <FavoritesPage />
      <ExternalFavoriteCapture />
    </main>
  );
}
