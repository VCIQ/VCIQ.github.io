import identityRegistry from "@/config/innovation_investor_project_identities.json";
import {
  globalInnovationInvestors,
  investorEvidenceRecords,
  type InvestorEvidenceRecord,
} from "@/lib/innovation-investor-research";

/**
 * Project identities are curated exact mappings. A shared company ID represents
 * the same project, never an inferred shared financing round or co-lead.
 */
export type ProjectIdentity = {
  id: string;
  name: string;
  observedNames: readonly string[];
  identityEvidenceUrls: readonly string[];
  identityNote?: string;
};

export interface ProjectPersonAttribution {
  name: string;
  type: "article-attributed-viewpoint" | "portfolio-listed-partner";
  roleOrRelationship: string;
  responsibilityCaveat: string;
  originalUrl: string;
  independentlyConfirmedDealOwner: false;
}

export interface ProjectFundingDisclosure {
  evidenceId: string;
  announcedDate: string;
  datePrecision: string;
  round: string | null;
  participation: string | null;
  roundAmount: {value: number; currency: string} | null;
  investorAmount: {value: number; currency: string} | null;
  sourceUrl: string;
}

export interface InvestorProjectRelation {
  institutionId: string;
  institutionName: string;
  evidenceCount: number;
  originalSourceUrls: string[];
  investmentDisclosures: ProjectFundingDisclosure[];
  portfolioRelationshipCount: number;
  viewpointRecordCount: number;
  personAttributions: ProjectPersonAttribution[];
  outcomes: {evidenceId: string; status: string; sourceKind: string; date: string}[];
  earliestEvidenceDate: string;
  latestEvidenceDate: string;
  confirmedTransactionOwner: false;
  realizedFundReturn: "unknown";
}

export interface CanonicalInvestorProject {
  projectId: string;
  name: string;
  identityEvidenceUrls: string[];
  identityNote: string | null;
  institutions: InvestorProjectRelation[];
  distinctSourceCount: number;
  earliestEvidenceDate: string;
  latestEvidenceDate: string;
  reportedInvestmentEvents: number;
  coInvestmentRound: "not-assessed";
}

export interface InvestorProjectCoverage {
  institutionId: string;
  name: string;
  reviewedProjectCount: number;
  reviewedSourceCount: number;
  evidenceRecordCount: number;
  disclosedInvestmentEvents: number;
  attributedViewpointPeople: number;
  portfolioListedPartners: number;
  observedOutcomeRecords: number;
  gapToThreeProjects: number;
  state: "no-project-evidence" | "partial-project-samples" | "sample-count-target-met";
}

const projectIdentities: readonly ProjectIdentity[] = identityRegistry.projects;
const keyOf = (name: string) => name.trim().toLocaleLowerCase("en-US");

const sourceUrlOkay = (raw: string) => {
  try {
    const u = new URL(raw);
    return u.protocol === "https:" && !u.username && !u.password && (!u.port || u.port === "443") &&
      !!u.hostname && !/^(localhost|127\\.|10\\.|192\\.168\\.|0\\.)/.test(u.hostname) &&
      !u.hostname.endsWith(".local") && !u.hostname.endsWith(".internal");
  } catch {
    return false;
  }
};

