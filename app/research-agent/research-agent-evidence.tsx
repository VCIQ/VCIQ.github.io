import { ExternalLink } from "lucide-react";

import type { ResearchAgentEvidence } from "@/lib/research-agent-data";
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

function evidenceAnchorId(id: string) {
  return `evidence-${id.replace(/[^A-Za-z0-9_-]/g, "-")}`;
}

function uniqueIds(ids: string[]) {
  return [...new Set(ids.filter(Boolean))];
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
            {id} · {item.sourceName || "来源待补"} · {item.evidenceGrade || "未分级"}
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
        <caption>本期唯一证据台账；上方内容仅通过证据编号引用此处记录。</caption>
        <thead>
          <tr>
            <th scope="col">证据</th>
            <th scope="col">标题与原始链接</th>
            <th scope="col">发布方 / 承载平台</th>
            <th scope="col">来源分类</th>
            <th scope="col">发布日期</th>
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
                <td>{quality}</td>
                <td>{item.publishedAt || "日期待补"}</td>
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
