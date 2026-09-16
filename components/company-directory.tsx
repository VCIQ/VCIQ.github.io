import { buildCompanyResearchSnapshot } from "@/lib/company-research";
import { companies } from "@/lib/catalog-data";
import { projectHomepageCompanyDisclosureEvents } from "@/lib/homepage-company-disclosure-events";
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

const latestDisclosureByCompany = new Map<string, ReturnType<typeof projectHomepageCompanyDisclosureEvents>[number]>();
for (const event of projectHomepageCompanyDisclosureEvents(120)) {
  if (event.companySlug && !latestDisclosureByCompany.has(event.companySlug)) {
    latestDisclosureByCompany.set(event.companySlug, event);
  }
}

export function CompanyDirectory({ pageSize = 12 }: { pageSize?: number }) {
  const records: CompanyDirectoryRecord[] = companies.map((company) => {
    const research = buildCompanyResearchSnapshot(company);
    const disclosure = latestDisclosureByCompany.get(company.slug);
    const disclosureChange = disclosure
      ? {
          date: disclosure.publishedAt,
          title: disclosure.title,
          summary: disclosure.summary,
          type: disclosure.type,
          source: disclosure.source.name,
          href: disclosure.source.url,
          importance: disclosure.importance,
        }
      : undefined;
    const latestChange = [research.latestChange, disclosureChange]
      .filter((item): item is NonNullable<typeof item> => Boolean(item))
      .sort(
        (left, right) =>
          right.date.localeCompare(left.date) ||
          right.importance - left.importance,
      )[0];
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
      latestChange: latestChange
        ? {
            date: latestChange.date,
            title: latestChange.title,
            type: latestChange.type,
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
      recentChange: recentChange(latestChange?.date),
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
        disclosure?.title,
        disclosure?.source.name,
        ...relatedTracks,
        ...relatedTopics,
        ...relatedPeople.slice(0, 6),
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("zh-CN")
        .slice(0, 620),
    };
  });

  return <CompanyDirectoryClient records={records} pageSize={pageSize} />;
}
