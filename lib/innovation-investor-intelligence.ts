import registry from "@/config/innovation_investor_registry_v2.json";
import identities from "@/config/innovation_investor_project_identities.json";
import {
  investorEvidenceRecords,
  type InvestorEvidenceRecord,
} from "@/lib/innovation-investor-research";

/**
 * Task 5: institution-first intelligence read model.
 *
 * Registered focus areas describe an institution's declared/curated research
 * coverage, not the sector classification of a particular portfolio company.
 * All observed activity below is restricted to reviewed evidence records.
 */
export type InvestorIntelligenceEvent = {
  evidenceId: string;
  projectId: string | null;
  projectName: string | null;
  kind: InvestorEvidenceRecord["kind"];
  date: string;
  datePrecision: InvestorEvidenceRecord["datePrecision"];
  headline: string;
  sourceUrl: string;
  sourceKind: string;
  participation: string | null;
  round: string | null;
  roundAmount: {value: number; currency: string} | null;
  investorAmount: {value: number; currency: string} | null;
  outcomeStatus: string | null;
  viewpoints: {name: string; roleAtPublication: string; projectResponsibility: string}[];
  followUp: string;
};

export type InstitutionIntelligence = {
  institutionId: string;
  name: string;
  cohorts: string[];
  focusAreas: string[];
  monitoredProjectCount: number;
  reviewedEvidenceCount: number;
  reviewedInvestmentCount: number;
  reviewedViewpointCount: number;
  reviewedOutcomeCount: number;
  latestEvidenceDate: string | null;
  events: InvestorIntelligenceEvent[];
  /** No realized fund performance can be inferred from the reviewed sources. */
  realizedReturn: "unknown";
  sampleOnly: true;
};

const canonicalByAlias = new Map(
  identities.projects.flatMap(project =>
    project.observedNames.map(name =>
      [name.trim().toLocaleLowerCase("en-US"), project.id] as const,
    ),
  ),
);

function toEvent(record: InvestorEvidenceRecord): InvestorIntelligenceEvent {
  const projectId = record.project
    ? canonicalByAlias.get(record.project.trim().toLocaleLowerCase("en-US"))
    : undefined;
  if (record.project && !projectId) {
    throw new Error(`Task 5: reviewed project lacks canonical identity: ${record.id}`);
  }
  return {
    evidenceId: record.id,
    projectId: projectId ?? null,
    projectName: record.project,
    kind: record.kind,
    date: record.date,
    datePrecision: record.datePrecision,
    headline: record.title,
    sourceUrl: record.source.url,
    sourceKind: record.source.kind,
    participation: record.participation,
    round: record.round,
    roundAmount: record.roundAmount,
    investorAmount: record.investorAmount,
    outcomeStatus: record.resultStatus,
    viewpoints: record.speakers.map(s => ({
      name: s.name,
      roleAtPublication: s.roleAtPublication,
      projectResponsibility: s.projectResponsibility,
    })),
    followUp: record.nextCheck,
  };
}

export function buildInvestorIntelligence(
  records: readonly InvestorEvidenceRecord[] = investorEvidenceRecords,
): InstitutionIntelligence[] {
  const institutions = registry.institutions;
  const known = new Set(institutions.map(i => i.id));
  for (const record of records) {
    if (!known.has(record.institutionId)) {
      throw new Error(`Task 5: evidence refers to unregistered institution: ${record.id}`);
    }
  }

  return institutions.map(institution => {
    const events = records.filter(record => record.institutionId === institution.id)
      .map(toEvent)
      .sort((a, b) => b.date.localeCompare(a.date) || a.evidenceId.localeCompare(b.evidenceId));
    return {
      institutionId: institution.id,
      name: institution.canonicalName,
      cohorts: [...institution.cohorts],
      focusAreas: [...institution.focusAreas],
      monitoredProjectCount: new Set(events.map(event => event.projectId).filter(Boolean)).size,
      reviewedEvidenceCount: events.length,
      reviewedInvestmentCount: events.filter(event => event.kind === "investment").length,
      reviewedViewpointCount: events.filter(event => event.kind === "viewpoint").length,
      reviewedOutcomeCount: events.filter(event => event.kind === "outcome").length,
      latestEvidenceDate: events[0]?.date ?? null,
      events,
      realizedReturn: "unknown" as const,
      sampleOnly: true as const,
    };
  });
}

export function investorIntelligenceCoverage(
  rows: readonly InstitutionIntelligence[] = buildInvestorIntelligence(),
) {
  return {
    registeredInstitutions: rows.length,
    evidenceCoveredInstitutions: rows.filter(row => row.reviewedEvidenceCount > 0).length,
    reviewedEvidenceRecords: rows.reduce((sum, row) => sum + row.reviewedEvidenceCount, 0),
    reviewedCanonicalProjects: new Set(rows.flatMap(row =>
      row.events.map(event => event.projectId).filter((id): id is string => !!id),
    )).size,
    investmentDisclosures: rows.reduce((sum, row) => sum + row.reviewedInvestmentCount, 0),
    outcomeDisclosures: rows.reduce((sum, row) => sum + row.reviewedOutcomeCount, 0),
    status: "reviewed-sample-only" as const,
  };
}
