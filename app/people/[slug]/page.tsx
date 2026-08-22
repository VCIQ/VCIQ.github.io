import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ExternalDatabaseLinks } from "@/components/external-database-links";
import { FavoriteButton } from "@/components/favorite-button";
import {
  hanghangchaResearchLink,
  personDatabaseLinks,
} from "@/lib/external-database-links";
import { getPersonResearchAgenda } from "@/lib/person-research-agenda";
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

const researchTaskLabels: Record<string, string> = {
  identity_verification: "身份核验",
  first_party_evidence: "补一手证据",
  viewpoint_verification: "观点变化核验",
  execution_verification: "组织执行核验",
  freshness_update: "近期证据补齐",
};

const researchTaskStatusLabels: Record<string, string> = {
  open: "待检索",
  candidate_found: "已找到候选证据",
  supported: "成功判据已满足",
  blocked: "暂时受阻",
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
      ? `${person.name}的研究摘要、关键变化、主动研究任务、研究主线、观点演进和事件级公开材料。`
      : "人物研究",
  };
}

export default async function PersonDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const person = researchPeople.find((item) => item.slug === slug);
  if (!person) notFound();
  const research = getPersonResearchSnapshot(person);
  const activeAgenda = getPersonResearchAgenda(person.slug);
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
    "主动研究计划",
    "影响映射",
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
            <span>{research.priority.level} · 研究优先级 {research.priority.score}</span>
            <span>证据覆盖 {research.coverage.score}%</span>
            <span>{research.viewChange.label}</span>
            {activeAgenda && <span>{activeAgenda.openCount} 项主动研究任务</span>}
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
              <div className={styles.snapshotCard}>
                <span>RESEARCH PRIORITY</span>
                <strong>{research.priority.level} · {research.priority.score} / 100</strong>
                <p>{research.priority.reasons.join("；") || "当前未出现需要提高研究优先级的额外信号。"}</p>
              </div>
              <div className={styles.snapshotCard}>
                <span>EVIDENCE COVERAGE</span>
                <strong>{research.coverage.label} · {research.coverage.score}%</strong>
                <p>
                  {research.coverage.gaps.length
                    ? `仍有 ${research.coverage.gaps.length} 项缺口；首要补齐：${research.coverage.gaps[0]}。`
                    : "当前关键身份、主线、一手材料与时间序列证据已达到较完整覆盖。"}
                </p>
              </div>
              <div className={styles.snapshotCard}>
                <span>VIEW CHANGE</span>
                <strong>{research.viewChange.label}</strong>
                <p>{research.viewChange.summary}</p>
              </div>
            </div>
          </Section>

          <Section id="主动研究计划" title="主动研究计划">
            <p className="method-note">
              这里展示系统下一步准备验证的问题，而不是已经成立的事实。规则引擎根据身份、一手材料、观点变化、近期证据和组织执行缺口生成任务；
              第三方报道最多把任务推进到“候选证据”，只有满足成功判据的一手或官方证据才会自动关闭任务。
            </p>
            {activeAgenda?.tasks.length ? (
              <div className={styles.researchTaskList}>
                {activeAgenda.tasks.map((task) => (
                  <div className={styles.researchTaskCard} key={task.id}>
                    <div className={styles.researchTaskMeta}>
                      <span>{task.priority}</span>
                      <span>{researchTaskLabels[task.taskType] ?? task.taskType}</span>
                      <span>{researchTaskStatusLabels[task.status] ?? task.status}</span>
                    </div>
                    <strong>{task.question}</strong>
                    <p>{task.objective}</p>
                    {task.preferredEvidence.length > 0 && (
                      <div className={styles.researchTaskEvidenceTypes}>
                        <b>首选证据</b>
                        {task.preferredEvidence.map((item) => <span key={item}>{item}</span>)}
                      </div>
                    )}
                    {task.searchQueries.length > 0 && (
                      <div className={styles.researchTaskQuery}>
                        <b>有界检索方向</b>
                        <code>{task.searchQueries[0]}</code>
                      </div>
                    )}
                    <div className={styles.researchTaskCriteria}>
                      <b>成功判据</b>
                      <p>{task.successCriteria}</p>
                    </div>
                    {task.candidateEvidence.length > 0 && (
                      <div className={styles.researchTaskCandidates}>
                        <b>当前候选证据</b>
                        {task.candidateEvidence.map((evidence) => (
                          <a href={evidence.url} target="_blank" rel="noreferrer" key={evidence.url}>
                            {evidence.sourceLevel ? `${evidence.sourceLevel} · ` : ""}{evidence.source} · {evidence.title}
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : <p>当前没有需要主动补证据的研究任务；后续人物事件或证据缺口变化时会重新生成。</p>}
          </Section>

          <Section id="影响映射" title="最新事件影响映射">
            <p className="method-note">
              这里回答“这条人物事件对公司、技术或赛道意味着什么”。只映射已有证据关系；未直接命中的对象不会因为人物知名度被自动扩展为事实关联。
            </p>
            {research.latestImplications.length ? (
              <div className={styles.implicationGrid}>
                {research.latestImplications.map((item) => (
                  <div className={styles.implicationCard} key={`${item.dimension}-${item.target}`}>
                    <span>{item.dimension}</span>
                    <strong>{item.target}</strong>
                    <p>{item.statement}</p>
                  </div>
                ))}
              </div>
            ) : <p>当前没有可映射的近期人物事件。</p>}
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
            <div className={styles.viewChangeBox}>
              <span>{research.viewChange.confidence === "supported" ? "SUPPORTED" : research.viewChange.confidence === "candidate" ? "CANDIDATE" : "INSUFFICIENT"}</span>
              <strong>{research.viewChange.label}</strong>
              <p>{research.viewChange.summary}</p>
              {research.viewChange.evidence.length > 0 && (
                <div className={styles.viewEvidence}>
                  {research.viewChange.evidence.map((evidence) => (
                    <a href={evidence.url} target="_blank" rel="noreferrer" key={evidence.url}>
                      {evidence.date} · {evidence.title}
                    </a>
                  ))}
                </div>
              )}
            </div>
            {!research.hasVerifiedEvolution && (
              <div className={styles.evolutionNotice}>
                下方时间线用于展示公开表达和人工整理的演进线索。只有绑定到足够原始证据的变化才会升级为已验证演进；
                时间先后本身不代表观点发生迁移。
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
            <span>研究优先级</span>
            <strong>{research.priority.level}</strong>
            <p>{research.priority.score} / 100 · 用于决定持续跟踪顺序，不等同于人物社会影响力排名</p>
          </div>
          <div className="confidence-box">
            <span>主动研究</span>
            <strong>{activeAgenda?.openCount ?? 0}</strong>
            <p>开放任务按证据缺口生成；满足成功判据后自动关闭或等待下一轮问题</p>
          </div>
          <div className="confidence-box">
            <span>证据覆盖</span>
            <strong>{research.coverage.score}%</strong>
            <p>{research.coverage.firstPartyCount} 条一手材料 · {research.coverage.directExpressionEventCount} 个直接表达事件</p>
          </div>
          <div className="confidence-box">
            <span>资料缺口</span>
            <strong>{research.coverage.gaps.length}</strong>
            <p>{research.coverage.gaps[0] ?? "当前关键证据维度无明显缺口"}</p>
          </div>
          <div className="confidence-box">
            <span>人物事件</span>
            <strong>{research.events.length}</strong>
            <p>由 {person.materials.length} 条原始材料按同一人物、标题语义与时间窗口聚合</p>
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
