import watchlistRaw from "@/config/innovation_listing_watchlist.json";
import lifecycleRaw from "@/config/innovation_listing_lifecycle.json";
import matureRaw from "@/config/innovation_capital_mature_candidates.json";
import trackingSeedsRaw from "@/config/innovation_capital_tracking_seeds.json";

type WatchProject = {
  company: string;
  broker: string;
  sector: string;
  route: string;
  pool: string;
  stage: string;
  capitalMarketPath: string;
  hkStatus?: string;
  everFiledBefore?: boolean;
  firstGuidanceDate: string;
  latestEventDate: string;
  fifteenthTags: string[];
};

type LifecycleProject = {
  company: string;
  broker: string;
  sector: string;
  route: string;
  lifecycleStatus: string;
  stage: string;
  capitalMarketPath: string;
};

type MatureCandidate = {
  name: string;
  sector: string;
  policyThemes: string[];
  financingRound: string;
  financingAmount: string;
  financingDate: string;
  institutionBackers: string[];
  brokerEvidence: string[];
  routeEvidence: string;
};

type CapitalInstitution = {
  name: string;
  linkedProjectCount: number;
  institutionTypes: string[];
  relationshipTypes: string[];
  evidenceLevels: string[];
};

type WatchlistPayload = {
  asOf: string;
  projects: WatchProject[];
};

type LifecyclePayload = {
  asOf: string;
  projects: LifecycleProject[];
};

type MaturePayload = {
  asOf: string;
  candidates: MatureCandidate[];
};

type TrackingSeedsPayload = {
  asOf: string;
  institutions: CapitalInstitution[];
};

const watchlist = watchlistRaw as unknown as WatchlistPayload;
const lifecycle = lifecycleRaw as unknown as LifecyclePayload;
const mature = matureRaw as unknown as MaturePayload;
const trackingSeeds = trackingSeedsRaw as unknown as TrackingSeedsPayload;

export type InnovationResearchPriority = "P0" | "P1" | "P2";

export type InnovationResearchTask = {
  id: string;
  rank: number;
  priority: InnovationResearchPriority;
  score: number;
  taskType: string;
  subject: string;
  question: string;
  whyNow: string[];
  nextEvidence: string;
  successCriteria: string;
  href: string;
};

export type InnovationResearchThesis = {
  id: string;
  title: string;
  status: "观察中" | "初步样本支持" | "待更多样本";
  observation: string;
  nextEvidence: string;
  caveat: string;
};

export type InnovationResearchPattern = {
  id: string;
  title: string;
  value: string;
  summary: string;
};

export type BrokerResearchSignal = {
  broker: string;
  projectCount: number;
  leadingSectors: Array<{ sector: string; count: number }>;
};

export type InnovationCapitalResearchModel = {
  asOf: string;
  stats: {
    projectCount: number;
    lifecycleCount: number;
    institutionCount: number;
    routeUnconfirmedCount: number;
    routeUnconfirmedRatio: number;
    aPlusHCount: number;
    refileCount: number;
    longGuidanceCount: number;
    veryLongGuidanceCount: number;
    medianGuidanceDays: number;
    repeatInstitutionCount: number;
    matureCandidateCount: number;
  };
  brokerSignals: BrokerResearchSignal[];
  patterns: InnovationResearchPattern[];
  theses: InnovationResearchThesis[];
  queue: InnovationResearchTask[];
};

function countBy<T>(rows: T[], valueOf: (row: T) => string) {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const value = valueOf(row);
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return counts;
}

function sortedCounts(counts: Map<string, number>) {
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name, "zh-CN"));
}

function daysBetween(start: string, end: string) {
  const left = Date.parse(start);
  const right = Date.parse(end);
  if (!Number.isFinite(left) || !Number.isFinite(right)) return null;
  return Math.max(0, Math.round((right - left) / 86_400_000));
}

function median(values: number[]) {
  if (!values.length) return 0;
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.floor(sorted.length / 2)] ?? 0;
}

function percent(numerator: number, denominator: number) {
  if (!denominator) return 0;
  return Math.round((numerator / denominator) * 1000) / 10;
}

