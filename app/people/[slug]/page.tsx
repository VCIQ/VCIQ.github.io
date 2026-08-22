import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ExternalDatabaseLinks } from "@/components/external-database-links";
import { FavoriteButton } from "@/components/favorite-button";
import {
  hanghangchaResearchLink,
  personDatabaseLinks,
} from "@/lib/external-database-links";
import { researchPeople } from "@/lib/people-data";
import {
  clusterPersonMaterials,
  getPersonResearchSnapshot,
  type PersonMaterialEvent,
} from "@/lib/people-research";
import styles from "./page.module.css";

const materialLabels: Record<string, string> = {
  official_profile: "官方档案",
  authored_work: "本人著作",
  biography: "人物背景",
  shareholder_letter: "股东信",
  interview: "采访",
  speech: "演讲",
  qa: "问答",
  article: "文章",
  public_post: "公开发文",
  public_document: "公开文件",
  compiled_work: "第三方整理",
  commentary: "第三方评论",
  research_paper: "研究论文",
};

export function generateStaticParams() {
  return researchPeople.map((item) => ({ slug: item.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const person = researchPeople.find((item) => item.slug === slug);
  return {
    title: person?.name ?? "人物研究",
    description: person
      ? `${person.name}的研究摘要、关键变化、研究主线、观点演进和事件级公开材料。`
      : "人物研究",
  };
}

export default async function PersonDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const person = researchPeople.find((item) => item.slug === slug);
  if (!person) notFound();
  const research = getPersonResearchSnapshot(person);
  const speechEvents = clusterPersonMaterials(person.speeches, person.name, person.updatedAt);
  const registryLinks = personDatabaseLinks(person.name);
  const externalLinks = [
    ...registryLinks,
    ...(registryLinks.length
      ? [hanghangchaResearchLink(person.name, "人物相关研报与公开观点检索")]
      : []),
  ].filter((link): link is NonNullable<typeof link> => Boolean(link));
  const sections = [
    "研究摘要",
    "人物背景",
    "公司与机构",
    "产品与项目",
    "作品与著作",
    "研究主线",
    "核心观点",
    "观点演进",
    "演讲与采访",
    "公开材料",
  ];

  return (
    <main className="page-shell subpage">
      <header className="entity-hero person-hero">
        <div>
          <p className="eyebrow">人物档案 · {person.englishName}</p>
          <div className="detail-title-row">
            <h1>{person.name}</h1>
            <FavoriteButton
              item={{
                id: `person:${person.slug}`,
                href: `/people/${person.slug}`,
                title: person.name,
                summary: research.whyImportant,
                channel: "people",
                channelLabel: "人物研究",
                keywords: [
                  ...person.concepts,
                  ...person.products,
                ],
                sectors: person.sectors,
                sources: research.events.slice(0, 16).map((event) => ({
                  name: event.representative.source,
                  url: event.representative.url,
                  level: "事件主信源",
                })),
                region: "全球",
                company: person.organizations[0] ?? "",
              }}
            />
          </div>
          <p>{person.role}</p>
          <div className="hero-chips">
            {person.sectors.map((sector) => <span key={sector}>{sector}</span>)}
            {person.handles.map((handle) => <span key={handle}>@{handle}</span>)}
            <span>{research.events.length} 个事件 / {person.materials.length} 条原始材料</span>
          </div>
        </div>
        <div className="person-monogram large">{person.name.slice(0, 1)}</div>
      </header>

      <div className="detail-layout">
        <aside className="toc">
          <strong>人物研究</strong>
          {sections.map((item) => <a href={`#${item}`} key={item}>{item}</a>)}
        </aside>

        <article className="detail-article">
          <Section id="研究摘要" title="人物研究摘要">
            <div className={styles.snapshotGrid}>
              <div className={styles.snapshotCard}>
                <span>WHY IT MATTERS</span>
                <strong>为什么重要</strong>
                <p>{research.whyImportant}</p>
              </div>
              <div className={styles.snapshotCard}>
                <span>LATEST CHANGE</span>
                <strong>最新变化</strong>
                {research.latestChange ? (
                  <>
                    <p>{research.latestChange.date} · {research.latestChange.title}</p>
                    <a href={research.latestChange.url} target="_blank" rel="noreferrer">
                      {research.latestChange.source} · 查看证据
                    </a>
                  </>
                ) : <p>暂无可核验的近期人物事件。</p>}
              </div>
              <div className={styles.snapshotCard}>
                <span>NEXT WATCH</span>
                <strong>下一步观察</strong>
                <p>{research.nextWatch}</p>
              </div>
            </div>
          </Section>

          <Section id="人物背景" title="人物背景">
            <p>{person.background || person.summary || "暂无可验证的背景资料，后台将在下一轮统一抓取时继续补充。"}</p>
            {person.aliases.length > 1 && <p className="method-note">别名：{person.aliases.join(" · ")}</p>}
          </Section>

          <Section id="公司与机构" title="公司与机构">
            <FactList values={person.organizations} empty="暂无已验证的公司、任职机构或研究机构信息。" />
          </Section>

          <Section id="产品与项目" title="产品与项目">
            <FactList values={person.products} empty="暂无已验证的产品或项目关联。" />
          </Section>

          <Section id="作品与著作" title="作品、论文与著作">
            <FactList values={[...person.works, ...person.books]} empty="暂无已验证的代表作品或著作条目；相关论文仍可在公开材料中查看。" />
          </Section>

          <Section id="研究主线" title="研究主线">
            <p>{research.researchOverview}</p>
            <p className="method-note">
              研究主线要求同一主题获得跨材料或跨行动的重复证据；人物简介、单次采访和转载数量本身不构成长期技术判断。
            </p>
          </Section>

          <Section id="核心观点" title="核心观点与概念">
            {research.coreConcepts.length ? (
              <div className="concept-grid">
                {research.coreConcepts.map((concept, index) => (
                  <div key={concept.name}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <strong>{concept.name}</strong>
                    <p>{concept.explanation}</p>
                    {concept.evidence && (
                      <a href={concept.evidence.url} target="_blank" rel="noreferrer">
                        相关证据 · {concept.evidence.title}
                      </a>
                    )}
                  </div>
                ))}
              </div>
            ) : <p>当前还没有足够证据提炼稳定的核心观点；暂不从人物背景自动生成观点。</p>}
          </Section>

          <Section id="观点演进" title="观点演进 / 公开表达时间线">
            {!research.hasVerifiedEvolution && (
              <div className={styles.evolutionNotice}>
                当前材料还不足以可靠判断观点发生了变化。以下仅展示按时间排列的公开材料样本，
                不把发布时间差异自动解释为观点迁移。
              </div>
            )}
            {research.evolution.length ? (
              <div className="timeline">
                {research.evolution.map((item, index) => (
                  <div key={`${item.label}-${item.statement}-${index}`}>
                    <time>{item.label}</time>
                    <div>
                      <strong>{item.statement}</strong>
                      {item.evidence && (
                        <p><a href={item.evidence.url} target="_blank" rel="noreferrer">{item.evidence.source} · 查看原始材料</a></p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : <p>当前没有足够的时间序列材料。</p>}
          </Section>

          <Section id="演讲与采访" title="演讲、采访与公开对话">
            <EventMaterialList events={speechEvents} empty="暂无已验证的演讲、采访或公开对话。" />
          </Section>

          <Section id="公开材料" title="事件级公开材料">
            <p className="method-note">
              同一人物的同一事件聚合为一条主记录，优先展示更接近原始出处的材料；其他转载或镜像仍作为同事件信源保留。
            </p>
            <EventMaterialList events={research.events} empty="暂无可追溯公开材料。" />
            <ExternalDatabaseLinks
              links={externalLinks}
              lead="以下入口跳转到外部商业数据库检索该人物的任职、持股、创投记录与相关研报；数据在对方平台查看，本站不抓取、不缓存其内容。"
            />
          </Section>
        </article>

        <aside className="source-rail">
          <div className="confidence-box">
            <span>人物事件</span>
            <strong>{research.events.length}</strong>
            <p>由 {person.materials.length} 条原始材料按同一人物、标题语义与时间窗口聚合</p>
          </div>
          <div className="confidence-box">
            <span>原始材料</span>
            <strong>{person.materials.length}</strong>
            <p>保留每个事件的公开信源，避免事件去重后丢失证据链</p>
          </div>
          <div className="confidence-box">
            <span>最后更新</span>
            <strong>{person.updatedAt ? person.updatedAt.slice(0, 10) : "精选"}</strong>
            <p>后台使用统一人物资料管线持续更新</p>
          </div>
        </aside>
      </div>
    </main>
  );
}

function FactList({ values, empty }: { values: string[]; empty: string }) {
  if (!values.length) return <p>{empty}</p>;
  return <div className="concept-grid">{values.map((value, index) => <div key={value}><span>{String(index + 1).padStart(2, "0")}</span><strong>{value}</strong></div>)}</div>;
}

function EventMaterialList({ events, empty }: { events: PersonMaterialEvent[]; empty: string }) {
  if (!events.length) return <p>{empty}</p>;
  return (
    <div className={styles.eventList}>
      {events.map((event) => {
        const material = event.representative;
        const label = materialLabels[material.type] ?? material.type;
        const otherSources = event.items
          .filter((item) => item.url !== material.url)
          .filter((item, index, values) => values.findIndex((candidate) => candidate.url === item.url) === index)
          .slice(0, 5);
        return (
          <div className={styles.eventGroup} key={event.id}>
            <a
              className={styles.eventPrimary}
              href={material.url}
              target="_blank"
              rel="noreferrer"
              data-intelligence-item="true"
              data-intelligence-title={material.title}
              data-intelligence-summary={material.source}
              data-intelligence-type={label}
              data-intelligence-date={material.date}
              data-intelligence-source={material.source}
              data-intelligence-source-level="事件主信源"
              data-intelligence-channel="people"
              data-intelligence-channel-label="人物研究"
            >
              <span data-intelligence-type>{label}</span>
              <div>
                <strong data-intelligence-title>{material.title}</strong>
                <p data-intelligence-source>{material.source}</p>
              </div>
              <time>{material.date}</time>
            </a>
            {event.sourceCount > 1 && (
              <div className={styles.eventSources}>
                <span>同事件 {event.sourceCount} 个公开信源</span>
                {otherSources.map((source) => (
                  <a href={source.url} target="_blank" rel="noreferrer" key={source.url}>
                    {source.source}
                  </a>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return <section id={id} className="article-section"><p className="section-index">{id}</p><h2>{title}</h2>{children}</section>;
}
