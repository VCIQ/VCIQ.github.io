import type { TrackingTrack } from "@/lib/user-tracking";

export type TrackOverlapSeverity = "error" | "warning";
export type TrackOverlapKind = "identity" | "keyword" | "company" | "person";

export type TrackOverlap = {
  value: string;
  normalized: string;
  kind: TrackOverlapKind;
  severity: TrackOverlapSeverity;
  tracks: Array<{ slug: string; name: string }>;
};

const SPLIT_PATTERN = /[\/／|｜,，;；、&＆+＋()（）\[\]【】]+/g;
const TRIM_PATTERN = /^[\s._:：\-—–]+|[\s._:：\-—–]+$/g;

function clean(value: string): string {
  return value.normalize("NFKC").replace(/\s+/g, " ").trim();
}

export function normalizeTaxonomyTerm(value: string): string {
  return clean(value)
    .toLocaleLowerCase("zh-CN")
    .replace(/[\s._:：\-—–/／|｜,，;；、&＆+＋()（）\[\]【】]+/g, "");
}

function meaningful(value: string): boolean {
  return normalizeTaxonomyTerm(value).length >= 2;
}

function unique(values: string[], limit = 80): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = clean(raw).replace(TRIM_PATTERN, "");
    const key = normalizeTaxonomyTerm(value);
    if (!value || !meaningful(value) || seen.has(key)) continue;
    result.push(value);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

/**
 * Derive stable aliases from any Chinese, English, bilingual or punctuation-rich
 * track name. No hand-maintained sector registry is required.
 */
export function trackNameAliases(name: string): string[] {
  const normalized = clean(name);
  const split = normalized
    .split(SPLIT_PATTERN)
    .map((item) => item.replace(TRIM_PATTERN, "").trim())
    .filter(Boolean);
  const compact = normalized.replace(/\s+/g, "");
  return unique([normalized, compact, ...split], 12);
}

/** Terms configured for one track before cross-track ownership is resolved. */
export function trackIdentityTerms(track: TrackingTrack): string[] {
  return unique([...trackNameAliases(track.name), ...track.keywords], 24);
}

/** Actors can expand discovery, but shared actors are handled conservatively. */
export function trackActorTerms(track: TrackingTrack): string[] {
  return unique([...track.sampleCompanies, ...track.people], 40);
}

export function trackSearchTerms(track: TrackingTrack): string[] {
  return unique([...trackIdentityTerms(track), ...trackActorTerms(track)], 64);
}

function collectOverlaps(
  tracks: TrackingTrack[],
  kind: TrackOverlapKind,
  termsForTrack: (track: TrackingTrack) => string[],
  severity: TrackOverlapSeverity,
): TrackOverlap[] {
  const owners = new Map<
    string,
    { value: string; tracks: Map<string, { slug: string; name: string }> }
  >();

  for (const track of tracks.filter((item) => item.enabled)) {
    for (const value of termsForTrack(track)) {
      const normalized = normalizeTaxonomyTerm(value);
      if (!normalized) continue;
      const record = owners.get(normalized) ?? {
        value,
        tracks: new Map<string, { slug: string; name: string }>(),
      };
      record.tracks.set(track.slug, { slug: track.slug, name: track.name });
      owners.set(normalized, record);
    }
  }

  return [...owners.entries()]
    .filter(([, record]) => record.tracks.size > 1)
    .map(([normalized, record]) => ({
      value: record.value,
      normalized,
      kind,
      severity,
      tracks: [...record.tracks.values()].sort((left, right) =>
        left.name.localeCompare(right.name, "zh-CN"),
      ),
    }));
}

/**
 * Exact identity collisions are blocking because event ownership becomes
 * ambiguous. Shared keywords, companies and people are warnings: they are
 * legitimate in adjacent sectors, but broad discovery terms must be scoped.
 */
export function detectTrackOverlaps(tracks: TrackingTrack[]): TrackOverlap[] {
  const identity = collectOverlaps(
    tracks,
    "identity",
    (track) => trackNameAliases(track.name),
    "error",
  );
  const keywords = collectOverlaps(
    tracks,
    "keyword",
    (track) => track.keywords,
    "warning",
  );
  const companies = collectOverlaps(
    tracks,
    "company",
    (track) => track.sampleCompanies,
    "warning",
  );
  const people = collectOverlaps(
    tracks,
    "person",
    (track) => track.people,
    "warning",
  );
  return [...identity, ...keywords, ...companies, ...people].sort(
    (left, right) =>
      (left.severity === right.severity
        ? 0
        : left.severity === "error"
          ? -1
          : 1) || left.value.localeCompare(right.value, "zh-CN"),
  );
}

function termCounts(
  tracks: TrackingTrack[],
  termsForTrack: (track: TrackingTrack) => string[],
): Map<string, number> {
  const counts = new Map<string, number>();
  for (const track of tracks.filter((item) => item.enabled)) {
    const seen = new Set<string>();
    for (const value of termsForTrack(track)) {
      const normalized = normalizeTaxonomyTerm(value);
      if (!normalized || seen.has(normalized)) continue;
      counts.set(normalized, (counts.get(normalized) ?? 0) + 1);
      seen.add(normalized);
    }
  }
  return counts;
}

function canonicalNameOwners(tracks: TrackingTrack[]) {
  const owners = new Map<string, Set<string>>();
  for (const track of tracks.filter((item) => item.enabled)) {
    for (const value of trackNameAliases(track.name)) {
      const key = normalizeTaxonomyTerm(value);
      if (!key) continue;
      const current = owners.get(key) ?? new Set<string>();
      current.add(track.slug);
      owners.set(key, current);
    }
  }
  return owners;
}

/**
 * Track names always own their derived aliases. A keyword can own event
 * matching only when it is unique across enabled-track keywords AND does not
 * collide with another enabled track's canonical name/derived name alias.
 *
 * This makes configured keywords strictly secondary discovery terms: they can
 * never steal identity keys such as `AI / AGI`, `机器人` or `半导体` from the
 * track whose name actually defines that key.
 */
export function uniqueIdentityTermsByTrack(
  tracks: TrackingTrack[],
): Map<string, string[]> {
  const keywordCounts = termCounts(tracks, (track) => track.keywords);
  const nameOwners = canonicalNameOwners(tracks);

  return new Map(
    tracks.map((track) => [
      track.slug,
      unique(
        [
          ...trackNameAliases(track.name),
          ...track.keywords.filter((value) => {
            const key = normalizeTaxonomyTerm(value);
            if (keywordCounts.get(key) !== 1) return false;
            const owners = nameOwners.get(key);
            return !owners || (owners.size === 1 && owners.has(track.slug));
          }),
        ],
        24,
      ),
    ]),
  );
}

export function uniqueActorTermsByTrack(
  tracks: TrackingTrack[],
): Map<string, string[]> {
  const counts = termCounts(tracks, trackActorTerms);
  return new Map(
    tracks.map((track) => [
      track.slug,
      trackActorTerms(track).filter(
        (value) => counts.get(normalizeTaxonomyTerm(value)) === 1,
      ),
    ]),
  );
}
