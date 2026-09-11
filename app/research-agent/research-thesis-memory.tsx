import { ExternalLink } from "lucide-react";

import type { ResearchThesisMemory } from "@/lib/research-agent-data";
import styles from "./research-agent.module.css";

const directionLabels: Record<string, string> = {
  positive: "正向",
  negative: "负向",
  mixed: "分化",
  neutral: "中性",
};

const transitionLabels: Record<string, string> = {
  initiated: "首次形成",
  reaffirmed: "本轮再次确认",
  revised: "同方向修订",
  direction_changed: "方向发生变化",
  returned: "回到既有判断",
};

function formatDate(value: string) {
  if (!value) return "时间待补";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "Asia/Shanghai",
  }).format(date);
}

export default function ResearchThesisMemoryPanel({
  memory,
}: {
  memory?: ResearchThesisMemory;
}) {
  if (!memory?.observations?.length) {
    return (
      <section className={styles.panel} aria-labelledby="thesis-memory-title">
        <h3 id="thesis-memory-title">Thesis Memory</h3>
        <p className={styles.empty}>等待形成第一条可持续追踪的研究假设记录。</p>
      </section>
    );
  }

  const currentIds = new Set(memory.currentObservationIds ?? []);
  const observations = [...memory.observations].sort(
    (left, right) => right.lastSeenAt.localeCompare(left.lastSeenAt) || left.id.localeCompare(right.id),
  );
  const current = observations.filter((item) => currentIds.has(item.id));
  const historical = observations.filter((item) => !currentIds.has(item.id));
  const primary = current.length ? current : observations.slice(0, 3);

  return (
    <section className={styles.panel} aria-labelledby="thesis-memory-title">
      <h3 id="thesis-memory-title">Thesis Memory</h3>
      <p className={styles.filterHint}>
        持续保存研究判断的演进。历史记录保留证据快照，不依赖下一轮会失效的临时 Evidence ID。
      </p>
      <div className={styles.compactList}>
        {primary.slice(0, 3).map((item) => (
          <article key={item.id}>
            <div className={styles.itemMeta}>
              <strong>{item.entity}</strong>
              <span data-direction={item.direction}>{directionLabels[item.direction] ?? item.direction}</span>
            </div>
            <p>{item.statement}</p>
            <small>
              {transitionLabels[item.lastTransition] ?? item.lastTransition} · 首次 {formatDate(item.firstSeenAt)} · 最近 {formatDate(item.lastSeenAt)} · 出现 {item.observationCount} 次
            </small>
            {item.evidence.length > 0 && (
              <div className={styles.evidenceRefs} aria-label={`${item.entity} 历史证据快照`}>
                {item.evidence.slice(-3).map((evidence, index) => (
                  evidence.url ? (
                    <a href={evidence.url} target="_blank" rel="noreferrer" key={`${evidence.url}-${index}`}>
                      {evidence.sourceName || evidence.title || "历史证据"}
                      <ExternalLink size={12} aria-hidden="true" />
                    </a>
                  ) : (
                    <span key={`${evidence.title}-${index}`}>{evidence.sourceName || evidence.title || "历史证据"}</span>
                  )
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
      {historical.length > 0 && (
        <details className={styles.analysisMore}>
          <summary>查看历史 Thesis observations（{historical.length}）</summary>
          <div className={styles.compactList}>
            {historical.slice(0, 12).map((item) => (
              <article key={item.id}>
                <strong>{item.entity} · {directionLabels[item.direction] ?? item.direction}</strong>
                <p>{item.statement}</p>
                <small>
                  {transitionLabels[item.lastTransition] ?? item.lastTransition} · {formatDate(item.lastSeenAt)}
                </small>
              </article>
            ))}
          </div>
        </details>
      )}
    </section>
  );
}
