import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const ROOT = process.cwd();
const read = (relativePath: string) => readFileSync(path.join(ROOT, relativePath), "utf8");

const page = read("app/page.tsx");
const hotPage = read("app/hot/page.tsx");
const layout = read("app/layout.tsx");
const searchPage = read("app/search/page.tsx");
const technologiesPage = read("app/technologies/page.tsx");
const channelDirectory = read("components/channel-update-directory.tsx");
const channelDirectoryClient = read("components/channel-update-directory-client.tsx");
const dashboard = read("components/dashboard-client.tsx");
const favoriteButton = read("components/favorite-button.tsx");
const favoriteControls = read("components/homepage-favorite-controls.tsx");
const favoritesPage = read("components/favorites-page.tsx");
const favoritesHook = read("components/use-favorites.ts");
const globalSearch = read("components/global-search.tsx");
const homepageUpdates = read("components/homepage-channel-updates.tsx");
const homepageFeed = read("components/homepage-sortable-feed.tsx");
const hotClient = read("components/hot-page.tsx");
const liveStatus = read("components/live-status.tsx");
const siteHeader = read("components/site-header.tsx");
const articles = read("lib/use-articles.ts");
const favorites = read("lib/favorites.ts");
const domRuntime = read("lib/intelligence-dom-runtime.ts");
const channelArchiveBuilder = read("scripts/build-channel-update-archives.ts");
const searchIndexBuilder = read("scripts/build-article-search-index.mjs");
const routeBudget = read("scripts/check-route-performance-budget.mjs");
const packageJson = read("package.json");

test("homepage client does not import full build-time research datasets", () => {
  assert.doesNotMatch(dashboard, /@\/lib\/intelligence-data/);
  assert.doesNotMatch(dashboard, /@\/lib\/tracked-sectors/);
  assert.doesNotMatch(dashboard, /@\/lib\/core-research-objects/);
  assert.match(page, /DashboardClient/);
  assert.match(page, /initialPayload/);
  assert.match(page, /bootstrap/);
});

test("global header status is build-time and cannot trigger the article archive fetch", () => {
  assert.doesNotMatch(liveStatus, /"use client"/);
  assert.doesNotMatch(liveStatus, /import[^\n]*useArticles/);
  assert.match(liveStatus, /@\/public\/data\/articles\.json/);
  assert.doesNotMatch(siteHeader, /@\/components\/live-status/);
  assert.match(siteHeader, /status: ReactNode/);
  assert.match(layout, /<SiteHeader status={<LiveStatus \/>} \/>/);
});

test("browser article archive is lazy and no longer requires a global react-query provider", () => {
  assert.doesNotMatch(articles, /from "zod"/);
  assert.doesNotMatch(articles, /@tanstack\/react-query/);
  assert.doesNotMatch(layout, /Providers/);
  assert.match(articles, /pointerdown/);
  assert.match(articles, /keydown/);
  assert.match(articles, /const enabled = options\.enabled \?\? interactionEnabled/);
  assert.match(articles, /cachedPayload/);
  assert.match(articles, /inFlight/);
  assert.match(articles, /cache: "default"/);
  assert.match(articles, /ARTICLE_REFRESH_INTERVAL_MS/);
});

test("global client shell does not retain the dead react-query runtime", () => {
  assert.doesNotMatch(packageJson, /@tanstack\/react-query/);
  assert.equal(
    existsSync(path.join(ROOT, "components", "providers.tsx")),
    false,
    "unused global QueryClient provider must stay removed",
  );
});

