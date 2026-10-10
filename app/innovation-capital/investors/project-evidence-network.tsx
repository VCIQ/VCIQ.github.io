import {
  buildCanonicalInvestorProjectGraph,
  investorProjectCoverageMatrix,
} from "@/lib/innovation-investor-project-graph";
import styles from "./project-network.module.css";

/**
 * Static, evidence-limited research projection. Never turns same-project
 * institutional references into an inferred co-investment or a fund return.
 */
export function InvestorProjectEvidenceNetwork() {
  const projects = buildCanonicalInvestorProjectGraph();
  const coverage = investorProjectCoverageMatrix(projects);
  const withEvidence = coverage.filter((row) => row.reviewedProjectCount > 0);
  const withoutEvidence = coverage.filter((row) => row.reviewedProjectCount === 0);
  const multiFirm = projects.filter((project) => project.institutions.length > 1);
  const relations = projects.reduce((n, project) => n + project.institutions.length, 0);
  const personRows = projects.flatMap((project) => project.institutions.flatMap((institution) =>
    institution.personAttributions.map((person) => ({
      projectId: project.projectId,
      project: project.name,
      institutionId: institution.institutionId,
      institution: institution.institutionName,
      ...person,
    })),
  ));

  return <section className={styles.section} id="investor-project-network">
    <header>
      <h2>项目身份与投资机构关联证据</h2>
      <p>对已收录证据进行人工确认的项目身份映射，而不是按名称相似度自动合并公司。研究数据只描述已观察到的材料，不构成机构持仓清单或投资收益分析。</p>
    </header>
    <div className={styles.stats} aria-label="当前项目研究样本分母">
      <article><strong>{projects.length}</strong><span>不同的规范项目</span></article>
      <article><strong>{relations}</strong><span>机构—项目证据关系</span></article>
      <article><strong>{withEvidence.length}/30</strong><span>有项目证据的机构</span></article>
      <article><strong>{multiFirm.length}</strong><span>有多家机构独立记录的项目</span></article>
    </div>
    <p className={styles.note}>有两家机构记录同一项目，只证明两份来源都提及该公司，不证明两家共同领投、同轮投资、相同基金主体或持有相同比例。</p>

    {multiFirm.length ? <div className={styles.sharedList}>
      <h3>跨机构项目：保留不同关系类型</h3>
      {multiFirm.map((project) => <article key={project.projectId} className={styles.shared}>
        <h4>{project.name}</h4>
        <p className={styles.note}>{project.identityNote ?? "不同机构分别保存原始材料；不推断同轮投资。"}</p>
        <div className={styles.relationGrid}>
          {project.institutions.map((relation) => <div key={relation.institutionId}>
            <strong>{relation.institutionName}</strong>
            <p>
              投资披露 {relation.investmentDisclosures.length} 条 ·
              组合关联 {relation.portfolioRelationshipCount} 条 ·
              观点 {relation.viewpointRecordCount} 条
            </p>
            {relation.personAttributions.map((person) => <p className={styles.person} key={person.type + ":" + person.name}>
              {person.name}：{person.type === "portfolio-listed-partner" ? "官方项目页关联人" : "文章署名／转述"}；不能据此确认独家交易责任
            </p>)}
            <p className={styles.sources}>
              {relation.originalSourceUrls.map((url, index) => <a key={url} href={url} target="_blank" rel="noreferrer">
                查看原始来源 {index + 1} ↗
              </a>)}
            </p>
          </div>)}
        </div>
      </article>)}
    </div> : null}

    <details className={styles.details}>
      <summary>查看30家机构的项目证据覆盖与缺口（{withEvidence.length}家有样例，{withoutEvidence.length}家暂无样例）</summary>
      <p className={styles.note}>目标是逐机构形成3–5个可持续研究项目。此处“0”仅表示当前已审定样例没有覆盖，绝非该机构没有实际投资。</p>
      <div className={styles.tableScroll}>
        <table className={styles.table}>
          <thead><tr><th scope="col">机构</th><th scope="col">项目样例</th><th scope="col">原始来源</th><th scope="col">投资披露</th><th scope="col">署名观点人物</th><th scope="col">项目结果记录</th><th scope="col">至少还缺项目</th></tr></thead>
          <tbody>
            {[...withEvidence, ...withoutEvidence].map((row) => <tr key={row.institutionId}>
              <th scope="row">{row.name}</th>
              <td>{row.reviewedProjectCount}</td>
              <td>{row.reviewedSourceCount}</td>
              <td>{row.disclosedInvestmentEvents}</td>
              <td>{row.attributedViewpointPeople}</td>
              <td>{row.observedOutcomeRecords}</td>
              <td>{row.gapToThreeProjects}</td>
            </tr>)}
          </tbody>
        </table>
      </div>
    </details>

    <details className={styles.details}>
      <summary>查看人物署名与项目合伙人证据（{personRows.length}条归属记录）</summary>
      <p className={styles.note}>“文章作者/受访人”和“官网Portfolio Partner”是两种证据。两种身份均不能自动确认此人亲自签署交易、主导特定轮次或负责基金回款。</p>
      <div className={styles.peopleList}>
        {personRows.map((person) => <article key={[person.projectId, person.institutionId, person.name, person.type].join(":")}>
          <strong>{person.name}</strong> · {person.institution} · {person.project}
          <p>{person.type === "article-attributed-viewpoint" ? "署名或明确归属的投资观点" : "官方项目页列出的合伙人"}</p>
          <p>{person.roleOrRelationship}；{person.responsibilityCaveat}</p>
          <a href={person.originalUrl} target="_blank" rel="noreferrer">核对原始证据 ↗</a>
        </article>)}
      </div>
    </details>
    <p className={styles.note}>每家项目数量、署名证据和结果记录数均是观察样本分母，不是机构实力、成功率或投资评级。项目缺少结果记录不能归类为失败；公司融资或收购也不能推算基金IRR／MOIC。</p>
  </section>;
}
