import { mergeRankedIntelligenceIntoArticlePayload } from "@/lib/ranked-intelligence";
import type { ArticlePayload } from "@/lib/use-articles";
import rawArticles from "@/public/data/articles.json";
import rawRankedIntelligence from "@/public/data/ranked-intelligence.json";

export type DailyHeadline = {
  id: string;
  title: string;
  href: string;
  source: string;
  platform: string;
  label: string;
  date: string;
  time: string;
  publishedAt: string;
  importance: number;
};

type ArticleRecord = {
  id?: string;
  title?: string;
  summary?: string;
  type?: string;
  publishedAt?: string;
  importance?: number;
  qualityStatus?: string;
  source?: { name?: string; url?: string; platform?: string };
};

type ArticlesPayload = { generatedAt?: string; articles?: ArticleRecord[] };

export const DAILY_HEADLINES_LIMIT = 200;
export const DAILY_HEADLINES_PER_SOURCE_PER_DAY = 50;

// Search and discovery proxies are query results, not the site's own
// configured publishers; regulator filings and paper indexes are not
// headline material either. Google Alerts RSS is allowed because the bridge
// projects the canonical publisher URL/source rather than a Google result URL.
const EXCLUDED_PLATFORMS = new Set([
  "Google News",
  "谷歌新闻",
  "Bing",
  "必应",
  "公开搜索",
  "SEC",
  "arXiv",
  "OpenAlex",
]);

const payload = mergeRankedIntelligenceIntoArticlePayload(
  rawArticles as unknown as ArticlePayload,
  rawRankedIntelligence,
) as ArticlesPayload;

function headlineDay(publishedAt: string): string {
  return publishedAt.slice(0, 10);
}

function headlineTime(publishedAt: string): string {
  if (!/[T ]\d{2}:\d{2}/u.test(publishedAt)) return "";
  const parsed = new Date(publishedAt);
  if (Number.isNaN(parsed.getTime())) return "";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Taipei",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parsed);
}

export function selectDailyHeadlines(
  articles: ArticleRecord[],
  limit: number = DAILY_HEADLINES_LIMIT,
  perSourcePerDay: number = DAILY_HEADLINES_PER_SOURCE_PER_DAY,
): DailyHeadline[] {
  const candidates = articles
    .filter((article) => {
      const source = article.source ?? {};
      const platform = (source.platform ?? "").trim();
      const day = headlineDay(String(article.publishedAt ?? ""));
      return Boolean(
        article.title &&
          article.qualityStatus !== "低可信" &&
          source.url &&
          (source.name || platform) &&
          /^\d{4}-\d{2}-\d{2}$/.test(day) &&
          !EXCLUDED_PLATFORMS.has(platform),
      );
    })
    .map((article, index) => {
      const publishedAt = String(article.publishedAt ?? "");
      return {
        id: String(article.id ?? `headline-${index}`),
        title: String(article.title),
        href: String(article.source?.url),
        source: String(article.source?.name || article.source?.platform || ""),
        platform: String(article.source?.platform || article.source?.name || ""),
        label: String(article.type ?? "动态"),
        date: headlineDay(publishedAt),
        time: headlineTime(publishedAt),
        publishedAt,
        importance: Number(article.importance ?? 0) || 0,
      };
    })
    .sort(
      (left, right) =>
        right.publishedAt.localeCompare(left.publishedAt) ||
        right.importance - left.importance ||
        left.title.localeCompare(right.title, "zh-CN"),
    );

  // 每个信息源每天最多贡献固定数量的头条，避免单一来源刷屏。
  const perGroup = new Map<string, number>();
  const seenUrls = new Set<string>();
  const headlines: DailyHeadline[] = [];
  for (const candidate of candidates) {
    if (headlines.length >= limit) break;
    const urlKey = candidate.href.toLowerCase();
    if (seenUrls.has(urlKey)) continue;
    const groupKey = `${candidate.source}|${candidate.date}`;
    const used = perGroup.get(groupKey) ?? 0;
    if (used >= perSourcePerDay) continue;
    perGroup.set(groupKey, used + 1);
    seenUrls.add(urlKey);
    headlines.push(candidate);
  }
  return headlines;
}

export function getDailyHeadlines(): {
  generatedAt: string;
  headlines: DailyHeadline[];
} {
  return {
    generatedAt: String(payload.generatedAt ?? ""),
    headlines: selectDailyHeadlines(payload.articles ?? []),
  };
}
