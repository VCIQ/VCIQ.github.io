import { ExternalLink } from "lucide-react";

import type {
  ResearchAgentEvidence,
  ResearchEvidenceVerificationStatus,
} from "@/lib/research-agent-data";
import styles from "./research-agent.module.css";

type EvidenceWithSourceDetails = ResearchAgentEvidence & {
  publisherName?: string;
  originalPublisherName?: string;
  platformName?: string;
  sourceType?: string;
  sourceRole?: string;
};

const sourceRoleLabels: Record<string, string> = {
  primary: "直接事实来源",
  corroboration: "独立交叉验证",
  discovery: "发现线索",
};

const verificationStatusLabels: Record<string, string> = {
  candidate: "候选证据",
  auto_verified: "自动核验通过",
  cross_verified: "已交叉验证",
  reviewed: "已人工复核",
  rejected: "未通过证据门",
};

const dateConfidenceLabels: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
  unknown: "待判定",
};

const dateSourceLabels: Record<string, string> = {
  event_date: "事件日期",
  page_created_at: "页面创建时间",
  page_updated_at: "页面更新时间",
  legacy_published_at: "历史来源时间（语义未解析）",
  observed_at: "本轮观测时间",
};

function evidenceAnchorId(id: string) {
  return `evidence-${id.replace(/[^A-Za-z0-9_-]/g, "-")}`;
}

function uniqueIds(ids: string[]) {
  return [...new Set(ids.filter(Boolean))];
}

function evidenceVerificationStatus(
  item: ResearchAgentEvidence,
): ResearchEvidenceVerificationStatus {
  if (
    item.reviewStatus === "rejected" ||
    item.qualityStatus === "rejected" ||
    item.publicationTier === "rejected"
  ) {
    return "rejected";
  }
  if (item.reviewStatus === "reviewed" || item.reviewStatus === "approved") {
    return "reviewed";
  }
  if (item.verificationStatus) return item.verificationStatus;
  if (
    item.publicationTier === "verified_change" &&
    item.qualityStatus === "passed" &&
    item.supportStatus === "supports"
  ) {
    return "auto_verified";
  }
  return "candidate";
}

function verificationLabel(item: ResearchAgentEvidence) {
  const status = evidenceVerificationStatus(item);
  return verificationStatusLabels[status] || status;
}

function EvidenceTime({ item }: { item: ResearchAgentEvidence }) {
  const hasExplicitSemanticTime = Boolean(
    item.eventDate || item.pageCreatedAt || item.pageUpdatedAt || item.observedAt,
  );
  const confidence = item.dateConfidence
    ? (dateConfidenceLabels[item.dateConfidence] || item.dateConfidence)
    : null;
  const dateSource = item.dateSource
    ? (dateSourceLabels[item.dateSource] || item.dateSource)
    : null;

  if (!hasExplicitSemanticTime && !item.publishedAt) {
    return <span>时间待补</span>;
  }

  return (
    <>
      {item.eventDate && <strong>事件：{item.eventDate}</strong>}
      {item.pageCreatedAt && <small>页面创建：{item.pageCreatedAt}</small>}
      {item.pageUpdatedAt && <small>页面更新：{item.pageUpdatedAt}</small>}
      {item.publishedAt && (
        <small>
          {item.eventDate ? "来源记录" : "来源记录（非事件时间）"}：{item.publishedAt}
        </small>
      )}
      {item.observedAt && <small>本轮观测：{item.observedAt}</small>}
      {!item.eventDate && item.publishedAt && (
        <small>事件时间尚未单独解析</small>
      )}
      {(dateSource || confidence) && (
        <small>
          {dateSource ? `时间来源：${dateSource}` : ""}
          {dateSource && confidence ? " · " : ""}
          {confidence ? `时间置信：${confidence}` : ""}
        </small>
      )}
    </>
  );
}

