// Pure public-snapshot diagnostics. Source Entity, registry rows and runtime
// channels are different populations; never add them into a single total.
const STATUSES = new Set(["ok", "partial", "error", "empty", "disabled"]);
const record = (v) => v && typeof v === "object" && !Array.isArray(v) ? v : {};
const text = (v) => typeof v === "string" ? v.trim() : "";
const rows = (v) => Array.isArray(v) ? v : [];

export function buildSourceCollectionAudit({ health, articleSourceStatus, directory } = {}) {
  const payload = record(health);
  const hasObservations = payload.sources && typeof payload.sources === "object"
    && !Array.isArray(payload.sources);
  const all = Object.entries(record(payload.sources));
  const current = all.filter(([, row]) => record(row).missingFromCurrentRun !== true);
  const represented = new Set(rows(directory).flatMap((source) =>
    rows(record(source).endpoints).flatMap((endpoint) => rows(record(endpoint).sourceIds)),
  ).filter((id) => typeof id === "string" && id));
  const statuses = { ok: 0, partial: 0, error: 0, empty: 0, disabled: 0, unknown: 0 };
  const unmapped = [];
  let mapped = 0;
  for (const [id, raw] of current) {
    const row = record(raw);
    const status = STATUSES.has(row.lastStatus) ? row.lastStatus : "unknown";
    statuses[status]++;
    if (represented.has(id)) mapped++;
    else unmapped.push({ id, name: text(row.name) || id, status });
  }
  const acceptedWithoutPublication = rows(articleSourceStatus).filter((raw) => {
    const row = record(raw);
    return Number(row.accepted) > 0 && row.publishedCount === 0;
  }).length;
  return {
    available: Boolean(hasObservations),
    observedAt: text(payload.generatedAt) || null,
    retainedRuntimeChannels: all.length,
    currentRuntimeChannels: current.length,
    historicalRuntimeChannels: all.length - current.length,
    representedRuntimeChannels: mapped,
    unrepresentedRuntimeChannels: current.length - mapped,
    statuses,
    acceptedWithoutPublication,
    // Stable, bounded examples only. These are already-public runtime identities,
    // not private Google Alert feed URLs, credentials or user preference records.
    examples: unmapped.sort((a, b) => a.id.localeCompare(b.id)).slice(0, 12),
  };
}
