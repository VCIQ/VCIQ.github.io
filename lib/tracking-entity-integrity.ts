import type { UserTrackingConfig } from "@/lib/user-tracking";

export type TrackingCompoundEntityIssue = {
  trackSlug: string;
  trackName: string;
  entityType: "company" | "person";
  value: string;
  parts: string[];
};

const ENTITY_CONTENT_PATTERN = /[A-Za-z0-9\u3400-\u9fff]/u;
const COMPOUND_ENTITY_SEPARATOR = /(?:[\n\r、，；;|｜]+|\s+[\/／]\s+|\s+(?:和|与|及)\s+)/u;

function normalizeEntityKey(value: string): string {
  return value
    .normalize("NFKC")
    .replace(/\s+/gu, " ")
    .trim()
    .toLocaleLowerCase("zh-CN");
}

export function splitCompoundTrackingEntityName(value: string): string[] {
  const raw = value.trim();
  if (!raw) return [];
  const parts = raw
    .split(COMPOUND_ENTITY_SEPARATOR)
    .map((part) => part.normalize("NFKC").replace(/\s+/gu, " ").trim())
    .filter((part) => ENTITY_CONTENT_PATTERN.test(part));
  return parts.length > 1 ? parts : [];
}

export function assertSingleTrackingEntityName(
  entityType: "company" | "person",
  value: string,
): void {
  const parts = splitCompoundTrackingEntityName(value);
  if (parts.length < 2) return;
  const label = entityType === "person" ? "人物" : "公司";
  throw new Error(
    `${label}追踪对象疑似包含多个实体：“${value.trim()}” → ${parts.join("、")}。请拆分为独立实体后再采集。`,
  );
}

export function findCompoundTrackingEntities(
  config: UserTrackingConfig,
): TrackingCompoundEntityIssue[] {
  const issues: TrackingCompoundEntityIssue[] = [];

  for (const track of config.tracks) {
    for (const { field, entityType } of [
      { field: "people" as const, entityType: "person" as const },
      { field: "sampleCompanies" as const, entityType: "company" as const },
    ]) {
      for (const value of track[field]) {
        const parts = splitCompoundTrackingEntityName(value);
        if (parts.length < 2) continue;
        issues.push({
          trackSlug: track.slug,
          trackName: track.name,
          entityType,
          value,
          parts,
        });
      }
    }
  }

  return issues;
}

export function assertNoCompoundTrackingEntities(config: UserTrackingConfig): void {
  const issues = findCompoundTrackingEntities(config);
  if (!issues.length) return;

  const preview = issues
    .slice(0, 5)
    .map((issue) => {
      const label = issue.entityType === "person" ? "人物" : "公司";
      return `${issue.trackName}/${label}“${issue.value}” → ${issue.parts.join("、")}`;
    })
    .join("；");
  const remainder = issues.length > 5 ? `；另有 ${issues.length - 5} 项` : "";
  throw new Error(
    `检测到复合追踪实体，user_tracking.json 必须保持零复合状态：${preview}${remainder}。`,
  );
}

export function findNewCompoundTrackingEntities(
  previous: UserTrackingConfig,
  next: UserTrackingConfig,
): TrackingCompoundEntityIssue[] {
  const issues: TrackingCompoundEntityIssue[] = [];

  for (const nextTrack of next.tracks) {
    const previousTrack = previous.tracks.find((track) => track.slug === nextTrack.slug);
    const fields = [
      { field: "people" as const, entityType: "person" as const },
      { field: "sampleCompanies" as const, entityType: "company" as const },
    ];

    for (const { field, entityType } of fields) {
      const previousValues = new Set(
        (previousTrack?.[field] ?? []).map((value) => normalizeEntityKey(value)),
      );
      for (const value of nextTrack[field]) {
        if (previousValues.has(normalizeEntityKey(value))) continue;
        const parts = splitCompoundTrackingEntityName(value);
        if (parts.length < 2) continue;
        issues.push({
          trackSlug: nextTrack.slug,
          trackName: nextTrack.name,
          entityType,
          value,
          parts,
        });
      }
    }
  }

  return issues;
}

export function assertNoNewCompoundTrackingEntities(
  previous: UserTrackingConfig,
  next: UserTrackingConfig,
): void {
  const issues = findNewCompoundTrackingEntities(previous, next);
  if (!issues.length) return;

  const preview = issues
    .slice(0, 3)
    .map((issue) => {
      const label = issue.entityType === "person" ? "人物" : "公司";
      return `${issue.trackName}/${label}“${issue.value}” → ${issue.parts.join("、")}`;
    })
    .join("；");
  const remainder = issues.length > 3 ? `；另有 ${issues.length - 3} 项` : "";
  throw new Error(
    `检测到本次新增的复合追踪实体，已阻止写入 user_tracking.json：${preview}${remainder}。请拆分为独立实体后再提交。`,
  );
}
