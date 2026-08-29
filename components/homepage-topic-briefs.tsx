import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { reports } from "@/lib/catalog-data";
import { intelligenceEvents, snapshotDate } from "@/lib/intelligence-data";
import { reportContent } from "@/lib/research-content";
import { buildTopicResearchBrief } from "@/lib/topic-research-brief";
import styles from "./homepage-topic-briefs.module.css";

const topicBriefs = reports.flatMap((report) => {
  const content = reportContent[report.slug];
  if (!content) return [];

  const brief = buildTopicResearchBrief({
    slug: report.slug,
    content,
    events: intelligenceEvents,
    snapshotDate,
  });
  const latestEvidenceDate = brief.evidence[0]?.event.publishedAt ?? report.date;

  return [{ report, brief, latestEvidenceDate }];
});

export function HomepageTopicBriefs() {
  return (
    <section className={styles.section} aria-label="专题研究与3分钟简报">
      <header className={styles.header}>
        <div>
          <p>04 / TOPIC RESEARCH BRIEFS</p>
          <h2>专题研究 / 3 分钟简报</h2>
          <span>
            将长期研究框架与最新可追溯证据合并，快速判断赛道最近发生了什么、原有判断是否需要调整。
          </span>
        </div>
        <Link href="/reports">
          查看全部专题 <ArrowUpRight size={14} aria-hidden="true" />
        </Link>
      </header>

      <div className={styles.grid}>
        {topicBriefs.map(({ report, brief, latestEvidenceDate }, index) => (
          <Link
            className={styles.card}
            href={`/reports/${report.slug}`}
            key={report.slug}
          >
            <div className={styles.topline}>
              <span>{String(index + 1).padStart(2, "0")} · {report.type}</span>
              <strong>3 分钟</strong>
            </div>

            <h3>{report.title}</h3>
            <p>{report.summary}</p>

            <div className={styles.metrics}>
              <span>简报重算 {brief.generatedAt}</span>
              <span>最新证据 {latestEvidenceDate}</span>
              <span>{brief.evidence.length} 条核心证据</span>
            </div>

            <div className={styles.tags}>
              {report.tags.map((tag) => <i key={tag}>{tag}</i>)}
            </div>

            <footer>
              <span>进入专题简报</span>
              <ArrowUpRight size={14} aria-hidden="true" />
            </footer>
          </Link>
        ))}
      </div>

      <div className={styles.note}>
        <span>当前 {topicBriefs.length} 个持续更新专题</span>
        <span>证据快照 {snapshotDate}</span>
        <span>仅纳入通过专题匹配与来源质量门的可追溯事件</span>
      </div>
    </section>
  );
}
