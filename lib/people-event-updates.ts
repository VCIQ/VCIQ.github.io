import type {
  ChannelUpdateDirectory,
  ChannelUpdateItem,
  ChannelUpdateSource,
} from "@/lib/channel-updates";
import { clusterPersonEventItems } from "@/lib/person-event-clustering";

function uniqueStrings(values: string[]) {
  const seen = new Set<string>();
  return values.filter((value) => {
    const key = value.trim().toLocaleLowerCase("zh-CN");
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function uniqueSources(values: ChannelUpdateSource[]) {
  const seen = new Set<string>();
  return values.filter((value) => {
    const key = value.href.trim().toLocaleLowerCase("en-US");
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function itemSources(item: ChannelUpdateItem): ChannelUpdateSource[] {
  return uniqueSources([
    { name: item.source, href: item.href, title: item.title },
    ...(item.sources ?? []),
  ]);
}

function representativeScore(item: ChannelUpdateItem) {
  const labelScore: Record<string, number> = {
    官方资料: 90,
    论文: 85,
    著作: 82,
    股东信: 80,
    演讲: 72,
    公开对话: 68,
    采访: 64,
    人物资料: 55,
  };
  const gradeScore = item.sourceGrade === "A" ? 40 : item.sourceGrade === "B" ? 30 : item.sourceGrade === "C" ? 20 : item.sourceGrade === "D" ? 10 : 0;
  return (labelScore[item.label] ?? 50) + gradeScore;
}

export function aggregatePeopleUpdateDirectory(
  directory: ChannelUpdateDirectory,
): ChannelUpdateDirectory {
  const clusters = clusterPersonEventItems(directory.items, {
    referenceDate: directory.generatedAt,
    scopeKey: (item) => item.context || item.id,
    representativeScore,
  });

  const items = clusters.map((cluster) => {
    const representative = cluster.representative;
    const newest = [...cluster.items].sort((left, right) => right.sortAt.localeCompare(left.sortAt))[0] ?? representative;
    const sources = uniqueSources(cluster.items.flatMap(itemSources));
    const firstSeenAt = cluster.items
      .map((item) => item.firstSeenAt)
      .filter((value): value is string => Boolean(value))
      .sort()[0];
    const lastVerifiedAt = cluster.items
      .map((item) => item.lastVerifiedAt)
      .filter((value): value is string => Boolean(value))
      .sort()
      .at(-1);

    return {
      ...representative,
      id: cluster.id,
      eventClusterId: cluster.id,
      date: newest.date,
      dateOriginal: newest.dateOriginal,
      datePrecision: newest.datePrecision,
      sortAt: newest.sortAt,
      keywords: uniqueStrings(cluster.items.flatMap((item) => item.keywords)),
      classifications: uniqueStrings(cluster.items.flatMap((item) => item.classifications ?? [])),
      sources,
      sourceCount: Math.max(cluster.sourceCount, sources.length || 1),
      firstSeenAt,
      firstSeenEstimated: firstSeenAt
        ? cluster.items.find((item) => item.firstSeenAt === firstSeenAt)?.firstSeenEstimated
        : representative.firstSeenEstimated,
      lastVerifiedAt,
      lastVerifiedEstimated: lastVerifiedAt
        ? cluster.items.find((item) => item.lastVerifiedAt === lastVerifiedAt)?.lastVerifiedEstimated
        : representative.lastVerifiedEstimated,
    } satisfies ChannelUpdateItem;
  });

  return {
    ...directory,
    title: "人物事件与材料更新目录",
    description:
      "按人物聚合演讲、采访、公开对话、论文与著作等材料；同一人物的同一事件只展示一条主记录，并保留多个可追溯公开信源。",
    items,
  };
}
