"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useNativeResearchReports } from "@/components/use-native-research-reports";
import { NATIVE_RESEARCH_WORKFLOW_FILE, RESEARCH_SECTIONS, validResearchEventId, validResearchRequestId, type NativeResearchReport, type ResearchClaim } from "@/lib/native-research-contract";
import styles from "./native-research-result.module.css";

function EvidenceRefs({ claim }: { claim: ResearchClaim }) {
  const label = claim.kind === "source_statement" ? "来源陈述 · 未独立核实" : claim.kind === "inference" ? "推断" : "待验证";
  return <div><small>{label}</small><p>{claim.text}</p><span>{claim.evidenceIds.map((id) => <a href={`#evidence-${id}`} key={id}>[{id}] </a>)}</span></div>;
}

function exportReport(report: NativeResearchReport) {
  const analysis = report.analysis;
  const lines = [`# ${report.title}`, "", `Event ID: ${report.eventId}`, `Request ID: ${report.requestId}`, `状态: ${report.status} / 自动草稿未人工复核`, "", report.methodology, "", "## 摘要", analysis?.executiveSummary.text || report.note];
  if (analysis) for (const section of Object.keys(RESEARCH_SECTIONS) as Array<keyof typeof RESEARCH_SECTIONS>) {
    lines.push("", `## ${RESEARCH_SECTIONS[section]}`, ...analysis.sections[section].map((row) => `${row.kind}: ${row.text} [${row.evidenceIds.join(", ")}]`));
  }
  lines.push("", "## 来源材料", ...report.evidence.map((row) => `[${row.id}] ${row.title}\n${row.url}\n${row.excerpt}`));
  const href = URL.createObjectURL(new Blob([lines.join("\n\n")], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = href; link.download = `vciq-report-${report.eventId.replace(/[^a-z0-9_-]/gi, "-").slice(0, 100)}.md`;
  link.click(); window.setTimeout(() => URL.revokeObjectURL(href), 1000);
}

export default function NativeResearchResultClient() {
  const params = useSearchParams();
  const eventId = params.get("event")?.trim() || "";
  const requestId = params.get("request")?.trim() || "";
  const runId = Number(params.get("run") || 0);
  const { reports, error, checkedAt } = useNativeResearchReports(Boolean(requestId));
  const [progress, setProgress] = useState("等待核对研究任务与公开结果…");
  const result = reports?.find((row) => row.eventId === eventId && (!requestId || row.requestId === requestId)) ?? null;

  useEffect(() => {
    if (result || !validResearchEventId(eventId) || !validResearchRequestId(requestId) || !Number.isSafeInteger(runId) || runId <= 0) return;
    let active = true;
    let reading = false;
    const deadline = Date.now() + 20 * 60_000;
    const controller = new AbortController();
    const read = async () => {
      if (!active || reading || document.hidden) return;
      if (Date.now() > deadline) { setProgress("本页自动核对已暂停；任务可能仍在排队或等待发布。稍后刷新即可，不必重新提交。"); return; }
      reading = true;
      try {
        // Public repository status only; no GitHub credentials or admin cookies.
        const response = await fetch(`https://api.github.com/repos/VCIQ/VCIQ.github.io/actions/runs/${runId}`, {
          cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15_000)]), headers: { accept: "application/vnd.github+json" },
        });
        if (!response.ok) throw new Error("公开任务状态暂不可读；仍在核对已发布报告，不自动重提。");
        const run = await response.json() as Record<string, unknown>;
        if (run.display_title !== `VCIQ native ${requestId} ${eventId}` || run.head_branch !== "main" || run.event !== "workflow_dispatch" || String(run.path).split("@")[0] !== `.github/workflows/${NATIVE_RESEARCH_WORKFLOW_FILE}`) throw new Error("任务回执与本事件不匹配；没有认领其他研究结果。");
        if (!active) return;
        if (run.status === "completed") setProgress(run.conclusion === "success"
          ? "研究运行已结束，正在等待报告通过发布流程后出现在公开索引。运行成功不等于已公开。"
          : `研究工作流未成功完成（${String(run.conclusion || "unknown")}）。已发布报告不会被清空；可查看任务日志。`);
        else setProgress(run.status === "in_progress" ? "研究正在执行；完成后将自动核对报告并展示。" : "任务已排队，等待研究运行资源；不需要到 GitHub 手动操作。");
      } catch (reason) { if (active) setProgress(reason instanceof Error ? reason.message : "任务状态读取失败。"); }
      finally { reading = false; }
    };
    void read();
    const interval = window.setInterval(() => void read(), 60_000);
    return () => { active = false; controller.abort(); window.clearInterval(interval); };
  }, [eventId, requestId, runId, result]);

  const valid = validResearchEventId(eventId) && (!requestId || validResearchRequestId(requestId));
  return <main className={styles.page}>
    <header className={styles.topbar}><Link href={valid ? `/research-agent/investigate/?event=${encodeURIComponent(eventId)}` : "/research-agent/"}>← 返回研究上下文</Link><Link href="/research-agent/#native-reports">专题深研报告</Link></header>
    <section className={styles.hero}><small>EVENT-SPECIFIC · REQUEST-CORRELATED</small><h1>专题深研报告</h1><p>每份结果与事件 ID、请求 ID 和运行回执关联。报告是自动草稿，来源陈述、推断与待验证项分开展示。</p></section>
    {!valid ? <section className={styles.state}>研究链接参数无效；未加载任意任务或替换事件。</section> : null}
    {error ? <section className={styles.state} role="alert">{error} {reports ? "保留最近可用索引。" : "读取失败不能视为没有报告。"}</section> : null}
    {valid && !result ? <section className={styles.state} role="status" aria-live="polite"><div>
      <b>{requestId ? progress : "尚无该事件的专题报告"}</b>
      <p>{requestId ? "无需反复点击提交；此页每20秒检查公开报告，任务状态每分钟核对，最多20分钟。" : "从“深研此条”提交后，回执对应的结果将自动出现在这里。"}</p>
      {runId > 0 && Number.isSafeInteger(runId) ? <a href={`https://github.com/VCIQ/VCIQ.github.io/actions/runs/${runId}`} target="_blank" rel="noreferrer">查看任务日志（可选）</a> : null}
      <p>最近成功读取：{checkedAt ? new Date(checkedAt).toLocaleTimeString("zh-CN") : "尚未读到索引"}</p>
    </div></section> : null}
    {valid && result ? <>
      <section className={styles.resultCard}>
        <div className={styles.statusRow}><span>{result.status === "completed-draft" ? "自动草稿已生成 · 未人工复核" : "NO EVENT-SPECIFIC EVIDENCE / 尚未形成可读报告"}</span></div>
        <h2>{result.title}</h2><p>{result.note}</p><p>{result.methodology}</p>
        <dl><div><dt>Event ID</dt><dd>{result.eventId}</dd></div><div><dt>Request ID</dt><dd>{result.requestId}</dd></div><div><dt>生成时间</dt><dd>{result.completedAt}</dd></div></dl>
        <button type="button" onClick={() => exportReport(result)}>导出当前报告 Markdown</button>
        {result.sourceUrl ? <a href={result.sourceUrl} target="_blank" rel="noreferrer">原始事件来源</a> : null}
      </section>
      {result.analysis ? <>
        <section className={styles.section}><h2>事件研究摘要</h2><EvidenceRefs claim={result.analysis.executiveSummary} /></section>
        {(Object.keys(RESEARCH_SECTIONS) as Array<keyof typeof RESEARCH_SECTIONS>).map((section) => <section className={styles.section} key={section}><h2>{RESEARCH_SECTIONS[section]}</h2><div className={styles.grid}>{result.analysis?.sections[section].map((row, index) => <article key={index}><EvidenceRefs claim={row} /></article>)}</div></section>)}
      </> : <section className={styles.section}>本次没有形成有效的事件级分析；不会用通用日报替代，也不会把失败当作完成。</section>}
      <section className={styles.section}><h2>直接关联材料</h2><p>引用关系经过结构校验；不代表已打开全文或完成独立交叉核验。</p><div className={styles.grid}>{result.evidence.map((row) => <article id={`evidence-${row.id}`} key={row.id}><b>[{row.id}] {row.title}</b><p>{row.excerpt}</p><span>{row.sourceName} · {row.publishedAt}</span><a href={row.url} target="_blank" rel="noreferrer">查看来源材料</a></article>)}</div></section>
    </> : null}
  </main>;
}
