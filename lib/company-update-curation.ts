import type {
  ChannelUpdateDirectory,
  ChannelUpdateItem,
  ChannelUpdateSource,
  SourceEvidenceGrade,
} from "@/lib/channel-updates";

const ALWAYS_EVENT_LABELS = new Set([
  "融资",
  "并购",
  "IPO",
  "财报",
  "监管文件",
  "产业投资",
]);

const ACTION_SIGNAL_RE = /(?:发布|推出|上线|升级|开源|完成|获得|获批|签署|签约|宣布|融资|募资|投资|收购|并购|上市|任命|离任|合作|订单|交付|量产|扩产|突破|部署|落地|启动|暂停|裁员|处罚|诉讼|召回|报告|增长|下降)|\b(?:launch(?:ed|es|ing)?|release(?:d|s)?|introduc(?:e|ed|es|ing)|unveil(?:ed|s)?|announc(?:e|ed|es|ing)|rais(?:e|ed|es|ing)|funding|invest(?:ed|s|ment)?|acquir(?:e|ed|es|ing)|merg(?:e|ed|es|ing)|list(?:ed|ing)|ipo|appoint(?:ed|s|ment)?|resign(?:ed|s|ation)?|partner(?:ed|s|ship)?|sign(?:ed|s|ing)|secur(?:e|ed|es|ing)|order|deliver(?:ed|s|y)|deploy(?:ed|s|ment)?|expand(?:ed|s|ing)|open(?:ed|s|ing)|close(?:d|s|ing)|report(?:ed|s|ing)|grow(?:th|s|ing)|declin(?:e|ed|es|ing)|recall(?:ed|s)?|sue(?:d|s)?|lawsuit)\b/iu;

const EVERGREEN_RE = /(?:品牌规范|招聘|加入我们|联系我们|帮助中心|支持中心|隐私政策|服务条款|用户协议|开发文档|文档中心|资源中心|国家和地区|可用地区|公司介绍|关于我们|白皮书下载|产品手册|资料下载)|\b(?:brand guidelines?|careers?|jobs?|contact us|help center|support center|privacy policy|terms of service|documentation|developer docs?|resource center|availability by country|about us|company overview|download center|white ?paper|product manual)\b/iu;

const gradeRank: Record<SourceEvidenceGrade, number> = {
  A: 4,
  B: 3,
  C: 2,
  D: 1,
};

function normalizeTitle(value: string) {
  return value
    .toLocaleLowerCase("zh-CN")
    .replace(/20\d{2}[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?/gu, "")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "")
    .slice(0, 180);
}

function titleFeatures(value: string) {
  const normalized = value.normalize("NFKC").toLocaleLowerCase("zh-CN");
  const latin = new Set(
    [...normalized.matchAll(/[a-z0-9](?:[a-z0-9.+-]*[a-z0-9])?/gu)]
      .map((match) => match[0])
      .filter((token) => token.length >= 2),
  );
  const cjk = new Set<string>();
  for (const chunk of normalized.match(/[\u3400-\u9fff]{2,}/gu) ?? []) {
    for (let index = 0; index < chunk.length - 1; index += 1) {
      cjk.add(chunk.slice(index, index + 2));
    }
  }
  return { latin, cjk };
}

function intersectionSize(left: Set<string>, right: Set<string>) {
  let count = 0;
  for (const value of left) if (right.has(value)) count += 1;
  return count;
}

function titleSimilarity(left: string, right: string) {
  const leftNormalized = normalizeTitle(left);
  const rightNormalized = normalizeTitle(right);
  if (!leftNormalized || !rightNormalized) return false;
  if (leftNormalized === rightNormalized) return true;
  if (
    Math.min(leftNormalized.length, rightNormalized.length) >= 12 &&
    (leftNormalized.includes(rightNormalized) || rightNormalized.includes(leftNormalized))
  ) {
    return true;
  }

  const leftFeatures = titleFeatures(left);
  const rightFeatures = titleFeatures(right);
  const sharedLatin = intersectionSize(leftFeatures.latin, rightFeatures.latin);
  if (sharedLatin >= 3) return true;

  const sharedCjk = intersectionSize(leftFeatures.cjk, rightFeatures.cjk);
  const cjkUnion = new Set([...leftFeatures.cjk, ...rightFeatures.cjk]).size;
  return sharedCjk >= 5 && cjkUnion > 0 && sharedCjk / cjkUnion >= 0.38;
}

