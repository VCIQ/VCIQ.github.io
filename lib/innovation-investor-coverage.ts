import {
  innovationInvestorRegistryV2,
  type InvestorRegistryV2Entry,
} from "@/lib/innovation-investor-registry-v2";
import {
  investorEvidenceRecords,
  type InvestorEvidenceRecord,
} from "@/lib/innovation-investor-research";

export type InvestorCoverageRow = {
  id: string;
  name: string;
  aliases: string[];
  cohorts: string[];
  region: string;
  focusAreas: string[];
  officialHomepage: string | null;
  discoveryUrl: string | null;
  sourceStatus: string;
  reviewedEvidenceCount: number;
  investmentDisclosureCount: number;
  reviewedCompanyCount: number;
  distinctOriginalCount: number;
  lastReviewedInvestment: {
    company: string;
    date: string;
    sourceUrl: string;
  } | null;
  coverageScore: null;
  lastScoutAt: null;
};

export function buildInvestorCoverageDirectory(
  institutions: readonly InvestorRegistryV2Entry[] = innovationInvestorRegistryV2,
  records: readonly InvestorEvidenceRecord[] = investorEvidenceRecords,
) {
  const sources = new Map<string, InvestorEvidenceRecord[]>();
  for (const entry of records) {
    const group = sources.get(entry.institutionId) ?? [];
    group.push(entry);
    sources.set(entry.institutionId, group);
  }

  const rows: InvestorCoverageRow[] = institutions.map((institution) => {
    const evidence = sources.get(institution.id) ?? [];
    const newest = evidence.filter((item) => item.kind === "investment" && item.project)
      .sort((a, b) => b.date.localeCompare(a.date) || a.id.localeCompare(b.id))[0];

    return {
      id: institution.id,
      name: institution.canonicalName,
      aliases: institution.aliases,
      cohorts: institution.cohorts,
      region: institution.regionGroup,
      focusAreas: institution.focusAreas,
      officialHomepage: institution.officialSources.homepage,
      discoveryUrl: institution.officialSources.discovery,
      sourceStatus: institution.sourceStatus,
      reviewedEvidenceCount: evidence.length,
      investmentDisclosureCount: evidence.filter((item) => item.kind === "investment").length,
      reviewedCompanyCount: new Set(evidence.map((item) => item.project).filter(Boolean)).size,
      distinctOriginalCount: new Set(evidence.map((item) => item.source.url)).size,
      lastReviewedInvestment: newest && newest.project ? {
        company: newest.project,
        date: newest.date,
        sourceUrl: newest.source.url,
      } : null,
      // Absent a time-series of successful source scans, coverage is NOT
      // measured. Zero evidence is NOT evidence of zero investment activity.
      coverageScore: null,
      lastScoutAt: null,
    };
  }).sort((a, b) => b.reviewedEvidenceCount - a.reviewedEvidenceCount ||
    a.name.localeCompare(b.name, "zh-CN"));

  const hasEvidence = rows.filter((row) => row.reviewedEvidenceCount > 0).length;
  return {
    rows,
    summary: {
      uniqueInstitutions: rows.length,
      globalCore: rows.filter((row) => row.cohorts.includes("global-core")).length,
      chinaFocus: rows.filter((row) => row.cohorts.includes("china-focus")).length,
      overlap: rows.filter((row) => row.cohorts.includes("global-core") &&
        row.cohorts.includes("china-focus")).length,
      registeredHomepages: rows.filter((row) => row.officialHomepage).length,
      pendingOfficialSources: rows.filter((row) => row.sourceStatus === "pending-official-source").length,
      withVerifiedEvidence: hasEvidence,
      reviewedEvidenceRecords: records.length,
      coverageScoreAvailability: "pending-baseline" as const,
    },
  };
}
