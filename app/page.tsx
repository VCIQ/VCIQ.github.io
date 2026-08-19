import {
  DashboardV2Client,
  type DashboardBootstrap,
} from "@/components/dashboard-v2-client";
import { HomepageTrackingActions } from "@/components/homepage-tracking-actions";
import unifiedStyles from "@/components/homepage-unified-inbox.module.css";
import { coreResearchObjectStats } from "@/lib/core-research-objects";
import {
  mergeRankedIntelligenceIntoArticlePayload,
  RANKED_INTELLIGENCE_FALLBACK_SECTOR,
} from "@/lib/ranked-intelligence";
import { formatTaipeiDate } from "@/lib/snapshot-freshness";
import { trackedSectors } from "@/lib/tracked-sectors";
import type { ArticlePayload, LiveIntelligenceEvent } from "@/lib/use-articles";
import rawArticles from "@/public/data/articles.json";
import rawRankedIntelligence from "@/public/data/ranked-intelligence.json";

const INITIAL_KEY_EVENTS_LIMIT = 36;
const snapshot = mergeRankedIntelligenceIntoArticlePayload(
  rawArticles as unknown as ArticlePayload,
  rawRankedIntelligence,
);
const trackedSectorAliases = [
  ...new Set([
    ...trackedSectors.flatMap((sector) => sector.aliases),
    RANKED_INTELLIGENCE_FALLBACK_SECTOR,
  ]),
];
const trackedSectorNames = new Set(trackedSectorAliases);
const activeArticles = snapshot.articles.filter(
  (item) => item.curated || trackedSectorNames.has(item.sector),
);

function compactHomepageArticle(item: LiveIntelligenceEvent): LiveIntelligenceEvent {
  return {
    id: item.id,
    title: item.title,
    summary: item.summary,
    type: item.type,
    region: item.region,
    sector: item.sector,
    company: item.company,
    companySlug: item.companySlug,
    personSlug: item.personSlug,
    sourceId: item.sourceId,
    publishedAt: item.publishedAt,
    importance: item.importance,
    source: item.source,
    curated: item.curated,
    qualityScore: item.qualityScore,
    qualityStatus: item.qualityStatus,
    qualitySignals: item.qualitySignals?.slice(0, 4),
    relatedSources: item.relatedSources?.slice(0, 3),
    duplicateCount: item.duplicateCount,
    eventClusterId: item.eventClusterId,
    wechatAccount: item.wechatAccount,
    mentionedCompanies: item.mentionedCompanies?.slice(0, 4),
    mentionedPeople: item.mentionedPeople?.slice(0, 4),
    matchedTrackingTerms: item.matchedTrackingTerms?.slice(0, 6),
  };
}

const initialArticles: LiveIntelligenceEvent[] = activeArticles
  .filter((item) => item.qualityStatus !== "低可信")
  .sort(
    (left, right) =>
      right.importance - left.importance ||
      right.publishedAt.localeCompare(left.publishedAt),
  )
  .slice(0, INITIAL_KEY_EVENTS_LIMIT)
  .map(compactHomepageArticle);

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
  todayArticleCount: activeArticles.filter((item) => item.publishedAt.slice(0, 10) === taipeiToday).length,
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
      <div className={unifiedStyles.root}>
        <DashboardV2Client
          bootstrap={bootstrap}
          initialPayload={initialPayload}
        >
          {null}
        </DashboardV2Client>
      </div>
      <HomepageTrackingActions />
    </main>
  );
}