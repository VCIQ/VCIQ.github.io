import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { FavoriteButton } from "@/components/favorite-button";
import { companies, reports } from "@/lib/catalog-data";
import { intelligenceEvents, snapshotDate } from "@/lib/intelligence-data";
import { reportContent } from "@/lib/research-content";
import { buildTopicResearchBrief } from "@/lib/topic-research-brief";
import styles from "./brief.module.css";

export function generateStaticParams() {
  return reports.map((item) => ({ slug: item.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const report = reports.find((item) => item.slug === slug);
  return {
    title: report?.title ?? "研究报告",
    description: report?.summary,
  };
}

export default async function ReportDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const report = reports.find((item) => item.slug === slug);
  const content = reportContent[slug];
  if (!report || !content) notFound();

  const relatedCompanies = content.companySlugs
    .map((companySlug) =>
      companies.find((company) => company.slug === companySlug),
    )
    .filter((company) => company !== undefined);
  const brief = buildTopicResearchBrief({
    slug,
    content,
    events: intelligenceEvents,
    snapshotDate,
  });
  const sources = Array.from(
    new Map(
      [
        ...brief.evidence.map(({ event }) => event.source),
        ...relatedCompanies.map((company) => company.source),
      ].map((source) => [source.url, source]),
    ).values(),
  );
  const latestSignals = brief.evidence.slice(0, 4);

  return (
    <main className="page-shell subpage printable">
      <header className="report-hero">
        <p className="eyebrow">
          {report.type} · 更新 {snapshotDate}
        </p>
        <div className="detail-title-row">
          <h1>{report.title}</h1>
          <FavoriteButton
            item={{
              id: `report:${report.slug}`,
              href: `/reports/${report.slug}`,
              title: report.title,
              summary: report.summary,
              channel: "reports",
              channelLabel: "研究报告",
              keywords: report.tags,
              sectors: content.eventSectors,
              sources: sources.slice(0, 16).map((source) => ({
                name: source.name,
                url: source.url,
                level: source.level,
              })),
              region: "全球",
            }}
          />
        </div>
        <p>{content.thesis}</p>
        <div>
          {report.tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
          <span>{sources.length} 个可追溯来源</span>
        </div>
      </header>

      <article className="report-body">
        <Section title="3 分钟研究简报">
          <div className={styles.briefPanel}>
            <div className={styles.briefHeader}>
              <div>
                <p className={styles.briefEyebrow}>自动生成 · 构建时预计算</p>
                <h3>本期专题判断</h3>
              </div>
              <div className={styles.metaRow}>
                <span>{brief.readMinutes} 分钟阅读</span>
                <span>更新 {brief.generatedAt}</span>
                <span>{brief.evidence.length} 条核心证据</span>
              </div>
            </div>

            <div className={styles.briefSummary}>
              <p>{content.thesis}</p>
              <p>{brief.coverageSummary}</p>
              <p>{brief.evidenceSummary}</p>
            </div>

            <div className={styles.briefGrid}>
              <div>
                <h3>最近证据信号</h3>
                {latestSignals.length > 0 ? (
                  <div className={styles.signalList}>
                    {latestSignals.map(
                      ({ event, evidenceId, matchLabel }) => (
                        <article
                          className={styles.signalCard}
                          id={`brief-${evidenceId}`}
                          key={event.id}
                        >
                          <div className={styles.signalTopline}>
                            <span className={styles.evidenceId}>{evidenceId}</span>
                            <time>{event.publishedAt}</time>
                            <span className={styles.matchBadge}>{matchLabel}</span>
                          </div>
                          <strong>{event.title}</strong>
                          <p>{event.summary}</p>
                          <a
                            href={event.source.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {event.source.name} · {event.source.level}
                          </a>
                        </article>
                      ),
                    )}
                  </div>
                ) : (
                  <p>当前快照暂无满足专题规则的新证据。</p>
                )}
              </div>

              <aside className={styles.briefAside}>
                <div>
                  <h3>证据覆盖</h3>
                  <div className={styles.statGrid}>
                    <div className={styles.statCard}>
                      <strong>{brief.totalMatches}</strong>
                      <span>专题匹配事件</span>
                    </div>
                    <div className={styles.statCard}>
                      <strong>{brief.recent30Count}</strong>
                      <span>近 30 天核心证据</span>
                    </div>
                    <div className={styles.statCard}>
                      <strong>{brief.sourceCount}</strong>
                      <span>证据来源</span>
                    </div>
                    <div className={styles.statCard}>
                      <strong>{brief.companyCount}</strong>
                      <span>公司 / 主体</span>
                    </div>
                  </div>
                </div>

                <div>
                  <h3>下一步验证</h3>
                  <ol className={styles.watchList}>
                    {content.watchlist.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ol>
                </div>

                <p className={styles.methodNote}>
                  简报只使用当前专题规则命中的已入库公开事件。研究判断与事实证据分层展示；同属一个大赛道，不代表自动进入本专题证据池。
                </p>
              </aside>
            </div>
          </div>
        </Section>

        <Section title="摘要">
          <p>{report.summary}</p>
          <p>{content.thesis}</p>
        </Section>

        <Section title="核心发现">
          <div className="insight-grid">
            {content.points.map((point, index) => (
              <div key={point.title}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{point.title}</strong>
                <p>{point.body}</p>
              </div>
            ))}
          </div>
        </Section>

        {brief.evidence.length > 0 && (
          <Section title="专题证据时间线">
            <div className="timeline">
              {brief.evidence.map(
                ({ event, evidenceId, matchLabel }) => (
                  <div id={`evidence-${evidenceId}`} key={event.id}>
                    <time>{event.publishedAt}</time>
                    <div>
                      <div className={styles.timelineMeta}>
                        <span className={styles.evidenceId}>{evidenceId}</span>
                        <span className={`tag tag-${event.type}`}>
                          {event.type}
                        </span>
                        <span>{event.company}</span>
                        <span className={styles.matchBadge}>{matchLabel}</span>
                      </div>
                      <strong>{event.title}</strong>
                      <p>{event.summary}</p>
                      <a
                        className={styles.evidenceLink}
                        href={event.source.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {event.source.name} · {event.source.level}
                      </a>
                    </div>
                  </div>
                ),
              )}
            </div>
          </Section>
        )}

        <Section title="公司样本">
          <div className="entity-list">
            {relatedCompanies.map((company) => (
              <Link href={`/companies/${company.slug}`} key={company.slug}>
                <strong>{company.name}</strong>
                <span>
                  {company.region} · {company.product}
                </span>
              </Link>
            ))}
          </div>
        </Section>

        <Section title="后续跟踪">
          <div className="analysis-grid">
            {content.watchlist.map((item, index) => (
              <div key={item}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{item}</strong>
                <p>后续公告和监管文件将进入同一专题证据筛选流程。</p>
              </div>
            ))}
          </div>
        </Section>

        <Section title="来源">
          {sources.map((source) => (
            <a
              className="source-card"
              href={source.url}
              target="_blank"
              rel="noreferrer"
              key={source.url}
            >
              <span>{source.level}</span>
              <strong>{source.name}</strong>
              <small>{source.url}</small>
            </a>
          ))}
        </Section>
        <footer>修订时间：{snapshotDate} · 研究记录，不构成投资建议</footer>
      </article>
    </main>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <p className="section-index">{title}</p>
      <h2>{title}</h2>
      {children}
    </section>
  );
}