/** Fail closed instead of matching by fuzzy project names, headlines, or investors. */
export function validateInvestorProjectIdentities(
  identities: readonly ProjectIdentity[] = projectIdentities,
  records: readonly InvestorEvidenceRecord[] = investorEvidenceRecords,
): string[] {
  const errors: string[] = [];
  const ids = new Set<string>();
  const observedNames = new Map<string, string>();
  const represented = new Set<string>();

  for (const item of identities) {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(item.id) || ids.has(item.id)) {
      errors.push(`invalid or duplicated canonical project ID: ${item.id}`);
    }
    ids.add(item.id);
    if (!item.name.trim() || !item.observedNames.length || !item.identityEvidenceUrls.length) {
      errors.push(`incomplete canonical project: ${item.id}`);
    }
    for (const name of item.observedNames) {
      const normalized = keyOf(name);
      if (!normalized || observedNames.has(normalized)) errors.push(`ambiguous project alias: ${name}`);
      observedNames.set(normalized, item.id);
    }
    if (!item.observedNames.some((name) => keyOf(name) === keyOf(item.name))) {
      errors.push(`display name missing from reviewed aliases: ${item.id}`);
    }
    const actualUrls = new Set(records.filter((record) =>
      record.project && item.observedNames.some((name) => keyOf(name) === keyOf(record.project!)),
    ).map((record) => record.source.url));
    for (const url of item.identityEvidenceUrls) {
      if (!sourceUrlOkay(url) || !actualUrls.has(url)) {
        errors.push(`identity source not traceable to project's reviewed evidence: ${item.id}`);
      }
    }
  }
  for (const record of records) {
    if (!record.project) continue;
    const id = observedNames.get(keyOf(record.project));
    if (!id) errors.push(`unmapped evidence project (manual identity review required): ${record.id}`);
    else represented.add(id);
  }
  for (const id of ids) if (!represented.has(id)) errors.push(`unreferenced canonical project: ${id}`);
  return errors;
}

function minMaxDates(rows: readonly InvestorEvidenceRecord[]) {
  const dates = rows.map((row) => row.date).sort((a, b) => a.localeCompare(b));
  return {earliest: dates[0] ?? "", latest: dates[dates.length - 1] ?? ""};
}

function projectPeople(rows: readonly InvestorEvidenceRecord[]): ProjectPersonAttribution[] {
  const result: ProjectPersonAttribution[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    for (const speaker of row.speakers) {
      const id = JSON.stringify([speaker.name, "article-attributed-viewpoint", row.source.url]);
      if (seen.has(id)) continue;
      seen.add(id);
      result.push({
        name: speaker.name,
        type: "article-attributed-viewpoint",
        roleOrRelationship: speaker.roleAtPublication,
        responsibilityCaveat: speaker.projectResponsibility,
        originalUrl: row.source.url,
        independentlyConfirmedDealOwner: false,
      });
    }
    if (row.linkedPerson) {
      const id = JSON.stringify([row.linkedPerson.name, "portfolio-listed-partner", row.source.url]);
      if (seen.has(id)) continue;
      seen.add(id);
      result.push({
        name: row.linkedPerson.name,
        type: "portfolio-listed-partner",
        roleOrRelationship: row.linkedPerson.relationship,
        responsibilityCaveat: "仅证明组合项目关联人，不能据此认定某轮投资签约/领投责任",
        originalUrl: row.source.url,
        independentlyConfirmedDealOwner: false,
      });
    }
  }
  return result;
}

