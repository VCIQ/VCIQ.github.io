import { buildCompanyResearchSnapshot } from "@/lib/company-research";
import { companies } from "@/lib/catalog-data";
import { snapshotDate } from "@/lib/intelligence-data";
import { getCompanyResearchRelations } from "@/lib/research-relations";
import {
  CompanyDirectoryClient,
  type CompanyDirectoryRecord,
} from "@/components/company-directory-client";

function recentChange(date: string | undefined) {
  if (!date) return false;
  const asOf = Date.parse(snapshotDate);
  const changedAt = Date.parse(date);
  if (!Number.isFinite(asOf) || !Number.isFinite(changedAt)) return false;
  return asOf - changedAt <= 90 * 86_400_000;
}

export function CompanyDirectory({ pageSize = 12 }: { pageSize?: number }) {
  const records: CompanyDirectoryRecord[] = companies.map((company) => {
    const research = buildCompanyResearchSnapshot(company);
    const relations = getCompanyResearchRelations(company.slug);
    const relatedTracks = relations.tracks.map((item) => item.name);
    const relatedTopics = relations.topics.map((item) => item.name);
    const relatedPeople = relations.people.map((item) => item.name);
    return {
      slug: company.slug,
      name: company.name,
      englishName: company.englishName ?? "",
      region: company.region,
      sector: company.sector,
      stage: company.stage,
      status: company.status,
      whyImportant: research.whyImportant,
      nextWatch: research.nextWatch,
      latestChange: research.latestChange
        ? {
            date: research.latestChange.date,
            title: research.latestChange.title,
            type: research.latestChange.type,
          }
        : undefined,
      priorityScore: research.priority.score,
      priorityLevel: research.priority.level,
      priorityLabel: research.priority.label,
      evidenceScore: research.coverage.score,
      coverageLabel: research.coverage.label,
      hasProfile: research.coverage.hasProfile,
      identityConfidence: research.coverage.identityConfidence,
      updatedAt: research.updatedAt,
      recentChange: recentChange(research.latestChange?.date),
      relatedTracks: relatedTracks.slice(0, 4),
      relatedTopics: relatedTopics.slice(0, 4),
      relatedPeople: relatedPeople.slice(0, 4),
      searchIndex: [
        company.name,
        company.englishName,
        company.summary.slice(0, 160),
        company.product.slice(0, 160),
        company.region,
        company.sector,
        company.stage,
        ...relatedTracks,
        ...relatedTopics,
        ...relatedPeople.slice(0, 6),
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("zh-CN")
        .slice(0, 520),
    };
  });

  return <CompanyDirectoryClient records={records} pageSize={pageSize} />;
}
