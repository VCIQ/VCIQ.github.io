import rawResearchAgentReport from "@/public/data/research_agent_daily.json";

export type ResearchPublicationTier =
  | "verified_change"
  | "candidate"
  | "external_clue"
  | "rejected";

export type ResearchReviewStatus =
  | "automated_unreviewed"
  | "pending"
  | "reviewed"
  | "approved"
  | "rejected"
  | string;

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
  entityMatchStatus?: "matched" | "mismatched" | "not_applicable";
  publicationTier?: ResearchPublicationTier;
  reviewStatus?: ResearchReviewStatus;
  publisherName?: string;
  originalPublisherName?: string;
  platformName?: string;
  sourceType?: string;
  sourceRole?: string;
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
  publicationTier?: ResearchPublicationTier;
  reviewStatus?: ResearchReviewStatus;
  eventClusterId?: string;
  eventId?: string;
  eventIds?: string[];
  eventLifecycles?: Record<string, string>;
  lifecycle?: "first_seen" | "reconfirmed" | "updated" | "correction" | "mixed";
  firstSeenAt?: string;
  lastSeenAt?: string;
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
  sourceClassificationWarnings?: {
    evidenceId: string;
    reason: string;
    sourceName: string;
    sourceType: string;
    sourceRole: string;
    evidenceGrade: string;
  }[];
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
  reviewStatus?: ResearchReviewStatus;
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
    verifiedChangeTotal?: number;
    candidateTotal?: number;
    auxiliaryLeadTotal?: number;
    rejectedTotal?: number;
    newEvents?: number;
    reconfirmations?: number;
    updates?: number;
    corrections?: number;
    possibleConflicts?: number;
    duplicatesSuppressed?: number;
  };
  researchScope?: Record<string, ResearchScopeEntry>;
  qualityDiagnostics?: ResearchQualityDiagnostics;
  sourceClassificationWarnings?: ResearchQualityDiagnostics["sourceClassificationWarnings"];
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
  eventLedger?: {
    schemaVersion: number;
    generatedAt: string;
    retentionDays: number;
    events: Record<string, Record<string, unknown>>;
    pendingPublications?: Record<string, unknown>[];
  };
  eventDiagnostics?: {
    newEvents?: number;
    reconfirmations?: number;
    updates?: number;
    corrections?: number;
    possibleConflicts?: number;
    duplicatesSuppressed?: number;
    observedEvents?: number;
    pendingPublications?: number;
    reviewQueue?: Record<string, unknown>[];
  };
  history: {
    metricsVersion?: number;
    date: string;
    generatedAt: string;
    runStatus: string;
    changeCount: number;
    executiveSummary: string;
    eventIds?: string[];
    eventStates?: { eventId: string; lifecycle: string }[];
    legacyChangeCount?: number;
    verifiedChangeTotal?: number;
    candidateTotal?: number;
    auxiliaryLeadTotal?: number;
    rejectedTotal?: number;
    eventSummary?: {
      newEvents?: number;
      reconfirmations?: number;
      updates?: number;
      corrections?: number;
      possibleConflicts?: number;
      duplicatesSuppressed?: number;
    };
  }[];
};

// Generated JSON contains heterogeneous record-key maps. TypeScript infers a
// closed union with optional `undefined` keys across those objects, even though
// the published JSON contract is a runtime string map. Treat the generated
// artifact as an external data boundary before applying the stable report type.
const typedRawResearchAgentReport = rawResearchAgentReport as unknown as ResearchAgentReport;

// Preserve the published JSON contract: `changeSummary.byDataset` is this-run
// change volume, while tracked-object coverage lives only in `researchScope`.
export const researchAgentReport: ResearchAgentReport = typedRawResearchAgentReport;

export const researchAgentEvidenceById = new Map(
  researchAgentReport.evidence.map((item) => [item.id, item]),
);

export const researchAgentDatasetLabels: Record<string, string> = {
  intelligenceEvent: "高价值情报事件",
  ventureCompany: "核心公司",
  person: "核心人物",
  institution: "辅助证据·投资机构",
  marketCompany: "辅助证据·公开市场",
  institutionEvent: "辅助证据·资本事件",
  listedDisclosure: "辅助证据·监管披露",
};
