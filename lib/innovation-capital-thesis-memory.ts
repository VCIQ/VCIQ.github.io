import type {
  InnovationCapitalResearchModel,
  InnovationResearchEvidenceMetrics,
  InnovationResearchHypothesis,
} from "@/lib/innovation-capital-research";

export type InnovationCapitalThesisTransition =
  | "initiated"
  | "reaffirmed"
  | "revised"
  | "direction_changed"
  | "returned";

export type InnovationCapitalThesisMetricDelta = {
  supportDelta: number;
  contrastDelta: number;
  universeDelta: number;
  evidenceCoverageDeltaPct: number;
  supportShareDeltaPct: number;
};

export type InnovationCapitalThesisObservation = {
  id: string;
  hypothesisId: string;
  title: string;
  status: InnovationResearchHypothesis["status"];
  evidence: string;
  nextCheck: string;
  metrics?: InnovationResearchEvidenceMetrics;
  metricDelta?: InnovationCapitalThesisMetricDelta;
  firstSeenAt: string;
  lastSeenAt: string;
  observationCount: number;
  lastTransition: InnovationCapitalThesisTransition;
  supersedesId?: string;
  returnedToId?: string;
};

export type InnovationCapitalThesisMemory = {
  schemaVersion: 1;
  generatedAt: string;
  asOf: string;
  currentObservationIds: string[];
  observationCount: number;
  observations: InnovationCapitalThesisObservation[];
};

const MAX_OBSERVATIONS = 180;

