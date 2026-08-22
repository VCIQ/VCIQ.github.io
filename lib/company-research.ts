import type { Company } from "@/lib/catalog-data";
import { intelligenceEvents, snapshotDate } from "@/lib/intelligence-data";
import { isActionableCompanySignal } from "@/lib/company-update-curation";
import { getCompanyResearch } from "@/lib/research-content";
import { getCompanyResearchRelations } from "@/lib/research-relations";
import { getCompanyVentureProfile } from "@/lib/venture-profile-data";

export type CompanyLatestChange = {
  date: string;
  title: string;
  summary: string;
  type: string;
  source: string;
  href: string;
  importance: number;
};

export type CompanyResearchSnapshot = {
  whyImportant: string;
  latestChange?: CompanyLatestChange;
  nextWatch: string;
  priority: {
    score: number;
    level: "P1" | "P2" | "P3";
    label: string;
    reasons: string[];
  };
  coverage: {
    score: number;
    label: string;
    hasProfile: boolean;
    identityConfidence: number;
  };
  updatedAt: string;
  relationCounts: {
    tracks: number;
    topics: number;
    people: number;
  };
};

function cleanSentence(value: string, limit = 160) {
  const text = value.replace(/\s+/gu, " ").trim();
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).replace(/[，、；：,.\s]+$/u, "")}…`;
}

function dateValue(value: string) {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function freshnessScore(date: string | undefined) {
  if (!date) return 0;
  const asOf = dateValue(snapshotDate);
  const eventAt = dateValue(date);
  if (!asOf || !eventAt) return 0;
  const days = Math.max(0, Math.round((asOf - eventAt) / 86_400_000));
  if (days <= 30) return 25;
  if (days <= 90) return 18;
  if (days <= 180) return 10;
  return 4;
}

function coverageLabel(score: number, hasProfile: boolean) {
  if (!hasProfile) return "待首次档案刷新";
  if (score >= 85) return "证据覆盖较高";
  if (score >= 65) return "证据可用";
  return "关键证据待补";
}

export function buildCompanyResearchSnapshot(
  company: Company,
): CompanyResearchSnapshot {
  const venture = getCompanyVentureProfile(company.slug);
  const research = getCompanyResearch(company);
  const relations = getCompanyResearchRelations(company.slug);
  const companyEvents = intelligenceEvents
    .filter((event) =>
      event.companySlug === company.slug &&
      isActionableCompanySignal({
        title: event.title,
        summary: event.summary,
        label: event.type,
        sourceLevel: event.source.level,
      }),
    )
    .sort(
      (left, right) =>
        right.publishedAt.localeCompare(left.publishedAt) ||
        right.importance - left.importance,
    );
  const latestEvent = companyEvents[0];
  const evidenceScore = venture?.evidenceScore ?? 0;
  const relationScore = Math.min(
    15,
    relations.tracks.length * 3 +
      relations.people.length * 2 +
      relations.topics.length,
  );
  const capitalEvents =
    (venture?.financing.length ?? 0) + (venture?.capitalMarkets.length ?? 0);
  const score = Math.max(
    0,
    Math.min(
      100,
      Math.round(
        evidenceScore * 0.35 +
          freshnessScore(latestEvent?.publishedAt) +
          Math.min(20, (latestEvent?.importance ?? 0) * 0.2) +
          relationScore +
          Math.min(5, capitalEvents),
      ),
    ),
  );
  const reasons = [
    latestEvent && freshnessScore(latestEvent.publishedAt) >= 18
      ? "近期出现可核验变化"
      : "近期变化信号有限",
    evidenceScore >= 65 ? "公司档案已有可用证据覆盖" : "仍需补齐关键公司证据",
    relations.people.length
      ? `已连接 ${relations.people.length} 位关键人物`
      : "关键人物关系待建立",
  ];
  const level = score >= 70 ? "P1" : score >= 45 ? "P2" : "P3";
  const whyImportant = cleanSentence(
    venture?.projectBackground?.summary ||
      venture?.background ||
      `${company.summary} ${research.industryPosition}`,
  );

  return {
    whyImportant,
    latestChange: latestEvent
      ? {
          date: latestEvent.publishedAt,
          title: latestEvent.title,
          summary: cleanSentence(latestEvent.summary, 140),
          type: latestEvent.type,
          source: latestEvent.source.name,
          href: latestEvent.source.url,
          importance: latestEvent.importance,
        }
      : undefined,
    nextWatch: cleanSentence(research.researchQuestions[0] ?? research.commercialization, 130),
    priority: {
      score,
      level,
      label:
        level === "P1" ? "重点跟踪" : level === "P2" ? "持续观察" : "资料积累",
      reasons,
    },
    coverage: {
      score: evidenceScore,
      label: coverageLabel(evidenceScore, Boolean(venture)),
      hasProfile: Boolean(venture),
      identityConfidence: Math.round(company.confidence * 100),
    },
    updatedAt: venture?.updatedAt?.slice(0, 10) ?? "",
    relationCounts: {
      tracks: relations.tracks.length,
      topics: relations.topics.length,
      people: relations.people.length,
    },
  };
}
