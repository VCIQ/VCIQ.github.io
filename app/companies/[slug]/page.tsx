import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CompanyEquityEvidence } from "@/components/company-equity-evidence";
import { ExternalDatabaseLinks } from "@/components/external-database-links";
import { FavoriteButton } from "@/components/favorite-button";
import { ListedInnovationSecurities } from "@/components/listed-innovation-securities";
import { listedInnovationCompany } from "@/lib/listed-innovation-companies";
import { companies, institutionCatalog, reports } from "@/lib/catalog-data";
import {
  companyDatabaseLinks,
  hanghangchaResearchLink,
} from "@/lib/external-database-links";
import { intelligenceEvents, snapshotDate } from "@/lib/intelligence-data";
import {
  getCompanyResearch,
  getInstitutionProfile,
  reportContent,
} from "@/lib/research-content";
import {
  getCompanyVentureProfile,
  ventureProfileGeneratedAt,
  type VentureCapitalEvent,
  type VentureSource,
} from "@/lib/venture-profile-data";

export function generateStaticParams() {
  return companies.map((item) => ({ slug: item.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const company = companies.find((item) => item.slug === slug);
  const venture = getCompanyVentureProfile(slug);
  return {
    title: company?.name ?? "公司档案",
    description: venture?.background || company?.summary,
  };
}

export default async function CompanyDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const company = companies.find((item) => item.slug === slug);
  if (!company) notFound();

  const research = getCompanyResearch(company);
  const venture = getCompanyVentureProfile(slug);
  const updateDate =
    venture?.updatedAt?.slice(0, 10) ||
    ventureProfileGeneratedAt?.slice(0, 10) ||
    snapshotDate;
  const background = venture?.projectBackground?.summary || venture?.background || company.summary;
  const projectBackground = venture?.projectBackground;
  const technology = venture?.researchTechnology || venture?.technology || research.technology;
  const products = venture?.products?.length ? venture.products : [company.product];
  const technologyProducts = venture?.technologyProducts ?? [];
  const team = venture?.team ?? [];
  const financing = venture?.financing ?? [];
  const capitalSummary = venture?.capitalSummary;
  const capitalMarkets = venture?.capitalMarkets ?? [];
  const exitPerformance = venture?.exitPerformance;
  const listedIdentity = listedInnovationCompany(slug);
  const conflictingExitSummary = Boolean(listedIdentity && exitPerformance &&
    /未发现.{0,20}上市|未上市|未识别.{0,20}上市|no.{0,15}listing evidence/iu.test(
      `${exitPerformance.status} ${exitPerformance.latestEvent} ${exitPerformance.summary}`));
  const events = intelligenceEvents
    .filter((item) => item.companySlug === slug)
    .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))
    .slice(0, 12);
  const peers = companies
    .filter((item) => item.sector === company.sector && item.slug !== company.slug)
    .slice(0, 8);
  const relatedInstitutions = institutionCatalog.filter((institution) =>
    getInstitutionProfile(institution).portfolio.some(
      (portfolio) => portfolio.slug === company.slug,
    ),
  );
  const relatedReports = reports.filter((report) =>
    reportContent[report.slug]?.companySlugs.includes(company.slug),
  );
  const sources = uniqueSources([
    ...(venture?.sources ?? []),
    {
      name: company.source.name,
      url: company.source.url,
      level: company.source.level,
      section: "公司官网",
    },
    ...events.slice(0, 6).map((event) => ({
      name: event.source.name,
      url: event.source.url,
      level: event.source.level,
      section: event.type,
      title: event.title,
      publishedAt: event.publishedAt,
    })),
  ]);
  const toc = [
    "公司概览",
    "核心技术与产品",
    "核心团队",
    "投融资与资本运作",
    "股权与工商核验",
    "上市与退出表现",
    "公开动态",
    "关键研究问题",
    "同赛道对照",
    "风险观察",
    "来源",
  ];

  return (
    <main className="page-shell subpage">
      <header className="entity-hero">
        <div>
          <p className="eyebrow">
            {company.region} · {company.sector} · {company.status}
          </p>
          <div className="detail-title-row">
            <h1>{company.name}</h1>
            <FavoriteButton
              item={{
                id: `company:${company.slug}`,
                href: `/companies/${company.slug}`,
                title: company.name,
                summary: background,
                channel: "companies",
                channelLabel: "创业案例",
                keywords: technologyProducts.flatMap((item) => [
                  item.name,
                  item.category ?? "",
                ]),
                sectors: [company.sector],
                sources: sources.slice(0, 16).map((source) => ({
                  name: source.name,
                  url: source.url,
                  level: source.level,
                })),
                region: company.region,
                company: company.name,
              }}
            />
          </div>
          <p>{company.englishName}</p>
          <div className="hero-chips">
            <span>{company.stage}</span>
            <span>{company.headquarters}</span>
            <span>资料更新 {updateDate}</span>
            {venture && <span>证据完整度 {venture.evidenceScore ?? 0}%</span>}
          </div>
        </div>
        <div className="entity-monogram">{company.name.slice(0, 2).toUpperCase()}</div>
      </header>

      <div className="detail-layout">
        <aside className="toc">
          <strong>公司档案</strong>
          {toc.map((item) => (
            <a href={`#${item}`} key={item}>
              {item}
            </a>
          ))}
        </aside>

        <article className="detail-article">
          <Section id="公司概览" title="项目背景与公司概览">
            <dl className="facts-grid">
              <div>
                <dt>成立时间</dt>
                <dd>{company.founded || "待公开资料补充"}</dd>
              </div>
              <div>
                <dt>总部</dt>
                <dd>{company.headquarters || "待公开资料补充"}</dd>
              </div>
              <div>
                <dt>当前阶段</dt>
                <dd>{company.stage}</dd>
              </div>
              <div>
                <dt>产业方向</dt>
                <dd>{company.sector}</dd>
              </div>
            </dl>
            <p>{background}</p>
            {(projectBackground?.problemSolved || projectBackground?.marketOpportunity) && (
              <div className="insight-grid">
                {projectBackground.problemSolved && (
                  <Insight label="解决的问题" text={projectBackground.problemSolved} />
                )}
                {projectBackground.marketOpportunity && (
                  <Insight label="市场与应用机会" text={projectBackground.marketOpportunity} />
                )}
              </div>
            )}
          </Section>

          <Section id="核心技术与产品" title="核心技术与技术产品">
            <p>{technology}</p>
            {technologyProducts.length ? (
              <div className="analysis-grid">
                {technologyProducts.map((product) => {
                  const content = (
                    <>
                      <span>{product.category || "技术产品"}</span>
                      <strong>{product.name}</strong>
                      <p>{product.description}</p>
                      {product.technicalHighlights?.length ? (
                        <small>技术要点：{product.technicalHighlights.join("；")}</small>
                      ) : null}
                    </>
                  );
                  return product.sourceUrl ? (
                    <a
                      href={product.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                      key={product.name}
                    >
                      {content}
                    </a>
                  ) : (
                    <div key={product.name}>{content}</div>
                  );
                })}
              </div>
            ) : (
              <div className="insight-grid">
                {products.map((product) => (
                  <Insight label="产品 / 平台" text={product} key={product} />
                ))}
                <Insight label="产业位置" text={research.industryPosition} />
                <Insight label="商业化观察" text={research.commercialization} />
              </div>
            )}
          </Section>

          <Section id="核心团队" title="核心团队背景">
            {team.length ? (
              <div className="entity-list">
                {team.map((member) => {
                  const content = (
                    <>
                      <strong>{member.name}</strong>
                      <span>
                        {[
                          member.role,
                          member.summary,
                          member.background,
                          member.previousExperience,
                        ]
                          .filter(Boolean)
                          .join(" · ") || "公开团队成员"}
                      </span>
                    </>
                  );
                  return member.sourceUrl ? (
                    <a
                      href={member.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                      key={`${member.name}-${member.role ?? ""}`}
                    >
                      {content}
                    </a>
                  ) : (
                    <div key={`${member.name}-${member.role ?? ""}`}>{content}</div>
                  );
                })}
              </div>
            ) : (
              <EvidenceEmpty>
                本轮未从官方团队页识别到可核对成员。系统保留公司官网入口，并在后续刷新中继续发现创始人、管理层和技术负责人资料。
              </EvidenceEmpty>
            )}
          </Section>

          <Section id="投融资与资本运作" title="投融资与资本运营过程">
            {capitalSummary && (
              <div className="insight-grid">
                <Insight label="融资证据汇总" text={capitalSummary.summary} />
                <Insight
                  label="已披露金额"
                  text={
                    capitalSummary.disclosedAmounts.length
                      ? capitalSummary.disclosedAmounts.join("、")
                      : "未披露或尚未识别"
                  }
                />
                <Insight
                  label="主要投资方"
                  text={
                    capitalSummary.majorInvestors.length
                      ? capitalSummary.majorInvestors.join("、")
                      : "未披露或尚未识别"
                  }
                />
                <Insight
                  label="融资阶段"
                  text={
                    capitalSummary.rounds.length
                      ? capitalSummary.rounds.join("、")
                      : "未披露或尚未识别"
                  }
                />
              </div>
            )}
            <CapitalTimeline
              items={financing}
              emptyText="当前公开页面未识别到可核对的融资轮次、金额或投资方。页面不会用推测数据填充，后续通过公司公告、投资机构披露、专业数据库与监管材料继续补充。"
            />
          </Section>

          <Section id="股权与工商核验" title="股权、股东与工商变更核验">
            <CompanyEquityEvidence slug={slug} />
            <ExternalDatabaseLinks
              links={companyDatabaseLinks(company.name, company.region)}
            />
          </Section>

          <Section id="上市与退出表现" title="上市、并购与退出表现">
            <ListedInnovationSecurities slug={slug} />
            {exitPerformance && !conflictingExitSummary && (
              <div className="source-card">
                <span>{exitPerformance.status}</span>
                <strong>{exitPerformance.latestEvent || "资本市场结论"}</strong>
                <small>{exitPerformance.summary}</small>
                {exitPerformance.sourceUrl && (
                  <a href={exitPerformance.sourceUrl} target="_blank" rel="noreferrer">
                    查看原始披露
                  </a>
                )}
              </div>
            )}
            <CapitalTimeline
              items={capitalMarkets}
              emptyText={
                listedIdentity
                  ? "证券身份与来源见上方。事件时间线尚待补充；不将本次档案补录作为新的上市事件。"
                  : company.status === "已上市"
                  ? "目录显示公司已上市，但本轮尚未识别到更细的上市、并购或退出证据；后续将连接交易所和监管披露补齐。"
                  : "当前未发现公司上市、并购退出或明确退出安排的可核对公开证据。"
              }
            />
          </Section>

          <Section id="公开动态" title="融资、产品与监管动态">
            {events.length ? (
              <div className="timeline">
                {events.map((event) => (
                  <div key={event.id}>
                    <time>{event.publishedAt}</time>
                    <div>
                      <div className="event-tags">
                        <span className={`tag tag-${event.type}`}>{event.type}</span>
                      </div>
                      <strong>{event.title}</strong>
                      <p>{event.summary}</p>
                      <a href={event.source.url} target="_blank" rel="noreferrer">
                        {event.source.level} · {event.source.name}
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <a
                className="source-card"
                href={company.source.url}
                target="_blank"
                rel="noreferrer"
              >
                <span>公司动态入口</span>
                <strong>{company.source.name}</strong>
                <small>查看产品、公告与公司资料</small>
              </a>
            )}
          </Section>

          <Section id="关键研究问题" title="关键研究问题">
            <div className="analysis-grid">
              {research.researchQuestions.map((question, index) => (
                <div key={question}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>{question}</strong>
                  <p>结合后续产品、客户、财务与监管披露持续跟踪。</p>
                </div>
              ))}
            </div>
          </Section>

          <Section id="同赛道对照" title={`${company.sector}对照样本`}>
            <div className="entity-list">
              {peers.map((peer) => (
                <Link href={`/companies/${peer.slug}`} key={peer.slug}>
                  <strong>{peer.name}</strong>
                  <span>
                    {peer.region} · {peer.product}
                  </span>
                </Link>
              ))}
            </div>
          </Section>

          <Section id="风险观察" title="风险观察">
            <ul className="risk-list">
              {research.risks.map((risk) => (
                <li key={risk}>{risk}</li>
              ))}
              {venture?.warnings?.slice(0, 3).map((warning) => (
                <li key={warning}>资料限制：{warning}</li>
              ))}
            </ul>
          </Section>

          <Section id="来源" title="原始来源与证据链">
            {sources.map((source) => (
              <a
                className="source-card"
                href={source.url}
                target="_blank"
                rel="noreferrer"
                key={source.url}
              >
                <span>{source.publishedAt || source.section || source.level}</span>
                <strong>{source.title || source.name}</strong>
                <small>{source.url}</small>
              </a>
            ))}
            <ExternalDatabaseLinks
              links={[hanghangchaResearchLink(company.name, "公司相关研报与数据图表检索")].filter(
                (link): link is NonNullable<typeof link> => Boolean(link),
              )}
              lead="以下入口跳转到外部研报数据库检索本公司；报告在对方平台查看，本站不抓取、不缓存其内容。"
            />
          </Section>
        </article>

        <aside className="source-rail">
          {relatedInstitutions.length > 0 && (
            <>
              <strong>公开投资机构</strong>
              {relatedInstitutions.map((institution) => (
                <Link href={`/institutions/${institution.slug}`} key={institution.slug}>
                  {institution.name}
                  <span>{institution.stages}</span>
                </Link>
              ))}
            </>
          )}
          <strong>相关研究</strong>
          {relatedReports.map((report) => (
            <Link href={`/reports/${report.slug}`} key={report.slug}>
              {report.title}
              <span>{report.date}</span>
            </Link>
          ))}
          <div className="confidence-box">
            <span>证据完整度</span>
            <strong>{venture?.evidenceScore ?? 0}%</strong>
            <p>{venture ? "官网多页面抽取结果" : "等待首次档案刷新"}</p>
          </div>
          <div className="confidence-box">
            <span>团队成员</span>
            <strong>{team.length}</strong>
            <p>来自官网团队页与结构化数据</p>
          </div>
          <div className="confidence-box">
            <span>资本事件</span>
            <strong>{financing.length + capitalMarkets.length}</strong>
            <p>融资、上市、并购与退出</p>
          </div>
          <div className="confidence-box">
            <span>公开动态</span>
            <strong>{events.length}</strong>
            <p>公司公告与监管文件</p>
          </div>
        </aside>
      </div>
    </main>
  );
}

function CapitalTimeline({
  items,
  emptyText,
}: {
  items: VentureCapitalEvent[];
  emptyText: string;
}) {
  if (!items.length) return <EvidenceEmpty>{emptyText}</EvidenceEmpty>;
  return (
    <div className="timeline">
      {items.map((item, index) => {
        const body = (
          <>
            <div className="event-tags">
              <span className="tag">{item.type}</span>
              {item.round && <span className="tag">{item.round}</span>}
              {item.amount && <span className="tag">{item.amount}</span>}
            </div>
            <strong>{item.title}</strong>
            <p>{item.summary}</p>
            {item.investors?.length ? (
              <small>公开投资方：{item.investors.join("、")}</small>
            ) : null}
          </>
        );
        return (
          <div key={`${item.date ?? "unknown"}-${item.title}-${index}`}>
            <time>{item.date || "时间待核对"}</time>
            <div>
              {body}
              {item.sourceUrl && (
                <a href={item.sourceUrl} target="_blank" rel="noreferrer">
                  查看原始披露
                </a>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function uniqueSources(sources: VentureSource[]) {
  const seen = new Set<string>();
  return sources.filter((source) => {
    if (!/^https?:\/\//u.test(source.url) || seen.has(source.url)) return false;
    seen.add(source.url);
    return true;
  });
}

function EvidenceEmpty({ children }: { children: React.ReactNode }) {
  return (
    <div className="source-card">
      <span>公开证据待补充</span>
      <strong>不使用未经核对的推测数据</strong>
      <small>{children}</small>
    </div>
  );
}

function Insight({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <span>{label}</span>
      <p>{text}</p>
    </div>
  );
}

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="article-section">
      <p className="section-index">{id}</p>
      <h2>{title}</h2>
      {children}
    </section>
  );
}