function cappedScore(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

export function buildInnovationCapitalResearchModel(): InnovationCapitalResearchModel {
  const projects = watchlist.projects ?? [];
  const lifecycleProjects = lifecycle.projects ?? [];
  const institutions = trackingSeeds.institutions ?? [];
  const matureCandidates = mature.candidates ?? [];

  const routeUnconfirmed = projects.filter((item) => item.route === "A-share-TBD");
  const aPlusH = projects.filter((item) => item.capitalMarketPath === "A+H");
  const refiles = projects.filter((item) => item.pool === "refile" || item.everFiledBefore);
  const guidanceDays = projects
    .map((item) => daysBetween(item.firstGuidanceDate, item.latestEventDate))
    .filter((value): value is number => value !== null);
  const longGuidance = guidanceDays.filter((value) => value >= 365);
  const veryLongGuidance = guidanceDays.filter((value) => value >= 730);
  const repeatInstitutions = institutions.filter((item) => Number(item.linkedProjectCount || 0) > 1);
  const topInstitutions = [...repeatInstitutions]
    .sort((left, right) =>
      Number(right.linkedProjectCount || 0) - Number(left.linkedProjectCount || 0)
      || left.name.localeCompare(right.name, "zh-CN"),
    )
    .slice(0, 5);

  const brokers = sortedCounts(countBy(projects, (item) => item.broker));
  const brokerSignals: BrokerResearchSignal[] = brokers.map(({ name: broker, count: projectCount }) => {
    const sectors = sortedCounts(
      countBy(projects.filter((item) => item.broker === broker), (item) => item.sector),
    ).slice(0, 3);
    return {
      broker,
      projectCount,
      leadingSectors: sectors.map(({ name: sector, count }) => ({ sector, count })),
    };
  });

  const tagCounts = sortedCounts(
    countBy(
      projects.flatMap((item) => item.fifteenthTags ?? []),
      (tag) => tag,
    ),
  );
  const lifecycleStarCount = lifecycleProjects.filter((item) => item.route === "STAR").length;
  const lifecycleListedCount = lifecycleProjects.filter((item) => item.lifecycleStatus === "listed").length;
  const topInstitution = topInstitutions[0];
  const topTags = tagCounts.slice(0, 4).map((item) => `${item.name} ${item.count}`).join(" · ");

  const stats = {
    projectCount: projects.length,
    lifecycleCount: lifecycleProjects.length,
    institutionCount: institutions.length,
    routeUnconfirmedCount: routeUnconfirmed.length,
    routeUnconfirmedRatio: percent(routeUnconfirmed.length, projects.length),
    aPlusHCount: aPlusH.length,
    refileCount: refiles.length,
    longGuidanceCount: longGuidance.length,
    veryLongGuidanceCount: veryLongGuidance.length,
    medianGuidanceDays: median(guidanceDays),
    repeatInstitutionCount: repeatInstitutions.length,
    matureCandidateCount: matureCandidates.length,
  };

  const patterns: InnovationResearchPattern[] = [
    {
      id: "route-uncertainty",
      title: "板块确认明显晚于辅导启动",
      value: `${stats.routeUnconfirmedCount}/${stats.projectCount}`,
      summary: `当前 ${stats.routeUnconfirmedRatio}% 的辅导项目只确认了 A 股方向、尚未由公开一级证据锁定科创板或创业板，因此路线确认本身应作为独立研究事件。`,
    },
    {
      id: "guidance-tail",
      title: "辅导周期呈长尾",
      value: `中位 ${stats.medianGuidanceDays} 天`,
      summary: `当前样本中 ${stats.longGuidanceCount} 个项目从首次辅导到最近实质事件已超过一年，其中 ${stats.veryLongGuidanceCount} 个超过两年。单纯“辅导时间长”不应被当作成熟度结论。`,
    },
    {
      id: "cross-market",
      title: "A+H / H先行形成独立研究路径",
      value: `${stats.aPlusHCount} 个`,
      summary: `已有 ${stats.aPlusHCount} 个储备项目带有 A+H 资本市场路径标签，应将港股递表、聆讯、上市与境内辅导分开记录，再观察二者的先后关系。`,
    },
    {
      id: "route-migration",
      title: "撤回与二次申报需要保留路径记忆",
      value: `${stats.refileCount} 个`,
      summary: `当前有 ${stats.refileCount} 个二次申报或历史递表项目。研究重点不是覆盖旧路线，而是记录“原路线 → 撤回/终止 → 新路线”的完整迁移链。`,
    },
    {
      id: "lifecycle-concentration",
      title: "当前后续生命周期样本高度集中于科创板",
      value: `${lifecycleStarCount}/${stats.lifecycleCount}`,
      summary: `当前进入交易所审核、注册或上市生命周期的 ${stats.lifecycleCount} 个样本中有 ${lifecycleStarCount} 个记录为科创板，已上市 ${lifecycleListedCount} 个。该现象只描述当前筛选样本，不外推为总体概率。`,
    },
    {
      id: "capital-network",
      title: "机构资本网络呈明显长尾",
      value: `${stats.repeatInstitutionCount}/${stats.institutionCount}`,
      summary: topInstitution
        ? `当前 ${stats.institutionCount} 家相关机构中仅 ${stats.repeatInstitutionCount} 家关联两个及以上项目；关联项目数最多的当前样本机构为${topInstitution.name}（${topInstitution.linkedProjectCount} 个）。这适合用于发现“重复命中成熟项目”的机构，而不是做机构优劣排名。`
        : "当前尚无重复关联多个项目的机构样本。",
    },
    {
      id: "multi-theme",
      title: "成熟硬科技项目经常跨多个产业标签",
      value: topTags || "待积累",
      summary: `当前高频十五五标签为 ${topTags || "待积累"}。后续应比较“芯片+AI”“机器人+具身智能”等复合标签与生命周期迁移，而不是只按单一行业分类。`,
    },
  ];

  const theses: InnovationResearchThesis[] = [
    {
      id: "broker-specialization",
      title: "五大券商可能存在稳定的硬科技赛道侧重",
      status: "观察中",
      observation: brokerSignals
        .map((item) => `${item.broker}：${item.leadingSectors.slice(0, 2).map((sector) => `${sector.sector}${sector.count}`).join("、")}`)
        .join("；"),
      nextEvidence: "持续累积新增辅导、辅导验收和交易所受理样本，观察同一券商的产业集中度是否稳定。",
      caveat: "当前是人工筛选后的硬科技样本，不用于评价券商能力或推断未来项目结果。",
    },
    {
      id: "state-transition",
      title: "监管状态跳变比辅导持续时间更能描述项目成熟进程",
      status: stats.longGuidanceCount > 0 ? "初步样本支持" : "待更多样本",
      observation: `辅导时长中位数 ${stats.medianGuidanceDays} 天，但已有 ${stats.veryLongGuidanceCount} 个项目超过两年；生命周期池另有 ${stats.lifecycleCount} 个项目进入交易所审核、注册或上市。`,
      nextEvidence: "记录辅导验收→受理→问询→上市委→注册等状态跳变及其日期，比较不同项目的转换间隔。",
      caveat: "辅导时间受历史遗留、重启申报等多因素影响，不能单独解释成熟度。",
    },
    {
      id: "cross-market-path",
      title: "A+H、H先行和H→A可能构成头部硬科技的独立资本市场路径",
      status: stats.aPlusHCount > 0 ? "观察中" : "待更多样本",
      observation: `当前储备池已有 ${stats.aPlusHCount} 个 A+H 路径项目。`,
      nextEvidence: "继续区分港股递表/聆讯/上市与A股辅导/受理节点，观察路径先后顺序是否形成重复模式。",
      caveat: "A+H 标签只表示公开资本市场动作，不等于任何一端已获监管批准。",
    },
    {
      id: "route-migration",
      title: "科创板、创业板之间的路线迁移可能存在可重复的前置信号",
      status: stats.refileCount > 0 ? "观察中" : "待更多样本",
      observation: `当前保留 ${stats.refileCount} 个二次申报/历史递表样本。`,
      nextEvidence: "重点记录撤回原因公开信息、重新辅导券商、治理整改、板块重新确认与再次受理。",
      caveat: "历史申报板块不能自动继承到新一轮辅导，只有新监管/交易所原文才能确认新路线。",
    },
    {
      id: "compound-hard-tech",
      title: "复合硬科技标签可能比单一行业更能解释成熟项目聚集",
      status: "待更多样本",
      observation: `当前高频标签：${topTags || "尚待积累"}。`,
      nextEvidence: "比较复合标签项目在辅导验收、交易所受理、注册和上市阶段的样本占比变化。",
      caveat: "当前样本由硬科技主题预筛选，存在明显选择偏差。",
    },
    {
      id: "repeat-capital",
      title: "少数投资机构可能反复出现在进入五大券商IPO管线的硬科技项目中",
      status: stats.repeatInstitutionCount > 0 ? "观察中" : "待更多样本",
      observation: topInstitution
        ? `${stats.repeatInstitutionCount} 家机构关联至少两个项目；当前最高重复关联样本为${topInstitution.name}（${topInstitution.linkedProjectCount} 个）。`
        : "尚无重复项目机构样本。",
      nextEvidence: "持续核验机构→项目关系，并观察这些项目后续是否进入辅导、受理和上市生命周期。",
      caveat: "重复出现只表示当前样本中的项目关联，不构成机构投资能力评价。",
    },
    {
      id: "late-stage-to-guidance",
      title: "大额成长轮 / D-E / Pre-IPO融资可能提供辅导前的成熟项目发现信号",
      status: stats.matureCandidateCount > 0 ? "观察中" : "待更多样本",
      observation: `成熟候选池当前有 ${stats.matureCandidateCount} 个项目，均保持券商和上市路线未分配，等待一级证据。`,
      nextEvidence: "观察成熟融资后是否出现股改、辅导协议、辅导备案或券商聘任等一级公开信号。",
      caveat: "融资轮次和金额只能用于项目发现，不能推断上市路线、上市时间或成功概率。",
    },
  ];

  const queue: InnovationResearchTask[] = [
    {
      id: "lifecycle-transition",
      rank: 1,
      priority: "P0",
      score: cappedScore(92 + Math.min(8, stats.lifecycleCount)),
      taskType: "生命周期验证",
      subject: `${stats.lifecycleCount} 个后续生命周期项目`,
      question: "已进入交易所审核、注册或上市阶段的项目，是否出现新的问询、上市委、注册、发行或上市节点？",
      whyNow: [
        "状态跳变是当前最强的成熟度证据",
        `当前已迁移 ${stats.lifecycleCount} 个项目进入后续生命周期`,
      ],
      nextEvidence: "上交所/深交所/港交所、中国证监会及发行人正式公告。",
      successCriteria: "只有出现新的官方状态节点才更新；重复披露、媒体复述不产生新状态。",
      href: "/innovation-capital/#listing-lifecycle",
    },
    {
      id: "route-confirmation",
      rank: 2,
      priority: "P0",
      score: cappedScore(88 + Math.min(10, stats.routeUnconfirmedCount / 3)),
      taskType: "上市路线确认",
      subject: `${stats.routeUnconfirmedCount} 个 A股板块待确认项目`,
      question: "哪些已辅导硬科技项目首次出现明确的科创板、创业板或其他申报路线一级证据？",
      whyNow: [
        `当前 ${stats.routeUnconfirmedRatio}% 的储备项目仍为 A-share-TBD`,
        "板块确认必须晚于、且独立于产业属性判断",
      ],
      nextEvidence: "证监会辅导文件、交易所受理/申报文件、券商正式辅导公告。",
      successCriteria: "板块只有被监管、交易所、发行人或券商正式文件明确写出时才确认；否则继续保持 A-share-TBD。",
      href: "/innovation-capital/#projects",
    },
    {
      id: "cross-market-path",
      rank: 3,
      priority: "P0",
      score: cappedScore(84 + stats.aPlusHCount * 2),
      taskType: "跨市场路径",
      subject: `${stats.aPlusHCount} 个 A+H / H先行项目`,
      question: "港股递表、聆讯、上市与境内A股辅导之间是否出现新的先后关系或实质节点？",
      whyNow: [
        "A股与港股状态不能被单一“上市状态”覆盖",
        `当前已有 ${stats.aPlusHCount} 个跨市场路径样本`,
      ],
      nextEvidence: "港交所申请版本/聆讯资料、证监会境外备案、A股辅导与交易所文件。",
      successCriteria: "分别记录A股与H股节点；不得把港股进度推断为A股板块或审批结论。",
      href: "/innovation-capital/#projects",
    },
    {
      id: "route-migration",
      rank: 4,
      priority: "P1",
      score: cappedScore(76 + stats.refileCount * 4),
      taskType: "二次申报/路线迁移",
      subject: `${stats.refileCount} 个历史递表项目`,
      question: "撤回或终止后重新辅导的项目，是否出现新的板块确认、保荐机构变化或再次受理？",
      whyNow: [
        "历史申请路径必须保留，不能被新状态覆盖",
        `当前有 ${stats.refileCount} 个可观察路线迁移的样本`,
      ],
      nextEvidence: "历史交易所终止文件 + 新辅导备案/验收 + 新一轮交易所申报原文。",
      successCriteria: "形成可追溯的“旧路线→撤回/终止→重新辅导→新路线”事件链。",
      href: "/innovation-capital/#projects",
    },
    {
      id: "broker-specialization",
      rank: 5,
      priority: "P1",
      score: cappedScore(72 + Math.min(12, brokerSignals.length * 2)),
      taskType: "券商赛道规律",
      subject: "五大券商硬科技储备结构",
      question: "随着新增辅导和验收样本积累，各券商的产业集中度是否保持稳定，还是只是当前样本造成的暂时现象？",
      whyNow: brokerSignals.slice(0, 3).map((item) =>
        `${item.broker} 当前 ${item.projectCount} 个项目，主要样本集中于 ${item.leadingSectors.slice(0, 2).map((sector) => sector.sector).join("、")}`,
      ),
      nextEvidence: "新增辅导备案、辅导进展、辅导验收以及交易所受理样本。",
      successCriteria: "只报告样本结构及其变化，不做券商能力排名或未来项目结果判断。",
      href: "/innovation-capital/#projects",
    },
    {
      id: "institution-network",
      rank: 6,
      priority: "P1",
      score: cappedScore(70 + Math.min(15, stats.repeatInstitutionCount)),
      taskType: "机构资本网络",
      subject: `${stats.institutionCount} 家相关资本机构`,
      question: "哪些机构反复出现在五大券商硬科技IPO储备项目中，并且这些被投项目是否继续向辅导/受理生命周期迁移？",
      whyNow: topInstitutions.slice(0, 3).map((item) => `${item.name} 当前关联 ${item.linkedProjectCount} 个项目`),
      nextEvidence: "公司官方融资公告、投资机构官方组合、监管股东披露和可信媒体的明确投资关系。",
      successCriteria: "只有可核验的机构—项目关系进入网络；重复出现作为发现信号，不转化为机构评级。",
      href: "/innovation-capital/#opportunity-pool",
    },
    {
      id: "mature-candidate",
      rank: 7,
      priority: "P1",
      score: cappedScore(68 + stats.matureCandidateCount * 5),
      taskType: "成熟项目发现",
      subject: `${stats.matureCandidateCount} 个成熟候选项目`,
      question: "大额成长轮或D/E/Pre-IPO等成熟期公司是否首次出现股改、辅导协议、券商聘任或辅导备案证据？",
      whyNow: matureCandidates.slice(0, 3).map((item) =>
        `${item.name}：${item.financingRound} · ${item.financingAmount}`,
      ),
      nextEvidence: "公司/投资机构官方披露、证监局辅导备案与目标券商正式公告。",
      successCriteria: "成熟融资只触发研究；在一级证据出现前 broker 与 route 必须保持 unassigned。",
      href: "/innovation-capital/#opportunity-pool",
    },
    {
      id: "guidance-tail",
      rank: 8,
      priority: "P2",
      score: cappedScore(58 + Math.min(18, stats.veryLongGuidanceCount)),
      taskType: "长期辅导异常检测",
      subject: `${stats.veryLongGuidanceCount} 个辅导超过两年的项目`,
      question: "长期辅导项目是否出现恢复推进、验收、路线调整、保荐变化，或长期无实质进展？",
      whyNow: [
        `当前辅导时长中位数 ${stats.medianGuidanceDays} 天`,
        `${stats.longGuidanceCount} 个超过一年，${stats.veryLongGuidanceCount} 个超过两年`,
      ],
      nextEvidence: "最新一期辅导进展、验收材料、保荐机构公告与交易所申报状态。",
      successCriteria: "只把新的监管/券商状态变化视为事件；时间流逝本身不是“进展”。",
      href: "/innovation-capital/#projects",
    },
  ];

  return {
    asOf: [watchlist.asOf, lifecycle.asOf, mature.asOf, trackingSeeds.asOf].filter(Boolean).sort().at(-1) ?? "",
    stats,
    brokerSignals,
    patterns,
    theses,
    queue,
  };
}
