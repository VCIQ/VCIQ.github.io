"use client";

import { ArrowLeft, ExternalLink, FileSearch, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import styles from "./native-research-result.module.css";

type NativeResearchResult = {
  eventId: string;
  title: string;
  sourceUrl: string;
  requestedAt: string;
  completedAt: string;
  runStatus: string;
  status: "evidence-linked" | "no-event-specific-evidence" | string;
  executiveSummary: string;
  changeIds: string[];
  evidenceIds: string[];
  changes: Array<Record<string, unknown>>;
  evidence: Array<Record<string, unknown>>;
  note: string;
};

type Payload = {
  schemaVersion: number;
  generatedAt: string;
  results: NativeResearchResult[];
};

function text(value: unknown) {
  return typeof value === "string" ? value : "";
}

export default function NativeResearchResultClient() {
  const searchParams = useSearchParams();
  const eventId = searchParams.get("event")?.trim() || "";
  const [payload, setPayload] = useState<Payload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetch("/data/native_research_results.json", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error(`native_research_results.json returned ${response.status}`);
        return response.json() as Promise<Payload>;
      })
      .then((value) => {
        if (!active) return;
        setPayload(value);
        setError("");
      })
      .catch(() => {
        if (!active) return;
        setError("暂时无法读取 Native Research 结果索引。");
      });
    return () => {
      active = false;
    };
  }, []);

  const result = useMemo(
    () => payload?.results?.find((row) => row.eventId === eventId) ?? null,
    [eventId, payload],
  );

  return (
    <main className={styles.page}>
      <header className={styles.topbar}>
        <Link href={eventId ? `/research-agent/investigate/?event=${encodeURIComponent(eventId)}` : "/research-agent/"}>
          <ArrowLeft size={14} aria-hidden="true" />
          返回研究上下文
        </Link>
        <b>VCIQ / NATIVE RESEARCH RESULT</b>
      </header>

      <section className={styles.hero}>
        <small>EVENT-SPECIFIC · EVIDENCE-BOUND</small>
        <h1>研究结果</h1>
        <p>这里只展示已经由公开 Research Agent 产物绑定到该事件的 evidence / change；没有直接证据时会明确显示未形成专属结果。</p>
      </section>

      {error ? <section className={styles.state}><FileSearch size={18} /><p>{error}</p></section> : null}
      {!error && !payload ? <section className={styles.state}><FileSearch size={18} /><p>正在读取结果索引…</p></section> : null}

      {payload && !result ? (
        <section className={styles.state}>
          <FileSearch size={18} />
          <div>
            <b>尚无该事件的 Native Research 记录</b>
            <p>提交深研后，Research Agent workflow 完成并发布结果索引，这里才会出现事件级结果。</p>
          </div>
        </section>
      ) : null}

      {result ? (
        <>
          <section className={styles.resultCard}>
            <div className={styles.statusRow}>
              <span className={result.status === "evidence-linked" ? styles.ready : styles.pending}>
                {result.status === "evidence-linked" ? "EVIDENCE LINKED" : "NO EVENT-SPECIFIC EVIDENCE"}
              </span>
              <span>{result.runStatus}</span>
            </div>
            <h2>{result.title || result.eventId}</h2>
            <p>{result.note}</p>
            <dl>
              <div><dt>Event ID</dt><dd>{result.eventId}</dd></div>
              <div><dt>Requested</dt><dd>{result.requestedAt || "—"}</dd></div>
              <div><dt>Completed</dt><dd>{result.completedAt || "—"}</dd></div>
            </dl>
            {result.sourceUrl ? (
              <a href={result.sourceUrl} target="_blank" rel="noreferrer">
                原始事件来源 <ExternalLink size={13} aria-hidden="true" />
              </a>
            ) : null}
          </section>

          {result.executiveSummary ? (
            <section className={styles.section}>
              <small>EXECUTIVE SUMMARY</small>
              <h2>研究摘要</h2>
              <p>{result.executiveSummary}</p>
            </section>
          ) : null}

          <section className={styles.section}>
            <small>EVIDENCE</small>
            <h2>直接绑定证据</h2>
            {result.evidence.length ? (
              <div className={styles.grid}>
                {result.evidence.map((row, index) => (
                  <article key={text(row.id) || String(index)}>
                    <ShieldCheck size={15} aria-hidden="true" />
                    <b>{text(row.title) || text(row.claim) || text(row.id)}</b>
                    <p>{text(row.claim)}</p>
                    <span>{text(row.sourceName)} · {text(row.evidenceGrade)}</span>
                    {text(row.url) ? (
                      <a href={text(row.url)} target="_blank" rel="noreferrer">打开证据 <ExternalLink size={12} /></a>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : <p className={styles.empty}>本轮没有与该事件直接绑定的公开 evidence。</p>}
          </section>

          <section className={styles.section}>
            <small>CHANGES</small>
            <h2>事件相关变化</h2>
            {result.changes.length ? (
              <div className={styles.grid}>
                {result.changes.map((row, index) => (
                  <article key={text(row.id) || String(index)}>
                    <b>{text(row.entityName) || text(row.id)}</b>
                    <p>{text(row.summary)}</p>
                    <span>Importance {String(row.importance ?? "—")}</span>
                  </article>
                ))}
              </div>
            ) : <p className={styles.empty}>本轮没有形成该事件的结构化 change；不会用通用日报替代。</p>}
          </section>
        </>
      ) : null}
    </main>
  );
}
