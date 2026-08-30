import type { ResearchAgentReport } from "@/lib/research-agent-data";
import styles from "./research-agent.module.css";

type HistoryRow = ResearchAgentReport["history"][number] & {
  metricsVersion?: number;
  verifiedChangeTotal?: number;
  candidateTotal?: number;
  auxiliaryLeadTotal?: number;
  rejectedTotal?: number;
  legacyChangeCount?: number;
  eventSummary?: {
    newEvents?: number;
    reconfirmations?: number;
    updates?: number;
    corrections?: number;
    possibleConflicts?: number;
    duplicatesSuppressed?: number;
  };
  newEventCount?: number;
  reconfirmationCount?: number;
  updateCount?: number;
  correctionCount?: number;
  possibleConflictCount?: number;
  duplicatesSuppressed?: number;
};

const statusLabels: Record<string, string> = {
  model: "自动分析完成",
  "no-material-change": "无新增重大变化",
  "offline-fallback": "离线规则摘要",
  "missing-key-fallback": "等待 API 密钥",
  "api-fallback": "API 降级摘要",
  "awaiting-first-run": "等待首次运行",
};

function formatDateTime(value: string) {
  if (!value) return "等待首次运行";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Shanghai",
  }).format(date);
}

function numeric(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function lifecycleSummary(row: HistoryRow) {
  const nested = row.eventSummary;
  const values = {
    newEvents: numeric(nested?.newEvents ?? row.newEventCount),
    reconfirmations: numeric(nested?.reconfirmations ?? row.reconfirmationCount),
    updates: numeric(nested?.updates ?? row.updateCount),
    corrections: numeric(nested?.corrections ?? row.correctionCount),
    possibleConflicts: numeric(nested?.possibleConflicts ?? row.possibleConflictCount),
    duplicatesSuppressed: numeric(nested?.duplicatesSuppressed ?? row.duplicatesSuppressed),
  };
  return [
    `首次发现 ${values.newEvents}`,
    `再次确认 ${values.reconfirmations}`,
    `信息更新 ${values.updates}`,
    `事实更正 ${values.corrections}`,
    values.possibleConflicts ? `待核冲突 ${values.possibleConflicts}` : "",
    values.duplicatesSuppressed ? `重复抑制 ${values.duplicatesSuppressed}` : "",
  ].filter(Boolean).join(" · ");
}

export default function ResearchRunHistory({
  history,
}: {
  history: ResearchAgentReport["history"];
}) {
  return (
    <section
      className={`${styles.panel} ${styles.anchorSection}`}
      id="history"
      aria-labelledby="history-title"
    >
      <div className={styles.sectionHeading}>
        <div>
          <p className="section-index">30-DAY HISTORY</p>
          <h2 id="history-title">运行记录</h2>
        </div>
        <span>{history.length ? `最近 ${Math.min(30, history.length)} 次` : "暂无运行记录"}</span>
      </div>
      {!history.length ? (
        <p className={styles.empty}>等待首次运行完成后记录日期、状态与输出口径。</p>
      ) : <div
        className={styles.historyTableWrap}
        role="region"
        aria-label="运行记录，可横向滚动"
        tabIndex={0}
      >
        <table className={styles.historyTable}>
          <caption>
            第二版记录展示正式变化、候选和线索；早期 changeCount 标为“旧口径 · 未复核”，不与首屏正式变化混用。
          </caption>
          <thead>
            <tr>
              <th scope="col">日期</th>
              <th scope="col">运行状态</th>
              <th scope="col">输出口径</th>
              <th scope="col">摘要与生成时间</th>
            </tr>
          </thead>
          <tbody>
            {[...history].reverse().slice(0, 30).map((rawItem) => {
              const item = rawItem as HistoryRow;
              const isV2 = item.metricsVersion === 2;
              const summary = item.runStatus.endsWith("-fallback")
                ? `${item.changeCount} 条结构化候选；降级运行未形成研究结论。`
                : item.executiveSummary;
              return (
                <tr key={`${item.date}-${item.generatedAt}`}>
                  <td><time dateTime={item.date}>{item.date}</time></td>
                  <td>
                    <span className={styles.historyStatus} data-status={item.runStatus}>
                      {statusLabels[item.runStatus] ?? item.runStatus}
                    </span>
                  </td>
                  <td>
                    {isV2 ? (
                      <div className={styles.historyMetrics} aria-label="发布层级统计">
                        <span>正式 <strong>{numeric(item.verifiedChangeTotal)}</strong></span>
                        <span>候选 <strong>{numeric(item.candidateTotal)}</strong></span>
                        <span>线索 <strong>{numeric(item.auxiliaryLeadTotal)}</strong></span>
                        {numeric(item.rejectedTotal) > 0 && (
                          <span>拒绝 <strong>{numeric(item.rejectedTotal)}</strong></span>
                        )}
                        {numeric(item.legacyChangeCount) > 0 && (
                          <span>另有旧口径 <strong>{numeric(item.legacyChangeCount)}</strong> 条（未复核）</span>
                        )}
                      </div>
                    ) : (
                      <>
                        <strong>{item.changeCount}</strong>
                        <small>旧口径 · 未复核</small>
                      </>
                    )}
                  </td>
                  <td>
                    <details className={styles.historyDisclosure}>
                      <summary>查看摘要</summary>
                      <p>{summary || "本次运行未记录摘要。"}</p>
                      {isV2 && <p className={styles.historyLifecycle}>{lifecycleSummary(item)}</p>}
                      <small>
                        生成于 <time dateTime={item.generatedAt}>{formatDateTime(item.generatedAt)}</time>
                      </small>
                    </details>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>}
    </section>
  );
}
