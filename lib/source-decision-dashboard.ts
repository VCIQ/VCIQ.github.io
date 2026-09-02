import type { SourceDirectoryEntry } from "@/lib/source-directory";

export type SourceFreshnessState = "fresh" | "aging" | "stale" | "unobserved";
export type SourceCoverageState = "covered" | "watch" | "gap";

export type SourceCoverageRow = {
  sector: string;
  total: number;
  primary: number;
  corroboration: number;
  discovery: number;
  healthy: number;
  gapScore: number;
  state: SourceCoverageState;
  gaps: string[];
};

export type SourceFreshness = {
  state: SourceFreshnessState;
  latestSuccessAt: string | null;
  ageHours: number | null;
};

export const SOURCE_COVERAGE_POLICY = {
  minimumPrimary: 2,
  minimumCorroboration: 2,
  minimumDiscovery: 1,
} as const;

export const SOURCE_FRESHNESS_POLICY = {
  freshHours: 12,
  staleHours: 36,
} as const;

function timestamp(value: unknown): number | null {
  if (typeof value !== "string" || !value.trim()) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function latestIso(values: unknown[]): string | null {
  const times = values
    .map(timestamp)
    .filter((value): value is number => value !== null);
  return times.length ? new Date(Math.max(...times)).toISOString() : null;
}

export function sourceHasObservedEndpoint(source: SourceDirectoryEntry): boolean {
  return source.endpoints.some(
    (endpoint) => endpoint.sourceIds.length > 0 && endpoint.status !== "unknown",
  );
}

export function sourceFreshness(
  source: SourceDirectoryEntry,
  now = new Date(),
): SourceFreshness {
  const latestSuccessAt = latestIso(source.endpoints.map((endpoint) => endpoint.lastSuccessAt));
  if (!latestSuccessAt || !sourceHasObservedEndpoint(source)) {
    return { state: "unobserved", latestSuccessAt: null, ageHours: null };
  }

  const latest = Date.parse(latestSuccessAt);
  const ageHours = Math.max(0, (now.getTime() - latest) / 3_600_000);
  if (ageHours < SOURCE_FRESHNESS_POLICY.freshHours) {
    return { state: "fresh", latestSuccessAt, ageHours };
  }
  if (ageHours <= SOURCE_FRESHNESS_POLICY.staleHours) {
    return { state: "aging", latestSuccessAt, ageHours };
  }
  return { state: "stale", latestSuccessAt, ageHours };
}

export function buildSourceCoverageRows(
  sources: SourceDirectoryEntry[],
): SourceCoverageRow[] {
  const bySector = new Map<string, SourceCoverageRow>();

  for (const source of sources) {
    for (const rawSector of source.sectors) {
      const sector = rawSector.normalize("NFKC").trim();
      if (!sector) continue;
      const row = bySector.get(sector) ?? {
        sector,
        total: 0,
        primary: 0,
        corroboration: 0,
        discovery: 0,
        healthy: 0,
        gapScore: 0,
        state: "covered" as SourceCoverageState,
        gaps: [],
      };
      row.total += 1;
      row[source.sourceRole] += 1;
      if (source.healthStatus === "ok") row.healthy += 1;
      bySector.set(sector, row);
    }
  }

  for (const row of bySector.values()) {
    const primaryGap = Math.max(0, SOURCE_COVERAGE_POLICY.minimumPrimary - row.primary);
    const corroborationGap = Math.max(
      0,
      SOURCE_COVERAGE_POLICY.minimumCorroboration - row.corroboration,
    );
    const discoveryGap = Math.max(0, SOURCE_COVERAGE_POLICY.minimumDiscovery - row.discovery);
    row.gapScore = primaryGap + corroborationGap + discoveryGap;
    row.gaps = [
      primaryGap ? `Primary 缺 ${primaryGap}` : "",
      corroborationGap ? `Corroboration 缺 ${corroborationGap}` : "",
      discoveryGap ? `Discovery 缺 ${discoveryGap}` : "",
    ].filter(Boolean);
    row.state = row.gapScore === 0
      ? "covered"
      : row.primary === 0 || row.gapScore >= 3
        ? "gap"
        : "watch";
  }

  const stateRank: Record<SourceCoverageState, number> = { gap: 0, watch: 1, covered: 2 };
  return [...bySector.values()].sort(
    (left, right) => stateRank[left.state] - stateRank[right.state]
      || right.gapScore - left.gapScore
      || right.total - left.total
      || left.sector.localeCompare(right.sector, "zh-CN"),
  );
}

export function sourceNeedsAction(source: SourceDirectoryEntry, now = new Date()): boolean {
  const freshness = sourceFreshness(source, now).state;
  return source.healthStatus === "error"
    || source.healthStatus === "partial"
    || freshness === "stale"
    || freshness === "unobserved"
    || source.promotion?.state === "blocked";
}

export function sourceReadinessDistance(source: SourceDirectoryEntry): number {
  if (source.promotion?.state === "core") return 0;
  if (source.promotion?.state === "review_pending") return 1;
  if (source.promotion?.state === "evidence_pending") {
    return 2 + Math.min(20, source.promotion.reasons.length);
  }
  if (source.promotion?.state === "candidate") return 50;
  if (source.promotion?.state === "blocked") return 90;
  return 60;
}

export function sourceReadinessLabel(source: SourceDirectoryEntry): string {
  const state = source.promotion?.state ?? "candidate";
  if (state === "core") return "CORE";
  if (state === "review_pending") return "CORE READY / REVIEW";
  if (state === "blocked") return "BLOCKED";
  if (state === "candidate") return "NOT ELIGIBLE";
  const reasons = source.promotion?.reasons.length ?? 0;
  return reasons ? `还差 ${reasons} 项` : "EVIDENCE PENDING";
}

export function buildSourceDecisionSummary(
  sources: SourceDirectoryEntry[],
  now = new Date(),
) {
  const coverageRows = buildSourceCoverageRows(sources);
  const freshness = sources.map((source) => sourceFreshness(source, now).state);
  return {
    fresh: freshness.filter((state) => state === "fresh").length,
    aging: freshness.filter((state) => state === "aging").length,
    stale: freshness.filter((state) => state === "stale").length,
    unobserved: freshness.filter((state) => state === "unobserved").length,
    actionRequired: sources.filter((source) => sourceNeedsAction(source, now)).length,
    coreReady: sources.filter((source) => source.promotion?.state === "review_pending").length,
    coverageGaps: coverageRows.filter((row) => row.state !== "covered").length,
    criticalCoverageGaps: coverageRows.filter((row) => row.state === "gap").length,
  };
}
