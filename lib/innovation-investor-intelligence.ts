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
  summary: string;
  sourceUrl: string;
  sourceKind: string;
  sourceTitle: string;
  sourcePublisher: string;
  sourcePublishedAt: string | null;
  sourceLocator: string;
  participation: string | null;
  round: string | null;
  roundAmount: {value: number; currency: string} | null;
  investorAmount: {value: number; currency: string} | null;
  outcomeStatus: string | null;
  viewpoints: {name: string; roleAtPublication: string; projectResponsibility: string}[];
  followUp: string;
};

export type ActivityEvidence = {
  status: "observed" | "unknown";
  evidenceIds: string[];
  explanation: string;
};

/** Independent evidence dimensions, not a regulatory status or a maturity score. */
export function investorActivityEvidence(events: readonly InvestorIntelligenceEvent[]) {
  const investments = events.filter(event => event.kind === "investment");
  return {
    registration: {status: "unknown", evidenceIds: [], explanation: "尚未逐项核验法律主体、适用登记制度及当前管理人档案；研究目录收录不代表取得管理人资格。"},
    fundraising: {status: "unknown", evidenceIds: [], explanation: "基金或主题公告不证明完成募集、产品备案或实缴；这些事项需要各自的基金级证据。"},
    investment: {status: investments.length ? "observed" : "unknown", evidenceIds: investments.map(event => event.evidenceId), explanation: investments.length ? "存在已审查投资披露；仅说明公开披露样本，不代表完整投资组合或出资现金流已审计。" : "暂无已审查投资披露；不代表现实中没有投资。"},
    exit: {status: "unknown", evidenceIds: [], explanation: "项目上市或被收购不证明该机构已出售持股、收到回款或完成基金分配。"},
  } satisfies Record<string, ActivityEvidence>;
}

export { investorEvidenceDateLabel } from "./investor-evidence-format";

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
  fundAnnouncementCount: number;
  activityEvidence: ReturnType<typeof investorActivityEvidence>;
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
    summary: record.summary,
    sourceUrl: record.source.url,
    sourceKind: record.source.kind,
    sourceTitle: record.source.title,
    sourcePublisher: record.source.publisher,
    sourcePublishedAt: record.source.publishedAt,
    sourceLocator: record.source.locator,
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
  const seen = new Set<string>();
  for (const record of records) {
    if (seen.has(record.id)) throw new Error(`Task 5: duplicate evidence ID: ${record.id}`);
    seen.add(record.id);
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
      fundAnnouncementCount: events.filter(event => event.kind === "fund-announcement").length,
      activityEvidence: investorActivityEvidence(events),
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

