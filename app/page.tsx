import { DailyHeadlines } from "@/components/daily-headlines";
import {
  DashboardClient,
  type DashboardBootstrap,
} from "@/components/dashboard-client";
import { HomepageChannelUpdates } from "@/components/homepage-channel-updates";
import { HomepageTrackingActions } from "@/components/homepage-tracking-actions";
import { coreResearchObjectStats } from "@/lib/core-research-objects";
import { formatTaipeiDate } from "@/lib/snapshot-freshness";
import { trackedSectors } from "@/lib/tracked-sectors";
import type { ArticlePayload, LiveIntelligenceEvent } from "@/lib/use-articles";
import rawArticles from "@/public/data/articles.json";

const INITIAL_KEY_EVENTS_LIMIT = 80;
const snapshot = rawArticles as unknown as ArticlePayload;
const trackedSectorAliases = [
  ...new Set(trackedSectors.flatMap((sector) => sector.aliases)),
];
const trackedSectorNames = new Set(trackedSectorAliases);
const activeArticles = snapshot.articles.filter((item) => trackedSectorNames.has(item.sector));
const initialArticles: LiveIntelligenceEvent[] = activeArticles
  .filter((item) => item.qualityStatus !== "低可信")
  .sort(
    (left, right) =>
      right.importance - left.importance ||
      right.publishedAt.localeCompare(left.publishedAt),
  )
  .slice(0, INITIAL_KEY_EVENTS_LIMIT);

function marketSourceCount(market: "中国" | "美国") {
  return new Set(
    activeArticles
      .filter((item) => item.region === market)
      .map((item) => item.source.url),
  ).size;
}

function topSector(market: "中国" | "美国") {
  const counts = new Map<string, number>();
  activeArticles
    .filter((item) => item.region === market)
    .forEach((item) => counts.set(item.sector, (counts.get(item.sector) ?? 0) + 1));
  return [...counts.entries()].sort((left, right) => right[1] - left[1])[0]?.[0] ?? "持续更新";
}

const initialPayload: ArticlePayload = {
  schemaVersion: snapshot.schemaVersion,
  generatedAt: snapshot.generatedAt,
  articleCount: snapshot.articleCount,
  articles: initialArticles,
  sourceStatus: snapshot.sourceStatus,
  qualityGate: snapshot.qualityGate,
  refreshAudit: snapshot.refreshAudit,
};

const taipeiToday = formatTaipeiDate(new Date());
const bootstrap: DashboardBootstrap = {
  trackedSectorAliases,
  todayArticleCount: activeArticles.filter((item) => item.publishedAt === taipeiToday).length,
  sectorCount: trackedSectors.length,
  activeArticleCount: activeArticles.length,
  sourceCount: new Set(activeArticles.map((item) => item.source.url)).size,
  platformCount: new Set(
    activeArticles.map((item) => item.source.platform).filter(Boolean),
  ).size,
  latestPublishedAt: activeArticles.reduce(
    (latest, item) => (item.publishedAt > latest ? item.publishedAt : latest),
    "",
  ),
  chinaCount: activeArticles.filter((item) => item.region === "中国").length,
  usCount: activeArticles.filter((item) => item.region === "美国").length,
  marketSourceCounts: {
    中国: marketSourceCount("中国"),
    美国: marketSourceCount("美国"),
  },
  topSectors: {
    中国: topSector("中国"),
    美国: topSector("美国"),
  },
  researchObjectStats: coreResearchObjectStats,
};

export default function Home() {
  return (
    <main className="page-shell">
      <DashboardClient
        bootstrap={bootstrap}
        initialPayload={initialPayload}
        middle={<DailyHeadlines />}
      >
        <HomepageChannelUpdates />
      </DashboardClient>
      <HomepageTrackingActions />
    </main>
  );
}
