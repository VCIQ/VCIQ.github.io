import type {
  ResearchAgentChange,
  ResearchAgentEvidence,
  ResearchAgentReport,
} from "@/lib/research-agent-data";

const DEGRADED_STATUSES = new Set([
  "offline-fallback",
  "missing-key-fallback",
  "api-fallback",
]);

const CORE_DATASETS = new Set(["person", "ventureCompany"]);
const COMPANY_DATASETS = new Set(["marketCompany", "ventureCompany"]);

type TieredChange = ResearchAgentChange & { publicationTier?: string };
type ReviewedReport = ResearchAgentReport & { reviewStatus?: string };
type TieredChangeSummary = ResearchAgentReport["changeSummary"] & {
  byPublicationTier?: Record<string, number>;
  verifiedChangeTotal?: number;
  candidateTotal?: number;
  auxiliaryLeadTotal?: number;
  rejectedTotal?: number;
};

const PUBLICATION_TIERS = new Set([
  "verified_change",
  "candidate",
  "external_clue",
  "rejected",
]);

function uniqueChanges(items: ResearchAgentChange[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = item.id || `${item.dataset}:${item.entityId}:${item.action}:${item.summary}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function uniqueResearchEvidence(items: ResearchAgentEvidence[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (!item.id || seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

function referencedEvidenceIds(report: ResearchAgentReport, changes: ResearchAgentChange[]) {
  const ids = new Set<string>();
  const add = (evidenceIds: string[]) => evidenceIds.forEach((id) => ids.add(id));

  changes.forEach((item) => add(item.evidenceIds));
  report.analysis.keyDevelopments.forEach((item) => add(item.evidenceIds));
  report.analysis.thesisUpdates.forEach((item) => add(item.evidenceIds));
  report.analysis.watchlist.forEach((item) => add(item.evidenceIds));
  report.analysis.risks.forEach((item) => add(item.evidenceIds));
  return ids;
}

function hasEvidenceQualityContract(report: ResearchAgentReport) {
  return Boolean(report.changeSummary.byChangeType) && report.changes.every(
    (change) =>
      typeof change.changeType === "string" &&
      typeof change.eligibleForKeyDevelopment === "boolean",
  );
}

function isExternalCandidate(change: ResearchAgentChange, hasQualityContract: boolean) {
  const tier = (change as TieredChange).publicationTier;
  if (tier && PUBLICATION_TIERS.has(tier)) return tier !== "rejected";
  if (tier && ["hidden", "maintenance"].includes(tier)) return false;
  if (hasQualityContract) {
    return change.changeType === "external_event" && change.eligibleForKeyDevelopment === true;
  }

  // Reports produced before the quality contract did not carry either field.
  // Keep their non-degraded public output readable, while still excluding a
  // maintenance classification when an intermediate schema happened to include it.
  return !change.changeType || change.changeType === "external_event";
}

function hasFormalTier(change: ResearchAgentChange) {
  const tier = (change as TieredChange).publicationTier;
  return !tier || tier === "verified_change";
}

function scopeCoverage(report: ResearchAgentReport, key: string) {
  const scope = report.researchScope?.[key];
  if (!scope) return "待同步";
  if (scope.status === "active" && typeof scope.count === "number") return scope.count;
  return "待接入";
}

export function buildResearchAgentViewModel(report: ResearchAgentReport) {
  const isDegraded = DEGRADED_STATUSES.has(report.runStatus);
  const qualityContract = hasEvidenceQualityContract(report);
  const suppressLegacyDegradedOutput = isDegraded && !qualityContract;
  const qualityEligibleChanges = suppressLegacyDegradedOutput
    ? []
    : uniqueChanges(report.changes.filter((change) => isExternalCandidate(change, qualityContract)));
  const eligibleChanges = qualityEligibleChanges.filter((change) => {
    const tier = (change as TieredChange).publicationTier;
    if (!tier) return true;
    if (tier === "verified_change") return CORE_DATASETS.has(change.dataset);
    if (tier === "external_clue") return change.dataset === "intelligenceEvent";
    if (tier === "candidate") return change.dataset !== "intelligenceEvent";
    return false;
  });

  const publicationTierSummary = (report.changeSummary as TieredChangeSummary).byPublicationTier;
  const tierTotals = report.changeSummary as TieredChangeSummary;
  const hasPublicationTierContract = Boolean(publicationTierSummary) || [
    tierTotals.verifiedChangeTotal,
    tierTotals.candidateTotal,
    tierTotals.auxiliaryLeadTotal,
    tierTotals.rejectedTotal,
  ].some((value) => typeof value === "number") || (
    report.changes.length > 0 && report.changes.every((change) => {
      const tier = (change as TieredChange).publicationTier;
      return Boolean(tier && PUBLICATION_TIERS.has(tier));
    })
  );
  const formalChanges = eligibleChanges.filter((change) => {
    const tier = (change as TieredChange).publicationTier;
    return CORE_DATASETS.has(change.dataset) && (
      tier ? tier === "verified_change" : hasFormalTier(change)
    );
  });
  const companyCandidateChanges = eligibleChanges.filter(
    (change) => {
      const tier = (change as TieredChange).publicationTier;
      return COMPANY_DATASETS.has(change.dataset) && (tier ? tier === "candidate" : (
        change.dataset === "marketCompany" ||
        (change.dataset === "ventureCompany" && !hasFormalTier(change))
      ));
    },
  );
  const candidateChanges = eligibleChanges.filter((change) => {
    const tier = (change as TieredChange).publicationTier;
    if (tier) return tier === "candidate";
    return !formalChanges.includes(change) && change.dataset !== "intelligenceEvent";
  });
  const externalClueChanges = eligibleChanges.filter((change) => {
    const tier = (change as TieredChange).publicationTier;
    return change.dataset === "intelligenceEvent" && (
      tier ? tier === "external_clue" : true
    );
  });
  const otherCandidateChanges = candidateChanges.filter(
    (change) => !companyCandidateChanges.includes(change),
  );

  const topDevelopments = suppressLegacyDegradedOutput
    ? []
    : report.analysis.keyDevelopments.slice(0, 3);
  const thesisUpdates = suppressLegacyDegradedOutput ? [] : report.analysis.thesisUpdates;
  const watchlist = suppressLegacyDegradedOutput ? [] : report.analysis.watchlist;
  const risks = suppressLegacyDegradedOutput ? [] : report.analysis.risks;
  const referencedIds = referencedEvidenceIds(report, eligibleChanges);
  const uniqueEvidence = suppressLegacyDegradedOutput
    ? []
    : uniqueResearchEvidence(report.evidence).filter(
        (item) => referencedIds.size === 0 || referencedIds.has(item.id),
      );
  const reviewStatus = (report as ReviewedReport).reviewStatus;

  return {
    isDegraded,
    hasEvidenceQualityContract: qualityContract,
    hasPublicationTierContract,
    suppressLegacyDegradedOutput,
    visibleChanges: eligibleChanges,
    visibleEvidence: uniqueEvidence,
    topDevelopments,
    thesisUpdates,
    watchlist,
    risks,
    hiddenDevelopmentCount: suppressLegacyDegradedOutput
      ? 0
      : Math.max(0, report.analysis.keyDevelopments.length - topDevelopments.length),
    formalChanges,
    companyCandidateChanges,
    candidateChanges,
    externalClueChanges,
    otherCandidateChanges,
    coverage: {
      technology: scopeCoverage(report, "technology"),
      track: scopeCoverage(report, "track"),
      person: scopeCoverage(report, "person"),
      ventureCompany: scopeCoverage(report, "ventureCompany"),
    },
    reviewStatus,
    metrics: {
      formalChangeCount: formalChanges.length,
      companyCandidateCount: companyCandidateChanges.length,
      candidateCount: candidateChanges.length,
      externalClueCount: externalClueChanges.length,
      pipelineHealthyCount: report.pipelineHealth?.healthyJobs ?? null,
      pipelineJobCount: report.pipelineHealth?.jobCount ?? null,
    },
  };
}

export type ResearchAgentViewModel = ReturnType<typeof buildResearchAgentViewModel>;
