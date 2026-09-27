"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useNativeResearchReports } from "@/components/use-native-research-reports";
import { researchResultHref } from "@/lib/native-research-contract";
import styles from "./native-research-reports.module.css";

export default function NativeResearchReportsPanel({ archive = false }: { archive?: boolean }) {
  const { reports, error, checkedAt } = useNativeResearchReports();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const visible = useMemo(() => (reports ?? []).filter((report) => {
    if (filter !== "all" && report.status !== filter) return false;
    return [report.title, report.eventId, report.sector].join(" ").toLocaleLowerCase("zh-CN").includes(query.trim().toLocaleLowerCase("zh-CN"));
  }).slice(0, archive ? 40 : 6), [reports, query, filter, archive]);
  const completed = (reports ?? []).filter((row) => row.status === "completed-draft").length;
  const labels = { "completed-draft": "自动草稿 · 未人工复核", "evidence-insufficient": "证据不足", "model-unavailable": "生成未完成", "event-unavailable": "事件待恢复" };

  return <section id="native-reports" className={styles.panel} aria-labelledby="native-reports-title">
    <header><div><p className={styles.eyebrow}>EVENT RESEARCH · NOT DAILY DIGEST</p><h2 id="native-reports-title">专题深研报告</h2></div>
      {!archive ? <Link href="/research-agent/reports/">查看报告库 →</Link> : <Link href="/research-agent/">返回 Research Agent →</Link>}
    </header>
    <p>每份报告对应一次明确提交的事件。草稿、证据不足和运行失败分开展示；既不把通用日报当专属报告，也不把机器生成当人工核验。</p>
    <div className={styles.metrics}><span>可读草稿 <b>{reports ? completed : "—"}</b></span><span>已有结果记录 <b>{reports ? reports.length : "—"}</b></span><span>需补证或重试 <b>{reports ? reports.length - completed : "—"}</b></span></div>
    <div className={styles.controls}>
      <label>搜索报告<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="事件 / 公司标题 / 赛道" /></label>
      <label>报告状态<select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">全部状态</option><option value="completed-draft">可读草稿</option><option value="evidence-insufficient">证据不足</option><option value="model-unavailable">生成未完成</option><option value="event-unavailable">事件待恢复</option></select></label>
    </div>
    {error ? <p role="alert">{error} {reports ? "当前仍显示上次成功读取内容。" : "未把读取失败计为零份报告。"}</p> : null}
    {!reports && !error ? <p role="status">正在读取已发布报告…</p> : null}
    {reports?.length === 0 ? <p className={styles.empty}>尚无已发布的专题报告。从情报卡片进入“深研此条”，点击“提交深研”，登录管理端后任务会自动执行并归档到这里。仅打开提交窗口不算已受理。</p> : null}
    {reports && reports.length > 0 && visible.length === 0 ? <p className={styles.empty}>当前筛选没有匹配报告。</p> : null}
    <div className={styles.grid}>{visible.map((report) => <article key={report.requestId}>
      <span className={styles.badge}>{labels[report.status]}</span><h3>{report.title}</h3>
      <p>{report.analysis?.executiveSummary.text || report.note}</p>
      <small>{report.sector || "赛道未标注"} · {report.evidence.length} 条关联材料 · {report.completedAt ? new Date(report.completedAt).toLocaleString("zh-CN") : "时间待确认"}</small>
      <Link href={researchResultHref(report.eventId, report.requestId, Number(report.runId))}>{report.status === "completed-draft" ? "阅读事件报告" : "查看状态与证据缺口"} →</Link>
    </article>)}</div>
    <footer>已发布索引更新于本次读取：{checkedAt ? new Date(checkedAt).toLocaleTimeString("zh-CN") : "—"}。运行中的任务从提交回执进入，不凭空增加已发布数量。</footer>
  </section>;
}