test("global search does not bundle research datasets or load the full article archive", () => {
  assert.doesNotMatch(globalSearch, /@\/lib\/catalog-data/);
  assert.doesNotMatch(globalSearch, /@\/lib\/core-research-objects/);
  assert.doesNotMatch(globalSearch, /@\/lib\/people-data/);
  assert.doesNotMatch(globalSearch, /@\/lib\/tracked-sectors/);
  assert.doesNotMatch(globalSearch, /useArticles/);
  assert.match(searchPage, /staticRecords/);
  assert.match(searchPage, /<GlobalSearch staticRecords={staticRecords} \/>/);
  assert.match(globalSearch, /article_search_index\.json/);
  assert.match(globalSearch, /EVENT_QUERY_MIN_LENGTH = 2/);
  assert.match(globalSearch, /SEARCH_DEBOUNCE_MS = 120/);
  assert.match(packageJson, /build:search-index/);
  assert.match(packageJson, /build-article-search-index\.mjs/);
  assert.match(searchIndexBuilder, /cleanText\([\s\S]*420/);
});

test("channel update directories hydrate only a bounded latest window", () => {
  assert.match(channelDirectory, /INITIAL_CHANNEL_UPDATE_LIMIT = 120/);
  assert.match(channelDirectory, /fullDirectory\.items\.slice\(0, INITIAL_CHANNEL_UPDATE_LIMIT\)/);
  assert.match(channelDirectory, /totalItemCount={fullDirectory\.items\.length}/);
  assert.match(channelDirectoryClient, /channel_update_directories\.json/);
  assert.match(channelDirectoryClient, /loadFullArchive/);
  assert.match(channelDirectoryClient, /加载完整更新目录/);
  assert.match(channelArchiveBuilder, /getChannelUpdateDirectory/);
  assert.match(packageJson, /build:channel-update-archives/);
});

test("homepage update stream keeps 200 candidates but mounts only 60 initially", () => {
  assert.match(homepageUpdates, /slice\(0, HOMEPAGE_CHANNEL_UPDATE_LIMIT\)/);
  assert.match(homepageFeed, /INITIAL_FEED_RENDER_LIMIT = 60/);
  assert.match(homepageFeed, /sortedItems\.slice\(0, renderLimit\)/);
  assert.match(homepageFeed, /显示更多/);
});

test("hot ranking starts from a bounded build-time pool and only loads the full archive explicitly", () => {
  assert.match(hotPage, /HOT_BOOTSTRAP_LIMIT = 240/);
  assert.match(hotPage, /<HotPage initialPayload={initialPayload} \/>/);
  assert.match(hotClient, /useArticles\(initialPayload, \{/);
  assert.match(hotClient, /enabled: false/);
  assert.match(hotClient, /loadFullArchive/);
  assert.match(hotClient, /refetch\(\)/);
  assert.match(hotClient, /需要时加载完整档案/);
});

test("favorites use one external store instead of one browser listener set per button", () => {
  assert.match(favoritesHook, /useSyncExternalStore/);
  assert.match(favorites, /favoriteSubscribers/);
  assert.match(favorites, /browserListenersAttached/);
  assert.match(favorites, /window\.addEventListener\(FAVORITES_CHANGED_EVENT/);
  assert.match(favorites, /cachedFavoriteIds/);
  assert.doesNotMatch(favoriteButton, /addEventListener/);
  assert.doesNotMatch(favoriteButton, /FAVORITES_STORAGE_KEY/);
  assert.doesNotMatch(favoriteControls, /FAVORITES_CHANGED_EVENT/);
  assert.doesNotMatch(favoriteControls, /FAVORITES_STORAGE_KEY/);
  assert.doesNotMatch(favoriteControls, /isFavorite/);
  assert.match(favoriteControls, /useFavorite\(item\.id\)/);
});

test("favorites render progressively instead of mounting the full local archive", () => {
  assert.match(favoritesPage, /FAVORITES_BATCH_SIZE = 60/);
  assert.match(favoritesPage, /visible\.slice\(0, visibleLimit\)/);
  assert.match(favoritesPage, /setVisibleLimit\(\(current\) => current \+ FAVORITES_BATCH_SIZE\)/);
  assert.match(favoritesPage, /content-visibility: auto/);
  assert.match(favoritesPage, /contain-intrinsic-size/);
});

test("intelligence controls mount progressively after hydration", () => {
  assert.match(domRuntime, /new IntersectionObserver/);
  assert.match(domRuntime, /rootMargin: "1200px 0px"/);
  assert.match(domRuntime, /requestIdleCallback/);
  assert.match(domRuntime, /activeRows/);
  assert.match(domRuntime, /scheduleCandidateRefresh/);
});

test("core technology directory keeps summaries on detail pages instead of repeating them in index HTML", () => {
  assert.doesNotMatch(technologiesPage, /entity\.summary/);
  assert.match(technologiesPage, /详情保留摘要与可追溯时间线/);
});

test("Pages build enforces homepage and route-level client asset budgets", () => {
  assert.match(packageJson, /check:homepage-performance/);
  assert.match(packageJson, /scripts\/check-homepage-performance-budget\.mjs/);
  assert.match(packageJson, /check:route-performance/);
  assert.match(packageJson, /scripts\/check-route-performance-budget\.mjs/);
  assert.match(routeBudget, /\/search\//);
  assert.match(routeBudget, /\/hot\//);
  assert.match(routeBudget, /\/favorites\//);
  assert.match(routeBudget, /\/technologies\//);
  assert.match(routeBudget, /article_search_index\.json/);
});
