import { HomepageSortableFeed } from "@/components/homepage-sortable-feed";
import {
  DAILY_HEADLINES_PER_SOURCE_PER_DAY,
  getDailyHeadlines,
} from "@/lib/daily-headlines";
import styles from "@/components/homepage-columns.module.css";

export const HOMEPAGE_HEADLINE_LIMIT = 10;

function canonicalHref(value: string) {
  const raw = value.trim();
  try {
    const url = new URL(raw);
    url.hash = "";
    if (url.pathname !== "/") url.pathname = url.pathname.replace(/\/+$/u, "");
    return url.toString();
  } catch {
    return raw.split("#", 1)[0].replace(/\/+$/u, "");
  }
}

export function getHomepageHeadlines(excludeHrefs: string[] = []) {
  const { headlines } = getDailyHeadlines();
  const excluded = new Set(excludeHrefs.map(canonicalHref));
  const seen = new Set<string>();
  return headlines
    .filter((headline) => {
      const key = canonicalHref(headline.href);
      if (!key || excluded.has(key) || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, HOMEPAGE_HEADLINE_LIMIT);
}

export function DailyHeadlines({
  excludeHrefs = [],
}: {
  excludeHrefs?: string[];
}) {
  const { generatedAt } = getDailyHeadlines();
  const items = getHomepageHeadlines(excludeHrefs)
    .map((headline) => ({
      id: headline.id,
      title: headline.title,
      href: headline.href,
      tag: headline.label,
      context:
        headline.platform && headline.platform !== headline.source
          ? `${headline.source} · ${headline.platform}`
          : headline.source,
      date: headline.date,
      time: headline.time,
      asideLabel: headline.label,
      sortAt: headline.publishedAt,
      importance: headline.importance,
    }));

  return (
    <aside className={`headlines-column ${styles.column}`} aria-label="最新头条">
      <div className="section-heading compact">
        <div>
          <p className="section-index">03 / LATEST HEADLINES</p>
          <h2>最新头条</h2>
        </div>
        <span>辅助线索 · {items.length} 条</span>
      </div>

      <HomepageSortableFeed
        items={items}
        limit={HOMEPAGE_HEADLINE_LIMIT}
        ariaLabel="最新头条列表"
        initialSort="latest"
        description={`补充首屏关键事件之外的最新公开线索；每个来源每天最多 ${DAILY_HEADLINES_PER_SOURCE_PER_DAY} 条，首页仅展示 ${HOMEPAGE_HEADLINE_LIMIT} 条。`}
        emptyMessage={`信息源头条等待下一次抓取（快照 ${generatedAt.slice(0, 10) || "待更新"}）。`}
        archiveHref="/search/"
        archiveLabel="搜索全部公开证据"
      />
    </aside>
  );
}
