import type { Metadata } from "next";
import Link from "next/link";
import { buildPeopleNetwork, peopleNetworkCoverage, peopleNetworkReviewedAt } from "@/lib/innovation-people-network";
import { PeopleNetworkDirectory } from "./people-network-directory";
import styles from "./people-network.module.css";

export const metadata: Metadata = {
  title: "科创人物与投资关系",
  description: "连接科创创始人、投资机构核心人物、项目与公开观点，附 LinkedIn 人物入口和逐项证据。",
};

export default function InnovationPeoplePage() {
  const people = buildPeopleNetwork();
  const coverage = peopleNetworkCoverage();
  const relations = people.flatMap(p => p.relations);
  const institutions = new Set(people.map(p => p.institutionId).filter(Boolean));
  return <main className="page-shell subpage">
    <header className="page-header">
      <p className="eyebrow">INNOVATION CAPITAL / PEOPLE & RELATIONSHIPS</p>
      <h1>科创人物与投资关系</h1>
      <p className={styles.intro}>从核心人物出发，查看所属机构、关联项目和公开判断。每一条关系都能回到原始材料。</p>
      <nav className="hero-chips" aria-label="人物关系导航">
        <Link href="/innovation-capital/">科创频道</Link>
        <Link href="/innovation-capital/investors/">投资机构研究</Link>
        <Link href="/people/">人物库</Link>
      </nav>
    </header>
    <section className={styles.metrics} aria-label="人物关系覆盖">
      <article><strong>{people.length}</strong><span>首批人物</span></article>
      <article><strong>{institutions.size}</strong><span>关联投资机构</span></article>
      <article><strong>{relations.length}</strong><span>项目与观点证据</span></article>
      <article><strong>{people.filter(p => p.linkedin).length}</strong><span>LinkedIn 候选入口</span></article>
    </section>
    <p className={styles.note}>资料核验：{peopleNetworkReviewedAt}（UTC）。LinkedIn 链接来自人物检索，身份绑定仍待复核；任职和项目关系依据下方官网材料。当前没有开启 LinkedIn 动态自动同步。</p>
    <PeopleNetworkDirectory people={people} />
    <section className={styles.method} aria-label="项目与人物关系路径">
      <h2>沿项目查看人物与机构</h2>
      <p>同一项目的不同来源并列展示，各人物的责任范围以对应原文为准。</p>
      <div className={styles.tableWrap}><table className={styles.table}>
        <thead><tr><th scope="col">项目</th><th scope="col">人物 / 机构</th><th scope="col">证据关系</th></tr></thead>
        <tbody>{people.flatMap(person => person.relations.filter(r => r.project).map(r => <tr key={`${person.id}:${r.id}`}>
          <td>{r.project}</td><td><a href={`#${person.id}`}>{person.name}</a><br />{person.organization}</td>
          <td><a href={r.sourceUrl} target="_blank" rel="noreferrer">{r.label} · {r.date} ↗</a></td>
        </tr>))}</tbody>
      </table></div>
    </section>
    <details className={styles.method}>
      <summary>关系口径与后续覆盖（{coverage.pendingAttributions.length} 条人物署名待映射）</summary>
      <p>相同项目下出现两位人物，只表示各自存在公开证据，不表示二人互为好友、直接合作或共同领投。历史职务按来源日期保留，访问日期不作为任职起始日期。</p>
      <p>公司公告、机构组合页和人物发言分别记录。LinkedIn 检索未命中表示本次没有结果，不等于这个人没有账号。</p>
      <ul>{coverage.pendingAttributions.map(item => <li key={`${item.institutionId}:${item.name}`}>
        <a href={item.sourceUrl} target="_blank" rel="noreferrer">{item.name}</a> · {item.institutionId} · 待身份映射
      </li>)}</ul>
    </details>
  </main>;
}
