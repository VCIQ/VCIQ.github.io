import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ExternalDatabaseLinks } from "@/components/external-database-links";
import { FavoriteButton } from "@/components/favorite-button";
import { companies, reports } from "@/lib/catalog-data";
import { hanghangchaResearchLink } from "@/lib/external-database-links";
import {
  getSectorInstitutionRelations,
  institutionDirectoryHref,
  institutionEvidenceLabels,
} from "@/lib/institution-activity";
import { heatMethodology, snapshotDate } from "@/lib/intelligence-data";
import { reportContent } from "@/lib/research-content";
import { buildTrackWatchlistLink } from "@/lib/tracking-admin-link";
import {
  eventsForTrackedSector,
  getTrackedSector,
  trackedSectors,
} from "@/lib/tracked-sectors";
import styles from "./sector-detail.module.css";

const genericCompanies = new Set(["", "科技产业", "AI 研究", "未分类"]);

function unique(values: string[], limit = 20): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = raw.replace(/\s+/g, " ").trim();
    const key = value.toLocaleLowerCase("zh-CN");
    if (!value || seen.has(key)) continue;
    result.push(value);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

function emptyEventMessage(status: string, message: string): string {
  if (status === "pending") {
    return "赛道配置已写入，正在等待首次爬虫运行；完成前网站不会把该空快照视为正式结果。";
  }
  if (status === "error") {
    return `赛道爬虫本轮失败：${message}`;
  }
  if (status === "partial") {
    return `赛道爬虫仅部分完成：${message}`;
  }
  return message || "全部发现源均已运行，但当前没有满足归属条件的公开事件。";
}

