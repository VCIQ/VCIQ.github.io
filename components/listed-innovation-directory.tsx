"use client";

import { useState } from "react";
import Link from "next/link";
import type { ListedInnovationCompany } from "@/lib/listed-innovation-companies";
import styles from "./listed-innovation-directory.module.css";

const PAGE_SIZE = 12;

export function ListedInnovationDirectory({ rows, approvedAt }: {
  rows: ListedInnovationCompany[];
  approvedAt: string;
}) {
  const [market, setMarket] = useState("全部");
  const [role, setRole] = useState("全部");
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(PAGE_SIZE);
  const needle = query.trim().toLocaleLowerCase("zh-CN");
  const filtered = rows.filter((row) =>
    (market === "全部" || row.securities.some((security) => security.market === market))
    && (role === "全部" || row.role === role)
    && (!needle || [row.name, row.issuerName, row.companySlug, row.sector, row.researchFocus,
      ...row.securities.map((security) => security.ticker)].join(" ").toLocaleLowerCase("zh-CN").includes(needle)));
  return (
    <section className={styles.section} id="listed-innovation" aria-labelledby="listed-innovation-heading">
      <header className={styles.header}>
        <div><p className="eyebrow">LISTED INNOVATION / SHARED COMPANY RECORDS</p>
          <h2 id="listed-innovation-heading">上市科创标杆与产业生态</h2>
          <p>{rows.length} 家已批准主体 · 批准日期 {approvedAt} · 与公司库共用档案，不计入拟上市项目储备。</p>
        </div>
        <Link href="/companies/">全部公司档案 →</Link>
      </header>
      <p className={styles.note}>美股按上市市场筛选，不代表注册地在美国。A/H、美/H和同一发行人的不同证券只计一家公司。
        公司入库不等于全部动态进入首页“科创”或“重点”；P2仍为待审候选。</p>
      <div className={styles.filters}>
        <label>上市市场<select value={market} onChange={(event) => { setMarket(event.target.value); setLimit(PAGE_SIZE); }}>
          {["全部", "美股", "A股", "港股"].map((value) => <option key={value}>{value}</option>)}
        </select></label>
        <label>研究角色<select value={role} onChange={(event) => { setRole(event.target.value); setLimit(PAGE_SIZE); }}>
          <option value="全部">全部角色</option><option value="benchmark">上市技术标杆</option><option value="ecosystem">产业生态</option>
        </select></label>
        <label className={styles.search}>公司／证券／技术<input type="search" value={query}
          placeholder="搜索公司、证券代码或技术方向" onChange={(event) => { setQuery(event.target.value); setLimit(PAGE_SIZE); }} /></label>
      </div>
      <p className={styles.count} aria-live="polite">匹配 {filtered.length} 家 · 已显示 {Math.min(limit, filtered.length)} 家</p>
      <div className={styles.grid}>
        {filtered.slice(0, limit).map((row) => (
          <article className={styles.card} key={row.companySlug} data-company-slug={row.companySlug}>
            <div className={styles.meta}><span>{row.role === "ecosystem" ? "产业生态" : "上市技术标杆"}</span><span>{row.region} · {row.sector}</span></div>
            <h3><Link href={`/companies/${row.companySlug}/`}>{row.name}</Link></h3>
            <p>{row.researchFocus}</p>
            <div className={styles.securities}>{row.securities.map((security) => (
              <a key={`${security.market}:${security.ticker}`} href={security.evidenceUrl} target="_blank" rel="noreferrer"
                title={`${security.exchange} · ${security.instrumentType ?? "证券身份来源"}`}>
                {security.market} {security.ticker}{security.exchange === "HKEX" ? ".HK" : security.exchange === "SSE" ? ".SH" : security.exchange === "SZSE" ? ".SZ" : ""} ↗
              </a>
            ))}</div>
            {row.issuerRelationship === "parent" && <small>上市发行人为母公司 {row.issuerName}，不是独立的Google证券。</small>}
            {row.lifecycleProjectIds?.length ? <small>港股上市与A股辅导分别跟踪，保留原有项目。</small> : null}
            <Link className={styles.profile} href={`/companies/${row.companySlug}/`}>公司档案与证券证据 →</Link>
          </article>
        ))}
      </div>
      {!filtered.length && <p className={styles.note}>没有符合当前筛选条件的已批准公司。</p>}
      {filtered.length > limit && <button className={styles.more} onClick={() => setLimit(limit + PAGE_SIZE)}>加载更多公司</button>}
    </section>
  );
}