function text(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function baseFingerprint(
  value: Pick<InnovationResearchHypothesis, "title" | "status" | "evidence" | "nextCheck">,
) {
  return JSON.stringify([value.title, value.status, value.evidence, value.nextCheck]);
}

function metricFingerprint(value: InnovationResearchEvidenceMetrics | undefined) {
  if (!value) return "";
  return JSON.stringify([
    value.sampleUnit,
    value.universeCount,
    value.supportCount,
    value.contrastCount,
    value.neutralCount,
    value.evidenceCoveredCount,
    value.evidenceCoveragePct,
    value.supportSharePct,
  ]);
}

function fingerprint(
  value: Pick<InnovationResearchHypothesis, "title" | "status" | "evidence" | "nextCheck"> & {
    metrics?: InnovationResearchEvidenceMetrics;
  },
) {
  return JSON.stringify([baseFingerprint(value), metricFingerprint(value.metrics)]);
}

function zeroMetricDelta(): InnovationCapitalThesisMetricDelta {
  return {
    supportDelta: 0,
    contrastDelta: 0,
    universeDelta: 0,
    evidenceCoverageDeltaPct: 0,
    supportShareDeltaPct: 0,
  };
}

function metricDelta(
  current: InnovationResearchEvidenceMetrics,
  previous?: InnovationResearchEvidenceMetrics,
): InnovationCapitalThesisMetricDelta {
  if (!previous) return zeroMetricDelta();
  return {
    supportDelta: current.supportCount - previous.supportCount,
    contrastDelta: current.contrastCount - previous.contrastCount,
    universeDelta: current.universeCount - previous.universeCount,
    evidenceCoverageDeltaPct:
      Math.round((current.evidenceCoveragePct - previous.evidenceCoveragePct) * 10) / 10,
    supportShareDeltaPct:
      Math.round((current.supportSharePct - previous.supportSharePct) * 10) / 10,
  };
}

function normalizePrevious(value: unknown): InnovationCapitalThesisMemory {
  if (!value || typeof value !== "object") {
    return {
      schemaVersion: 1,
      generatedAt: "",
      asOf: "",
      currentObservationIds: [],
      observationCount: 0,
      observations: [],
    };
  }
  const row = value as Partial<InnovationCapitalThesisMemory>;
  const observations = Array.isArray(row.observations)
    ? row.observations.filter((item): item is InnovationCapitalThesisObservation =>
        Boolean(item)
        && typeof item === "object"
        && Boolean(text((item as InnovationCapitalThesisObservation).id))
        && Boolean(text((item as InnovationCapitalThesisObservation).hypothesisId)),
      )
    : [];
  const retained = observations.slice(-MAX_OBSERVATIONS);
  const ids = new Set(retained.map((item) => item.id));
  return {
    schemaVersion: 1,
    generatedAt: text(row.generatedAt),
    asOf: text(row.asOf),
    currentObservationIds: Array.isArray(row.currentObservationIds)
      ? row.currentObservationIds.map(text).filter((id) => ids.has(id))
      : [],
    observationCount: retained.length,
    observations: retained.map((item) => ({ ...item })),
  };
}

function nextObservationId(
  hypothesisId: string,
  observations: InnovationCapitalThesisObservation[],
) {
  const revision = observations.filter((item) => item.hypothesisId === hypothesisId).length + 1;
  return `innovation-thesis:${hypothesisId}:r${revision}`;
}

export function currentInnovationCapitalThesisObservations(
  memory: InnovationCapitalThesisMemory,
) {
  const byId = new Map(memory.observations.map((item) => [item.id, item]));
  return memory.currentObservationIds
    .map((id) => byId.get(id))
    .filter((item): item is InnovationCapitalThesisObservation => Boolean(item));
}

export function buildInnovationCapitalThesisMemory(
  previousValue: unknown,
  model: InnovationCapitalResearchModel,
  generatedAt: string,
): InnovationCapitalThesisMemory {
  const previous = normalizePrevious(previousValue);
  const observations = previous.observations.map((item) => ({ ...item }));
  const byId = new Map(observations.map((item) => [item.id, item]));
  const currentByHypothesis = new Map<string, InnovationCapitalThesisObservation>();

  for (const id of previous.currentObservationIds) {
    const observation = byId.get(id);
    if (observation) currentByHypothesis.set(observation.hypothesisId, observation);
  }

  if (currentByHypothesis.size === 0 && observations.length > 0) {
    for (const observation of observations) {
      const prior = currentByHypothesis.get(observation.hypothesisId);
      if (!prior || observation.lastSeenAt >= prior.lastSeenAt) {
        currentByHypothesis.set(observation.hypothesisId, observation);
      }
    }
  }

  const nextCurrentIds: string[] = [];
  let changed = false;

  for (const hypothesis of model.hypotheses) {
    const prior = currentByHypothesis.get(hypothesis.id);
    const currentFingerprint = fingerprint(hypothesis);
    const currentBaseFingerprint = baseFingerprint(hypothesis);
    const priorFingerprint = prior
      ? fingerprint({
          title: prior.title,
          status: prior.status,
          evidence: prior.evidence,
          nextCheck: prior.nextCheck,
          metrics: prior.metrics,
        })
      : "";
    const priorBaseFingerprint = prior
      ? baseFingerprint({
          title: prior.title,
          status: prior.status,
          evidence: prior.evidence,
          nextCheck: prior.nextCheck,
        })
      : "";

    // Schema migration: backfill quantitative metrics onto an otherwise
    // identical current observation without manufacturing a new thesis revision.
    if (prior && !prior.metrics && priorBaseFingerprint === currentBaseFingerprint) {
      prior.metrics = { ...hypothesis.metrics };
      prior.metricDelta = zeroMetricDelta();
      if (model.asOf && prior.lastSeenAt !== model.asOf) {
        prior.lastSeenAt = model.asOf;
        prior.observationCount = Math.max(1, Number(prior.observationCount) || 1) + 1;
        prior.lastTransition = "reaffirmed";
      }
      changed = true;
      nextCurrentIds.push(prior.id);
      continue;
    }

    if (prior && priorFingerprint === currentFingerprint) {
      const metricMetadataChanged =
        JSON.stringify(prior.metrics ?? null) !== JSON.stringify(hypothesis.metrics);
      if (metricMetadataChanged) {
        prior.metrics = { ...hypothesis.metrics };
        prior.metricDelta = prior.metricDelta ?? zeroMetricDelta();
        changed = true;
      }
      if (model.asOf && prior.lastSeenAt !== model.asOf) {
        prior.lastSeenAt = model.asOf;
        prior.observationCount = Math.max(1, Number(prior.observationCount) || 1) + 1;
        prior.lastTransition = "reaffirmed";
        prior.metricDelta = zeroMetricDelta();
        changed = true;
      }
      nextCurrentIds.push(prior.id);
      continue;
    }

    const returnedTo = [...observations]
      .reverse()
      .find((item) =>
        item.hypothesisId === hypothesis.id
        && fingerprint({
          title: item.title,
          status: item.status,
          evidence: item.evidence,
          nextCheck: item.nextCheck,
          metrics: item.metrics,
        }) === currentFingerprint,
      );

    let transition: InnovationCapitalThesisTransition = "initiated";
    if (prior) {
      if (returnedTo && returnedTo.id !== prior.id) transition = "returned";
      else if (prior.status !== hypothesis.status) transition = "direction_changed";
      else transition = "revised";
    }

    const observation: InnovationCapitalThesisObservation = {
      id: nextObservationId(hypothesis.id, observations),
      hypothesisId: hypothesis.id,
      title: hypothesis.title,
      status: hypothesis.status,
      evidence: hypothesis.evidence,
      nextCheck: hypothesis.nextCheck,
      metrics: { ...hypothesis.metrics },
      metricDelta: metricDelta(hypothesis.metrics, prior?.metrics),
      firstSeenAt: model.asOf,
      lastSeenAt: model.asOf,
      observationCount: 1,
      lastTransition: transition,
    };
    if (prior) observation.supersedesId = prior.id;
    if (transition === "returned" && returnedTo) observation.returnedToId = returnedTo.id;
    observations.push(observation);
    nextCurrentIds.push(observation.id);
    currentByHypothesis.set(hypothesis.id, observation);
    changed = true;
  }

  let retained = observations;
  if (observations.length > MAX_OBSERVATIONS) {
    const current = new Set(nextCurrentIds);
    const historical = observations.filter((item) => !current.has(item.id));
    const currentRows = observations.filter((item) => current.has(item.id));
    retained = [...historical.slice(-(MAX_OBSERVATIONS - currentRows.length)), ...currentRows];
    changed = true;
  }

  const retainedIds = new Set(retained.map((item) => item.id));
  const currentObservationIds = nextCurrentIds.filter((id) => retainedIds.has(id));
  const pointerChanged =
    JSON.stringify(previous.currentObservationIds) !== JSON.stringify(currentObservationIds);
  const materialChanged = changed || previous.asOf !== model.asOf || pointerChanged;
  const candidate: InnovationCapitalThesisMemory = {
    schemaVersion: 1,
    generatedAt: materialChanged ? generatedAt : previous.generatedAt,
    asOf: model.asOf,
    currentObservationIds,
    observationCount: retained.length,
    observations: retained,
  };

  return materialChanged ? candidate : previous;
}
