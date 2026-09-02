"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  Filter,
  Radio,
  Search,
  ShieldCheck,
} from "lucide-react";
import type { SourceDirectoryEntry } from "@/lib/source-directory";
import {
  SOURCE_COVERAGE_POLICY,
  SOURCE_FRESHNESS_POLICY,
  SOURCE_OPERATION_REASON_LABELS,
  buildSourceCoverageRows,
  buildSourceDecisionSummary,
  sourceFreshness,
  sourceHasObservedEndpoint,
  sourceNeedsEvidence,
  sourceNeedsGovernanceDecision,
  sourceNeedsOperationalAction,
  sourceOperationalReasons,
  sourceReadinessDistance,
  sourceReadinessLabel,
  type SourceCoverageState,
  type SourceFreshnessState,
} from "@/lib/source-decision-dashboard";
import {
  sourceCoreEligibilityReason,
  sourceCoreEligible,
  sourceRolePriority,
} from "@/lib/source-governance";
import styles from "./source-operations.module.css";

type QueueMode =
  | "all"
  | "operational"
  | "governance"
  | "evidence"
  | "near-core"
  | "coverage-gap"
  | "unobserved";
type SortMode = "default" | "near-core" | "health" | "freshness" | "name";
type RoleFilter = "all" | SourceDirectoryEntry["sourceRole"];
type HealthFilter = "all" | SourceDirectoryEntry["healthStatus"];
type LifecycleFilter = "all" | SourceDirectoryEntry["lifecycle"];
type ReadinessFilter = "all" | "candidate" | "evidence_pending" | "review_pending" | "blocked" | "core";

const roleLabels = {
  primary: "PRIMARY",
  corroboration: "CORROBORATION",
  discovery: "DISCOVERY",
} as const;

const healthLabels = {
  ok: "OK",
  partial: "PARTIAL",
  error: "ERROR",
  unknown: "UNKNOWN",
} as const;

const freshnessLabels: Record<SourceFreshnessState, string> = {
  fresh: "FRESH",
  aging: "AGING",
  stale: "STALE",
  unobserved: "UNOBSERVED",
};

const coverageLabels: Record<SourceCoverageState, string> = {
  covered: "COVERED",
  watch: "WATCH",
  gap: "GAP",
};

const queueOptions: Array<{ key: QueueMode; label: string; description: string }> = [
  { key: "all", label: "全部 Source", description: "完整目录" },
  { key: "operational", label: "采集处理", description: "失败 / 部分成功 / 过期" },
  { key: "governance", label: "治理决策", description: "Candidate / Blocked" },
  { key: "evidence", label: "证据补齐", description: "Core 候选 Evidence Pending" },
  { key: "near-core", label: "最接近 Core", description: "优先补齐证据" },
  { key: "coverage-gap", label: "Coverage 缺口", description: "盲区相关 Source" },
  { key: "unobserved", label: "Unobserved", description: "尚无可靠观测" },
];

function healthTone(status: SourceDirectoryEntry["healthStatus"]): string {
  if (status === "ok") return styles.toneOk;
  if (status === "partial") return styles.toneWarn;
  if (status === "error") return styles.toneBad;
  return styles.toneMuted;
}

function freshnessTone(status: SourceFreshnessState): string {
  if (status === "fresh") return styles.toneOk;
  if (status === "aging") return styles.toneWarn;
  if (status === "stale") return styles.toneBad;
  return styles.toneMuted;
}

function coverageTone(status: SourceCoverageState): string {
  if (status === "covered") return styles.toneOk;
  if (status === "watch") return styles.toneWarn;
  return styles.toneBad;
}

function compactDate(value?: string | null): string {
  if (!value) return "尚无成功记录";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "尚无成功记录";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Taipei",
  }).format(parsed);
}

function ageLabel(ageHours: number | null): string {
  if (ageHours === null) return "无成功时间";
  if (ageHours < 1) return `${Math.max(1, Math.round(ageHours * 60))}m ago`;
  if (ageHours < 48) return `${Math.round(ageHours)}h ago`;
  return `${Math.round(ageHours / 24)}d ago`;
}

function promotionState(source: SourceDirectoryEntry): ReadinessFilter {
  return source.promotion?.state ?? "candidate";
}