function companyIdentity(item: ChannelUpdateItem) {
  if (item.companySlugs?.length) return [...item.companySlugs].sort().join("|");
  return normalizeTitle(item.context.split("·")[0] ?? item.context);
}

function sameCompanyEvent(left: ChannelUpdateItem, right: ChannelUpdateItem) {
  if (left.eventClusterId && right.eventClusterId && left.eventClusterId === right.eventClusterId) return true;
  if (left.label !== right.label) return false;
  if (left.sortAt.slice(0, 10) !== right.sortAt.slice(0, 10)) return false;
  if (companyIdentity(left) !== companyIdentity(right)) return false;
  return titleSimilarity(left.title, right.title);
}

export function isActionableCompanySignal({
  title,
  summary,
  label,
  undated = false,
  sourceGrade,
  sourceLevel,
}: {
  title: string;
  summary: string;
  label: string;
  undated?: boolean;
  sourceGrade?: SourceEvidenceGrade;
  sourceLevel?: string;
}) {
  if (sourceGrade === "D" || sourceLevel === "待交叉验证" || undated) return false;
  const text = `${label} ${title} ${summary}`;
  if (EVERGREEN_RE.test(text)) return false;
  if (ALWAYS_EVENT_LABELS.has(label)) return true;
  return ACTION_SIGNAL_RE.test(`${title} ${summary}`);
}

function isActionableCompanyUpdate(item: ChannelUpdateItem) {
  return isActionableCompanySignal({
    title: item.title,
    summary: item.summary,
    label: item.label,
    undated: item.datePrecision === "undated",
    sourceGrade: item.sourceGrade,
  });
}

function sourceForItem(item: ChannelUpdateItem): ChannelUpdateSource {
  return {
    name: item.source,
    href: item.href,
    title: item.title,
  };
}

function uniqueSources(values: ChannelUpdateSource[]) {
  const result: ChannelUpdateSource[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const key = value.href.trim().toLocaleLowerCase("en-US");
    if (!key || seen.has(key)) continue;
    seen.add(key);
    result.push(value);
  }
  return result;
}

function representative(items: ChannelUpdateItem[]) {
  return [...items].sort((left, right) => {
    const gradeDelta =
      (right.sourceGrade ? gradeRank[right.sourceGrade] : 0) -
      (left.sourceGrade ? gradeRank[left.sourceGrade] : 0);
    return (
      gradeDelta ||
      right.sortAt.localeCompare(left.sortAt) ||
      right.summary.length - left.summary.length
    );
  })[0];
}

function aggregateCompanyUpdates(items: ChannelUpdateItem[]) {
  const groups: ChannelUpdateItem[][] = [];
  for (const item of items) {
    const group = groups.find((candidate) =>
      candidate.some((existing) => sameCompanyEvent(existing, item)),
    );
    if (group) group.push(item);
    else groups.push([item]);
  }

  return groups.map((group) => {
    const selected = representative(group);
    if (!selected) throw new Error("company update group has no representative");
    const newest = [...group].sort((left, right) =>
      right.sortAt.localeCompare(left.sortAt),
    )[0];
    const sources = uniqueSources(
      group.flatMap((item) => item.sources?.length ? item.sources : [sourceForItem(item)]),
    );
    return {
      ...selected,
      date: newest?.date ?? selected.date,
      dateOriginal: newest?.dateOriginal ?? selected.dateOriginal,
      datePrecision: newest?.datePrecision ?? selected.datePrecision,
      sortAt: newest?.sortAt ?? selected.sortAt,
      sources,
      sourceCount: Math.max(sources.length, ...group.map((item) => item.sourceCount ?? 1)),
      eventClusterId:
        selected.eventClusterId || (group.length > 1 ? `company:${selected.id}` : undefined),
    } satisfies ChannelUpdateItem;
  });
}

export function curateCompanyUpdateDirectory(
  directory: ChannelUpdateDirectory,
): ChannelUpdateDirectory {
  const items = aggregateCompanyUpdates(
    directory.items.filter(isActionableCompanyUpdate),
  ).sort(
    (left, right) =>
      right.sortAt.localeCompare(left.sortAt) ||
      (right.sourceGrade ? gradeRank[right.sourceGrade] : 0) -
        (left.sourceGrade ? gradeRank[left.sourceGrade] : 0),
  );

  return {
    ...directory,
    title: "重要公司事件",
    description:
      "仅保留与已收录公司直接相关的融资、产品、经营、监管和资本市场变化；常青页面、低证据记录与同事件重复报道默认折叠。",
    items,
  };
}
