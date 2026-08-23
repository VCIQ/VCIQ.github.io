import rawResearchAgentReport from "@/public/data/research_agent_daily.json";

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
    byDataset: Record<string, number>;
    byChangeType?: Record<string, number>;
    externalCandidates?: number;
    qualityRejected?: number;
    maintenanceExcluded?: number;
    aggregatedEvents?: number;
    highestImportance: number;
  };
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

export const researchAgentReport = rawResearchAgentReport as ResearchAgentReport;
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
