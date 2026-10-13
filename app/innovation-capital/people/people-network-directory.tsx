"use client";

import { useState } from "react";
import Link from "next/link";
import type { NetworkPersonView } from "@/lib/innovation-people-network";
import styles from "./people-network.module.css";

export function PeopleNetworkDirectory({people}: {people: NetworkPersonView[]}) {
  const [query, setQuery] = useState("");
  const [organization, setOrganization] = useState("");
  const [kind, setKind] = useState("");
  const visible = people.filter(p => (!organization || p.organization === organization) &&
    (!kind || p.kind === kind) &&
    [p.name, ...p.aliases, p.organization, p.profileRole, ...p.topics, ...p.relations.map(r => r.project ?? "")]
      .join(" ").toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
  return <section aria-label="科创人物关系目录">
    <div className={styles.filters}>
      <label>搜索人物或项目<input value={query} onChange={e => setQuery(e.target.value)} placeholder="姓名、机构、公司、研究主题" /></label>
      <label>所属机构 / 公司<select value={organization} onChange={e => setOrganization(e.target.value)}>
        <option value="">全部机构与公司</option>{[...new Set(people.map(p => p.organization))].map(n => <option key={n}>{n}</option>)}
      </select></label>
      <label>人物类型<select value={kind} onChange={e => setKind(e.target.value)}><option value="">全部人物</option><option value="investor">投资机构人物</option><option value="founder">科创公司创始人</option></select></label>
      <button type="button" onClick={() => {setQuery("");setOrganization("");setKind("");}}>重置</button>
    </div>
    <p className={styles.note} role="status" aria-live="polite">显示 {visible.length} / {people.length} 位人物</p>
    {!visible.length && <p className={styles.empty}>没有匹配人物，请调整关键词或筛选条件。</p>}
    <div className={styles.directory}>{visible.map(person => <article className={styles.card} key={person.id} id={person.id}>
      <header><span className={styles.tag}>{person.kind === "investor" ? "投资机构人物" : "科创公司创始人"}</span><h2>{person.name}</h2><p>{person.profileRole}</p></header>
      <div className={styles.affiliation} aria-label="公开职业关系">
        <strong>{person.name}</strong><span>官网所述身份 →</span>
        {person.institutionId ? <Link href={`/innovation-capital/investors/#institution-${person.institutionId}`}>{person.organization}</Link>
          : person.companySlug ? <Link href={`/companies/${person.companySlug}/`}>{person.organization}</Link> : <strong>{person.organization}</strong>}
      </div>
      <p className={styles.note}>{person.topics.join(" · ")} · 来源日期 {person.officialSource.publishedAt ?? "未注明"} · 核验 {person.officialSource.checkedAt}</p>
      <div className={styles.links}>
        <a href={person.officialSource.url} target="_blank" rel="noreferrer">官网身份依据 ↗</a>
        {person.linkedin && <a href={person.linkedin.url} target="_blank" rel="noreferrer" aria-label={`${person.name} 的 LinkedIn 候选档案`}>LinkedIn 候选档案 ↗</a>}
        {person.personSlug && <Link href={`/people/${person.personSlug}/`}>站内人物档案 →</Link>}
      </div>
      {person.linkedin && <p className={styles.note}>LinkedIn 检索日期 {person.linkedin.checkedAt}；链接匹配待复核。</p>}
      <div className={styles.relations}>
        <h3>关联项目与公开判断</h3>
        {person.relations.length ? person.relations.map(relation => <section className={styles.relation} key={relation.id}>
          <span className={styles.tag}>{relation.label} · {relation.date}</span>
          <h4>{relation.project ?? relation.institutionName}</h4>
          <p>{relation.title}</p>
          <p className={styles.note}>{relation.caveat}</p>
          <a href={relation.sourceUrl} target="_blank" rel="noreferrer">查看这条关系的原文 ↗</a>
        </section>) : <p className={styles.note}>已核验公司职业身份；个人与投资机构之间的交易责任尚未建立证据。</p>}
      </div>
    </article>)}</div>
  </section>;
}
