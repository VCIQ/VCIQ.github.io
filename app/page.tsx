import type { Metadata } from "next";
import {
  DailyHeadlines,
  getHomepageHeadlines,
} from "@/components/daily-headlines";
import {
  DashboardClient,
  type DashboardBootstrap,
} from "@/components/dashboard-client";
import { HomepageChannelUpdates } from "@/components/homepage-channel-updates";
import { coreResearchObjectStats } from "@/lib/core-research-objects";
import { formatTaipeiDate } from "@/lib/snapshot-freshness";
import { trackedSectors } from "@/lib/tracked-sectors";
import type { ArticlePayload, LiveIntelligenceEvent } from "@/lib/use-articles";
import rawArticles from "@/public/data/articles.json";

// Keep the public landing page useful before hydrating or downloading the full
// article archive. The complete archive remains available after an explicit
// filter, sort, or "load more" action in DashboardClient.
const INITIAL_KEY_EVENTS_LIMIT = 20;
const SITE_URL = "https://vciq.github.io";
const HOME_TITLE = "丽泽路1号｜一级市场科技研究";
const HOME_DESCRIPTION =
  "围绕核心技术、核心赛道、核心人物与核心公司的公开、可追溯一级市场科技研究。";
const HOME_SOCIAL_IMAGE = {
  url: "/og-image.png",
  width: 1200,
  height: 630,
  type: "image/png",
  alt: "丽泽路1号：围绕四类核心研究对象的一级市场科技研究",
};

export const metadata: Metadata = {
  title: { absolute: HOME_TITLE },
  description: HOME_DESCRIPTION,
  alternates: { canonical: "/" },
  openGraph: {
    title: HOME_TITLE,
    description: HOME_DESCRIPTION,
    url: "/",
    siteName: "丽泽路1号",
    type: "website",
    locale: "zh_CN",
    images: [HOME_SOCIAL_IMAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: HOME_TITLE,
    description: HOME_DESCRIPTION,
    images: [HOME_SOCIAL_IMAGE],
  },
};

const structuredData = {
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "@id": `${SITE_URL}/#homepage`,
  url: `${SITE_URL}/`,
  name: HOME_TITLE,
  description: HOME_DESCRIPTION,
  inLanguage: "zh-CN",
  isPartOf: {
    "@type": "WebSite",
    "@id": `${SITE_URL}/#website`,
    url: `${SITE_URL}/`,
    name: "丽泽路1号",
  },
  about: ["核心技术", "核心赛道", "核心人物", "核心公司"].map((name) => ({
    "@type": "Thing",
    name,
  })),
};

const structuredDataJson = JSON.stringify(structuredData).replace(/</gu, "\\u003c");
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
  qualityGate: snapshot.qualityGate,
  refreshAudit: snapshot.refreshAudit,
};

const initialEventHrefs = initialArticles.map((item) => item.source.url);
const initialHeadlineHrefs = getHomepageHeadlines(initialEventHrefs).map(
  (item) => item.href,
);

const activeSourceIds = new Set(activeArticles.map((item) => item.sourceId).filter(Boolean));
const healthySourceCount = (snapshot.sourceStatus ?? []).filter(
  (item) =>
    activeSourceIds.has(item.id) &&
    ["ok", "partial"].includes(item.status) &&
    item.accepted > 0,
).length;

const taipeiToday = formatTaipeiDate(new Date());
const bootstrap: DashboardBootstrap = {
  trackedSectorAliases,
  todayArticleCount: activeArticles.filter((item) => item.publishedAt === taipeiToday).length,
  sectorCount: trackedSectors.length,
  activeArticleCount: activeArticles.length,
  healthySourceCount,
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
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: structuredDataJson }}
      />
      <DashboardClient
        bootstrap={bootstrap}
        initialPayload={initialPayload}
        middle={
          <DailyHeadlines
            excludeHrefs={initialEventHrefs}
          />
        }
      >
        <HomepageChannelUpdates
          excludeHrefs={[...initialEventHrefs, ...initialHeadlineHrefs]}
        />
      </DashboardClient>
    </main>
  );
}