export function EvidenceRefs({
  ids,
  evidenceById,
}: {
  ids: string[];
  evidenceById: ReadonlyMap<string, ResearchAgentEvidence>;
}) {
  const references = uniqueIds(ids);
  if (!references.length) return null;

  return (
    <div className={styles.evidenceRefs} aria-label="引用证据">
      {references.map((id) => {
        const item = evidenceById.get(id);
        if (!item) return <span key={id}>{id} · 证据待同步</span>;
        return (
          <a href={`#${evidenceAnchorId(id)}`} key={id}>
            {id} · {item.sourceName || "来源待补"} · {item.evidenceGrade || "未分级"} · {verificationLabel(item)}
          </a>
        );
      })}
    </div>
  );
}

export function EvidenceLedger({ evidence }: { evidence: ResearchAgentEvidence[] }) {
  if (!evidence.length) {
    return <p className={styles.empty}>本轮没有可公开的证据节点。</p>;
  }

  return (
    <div
      className={styles.evidenceTableWrap}
      role="region"
      aria-label="证据台账，可横向滚动"
      tabIndex={0}
    >
      <table className={styles.evidenceTable}>
        <caption>
          本期唯一证据台账；发布层级表示自动准入状态，不等同于事实已经人工确认。
        </caption>
        <thead>
          <tr>
            <th scope="col">证据</th>
            <th scope="col">标题与原始链接</th>
            <th scope="col">发布方 / 承载平台</th>
            <th scope="col">核验状态</th>
            <th scope="col">来源分类</th>
            <th scope="col">时间语义</th>
            <th scope="col">支持对象 / 字段</th>
          </tr>
        </thead>
        <tbody>
          {evidence.map((rawItem) => {
            const item = rawItem as EvidenceWithSourceDetails;
            const attribution = [
              item.originalPublisherName ? `原始：${item.originalPublisherName}` : null,
              item.publisherName && item.publisherName !== item.originalPublisherName
                ? `发布：${item.publisherName}`
                : null,
              item.platformName && ![item.originalPublisherName, item.publisherName].includes(item.platformName)
                ? `平台：${item.platformName}`
                : null,
            ].filter((value): value is string => Boolean(value));
            if (!attribution.length) attribution.push(item.sourceName || "发布方待补");
            const sourceRole = item.sourceRole
              ? (sourceRoleLabels[item.sourceRole] || item.sourceRole)
              : null;
            const quality = [
              item.evidenceGrade || "未分级",
              item.sourceType || (!sourceRole ? "类型待补" : null),
              sourceRole,
              item.qualityStatus === "rejected" ? "质量未通过" : null,
              item.supportStatus === "insufficient" ? "支持不足" : null,
            ].filter(Boolean).join(" · ");
            const claimFields = item.claimFields?.join("、") || "字段待补";

            return (
              <tr id={evidenceAnchorId(item.id)} key={item.id} tabIndex={-1}>
                <th scope="row">{item.id}</th>
                <td>
                  {item.url ? (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      aria-label={`${item.title || item.sourceName || item.id}（新窗口打开）`}
                    >
                      {item.title || item.sourceName || "证据标题待补"}
                      <ExternalLink size={13} aria-hidden="true" />
                    </a>
                  ) : (
                    <span>{item.title || item.sourceName || "证据标题待补"}</span>
                  )}
                </td>
                <td>
                  <strong>{attribution[0]}</strong>
                  {attribution.slice(1).map((label) => <small key={label}>{label}</small>)}
                </td>
                <td>
                  <strong>{verificationLabel(item)}</strong>
                  <small>
                    {item.reviewStatus === "reviewed" || item.reviewStatus === "approved"
                      ? "人工状态已确认"
                      : "人工复核状态另行记录"}
                  </small>
                </td>
                <td>{quality}</td>
                <td><EvidenceTime item={item} /></td>
                <td>
                  <strong>{item.entityName || "对象待补"}</strong>
                  <small>{claimFields}</small>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