export function generateStaticParams() {
  return trackedSectors.map((sector) => ({ slug: sector.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const sector = getTrackedSector(slug);
  return { title: sector?.name ?? "赛道" };
}

export default async function SectorDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const sector = getTrackedSector(slug);
  if (!sector) notFound();

  const allEvents = eventsForTrackedSector(sector).sort((a, b) =>
    b.publishedAt.localeCompare(a.publishedAt),
  );
  const events = allEvents.slice(0, 20);
  const relatedCompanies = companies
    .filter((item) => sector.aliases.includes(item.sector))
    .slice(0, 12);
  const catalogCompanyNames = new Set(
    relatedCompanies.map((company) => company.name.toLocaleLowerCase("zh-CN")),
  );
  const observedCompanies = events
    .map((event) => event.company)
    .filter((company) => !genericCompanies.has(company));
  const customCompanies = unique([
    ...sector.tracking.sampleCompanies,
    ...observedCompanies,
  ]).filter(
    (name) => !catalogCompanyNames.has(name.toLocaleLowerCase("zh-CN")),
  );
  const institutionRelations = getSectorInstitutionRelations(
    {
      slug: sector.slug,
      name: sector.name,
      aliases: sector.aliases,
      keywords: sector.tracking.keywords,
      subsectors: sector.subsectors,
    },
    allEvents,
  ).slice(0, 18);
  const relatedReports = reports.filter((report) =>
    reportContent[report.slug]?.eventSectors.some((name) =>
      sector.aliases.includes(name),
    ),
  );
  const chinaCompanies = relatedCompanies.filter(
    (item) => item.region === "中国",
  ).length;
  const usCompanies = relatedCompanies.filter(
    (item) => item.region === "美国",
  ).length;
  const coverage = sector.coverage;

  return (
    <main className="page-shell subpage">
      <header className={styles.hero}>
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}>
            SECTOR DOSSIER · {coverage.label} · {sector.events} 项公开事件
          </p>
          <div className="detail-title-row">
            <h1>{sector.name}</h1>
            <FavoriteButton
              item={{
                id: `technology:${sector.slug}`,
                href: `/technology/${sector.slug}`,
                title: sector.name,
                summary: sector.definition,
                channel: "technology",
                channelLabel: "新兴科技",
                keywords: [
                  ...sector.subsectors,
                  ...sector.tracking.keywords,
                ],
                sectors: [sector.name, ...sector.aliases],
                sources: events.slice(0, 12).map((event) => ({
                  name: event.source.name,
                  url: event.source.url,
                  level: event.source.level,
                })),
                region: "全球",
              }}
            />
          </div>
          <p className={styles.heroDescription}>{sector.definition}</p>
          <div className={styles.chips}>
            {sector.subsectors.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </div>
        <div className={styles.heroStat}>
          <span>HeatScore</span>
          <strong>{sector.heat}</strong>
          <small>
            {coverage.completedSources}/{coverage.expectedSources} 路爬虫完成
          </small>
        </div>
      </header>

      <div className={styles.stack}>
        <article className={styles.article}>
          <Section id="赛道定义" title="赛道定义">
            <p className={styles.lead}>{sector.definition}</p>
            <div className={styles.summaryGrid}>
              <div className={styles.summaryCard}>
                <span>公开事件</span>
                <strong>{sector.events}</strong>
                <p>包含本轮新抓取及从既有快照回填的相关事件。</p>
              </div>
              <div className={styles.summaryCard}>
                <span>独立来源</span>
                <strong>{sector.sourceCount}</strong>
                <p>当前赛道事件对应的独立原始链接数量。</p>
              </div>
              <div className={styles.summaryCard}>
                <span>活跃 / 关联机构</span>
                <strong>
                  {sector.institutions} / {sector.associatedInstitutions}
                </strong>
                <p>活跃要求直接公开事件或投资榜单证据；方向和组合关系单独记为关联。</p>
              </div>
              <div className={styles.summaryCard}>
                <span>自定义对象</span>
                <strong>
                  {sector.tracking.keywords.length +
                    sector.tracking.people.length +
                    sector.tracking.sampleCompanies.length}
                </strong>
                <p>用户配置的关键词、关键人物和样本公司总数。</p>
              </div>
            </div>
          </Section>

          <Section id="爬取覆盖" title="赛道爬取覆盖">
            <p className={styles.lead}>{coverage.message}</p>
            <div className={styles.summaryGrid}>
              <div className={styles.summaryCard}>
                <span>发现源完成度</span>
                <strong>
                  {coverage.completedSources}/{coverage.expectedSources}
                </strong>
                <p>Bing、Google News 中英文与今日头条四路发现。</p>
              </div>
              <div className={styles.summaryCard}>
                <span>扫描 / 接收</span>
                <strong>
                  {coverage.scanned} / {coverage.accepted}
                </strong>
                <p>本轮搜索结果扫描数与通过基础解析的记录数。</p>
              </div>
              <div className={styles.summaryCard}>
                <span>历史回填</span>
                <strong>{coverage.backfilledArticles}</strong>
                <p>从现有情报库重新识别并归入该赛道的文章。</p>
              </div>
              <div className={styles.summaryCard}>
                <span>失败来源</span>
                <strong>{coverage.failedSources}</strong>
                <p>最近一次覆盖检查中返回错误的发现源数量。</p>
              </div>
            </div>
          </Section>

          <Section id="中美对照" title="中美发展对照">
            <div className={styles.comparisonGrid}>
              <div className={styles.comparisonCard}>
                <span>中国</span>
                <strong>{chinaCompanies} 家目录公司</strong>
                <p>{sector.chinaLens}</p>
              </div>
              <div className={styles.comparisonCard}>
                <span>美国</span>
                <strong>{usCompanies} 家目录公司</strong>
                <p>{sector.usLens}</p>
              </div>
            </div>
          </Section>

          <Section id="产业链" title="产业链结构">
            <div className={styles.chain}>
              {sector.chain.map((node) => (
                <div className={styles.chainNode} key={node.title}>
                  <strong>{node.title}</strong>
                  <span>{node.detail}</span>
                </div>
              ))}
            </div>
          </Section>

          <Section id="代表公司" title="代表公司">
            {relatedCompanies.length || customCompanies.length ? (
              <div className={styles.entityGrid}>
                {relatedCompanies.map((company) => (
                  <Link
                    className={styles.companyCard}
                    href={`/companies/${company.slug}`}
                    key={company.slug}
                  >
                    <span>
                      {company.region} · {company.stage}
                    </span>
                    <strong>{company.name}</strong>
                    <p>{company.product}</p>
                  </Link>
                ))}
                {customCompanies.map((company) => (
                  <div className={styles.companyCard} key={company}>
                    <span className={styles.customBadge}>
                      {sector.tracking.sampleCompanies.includes(company)
                        ? "用户添加"
                        : "事件识别"}
                    </span>
                    <strong>{company}</strong>
                    <p>该主体已进入本赛道的搜索、事件归属和持续跟踪范围。</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className={styles.empty}>暂无样本公司，可在追踪配置中添加。</p>
            )}
            <a
              className={styles.configLink}
              href={buildTrackWatchlistLink(sector.slug)}
              target="_blank"
              rel="noreferrer"
            >
              管理关注技术、人物与公司 ↗
            </a>
          </Section>

          <Section id="投资机构" title="活跃与关联机构">
            <p className={styles.lead}>
              直接事件与投资类榜单用于激活机构；被投组合和明确投资方向只建立关联，不会被冒充为近期投资动作。机构关联文章的浏览、收藏和分享会同步进入 09 热点的机构榜。
            </p>
            {institutionRelations.length ? (
              <div className={styles.entityGrid}>
                {institutionRelations.map((relation) => {
                  const institution = relation.institution;
                  const labels = institutionEvidenceLabels(relation);
                  return (
                    <Link
                      className={styles.institutionCard}
                      href={institutionDirectoryHref(institution)}
                      key={institution.name}
                    >
                      <span>
                        {relation.active ? "活跃" : "已关联"} · {institution.region} · {institution.type}
                      </span>
                      <strong>{institution.name}</strong>
                      <p>
                        {labels.join(" · ")}
                        {relation.latestActivity
                          ? ` · 最近 ${relation.latestActivity}`
                          : ""}
                      </p>
                    </Link>
                  );
                })}
              </div>
            ) : (
              <p className={styles.empty}>
                当前没有达到证据门槛的机构关联；系统不会仅凭“科技”一类宽泛标签批量挂接机构。
              </p>
            )}
          </Section>

          <Section id="最新事件" title="最新公开事件">
            {events.length ? (
              <div className={styles.eventList}>
                {events.map((event) => (
                  <a
                    className={styles.eventCard}
                    href={event.source.url}
                    key={event.id}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <div className={styles.eventMeta}>
                      {event.publishedAt}
                      <br />
                      {event.type} · {event.region}
                    </div>
                    <div>
                      <strong>{event.title}</strong>
                      <p>{event.summary}</p>
                    </div>
                  </a>
                ))}
              </div>
            ) : (
              <p className={styles.empty}>
                {emptyEventMessage(coverage.status, coverage.message)}
              </p>
            )}
          </Section>

          <Section id="研究重点" title="关键研究变量">
            <div className={styles.focusGrid}>
              {sector.researchFocus.map((item, index) => (
                <div className={styles.focusCard} key={item}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>{item}</strong>
                </div>
              ))}
            </div>
          </Section>

          <Section id="相关研究" title="相关研究">
            {relatedReports.length ? (
              <div className={styles.researchGrid}>
                {relatedReports.map((report) => (
                  <Link
                    className={styles.researchCard}
                    href={`/reports/${report.slug}`}
                    key={report.slug}
                  >
                    <strong>{report.title}</strong>
                    <p>{report.summary}</p>
                    <span>
                      {report.date} · {report.sources} 个来源
                    </span>
                  </Link>
                ))}
              </div>
            ) : (
              <p className={styles.empty}>暂无与该赛道直接关联的专题研究。</p>
            )}
            <ExternalDatabaseLinks
              links={[hanghangchaResearchLink(sector.name, "赛道研报与数据图表公开索引检索")].filter(
                (link): link is NonNullable<typeof link> => Boolean(link),
              )}
              lead="以下入口跳转到外部研报数据库检索本赛道；报告在对方平台查看，本站不抓取、不缓存其内容。"
            />
          </Section>

          <Section id="风险" title="主要风险">
            <ul className={styles.riskList}>
              {sector.risks.map((risk) => (
                <li key={risk}>{risk}</li>
              ))}
            </ul>
          </Section>

          <Section id="数据口径" title="热度计算口径">
            <div className={styles.methodRow}>
              <p>{heatMethodology}</p>
              <p>
                数据更新：{coverage.lastRun?.slice(0, 10) || snapshotDate}
              </p>
            </div>
          </Section>
        </article>
      </div>
    </main>
  );
}

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className={styles.section} id={id}>
      <p className={styles.sectionLabel}>{id}</p>
      <h2>{title}</h2>
      {children}
    </section>
  );
}
