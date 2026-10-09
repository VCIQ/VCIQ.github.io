"use client";

import { useMemo, useState } from "react";
import type { InnovationInvestor, InvestorEvidenceRecord } from "@/lib/innovation-investor-research";
import styles from "./research.module.css";

const labels: Record<string, string> = { investment:"投资披露", viewpoint:"观点转述", outcome:"结果节点", "portfolio-relationship":"组合关系", "fund-announcement":"基金/主题公告" };
const money = (value: {value:number;currency:string} | null) => value ? `${value.currency} ${value.value.toLocaleString("en-US")}` : "未披露 / 未核验";
const outcomeDescription = (status: string | null) => status === "company-reported-commercial-update"
  ? "公司披露的商业化进展（尚无独立财务或工程验收）"
  : status === "acquired"
    ? "公司披露的收购节点（不代表该投资机构获得现金回报）"
    : (status ?? "尚无结果结论");

export function InvestorResearchDirectory({institutions, records}: {institutions: InnovationInvestor[]; records: InvestorEvidenceRecord[]}) {
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState("全部");
  const [topic, setTopic] = useState("全部");
  const [selected, setSelected] = useState("全部");
  const regions = [...new Set(institutions.map((item) => item.regionGroup))];
  const topics = [...new Set(institutions.flatMap((item) => item.researchTopics))].sort();
  const visible = useMemo(() => institutions.filter((item) =>
    (region === "全部" || item.regionGroup === region) &&
    (topic === "全部" || item.researchTopics.includes(topic)) &&
    `${item.name} ${item.aliases.join(" ")} ${item.researchTopics.join(" ")}`.toLowerCase().includes(query.trim().toLowerCase()),
  ), [institutions, query, region, topic]);
  const visibleIds = new Set(visible.map((item) => item.id));
  const evidence = records.filter((item) => visibleIds.has(item.institutionId) && (selected === "全部" || selected === item.institutionId));
  const byId = new Map(institutions.map((item) => [item.id, item]));
  return <>
    <section className={styles.section} id="directory">
      <header><h2>30家研究样本与官方入口</h2><p>按名称、研究分组或主题筛选。这里的序号不是收益或能力排名。</p></header>
      <div className={styles.filters}>
        <label>搜索<input value={query} onChange={(event) => {setQuery(event.target.value); setSelected("全部");}} placeholder="机构、别名、研究主题" /></label>
        <label>研究分组<select value={region} onChange={(event) => {setRegion(event.target.value); setSelected("全部");}}><option>全部</option>{regions.map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>研究主题<select value={topic} onChange={(event) => {setTopic(event.target.value); setSelected("全部");}}><option>全部</option>{topics.map((value) => <option key={value}>{value}</option>)}</select></label>
      </div>
      <p className={styles.note} role="status">显示 {visible.length} / {institutions.length} 家；筛选不会更改生产订阅。</p>
      <div className={styles.directory}>
        {visible.map((item) => {
          const count = records.filter((row) => row.institutionId === item.id).length;
          return <article key={item.id} id={`institution-${item.id}`}>
            <span className={styles.tag}>{item.regionGroup} · {item.style}</span>
            <h3>{item.name}</h3><p>{item.researchTopics.join(" · ")}</p>
            <p className={styles.note}>{item.identityNote}</p>
            <div className={styles.links}><a href={item.officialUrl} target="_blank" rel="noreferrer">官方入口 ↗</a><a href={item.evidenceUrl} target="_blank" rel="noreferrer">身份/范围依据 ↗</a></div>
            <a className={styles.action} href="#evidence" onClick={() => setSelected(item.id)}>{count ? `查看 ${count} 条核验样例` : "查看覆盖说明（尚无核验事件）"}</a>
          </article>;
        })}
      </div>
    </section>
    <section className={styles.section} id="evidence">
      <header><h2>项目、发言、行为与结果证据台账</h2><p>历史案例用于说明核验口径，不冒充今日新闻。当前筛选与上方机构列表一致。</p></header>
      <label>证据机构<select value={selected} onChange={(event) => setSelected(event.target.value)}><option>全部</option>{visible.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      {!evidence.length ? <div className={styles.boundary}><strong>尚无经过核验的事件样例</strong><p>该机构已进入研究目录，但没有足够已核验证据。不能把“无记录”写成“没有投资”，也不会用新闻提及自动补造投资关系。</p></div> : null}
      <div className={styles.evidence}>
        {evidence.map((item) => <article key={item.id}>
          <div className={styles.links}><span className={styles.tag}>{labels[item.kind]}</span><span>{byId.get(item.institutionId)?.name}</span><time>{item.date}（{item.datePrecision === "day" ? "日" : item.datePrecision === "month" ? "月" : "年"}粒度）</time></div>
          <h3>{item.title}</h3><p>{item.summary}</p>
          <dl><div><dt>项目</dt><dd>{item.project ?? "主题/基金层面，非具体项目融资"}</dd></div><div><dt>轮次/参与角色</dt><dd>{item.round ?? "未披露 / 不适用"} · {item.participation ?? "不据此认定出资角色"}</dd></div><div><dt>本轮融资总额</dt><dd>{money(item.roundAmount)}</dd></div><div><dt>本机构投资额</dt><dd>{money(item.investorAmount)}</dd></div></dl>
          {item.linkedPerson ? <p><b>项目关联人：</b>{item.linkedPerson.name}；{item.linkedPerson.relationship}</p> : null}
          {item.speakers.map((speaker) => <p key={speaker.name}><b>发言/署名：</b>{speaker.name} · {speaker.roleAtPublication}。{speaker.projectResponsibility}。</p>)}
          {item.kind === "outcome" ? <p className={styles.boundary}>结果：{outcomeDescription(item.resultStatus)}；基金实际回报未知。没有完整投入、持股变化、退出分配与现金流日期，不计算收益。</p> : null}
          <p className={styles.next}><b>下一验证：</b>{item.nextCheck}</p>
          <details><summary>证据位置与披露边界</summary><p>{item.source.publisher} · 原文发布日期 {item.source.publishedAt ?? "未标注"}</p><p>{item.source.locator}</p><p>来源类型：{item.source.kind}。机构官网属于关联方一手披露，不等于独立第三方验证。</p><a href={item.source.url} target="_blank" rel="noreferrer">打开具体原文 ↗</a></details>
        </article>)}
      </div>
    </section>
  </>;
}
