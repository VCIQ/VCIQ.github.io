export type PersonEventLike = {
  title: string;
  date?: string;
  sortAt?: string;
  href?: string;
  source?: string;
  context?: string;
};

export type PersonEventCluster<T extends PersonEventLike> = {
  id: string;
  representative: T;
  items: T[];
  sourceCount: number;
  sortAt: string;
};

type ClusterOptions<T extends PersonEventLike> = {
  referenceDate?: string;
  scopeKey?: (item: T) => string;
  representativeScore?: (item: T) => number;
};

const TITLE_NOISE = [
  "专访",
  "采访",
  "演讲",
  "对话",
  "视频",
  "全文",
  "独家",
  "最新",
  "重磅",
  "回应",
  "表示",
  "观点",
  "实录",
];

const LATIN_STOP_WORDS = new Set([
  "the",
  "and",
  "for",
  "with",
  "from",
  "into",
  "about",
  "interview",
  "keynote",
  "fireside",
  "chat",
  "talk",
  "video",
  "full",
]);

function compact(value: string) {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/https?:\/\/\S+/gu, " ")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "")
    .trim();
}

function stripScope(title: string, scope: string) {
  if (!scope.trim()) return title;
  const compactScope = compact(scope);
  if (!compactScope) return title;
  return title.replaceAll(scope, " ").replaceAll(compactScope, " ");
}

function titleTokens(value: string) {
  let normalized = value.normalize("NFKC").toLocaleLowerCase("zh-CN");
  for (const noise of TITLE_NOISE) normalized = normalized.replaceAll(noise, " ");

  const tokens = new Set<string>();
  for (const match of normalized.matchAll(/[\u3400-\u9fff]+|[a-z0-9]+/gu)) {
    const token = match[0];
    if (/^[a-z0-9]+$/u.test(token)) {
      if (token.length >= 3 && !LATIN_STOP_WORDS.has(token)) tokens.add(token);
      continue;
    }
    if (token.length <= 3) {
      if (token.length >= 2) tokens.add(token);
      continue;
    }
    for (let index = 0; index < token.length - 1; index += 1) {
      tokens.add(token.slice(index, index + 2));
    }
  }
  return tokens;
}

export function personEventTitleSimilarity(leftTitle: string, rightTitle: string) {
  const left = compact(leftTitle);
  const right = compact(rightTitle);
  if (!left || !right) return 0;
  if (left === right) return 1;

  const shorter = left.length <= right.length ? left : right;
  const longer = left.length > right.length ? left : right;
  if (shorter.length >= 8 && longer.includes(shorter)) {
    const ratio = shorter.length / longer.length;
    if (ratio >= 0.65) return 0.9;
  }

  const leftTokens = titleTokens(leftTitle);
  const rightTokens = titleTokens(rightTitle);
  if (!leftTokens.size || !rightTokens.size) return 0;

  let intersection = 0;
  for (const token of leftTokens) {
    if (rightTokens.has(token)) intersection += 1;
  }
  const union = leftTokens.size + rightTokens.size - intersection;
  const jaccard = union ? intersection / union : 0;
  const containment = intersection / Math.min(leftTokens.size, rightTokens.size);
  return Math.max(jaccard, containment * 0.82);
}

function referenceTime(referenceDate?: string) {
  const parsed = referenceDate ? Date.parse(referenceDate) : Number.NaN;
  return Number.isFinite(parsed) ? parsed : 0;
}

export function personEventDateMs(value: string | undefined, referenceDate?: string) {
  if (!value?.trim()) return 0;
  const raw = value.trim();
  const direct = Date.parse(raw);
  if (Number.isFinite(direct)) return direct;

  const chineseDate = raw.match(/(20\d{2})\s*[年\/-]\s*(\d{1,2})\s*[月\/-]\s*(\d{1,2})\s*日?/u);
  if (chineseDate) {
    const [, year, month, day] = chineseDate;
    return Date.UTC(Number(year), Number(month) - 1, Number(day));
  }

  const reference = referenceTime(referenceDate);
  if (!reference) return 0;
  const relative = raw.match(/(\d+)\s*(小时|天|周|个月|月|年)前/u);
  if (!relative) return 0;
  const amount = Number(relative[1]);
  const unit = relative[2];
  const day = 24 * 60 * 60 * 1000;
  const multipliers: Record<string, number> = {
    小时: 60 * 60 * 1000,
    天: day,
    周: 7 * day,
    个月: 30 * day,
    月: 30 * day,
    年: 365 * day,
  };
  return reference - amount * (multipliers[unit] ?? 0);
}

