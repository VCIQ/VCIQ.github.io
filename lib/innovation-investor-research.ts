import roster from "@/config/innovation_global_investors.json";
import evidence from "@/config/innovation_investor_evidence.json";

export type InnovationInvestor = (typeof roster.institutions)[number];
export type InvestorEvidenceRecord = (typeof evidence.records)[number];
export const globalInnovationInvestors = roster.institutions;
export const investorResearchScope = roster.scope;
export const investorMonitoringPolicy = roster.monitoringPolicy;
export const investorEvidenceScope = evidence.scopeNote;
export const investorResearchReviewedAt = evidence.reviewedAt;
export const investorEvidenceRecords = evidence.records;

/** Public statements are evidence about the stated claim, never inferred cash flows. */
export function validateInvestorResearch(
  institutions: readonly InnovationInvestor[] = globalInnovationInvestors,
  records: readonly InvestorEvidenceRecord[] = investorEvidenceRecords,
): string[] {
  const errors: string[] = [];
  const ids = new Set<string>();
  const publicHttps = (value: string) => {
    try {
      const url = new URL(value);
      return url.protocol === "https:" && !url.username && !url.password &&
        !/^(localhost|127\.|10\.|192\.168\.|0\.|\[)/.test(url.hostname) &&
        !/\.(local|internal)$/.test(url.hostname);
    } catch { return false; }
  };
  for (const institution of institutions) {
    if (ids.has(institution.id)) errors.push(`duplicate institution: ${institution.id}`);
    ids.add(institution.id);
    if (!publicHttps(institution.officialUrl) || !publicHttps(institution.evidenceUrl)) {
      errors.push(`invalid official source: ${institution.id}`);
    }
  }
  const recordIds = new Set<string>();
  const disclosedDealKeys = new Set<string>();
  for (const item of records) {
    if (recordIds.has(item.id)) errors.push(`duplicate evidence: ${item.id}`);
    recordIds.add(item.id);
    if (!ids.has(item.institutionId)) errors.push(`unknown institution: ${item.id}`);
    if (!publicHttps(item.source.url) || !item.source.locator) errors.push(`missing evidence: ${item.id}`);
    const datePattern = item.datePrecision === "day" ? /^\d{4}-\d{2}-\d{2}$/ :
      item.datePrecision === "month" ? /^\d{4}-\d{2}$/ : /^\d{4}$/;
    if (!datePattern.test(item.date)) errors.push(`invalid date precision: ${item.id}`);
    if (item.kind === "investment" && (!item.project || !item.participation)) {
      errors.push(`investment lacks project or role: ${item.id}`);
    }
    if (item.kind === "investment" && item.project) {
      const dealKey = JSON.stringify([item.institutionId, item.project, item.round, item.date]);
      if (disclosedDealKeys.has(dealKey)) errors.push(`duplicate investment disclosure: ${item.id}`);
      disclosedDealKeys.add(dealKey);
    }
    if (item.kind === "outcome" && !item.resultStatus) errors.push(`outcome missing result: ${item.id}`);
    if (item.kind !== "outcome" && item.resultStatus !== null) {
      errors.push(`non-outcome has result status: ${item.id}`);
    }
    for (const speaker of item.speakers) {
      if (!speaker.name.trim() || !speaker.roleAtPublication.trim() || !speaker.projectResponsibility.trim() || speaker.attribution !== "paraphrase") {
        errors.push(`unverified speaker attribution: ${item.id}`);
      }
    }
    if (item.kind !== "investment" && (item.roundAmount || item.investorAmount || item.participation)) {
      errors.push(`non-investment carries transaction amounts: ${item.id}`);
    }
    // The starter evidence set has no realized cash-flow schedules. Fail closed
    // rather than allowing a listing/acquisition to be promoted into a return.
    if (item.realizedProceeds !== null) errors.push(`unsupported realized proceeds: ${item.id}`);
    for (const amount of [item.roundAmount, item.investorAmount]) {
      if (amount && (!(amount.value > 0) || !Number.isFinite(amount.value) || !/^[A-Z]{3}$/.test(amount.currency))) {
        errors.push(`invalid amount: ${item.id}`);
      }
    }
  }
  return errors;
}

export function investorEvidenceSummary(records: readonly InvestorEvidenceRecord[] = investorEvidenceRecords) {
  const covered = new Set(records.map((item) => item.institutionId));
  const investments = new Set(records.filter((item) => item.kind === "investment").map(
    (item) => `${item.institutionId}:${item.project}:${item.round ?? item.id}:${item.date}`,
  ));
  return {
    registeredInstitutions: globalInnovationInvestors.length,
    evidenceCoveredInstitutions: covered.size,
    reviewedRecords: records.length,
    disclosedInvestmentEvents: investments.size,
    outcomeMilestones: records.filter((item) => item.kind === "outcome").length,
    returnStatus: "unknown" as const,
    coverageLabel: `${covered.size}/${globalInnovationInvestors.length}家有核验样例；不表示完整组合覆盖`,
  };
}

/** Chronology of published evidence, not an inferred history of all investments. */
export interface InvestorProjectEvidenceTimeline {
  institutionId: string;
  project: string;
  entries: InvestorEvidenceRecord[];
  earliestEvidenceDate: string;
  latestEvidenceDate: string;
  sourceCount: number;
  investmentDisclosures: number;
  viewpointDisclosures: number;
  portfolioRelationships: number;
  outcomeMilestones: number;
  returnStatus: "unknown";
}

export function investorProjectEvidenceTimelines(
  records: readonly InvestorEvidenceRecord[] = investorEvidenceRecords,
): InvestorProjectEvidenceTimeline[] {
  const projects = new Map<string, {institutionId: string; project: string; entries: InvestorEvidenceRecord[]}>();
  for (const row of records) {
    if (!row.project) continue; // A fund launch is not a company investment.
    const key = JSON.stringify([row.institutionId, row.project]);
    const group = projects.get(key);
    if (group) group.entries.push(row);
    else projects.set(key, {institutionId: row.institutionId, project: row.project, entries: [row]});
  }
  const order: Record<string, number> = {investment: 0, "portfolio-relationship": 1, viewpoint: 2, outcome: 3};
  return [...projects.values()].map((group) => {
    const entries = [...group.entries].sort((a, b) =>
      a.date.localeCompare(b.date) || (order[a.kind] ?? 9) - (order[b.kind] ?? 9) || a.id.localeCompare(b.id),
    );
    return {
      institutionId: group.institutionId,
      project: group.project,
      entries,
      earliestEvidenceDate: entries[0].date,
      latestEvidenceDate: entries[entries.length - 1].date,
      sourceCount: new Set(entries.map((row) => row.source.url)).size,
      investmentDisclosures: new Set(entries.filter((row) => row.kind === "investment").map(
        (row) => JSON.stringify([row.institutionId, row.project, row.round, row.date]),
      )).size,
      viewpointDisclosures: entries.filter((row) => row.kind === "viewpoint").length,
      portfolioRelationships: entries.filter((row) => row.kind === "portfolio-relationship").length,
      outcomeMilestones: entries.filter((row) => row.kind === "outcome").length,
      returnStatus: "unknown" as const,
    };
  }).sort((a, b) =>
    b.latestEvidenceDate.localeCompare(a.latestEvidenceDate) ||
    a.institutionId.localeCompare(b.institutionId) || a.project.localeCompare(b.project),
  );
}

export const investorEvidenceKindLabels: Record<string, string> = {
  investment: "投资披露",
  viewpoint: "观点转述",
  outcome: "结果节点",
  "portfolio-relationship": "组合关系",
  "fund-announcement": "基金/主题公告",
};

export function formatDisclosedMoney(value: {value: number; currency: string} | null) {
  return value ? `${value.currency} ${new Intl.NumberFormat("en-US").format(value.value)}` : "未披露 / 未核验";
}

/** Counterfactual: a project outcome never reveals what a particular fund received. */
export function investorReturnLabel(_record: InvestorEvidenceRecord): string {
  void _record;
  return "实际回报未知：缺少完整投入、持股变化、退出分配与现金流日期";
}
