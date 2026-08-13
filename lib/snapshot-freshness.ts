export type RefreshAudit = {
  mode?: string;
  pipelineCompleted?: boolean;
  completedAt?: string;
  lastNewsCrawlAt?: string;
  localDate?: string;
  articleCount?: number;
  previousArticleCount?: number;
  newArticleCount?: number;
  latestPublishedAt?: string;
  todayArticleCount?: number;
  todaySourceCount?: number;
};

export type SnapshotFreshness = {
  processedAt: string;
  label: "内置快照" | "数据异常" | "当日情报已更新" | "本轮抓取已完成" | "内容待刷新";
  description: string;
  stale: boolean;
};

function taipeiParts(value: string | Date) {
  const timestamp = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(timestamp.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(timestamp);
  return Object.fromEntries(parts.map((part) => [part.type, part.value]));
}

export function formatTaipeiDate(value: string | Date): string {
  const values = taipeiParts(value);
  if (!values) {
    return typeof value === "string" ? value.slice(0, 10) : "";
  }
  return `${values.year}-${values.month}-${values.day}`;
}

export function formatTaipeiDateTime(value: string | Date): string {
  const values = taipeiParts(value);
  if (!values) {
    return typeof value === "string" ? value.replace("T", " ").slice(0, 16) : "";
  }
  return `${values.year}-${values.month}-${values.day} ${values.hour}:${values.minute}`;
}

export function getSnapshotFreshness({
  isLive,
  generatedAt,
  latestPublishedAt,
  qualityPassed,
  refreshAudit,
  now = new Date(),
}: {
  isLive: boolean;
  generatedAt: string;
  latestPublishedAt: string;
  qualityPassed?: boolean;
  refreshAudit?: RefreshAudit;
  now?: Date;
}): SnapshotFreshness {
  const processedDate = formatTaipeiDate(generatedAt);
  const processedAt = formatTaipeiDateTime(refreshAudit?.completedAt || generatedAt);
  const today = formatTaipeiDate(now);

  if (!isLive) {
    return {
      processedAt,
      label: "内置快照",
      description: "当前展示构建时公开快照；筛选时按需读取完整事件档案",
      stale: false,
    };
  }

  if (qualityPassed === false) {
    return {
      processedAt,
      label: "数据异常",
      description: "数据质量门未通过",
      stale: true,
    };
  }

  const auditDate = refreshAudit?.localDate ||
    (refreshAudit?.completedAt ? formatTaipeiDate(refreshAudit.completedAt) : "");
  const completedCurrentSnapshot =
    refreshAudit?.pipelineCompleted === true &&
    Boolean(auditDate) &&
    auditDate === processedDate;
  const processedToday = processedDate === today;
  const latestIsProcessedDay = latestPublishedAt === processedDate;

  if (completedCurrentSnapshot || processedToday) {
    if (latestIsProcessedDay) {
      return {
        processedAt,
        label: "当日情报已更新",
        description: "当前启用赛道的可追溯公开情报",
        stale: false,
      };
    }
    return {
      processedAt,
      label: "本轮抓取已完成",
      description: latestPublishedAt
        ? `本轮数据已处理，最新公开情报截至 ${latestPublishedAt}`
        : "本轮数据已处理，暂未发现可发布的新情报",
      stale: false,
    };
  }

  return {
    processedAt,
    label: "内容待刷新",
    description: latestPublishedAt
      ? `上次有效情报截至 ${latestPublishedAt}`
      : "尚未取得有效公开情报",
    stale: true,
  };
}
