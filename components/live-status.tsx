import { formatTaipeiDateTime } from "@/lib/snapshot-freshness";
import rawArticles from "@/public/data/articles.json";
import rawPipelineHealth from "@/public/data/pipeline_health.json";

const BUILD_PROVENANCE_URL = "https://vciq.github.io/build-provenance.json";

type StatusSnapshot = {
  generatedAt?: string;
  refreshAudit?: {
    completedAt?: string;
    pipelineCompleted?: boolean;
  };
  qualityGate?: {
    passed?: boolean;
  };
};

type PipelineHealth = {
  overallStatus?: "healthy" | "stale" | "degraded" | "missing" | "unknown";
  summary?: {
    staleJobs?: number;
    degradedJobs?: number;
    missingJobs?: number;
    unknownJobs?: number;
  };
};

function siteHealthLabel(status: PipelineHealth["overallStatus"]) {
  switch (status) {
    case "healthy":
      return "全站数据正常";
    case "stale":
      return "全站部分过期";
    case "degraded":
      return "全站部分降级";
    case "missing":
      return "全站数据缺失";
    default:
      return "全站状态待核对";
  }
}

/**
 * Build-time status only. The previous client component called useArticles()
 * from the global header, which downloaded the entire public article database
 * on every route just to render this timestamp.
 */
export function LiveStatus() {
  const snapshot = rawArticles as StatusSnapshot;
  const pipelineHealth = rawPipelineHealth as PipelineHealth;
  const snapshotAt = formatTaipeiDateTime(
    snapshot.refreshAudit?.completedAt || snapshot.generatedAt || "",
  );
  const snapshotHealthy =
    snapshot.refreshAudit?.pipelineCompleted === true &&
    snapshot.qualityGate?.passed === true;
  const allSiteHealthy = pipelineHealth.overallStatus === "healthy";
  const healthLabel = siteHealthLabel(pipelineHealth.overallStatus);
  const summary = pipelineHealth.summary;
  const healthDetails = [
    summary?.staleJobs ? `${summary.staleJobs} 个任务过期` : "",
    summary?.degradedJobs ? `${summary.degradedJobs} 个任务降级` : "",
    summary?.missingJobs ? `${summary.missingJobs} 个任务缺失` : "",
    summary?.unknownJobs ? `${summary.unknownJobs} 个任务待核对` : "",
  ].filter(Boolean);
  const statusTitle = [
    `事件快照最后成功更新：${snapshotAt}`,
    `全站数据状态：${healthLabel.replace("全站", "")}`,
    healthDetails.length ? healthDetails.join("，") : "",
  ].filter(Boolean).join("；");

  return (
    <>
      <a
        className="updated"
        title={`${statusTitle}；查看公开数据健康快照`}
        href="/data/pipeline_health.json"
      >
        <i
          className={snapshotHealthy && allSiteHealthy ? "" : "muted-dot"}
          aria-hidden="true"
        />
        <span>
          {snapshotHealthy ? "事件快照已更新" : "事件快照待复核"} {snapshotAt} · {healthLabel}
        </span>
      </a>
      <a
        className="updated build-provenance-link"
        href={BUILD_PROVENANCE_URL}
        target="_blank"
        rel="noopener noreferrer"
        title="查看本次公开站构建记录"
      >
        构建记录
      </a>
    </>
  );
}
