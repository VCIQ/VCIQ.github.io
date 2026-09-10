import { ArrowUpRight } from "lucide-react";
import { homepageSourceEvidence } from "@/lib/homepage-event-identity";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";
import styles from "./dashboard-quality.module.css";

export function EventQualityIndicator({ item }: { item: LiveIntelligenceEvent }) {
  const { totalLinks, additionalLinks } = homepageSourceEvidence(item);
  const hasQuality =
    Boolean(item.qualityStatus) ||
    typeof item.qualityScore === "number" ||
    additionalLinks.length > 0 ||
    Boolean(item.qualitySignals?.length);
  if (!hasQuality) return null;

  return (
    <div className={styles.sourceRow} aria-label="信息质量与关联证据">
      {item.qualityStatus && (
        <span
          className={styles.qualityBadge}
          data-status={item.qualityStatus}
          title={item.qualitySignals?.join("；") || "用户追踪结果质量等级"}
        >
          {item.qualityStatus}
          {typeof item.qualityScore === "number" ? ` · ${item.qualityScore}` : ""}
        </span>
      )}
      {!item.qualityStatus && typeof item.qualityScore === "number" && (
        <span className={styles.qualityBadge}>质量分 {item.qualityScore}</span>
      )}
      {totalLinks > 0 && (
        <span title="可查看的去重来源链接数；不代表独立信源数或事实已获交叉验证。">
          来源链接 {totalLinks}
        </span>
      )}
      {additionalLinks.length > 0 && (
        <details className={styles.evidence}>
          <summary>其他来源链接 {additionalLinks.length}</summary>
          <div className={styles.evidenceList}>
            {additionalLinks.map((source, index) => (
              <a
                href={source.url}
                key={`${source.url}-${index}`}
                target="_blank"
                rel="noreferrer"
                title={source.title}
              >
                <strong>{source.title || source.name}</strong>
                <span>
                  {source.level || source.platform || source.name}
                  <ArrowUpRight size={11} />
                </span>
              </a>
            ))}
          </div>
        </details>
      )}
      {item.qualitySignals?.length ? (
        <span title={item.qualitySignals.join("；")}>{item.qualitySignals[0]}</span>
      ) : null}
    </div>
  );
}
