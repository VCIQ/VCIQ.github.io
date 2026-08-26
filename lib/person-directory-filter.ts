export type PersonDirectoryFilterRecord = {
  text: string;
  sectors: string[];
  status: string;
  recentChange: boolean;
};

export type PersonDirectoryFilters = {
  query: string;
  sector: string;
  status: string;
  change: "all" | "recent" | "quiet";
};

export function normalizePersonDirectoryText(value: string) {
  return value.trim().replace(/\s+/g, " ").toLocaleLowerCase("zh-CN");
}

export function isPersonDirectoryChangeRecent(
  date: string | undefined,
  asOf: string,
  windowDays = 90,
) {
  if (!date) return false;
  const reference = Date.parse(asOf);
  const changedAt = Date.parse(date);
  if (!Number.isFinite(reference) || !Number.isFinite(changedAt)) return false;
  const age = reference - changedAt;
  return age >= 0 && age <= windowDays * 86_400_000;
}

export function matchesPersonDirectoryRecord(
  record: PersonDirectoryFilterRecord,
  filters: PersonDirectoryFilters,
) {
  const needle = normalizePersonDirectoryText(filters.query);
  if (needle && !normalizePersonDirectoryText(record.text).includes(needle)) return false;
  if (filters.sector !== "all" && !record.sectors.includes(filters.sector)) return false;
  if (filters.status !== "all" && record.status !== filters.status) return false;
  if (filters.change === "recent" && !record.recentChange) return false;
  if (filters.change === "quiet" && record.recentChange) return false;
  return true;
}