function itemDateMs<T extends PersonEventLike>(item: T, referenceDate?: string) {
  const sortAt = item.sortAt ? Date.parse(item.sortAt) : Number.NaN;
  if (Number.isFinite(sortAt)) return sortAt;
  return personEventDateMs(item.date, referenceDate);
}

function sameEvent<T extends PersonEventLike>(
  left: T,
  right: T,
  scope: string,
  referenceDate?: string,
) {
  const leftTitle = stripScope(left.title, scope);
  const rightTitle = stripScope(right.title, scope);
  const similarity = personEventTitleSimilarity(leftTitle, rightTitle);
  if (similarity < 0.5) return false;

  const leftMs = itemDateMs(left, referenceDate);
  const rightMs = itemDateMs(right, referenceDate);
  if (!leftMs || !rightMs) return similarity >= 0.9;

  const daysApart = Math.abs(leftMs - rightMs) / (24 * 60 * 60 * 1000);
  if (similarity >= 0.9) return daysApart <= 45;
  if (similarity >= 0.72) return daysApart <= 21;
  return daysApart <= 10;
}

function hashString(value: string) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

function uniqueSourceCount<T extends PersonEventLike>(items: T[]) {
  const hrefs = new Set(items.map((item) => item.href?.trim().toLocaleLowerCase("en-US")).filter(Boolean));
  if (hrefs.size) return hrefs.size;
  const sources = new Set(items.map((item) => item.source?.trim().toLocaleLowerCase("zh-CN")).filter(Boolean));
  return Math.max(1, sources.size);
}

export function clusterPersonEventItems<T extends PersonEventLike>(
  values: T[],
  options: ClusterOptions<T> = {},
): PersonEventCluster<T>[] {
  const referenceDate = options.referenceDate;
  const sorted = values
    .filter((item) => item.title?.trim() && (item.href?.trim() || item.source?.trim()))
    .map((item, index) => ({ item, index, timestamp: itemDateMs(item, referenceDate) }))
    .sort((left, right) => right.timestamp - left.timestamp || left.index - right.index);

  const groups: { scope: string; items: T[] }[] = [];
  for (const entry of sorted) {
    const scope = (options.scopeKey?.(entry.item) ?? entry.item.context ?? "").trim();
    const existing = groups.find((group) => {
      if (group.scope !== scope) return false;
      return group.items.some((candidate) => sameEvent(entry.item, candidate, scope, referenceDate));
    });
    if (existing) existing.items.push(entry.item);
    else groups.push({ scope, items: [entry.item] });
  }

  return groups
    .map((group) => {
      const representative = [...group.items].sort((left, right) => {
        const scoreDelta =
          (options.representativeScore?.(right) ?? 0) -
          (options.representativeScore?.(left) ?? 0);
        return scoreDelta || itemDateMs(right, referenceDate) - itemDateMs(left, referenceDate);
      })[0];
      const newestMs = Math.max(...group.items.map((item) => itemDateMs(item, referenceDate)), 0);
      const newestSortAt = newestMs ? new Date(newestMs).toISOString() : representative.sortAt ?? "";
      const idSeed = `${group.scope}|${compact(representative.title)}|${newestSortAt.slice(0, 10)}`;
      return {
        id: `person-event-${hashString(idSeed)}`,
        representative,
        items: group.items,
        sourceCount: uniqueSourceCount(group.items),
        sortAt: newestSortAt,
      } satisfies PersonEventCluster<T>;
    })
    .sort((left, right) => right.sortAt.localeCompare(left.sortAt));
}
