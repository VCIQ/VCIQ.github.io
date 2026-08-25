import rawResearchAgentReport from "@/public/data/research_agent_daily.json";
import rawResearchAgentSnapshot from "@/public/data/research_agent_snapshot.json";

export type ResearchAgentEvidence = {
  id: string;
  changeId: string;
  entityName: string;
  claim: string;
  sourceName: string;
  title: string;
  url: string;
  publishedAt: string;
  evidenceGrade: string;
  claimFields?: string[];
  qualityIssues?: string[];
  qualityStatus?: "passed" | "rejected";
  supportStatus?: "supports" | "insufficient";
};

export type ResearchAgentChange = {
  id: string;
  dataset: string;
  entityType: string;
  entityId: string;
  entityName: string;
  action: "added" | "updated" | "removed";
  changedFields: string[];
  summary: string;
  importance: number;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  evidenceIds: string[];
  changeType?: "external_event" | "data_maintenance" | "entity_reconciliation" | "source_refresh";
  classificationReason?: string;
  claimFields?: string[];
  claimBindings?: {
    field: string;
    before: unknown;
    after: unknown;
    evidenceIds: string[];
  }[];
  supportingEvidenceIds?: string[];
  eligibleForKeyDevelopment?: boolean;
};

export type ResearchDevelopment = {
  title: string;
  assessment: string;
  importance: number;
  confidence: "high" | "medium" | "low";
  entities: string[];
  evidenceIds: string[];
};

export type ResearchThesisUpdate = {
  entity: string;
  direction: "positive" | "negative" | "mixed" | "neutral";
  statement: string;
  evidenceIds: string[];
};

export type ResearchWatchItem = {
  item: string;
  reason: string;
  nextEvidence: string;
  evidenceIds: string[];
};

export type ResearchRisk = {
  risk: string;
  reason: string;
  evidenceIds: string[];
};

export type ResearchScopeEntry = {
  label: string;
  status: "active" | "pending-artifact" | string;
  count: number | null;
  note: string;
};

export type ResearchQualityDiagnostics = {
  candidateCount: number;
  eligibleCandidateCount: number;
  rejectedCandidateCount: number;
  rejectedByDataset: Record<string, number>;
  evidenceCount: number;
  supportingEvidenceCount: number;
  rejectedEvidenceCount: number;
  passedButUnboundEvidenceCount: number;
  rejectionReasons: Record<string, number>;
};

export type ResearchPipelineHealth = {
  overallStatus: string;
  healthyJobs: number;
  jobCount: number;
  issueJobs: {
    jobId: string;
    name: string;
    status: string;
    lastCompletedAt: string | null;
  }[];
};

export type ResearchDatasetMetric = number | string;

export type ResearchAgentReport = {
  schemaVersion: number;
  generatedAt: string;
  asOfDate: string;
  runStatus: string;
  baselineSource: string;
  model: {
    provider: string;
    name: string;
    baseUrl: string;
    reasoningEffort: string;
    used: boolean;
    usage?: Record<string, unknown>;
  };
  changeSummary: {
    totalDetected: number;
    total: number;
    byDataset: Record<string, ResearchDatasetMetric>;
    byChangeType?: Record<string, number>;
    externalCandidates?: number;
    qualityRejected?: number;
    maintenanceExcluded?: number;
    aggregatedEvents?: number;
    highestImportance: number;
  };
  researchScope?: Record<string, ResearchScopeEntry>;
  qualityDiagnostics?: ResearchQualityDiagnostics;
  pipelineHealth?: ResearchPipelineHealth;
  analysis: {
    mode?: "model-analysis" | "structured-change-only";
    isResearchJudgment?: boolean;
    executiveSummary: string;
    keyDevelopments: ResearchDevelopment[];
    thesisUpdates: ResearchThesisUpdate[];
    watchlist: ResearchWatchItem[];
    risks: ResearchRisk[];
    methodologyNote: string;
  };
  changes: ResearchAgentChange[];
  evidence: ResearchAgentEvidence[];
  methodology: {
    stages: string[];
    fallbackReason: string;
    disclaimer: string;
  };
  history: {
    date: string;
    generatedAt: string;
    runStatus: string;
    changeCount: number;
    executiveSummary: string;
  }[];
};

type ResearchAgentSnapshot = {
  datasets?: Record<string, Record<string, unknown>>;
};

const typedRawResearchAgentReport = rawResearchAgentReport as ResearchAgentReport;
const typedRawResearchAgentSnapshot = rawResearchAgentSnapshot as ResearchAgentSnapshot;

function snapshotCoverageCount(dataset: string): number | null {
  const rows = typedRawResearchAgentSnapshot.datasets?.[dataset];
  return rows && typeof rows === "object" ? Object.keys(rows).length : null;
}

function coverageMetric(
  scopeKey: string,
  fallbackKey: string = scopeKey,
): ResearchDatasetMetric {
  const scope = typedRawResearchAgentReport.researchScope?.[scopeKey];
  if (scope) {
    if (scope.status === "active" && typeof scope.count === "number") return scope.count;
    return "待接入";
  }

  // Technology and track are not yet part of the stable Research Agent snapshot.
  // Never translate a missing daily-report metric into the misleading value 0.
  if (scopeKey === "technology" || scopeKey === "track") return "待接入";

  // A report can lag behind its companion snapshot while the repository writer
  // queue is busy. Fall back to the stable snapshot so page coverage remains
  // semantically correct even before the next daily report is generated.
  const snapshotCount = snapshotCoverageCount(scopeKey);
  if (snapshotCount !== null) return snapshotCount;

  return typedRawResearchAgentReport.changeSummary.byDataset[fallbackKey] ?? 0;
}

// `page.tsx` historically reused changeSummary.byDataset for the coverage strip.
// Keep the canonical JSON semantics intact, but adapt only the exported view so
// that the four core-object cards display tracked-object coverage rather than
// this-run change counts. The page already treats `sector` as the legacy track
// key and filters it out of the auxiliary-dataset strip, so keep that key here.
export const researchAgentReport: ResearchAgentReport = {
  ...typedRawResearchAgentReport,
  changeSummary: {
    ...typedRawResearchAgentReport.changeSummary,
    byDataset: {
      ...typedRawResearchAgentReport.changeSummary.byDataset,
      technology: coverageMetric("technology"),
      sector: coverageMetric("track", "sector"),
      person: coverageMetric("person"),
      ventureCompany: coverageMetric("ventureCompany"),
    },
  },
};

export const researchAgentEvidenceById = new Map(
  researchAgentReport.evidence.map((item) => [item.id, item]),
);

export const researchAgentDatasetLabels: Record<string, string> = {
  ventureCompany: "核心公司",
  person: "核心人物",
  institution: "辅助证据·投资机构",
  marketCompany: "辅助证据·公开市场",
  institutionEvent: "辅助证据·资本事件",
  listedDisclosure: "辅助证据·监管披露",
};