/** Project-first read model; keeps each institution's source and role separate. */
export function buildCanonicalInvestorProjectGraph(
  identities: readonly ProjectIdentity[] = projectIdentities,
  records: readonly InvestorEvidenceRecord[] = investorEvidenceRecords,
): CanonicalInvestorProject[] {
  const errors = validateInvestorProjectIdentities(identities, records);
  if (errors.length) throw new Error(`Canonical project review required: ${errors.join("; ")}`);
  const byName = new Map(identities.flatMap((project) =>
    project.observedNames.map((name): [string, string] => [keyOf(name), project.id]),
  ));
  const firmNames = new Map(globalInnovationInvestors.map((firm) => [firm.id, firm.name]));
  return identities.map((identity) => {
    const rows = records.filter((row) => row.project && byName.get(keyOf(row.project)) === identity.id);
    const byInstitution = new Map<string, InvestorEvidenceRecord[]>();
    for (const row of rows) {
      const existing = byInstitution.get(row.institutionId) ?? [];
      existing.push(row);
      byInstitution.set(row.institutionId, existing);
    }
    const institutions = [...byInstitution].map(([institutionId, institutionRows]): InvestorProjectRelation => {
      const dates = minMaxDates(institutionRows);
      return {
        institutionId, institutionName: firmNames.get(institutionId) ?? institutionId,
        evidenceCount: institutionRows.length,
        originalSourceUrls: [...new Set(institutionRows.map((row) => row.source.url))],
        investmentDisclosures: institutionRows.filter((row) => row.kind === "investment").map((row) => ({
          evidenceId: row.id, announcedDate: row.date, datePrecision: row.datePrecision,
          round: row.round, participation: row.participation, roundAmount: row.roundAmount,
          investorAmount: row.investorAmount, sourceUrl: row.source.url,
        })),
        portfolioRelationshipCount: institutionRows.filter((row) => row.kind === "portfolio-relationship").length,
        viewpointRecordCount: institutionRows.filter((row) => row.kind === "viewpoint").length,
        personAttributions: projectPeople(institutionRows),
        outcomes: institutionRows.filter((row) => row.kind === "outcome").map((row) => ({
          evidenceId: row.id, status: row.resultStatus ?? "unknown", sourceKind: row.source.kind, date: row.date,
        })),
        earliestEvidenceDate: dates.earliest,
        latestEvidenceDate: dates.latest,
        confirmedTransactionOwner: false,
        realizedFundReturn: "unknown",
      };
    }).sort((a, b) => a.institutionName.localeCompare(b.institutionName, "zh"));
    const dates = minMaxDates(rows);
    return {
      projectId: identity.id,
      name: identity.name,
      identityEvidenceUrls: [...identity.identityEvidenceUrls],
      identityNote: identity.identityNote ?? null,
      institutions,
      distinctSourceCount: new Set(rows.map((row) => row.source.url)).size,
      earliestEvidenceDate: dates.earliest, latestEvidenceDate: dates.latest,
      reportedInvestmentEvents: institutions.reduce((n, group) => n + group.investmentDisclosures.length, 0),
      coInvestmentRound: "not-assessed" as const,
    };
  }).sort((a, b) => b.institutions.length - a.institutions.length || a.name.localeCompare(b.name, "zh"));
}

/**
 * Sample coverage, never an investor score. Zero here means no evidence in the
 * reviewed sample, not zero real-world investment activity.
 */
export function investorProjectCoverageMatrix(
  projects: readonly CanonicalInvestorProject[] = buildCanonicalInvestorProjectGraph(),
): InvestorProjectCoverage[] {
  return globalInnovationInvestors.map((firm) => {
    const relevant = projects.map((project) => project.institutions.find((part) =>
      part.institutionId === firm.id,
    )).filter((row): row is InvestorProjectRelation => !!row);
    const reviewedProjectCount = relevant.length;
    return {
      institutionId: firm.id, name: firm.name,
      reviewedProjectCount,
      reviewedSourceCount: new Set(relevant.flatMap((row) => row.originalSourceUrls)).size,
      evidenceRecordCount: relevant.reduce((n, row) => n + row.evidenceCount, 0),
      disclosedInvestmentEvents: relevant.reduce((n, row) => n + row.investmentDisclosures.length, 0),
      attributedViewpointPeople: relevant.reduce((n, row) =>
        n + row.personAttributions.filter((person) => person.type === "article-attributed-viewpoint").length, 0),
      portfolioListedPartners: relevant.reduce((n, row) =>
        n + row.personAttributions.filter((person) => person.type === "portfolio-listed-partner").length, 0),
      observedOutcomeRecords: relevant.reduce((n, row) => n + row.outcomes.length, 0),
      gapToThreeProjects: Math.max(0, 3 - reviewedProjectCount),
      state: reviewedProjectCount === 0 ? "no-project-evidence" as const :
        reviewedProjectCount < 3 ? "partial-project-samples" as const : "sample-count-target-met" as const,
    };
  });
}