function sourceSearchText(source: SourceDirectoryEntry): string {
  return [
    source.name,
    source.kind,
    source.platform,
    source.sourceLevel,
    source.region,
    ...source.sectors,
    ...source.keywords,
    ...source.companies,
    ...source.people,
  ].join(" ").normalize("NFKC").toLocaleLowerCase("zh-CN");
}

function compareDefault(left: SourceDirectoryEntry, right: SourceDirectoryEntry): number {
  return left.kind.localeCompare(right.kind, "zh-CN")
    || left.sourceRole.localeCompare(right.sourceRole, "en-US")
    || left.name.localeCompare(right.name, "zh-CN");
}

function closestReason(source: SourceDirectoryEntry): string {
  if (source.promotion?.state === "review_pending") return "量化门槛已满足，只待人工 Core 审批。";
  if (source.promotion?.state === "core") return "已进入 Core。";
  if (source.promotion?.state === "blocked") return source.promotion.reasons[0] ?? "人工审核阻塞。";
  return source.promotion?.reasons[0] ?? "尚未建立可持续晋级证据。";
}

export default function SourceOperationsClient({
  sources,
  snapshotAt,
}: {
  sources: SourceDirectoryEntry[];
  snapshotAt: string;
}) {
  const now = useMemo(() => new Date(snapshotAt), [snapshotAt]);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState<RoleFilter>("all");
  const [health, setHealth] = useState<HealthFilter>("all");
  const [lifecycle, setLifecycle] = useState<LifecycleFilter>("all");
  const [readiness, setReadiness] = useState<ReadinessFilter>("all");
  const [sector, setSector] = useState("all");
  const [queue, setQueue] = useState<QueueMode>("all");
  const [sort, setSort] = useState<SortMode>("default");

  const coverageRows = useMemo(() => buildSourceCoverageRows(sources), [sources]);
  const summary = useMemo(() => buildSourceDecisionSummary(sources, now), [now, sources]);
  const gapSectors = useMemo(
    () => new Set(coverageRows.filter((row) => row.state !== "covered").map((row) => row.sector)),
    [coverageRows],
  );
  const sectors = useMemo(
    () => [...new Set(sources.flatMap((source) => source.sectors).filter(Boolean))]
      .sort((left, right) => left.localeCompare(right, "zh-CN")),
    [sources],
  );

  const visibleSources = useMemo(() => {
    const needle = search.trim().normalize("NFKC").toLocaleLowerCase("zh-CN");
    const filtered = sources.filter((source) => {
      if (needle && !sourceSearchText(source).includes(needle)) return false;
      if (role !== "all" && source.sourceRole !== role) return false;
      if (health !== "all" && source.healthStatus !== health) return false;
      if (lifecycle !== "all" && source.lifecycle !== lifecycle) return false;
      if (readiness !== "all" && promotionState(source) !== readiness) return false;
      if (sector !== "all" && !source.sectors.includes(sector)) return false;

      if (queue === "operational" && !sourceNeedsOperationalAction(source, now)) return false;
      if (queue === "governance" && !sourceNeedsGovernanceDecision(source)) return false;
      if (queue === "evidence" && !sourceNeedsEvidence(source)) return false;
      if (
        queue === "near-core"
        && (
          !sourceCoreEligible(source)
          || !["evidence_pending", "review_pending"].includes(source.promotion?.state ?? "candidate")
        )
      ) return false;
      if (queue === "coverage-gap" && !source.sectors.some((item) => gapSectors.has(item))) return false;
      if (queue === "unobserved" && sourceFreshness(source, now).state !== "unobserved") return false;
      return true;
    });

    return [...filtered].sort((left, right) => {
      if (queue === "near-core" || sort === "near-core") {
        return sourceReadinessDistance(left) - sourceReadinessDistance(right)
          || sourceRolePriority(left) - sourceRolePriority(right)
          || compareDefault(left, right);
      }
      if (sort === "health") {
        const rank = { error: 0, partial: 1, unknown: 2, ok: 3 } as const;
        return rank[left.healthStatus] - rank[right.healthStatus] || compareDefault(left, right);
      }
      if (sort === "freshness") {
        const rank: Record<SourceFreshnessState, number> = {
          stale: 0,
          unobserved: 1,
          aging: 2,
          fresh: 3,
        };
        return rank[sourceFreshness(left, now).state] - rank[sourceFreshness(right, now).state]
          || compareDefault(left, right);
      }
      if (sort === "name") return left.name.localeCompare(right.name, "zh-CN");
      return compareDefault(left, right);
    });
  }, [gapSectors, health, lifecycle, now, queue, readiness, role, search, sector, sort, sources]);

  const closestToCore = useMemo(
    () => [...sources]
      .filter((source) =>
        sourceCoreEligible(source)
        && ["evidence_pending", "review_pending"].includes(source.promotion?.state ?? "candidate")
      )
      .sort((left, right) =>
        sourceReadinessDistance(left) - sourceReadinessDistance(right)
        || sourceRolePriority(left) - sourceRolePriority(right)
        || compareDefault(left, right)
      )
      .slice(0, 5),
    [sources],
  );

  return (
    <>
      <section className={styles.decisionSummary} aria-label="Source decision summary">
        <article>
          <small>采集处理</small>
          <b>{summary.operationalActionRequired}</b>
          <span>采集失败 / 部分成功 / stale / unobserved</span>
        </article>
        <article>
          <small>治理决策</small>
          <b>{summary.governanceDecisionRequired}</b>
          <span>稳定入口不足或人工 Core 决策阻塞</span>
        </article>
        <article>
          <small>Core Ready</small>
          <b>{summary.coreReady}</b>
          <span>量化门槛已满足，等待人工审核</span>
        </article>
        <article>
          <small>Coverage Gap</small>
          <b>{summary.criticalCoverageGaps}</b>
          <span>{summary.coverageGaps} 个赛道仍未满足覆盖合同</span>
        </article>
      </section>

      <section className={styles.controlPlane}>
        <div className={styles.sectionHeading}>
          <div>
            <span>SOURCE DECISION CONTROL PLANE</span>
            <h2>先区分采集故障、治理决策、证据积累与覆盖盲区。</h2>
          </div>
          <small>快照基准 {compactDate(snapshotAt)}</small>
        </div>

        <div className={styles.queueBar} aria-label="Source quick queues">
          {queueOptions.map((item) => (
            <button
              className={queue === item.key ? styles.queueActive : ""}
              key={item.key}
              onClick={() => setQueue(item.key)}
              type="button"
            >
              <b>{item.label}</b>
              <span>{item.description}</span>
            </button>
          ))}
        </div>

        <div className={styles.controls}>
          <label className={styles.searchBox}>
            <Search size={15} aria-hidden="true" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜索 Source / 平台 / 赛道 / 公司 / 人物 / 关键词"
            />
          </label>
          <div className={styles.selects}>
            <Filter size={14} aria-hidden="true" />
            <select value={role} onChange={(event) => setRole(event.target.value as RoleFilter)}>
              <option value="all">全部 Role</option>
              <option value="primary">Primary</option>
              <option value="corroboration">Corroboration</option>
              <option value="discovery">Discovery</option>
            </select>
            <select value={health} onChange={(event) => setHealth(event.target.value as HealthFilter)}>
              <option value="all">全部 Health</option>
              <option value="ok">OK</option>
              <option value="partial">Partial</option>
              <option value="error">Error</option>
              <option value="unknown">Unknown</option>
            </select>
            <select value={lifecycle} onChange={(event) => setLifecycle(event.target.value as LifecycleFilter)}>
              <option value="all">全部 Lifecycle</option>
              <option value="candidate">Candidate</option>
              <option value="tracked">Tracked</option>
              <option value="core">Core</option>
            </select>
            <select value={readiness} onChange={(event) => setReadiness(event.target.value as ReadinessFilter)}>
              <option value="all">全部 Readiness</option>
              <option value="candidate">Not eligible</option>
              <option value="evidence_pending">Evidence pending</option>
              <option value="review_pending">Core ready / review</option>
              <option value="blocked">Blocked</option>
              <option value="core">Core</option>
            </select>
            <select value={sector} onChange={(event) => setSector(event.target.value)}>
              <option value="all">全部赛道</option>
              {sectors.map((item) => <option value={item} key={item}>{item}</option>)}
            </select>
            <select value={sort} onChange={(event) => setSort(event.target.value as SortMode)}>
              <option value="default">默认排序</option>
              <option value="near-core">最接近 Core</option>
              <option value="health">问题优先</option>
              <option value="freshness">Stale 优先</option>
              <option value="name">名称</option>
            </select>
          </div>
        </div>

        <div className={styles.resultsMeta}>
          <span>显示 {visibleSources.length} / {sources.length} 个 Source Entity</span>
          <span>
            Fresh &lt; {SOURCE_FRESHNESS_POLICY.freshHours}h ·
            Aging {SOURCE_FRESHNESS_POLICY.freshHours}–{SOURCE_FRESHNESS_POLICY.staleHours}h ·
            Stale &gt; {SOURCE_FRESHNESS_POLICY.staleHours}h ·
            {summary.discoveryOnly} Discovery-only · {summary.evidencePending} Core 候选等待证据
          </span>
        </div>
      </section>

      <section className={styles.coverageSection} aria-label="Coverage gap matrix">
        <div className={styles.sectionHeading}>
          <div>
            <span>COVERAGE / GAP MATRIX</span>
            <h2>赛道覆盖合同</h2>
          </div>
          <small>
            最低 {SOURCE_COVERAGE_POLICY.minimumPrimary} Primary · {SOURCE_COVERAGE_POLICY.minimumCorroboration} Corroboration · {SOURCE_COVERAGE_POLICY.minimumDiscovery} Discovery
          </small>
        </div>
        <div className={styles.coverageTable}>
          <div className={styles.coverageHead}>
            <span>赛道</span><span>Primary</span><span>Corrob.</span><span>Discovery</span><span>Healthy</span><span>Gap</span>
          </div>
          {coverageRows.map((row) => (
            <button
              type="button"
              className={styles.coverageRow}
              key={row.sector}
              onClick={() => {
                setSector(row.sector);
                setQueue(row.state === "covered" ? "all" : "coverage-gap");
              }}
            >
              <span><b>{row.sector}</b><small>{row.total} Source</small></span>
              <strong>{row.primary}</strong>
              <strong>{row.corroboration}</strong>
              <strong>{row.discovery}</strong>
              <strong>{row.healthy}</strong>
              <span className={`${styles.coverageState} ${coverageTone(row.state)}`}>
                {coverageLabels[row.state]}
                <small>{row.gaps.length ? row.gaps.join(" · ") : "覆盖合同满足"}</small>
              </span>
            </button>
          ))}
          {!coverageRows.length ? <p className={styles.empty}>当前 Source 尚未配置可统计赛道。</p> : null}
        </div>
      </section>

      <section className={styles.readinessSection} aria-label="Closest to Core queue">
        <div className={styles.sectionHeading}>
          <div>
            <span>CORE READINESS QUEUE</span>
            <h2>最接近 Core 的默认可晋级 Source</h2>
          </div>
          <button type="button" onClick={() => { setQueue("near-core"); setSort("near-core"); }}>查看完整队列 →</button>
        </div>
        <div className={styles.readinessGrid}>
          {closestToCore.map((source, index) => (
            <article key={source.id}>
              <span className={styles.rank}>#{index + 1}</span>
              <div>
                <b>{source.name}</b>
                <small>{roleLabels[source.sourceRole]} · {source.kind}</small>
              </div>
              <strong>{sourceReadinessLabel(source)}</strong>
              <p>{closestReason(source)}</p>
            </article>
          ))}
          {!closestToCore.length ? <p className={styles.empty}>当前没有处于 Core 晋级验证中的默认可晋级 Source。</p> : null}
        </div>
      </section>

      <section className={styles.directorySection} aria-label="Filtered source directory">
        <div className={styles.sectionHeading}>
          <div>
            <span>SOURCE ENTITIES</span>
            <h2>证据角色、采集健康与治理动作分轴展示</h2>
          </div>
          <small>Discovery-only 保留发现价值，但不进入 Core 晋级和 Core QA 队列。</small>
        </div>

        <div className={styles.sourceGrid}>
          {visibleSources.map((source) => {
            const freshness = sourceFreshness(source, now);
            const observed = sourceHasObservedEndpoint(source);
            const coreEligible = sourceCoreEligible(source);
            const operationalReasons = sourceOperationalReasons(source, now);
            const governanceDecision = sourceNeedsGovernanceDecision(source);
            const evidencePending = sourceNeedsEvidence(source);
            return (
              <article className={styles.sourceCard} id={source.id.replace(/[:]/g, "-")} key={source.id}>
                <div className={styles.sourceHeader}>
                  <div>
                    <span>{source.region} · {source.platform}</span>
                    <h3>{source.name}</h3>
                    <p>{source.sourceLevel} · {source.kind}</p>
                  </div>
                  {source.url ? (
                    <a href={source.url} target="_blank" rel="noreferrer" aria-label={`${source.name} 原始入口`}>
                      <ArrowUpRight size={15} />
                    </a>
                  ) : null}
                </div>

                <div className={styles.axisGrid}>
                  <section className={styles.roleAxis}>
                    <span>EVIDENCE ROLE</span>
                    <b>{roleLabels[source.sourceRole]}</b>
                    <small>{source.lifecycle.toUpperCase()}</small>
                    <p>{sourceReadinessLabel(source)}</p>
                  </section>
                  <section className={styles.healthAxis}>
                    <span>COLLECTOR HEALTH</span>
                    <b className={healthTone(source.healthStatus)}>{healthLabels[source.healthStatus]}</b>
                    <small className={freshnessTone(freshness.state)}>{freshnessLabels[freshness.state]}</small>
                    <p>{ageLabel(freshness.ageHours)}</p>
                  </section>
                </div>

                <div className={styles.coverageTags}>
                  {source.sectors.slice(0, 5).map((item) => <span key={item}>{item}</span>)}
                  {!source.sectors.length ? <span>未归类赛道</span> : null}
                </div>

                <div className={styles.endpointPanel}>
                  <div className={styles.endpointTitle}>
                    <span>COLLECTION ENDPOINTS</span>
                    <small>{observed ? `${source.endpoints.length} 通道` : "尚未建立可靠观测"}</small>
                  </div>
                  {source.endpoints.slice(0, 4).map((endpoint) => (
                    <div className={styles.endpointRow} key={endpoint.id}>
                      <div>
                        <b>{endpoint.label}</b>
                        <small>
                          {endpoint.evidenceGrade ? `Grade ${endpoint.evidenceGrade} · ` : ""}
                          扫描 {endpoint.scanned} · 接受 {endpoint.accepted}
                        </small>
                      </div>
                      <div>
                        <strong className={healthTone(endpoint.status)}>{healthLabels[endpoint.status]}</strong>
                        <small>{compactDate(endpoint.lastSuccessAt)}</small>
                      </div>
                    </div>
                  ))}
                </div>

                <div className={styles.readinessBlock}>
                  <div>
                    {source.promotion?.state === "review_pending" && coreEligible
                      ? <CheckCircle2 size={14} aria-hidden="true" />
                      : <ShieldCheck size={14} aria-hidden="true" />}
                    <span>CORE READINESS</span>
                    <b>{sourceReadinessLabel(source)}</b>
                  </div>
                  {!coreEligible ? (
                    <p>{sourceCoreEligibilityReason(source)}</p>
                  ) : source.promotion?.reasons.length ? (
                    <ol>
                      {source.promotion.reasons.slice(0, 3).map((reason) => <li key={reason}>{reason}</li>)}
                    </ol>
                  ) : (
                    <p>当前没有未满足的量化 Gate。</p>
                  )}
                </div>

                <div className={styles.sourceFooter}>
                  <span><Radio size={11} aria-hidden="true" /> 健康快照 {source.healthUpdatedAt?.slice(0, 10) || "不可用"}</span>
                  {operationalReasons.length ? (
                    <strong className={styles.actionFlag}>
                      <AlertTriangle size={11} />
                      采集处理 · {operationalReasons.slice(0, 2).map((reason) => SOURCE_OPERATION_REASON_LABELS[reason]).join(" / ")}
                    </strong>
                  ) : governanceDecision ? (
                    <strong className={styles.actionFlag}><ShieldCheck size={11} /> 治理决策</strong>
                  ) : source.promotion?.state === "review_pending" && coreEligible ? (
                    <strong className={styles.actionFlag}><CheckCircle2 size={11} /> 待 Core 审批</strong>
                  ) : evidencePending ? (
                    <strong className={styles.stableFlag}><Clock3 size={11} /> 证据积累</strong>
                  ) : !coreEligible ? (
                    <strong className={styles.stableFlag}><Radio size={11} /> Discovery only</strong>
                  ) : (
                    <strong className={styles.stableFlag}><Clock3 size={11} /> 稳定观察</strong>
                  )}
                </div>
              </article>
            );
          })}
        </div>
        {!visibleSources.length ? <p className={styles.empty}>当前筛选条件下没有 Source Entity。</p> : null}
      </section>
    </>
  );
}
