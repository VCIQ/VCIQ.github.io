import lifecycleJson from "@/config/innovation_listing_lifecycle.json";
import matureJson from "@/config/innovation_capital_mature_candidates.json";
import seedsJson from "@/config/innovation_capital_tracking_seeds.json";
import watchlistJson from "@/config/innovation_listing_watchlist.json";

type AnyRecord = Record<string, unknown>;

export type InnovationResearchTaskType =
  | "lifecycle_validation"
  | "cross_market_path"
  | "route_migration"
  | "broker_pattern"
  | "capital_network"
  | "mature_discovery"
  | "evidence_maintenance";

export type InnovationResearchTask = {
  id: string;
  rank: number;
  priority: "P0" | "P1" | "P2";
  taskType: InnovationResearchTaskType;
  title: string;
  target: string;
  question: string;
  whyNow: string[];
  successCriteria: string;
  sourceRoute: string;
  score: number;
};

export type InnovationResearchHypothesis = {
  id: string;
  title: string;
  status: "observed" | "watch";
  evidence: string;
  nextCheck: string;
};

export type InnovationCapitalResearchModel = {
  asOf: string;
  projectCount: number;
  lifecycleCount: number;
  institutionCount: number;
  matureCandidateCount: number;
  unknownRouteCount: number;
  aPlusHCount: number;
  refileCount: number;
  hypotheses: InnovationResearchHypothesis[];
  tasks: InnovationResearchTask[];
  methodology: string;
};

function rows(value: unknown): AnyRecord[] {
  return Array.isArray(value) ? value.filter((item): item is AnyRecord => Boolean(item) && typeof item === "object") : [];
}

function text(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function list(value: unknown) {
  return Array.isArray(value) ? value.map(text).filter(Boolean) : [];
}

function numberValue(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function countBy(items: AnyRecord[], key: string) {
  const counts = new Map<string, number>();
  for (const item of items) {
    const value = text(item[key]) || "未分类";
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return [...counts.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], "zh-CN"));
}

function topBrokerSector(projects: AnyRecord[]) {
  const counts = new Map<string, { broker: string; sector: string; count: number }>();
  for (const project of projects) {
    const broker = text(project.broker);
    const sector = text(project.sector);
    if (!broker || !sector) continue;
    const key = `${broker}\u0000${sector}`;
    const row = counts.get(key) ?? { broker, sector, count: 0 };
    row.count += 1;
    counts.set(key, row);
  }
  return [...counts.values()].sort((left, right) => right.count - left.count)[0];
}

function researchTask(
  id: string,
  priority: InnovationResearchTask["priority"],
  taskType: InnovationResearchTaskType,
  title: string,
  target: string,
  question: string,
  whyNow: string[],
  successCriteria: string,
  sourceRoute: string,
  score: number,
): InnovationResearchTask {
  return { id, rank: 0, priority, taskType, title, target, question, whyNow, successCriteria, sourceRoute, score };
}

export function buildInnovationCapitalResearchModel(): InnovationCapitalResearchModel {
  const watchlist = watchlistJson as AnyRecord;
  const lifecycle = lifecycleJson as AnyRecord;
  const mature = matureJson as AnyRecord;
  const seeds = seedsJson as AnyRecord;

  const projects = rows(watchlist.projects);
  const lifecycleProjects = rows(lifecycle.projects);
  const matureCandidates = rows(mature.candidates);
  const institutions = rows(seeds.institutions);

  const unknownRoute = projects.filter((item) => text(item.route) === "A-share-TBD");
  const aPlusH = projects.filter((item) => text(item.capitalMarketPath) === "A+H");
  const refiles = projects.filter((item) => Boolean(item.everFiledBefore) || text(item.pool) === "refile");
  const accepted = projects.filter((item) => text(item.stage) === "辅导验收");
  const topInstitution = [...institutions].sort(
    (left, right) => numberValue(right.linkedProjectCount) - numberValue(left.linkedProjectCount),
  )[0];
  const brokerSector = topBrokerSector(projects);
  const lifecycleListed = lifecycleProjects.filter((item) => text(item.lifecycleStatus) === "listed").length;
  const lifecycleStar = lifecycleProjects.filter((item) => text(item.route) === "STAR").length;

  const tasks: InnovationResearchTask[] = [];

  for (const project of accepted.slice(0, 3)) {
    const company = text(project.company);
    tasks.push(researchTask(
      `lifecycle-${text(project.id) || company}`,
      "P0",
      "lifecycle_validation",
      "辅导验收后的下一监管节点",
      company,
      `${company} 已处于辅导验收状态，是否出现交易所受理、板块确认或新的监管文件？`,
      ["辅导验收是进入申报前后的关键状态跃迁", text(project.broker) ? `辅导券商：${text(project.broker)}` : ""].filter(Boolean),
      "仅在证监会、交易所或券商一级公开材料出现新节点时关闭任务。",
      "/innovation-capital/#projects",
      98,
    ));
  }

  for (const project of aPlusH.slice(0, 3)) {
    const company = text(project.company);
    tasks.push(researchTask(
      `cross-market-${text(project.id) || company}`,
      "P0",
      "cross_market_path",
      "A+H / H→A 路径变化",
      company,
      `${company} 的港股与A股路径是否出现新的递表、聆讯、辅导、受理或发行节点？`,
      [text(project.hkStatus) ? `当前港股状态：${text(project.hkStatus)}` : "已标记跨市场路径", text(project.route) === "A-share-TBD" ? "A股板块尚未公开确认" : `A股路线：${text(project.route)}`],
      "分别记录A股与港股状态；板块未公开确认时不得推断。",
      "/innovation-capital/#projects",
      94,
    ));
  }

  for (const project of refiles.slice(0, 3)) {
    const company = text(project.company);
    tasks.push(researchTask(
      `route-${text(project.id) || company}`,
      "P1",
      "route_migration",
      "二次申报与路线迁移",
      company,
      `${company} 的历史申报、撤回与当前辅导路线之间是否出现新的实质迁移信号？`,
      [text(project.priorFilingSummary) || "存在历史申报记录", text(project.route) ? `当前路线：${text(project.route)}` : ""].filter(Boolean),
      "形成可追溯 route_history，仅用监管/交易所/券商原文确认路线。",
      "/innovation-capital/#projects",
      88,
    ));
  }

  if (brokerSector) {
    tasks.push(researchTask(
      "broker-specialization",
      "P1",
      "broker_pattern",
      "五大券商硬科技赛道集中度",
      brokerSector.broker,
      `新增项目是否继续强化“${brokerSector.broker}—${brokerSector.sector}”的样本集中现象，还是出现结构性扩散？`,
      [`当前该组合样本数：${brokerSector.count}`, "只描述样本分布，不将集中度解释为券商能力排名"],
      "新增样本后更新券商×赛道矩阵，并区分观察池、核心池与生命周期池。",
      "/innovation-capital/",
      82,
    ));
  }

  if (topInstitution) {
    const name = text(topInstitution.name);
    const linked = numberValue(topInstitution.linkedProjectCount);
    tasks.push(researchTask(
      "capital-network-repeat",
      "P1",
      "capital_network",
      "机构资本重复命中",
      name,
      `${name} 是否继续出现在进入五大券商IPO辅导或后续审核阶段的硬科技项目中？`,
      [`当前关联已跟踪项目：${linked} 个`, "机构关系必须保留证据层级，不把候选关系自动晋级为确认关系"],
      "新关联必须有公司、投资机构、监管或可信媒体证据，并记录关系类型与证据等级。",
      "/innovation-capital/#opportunities",
      80,
    ));
  }

  for (const candidate of matureCandidates.slice(0, 2)) {
    const name = text(candidate.name);
    tasks.push(researchTask(
      `mature-${text(candidate.id) || name}`,
      "P1",
      "mature_discovery",
      "成熟硬科技候选转化",
      name,
      `${name} 在大额成长轮融资后，是否出现股改、券商聘任、辅导备案或上市路径一级证据？`,
      [text(candidate.financingRound) ? `融资阶段：${text(candidate.financingRound)}` : "", text(candidate.financingAmount) ? `融资金额：${text(candidate.financingAmount)}` : ""].filter(Boolean),
      "只有出现券商/监管一级证据后才标记辅导券商或上市板块。",
      "/innovation-capital/#opportunities",
      78,
    ));
  }

  if (unknownRoute.length > 0) {
    tasks.push(researchTask(
      "route-evidence-maintenance",
      "P2",
      "evidence_maintenance",
      "未定A股板块证据补齐",
      `${unknownRoute.length} 个 A-share-TBD 项目`,
      "哪些观察池项目已经出现能够公开确认科创板或创业板路线的一手材料？",
      ["保持“未知”优于猜测", "优先核对辅导报告、交易所文件和公司正式公告"],
      "没有一级证据时保持 A-share-TBD，不根据行业属性推断板块。",
      "/innovation-capital/#projects",
      64,
    ));
  }

  tasks.sort((left, right) => right.score - left.score || left.title.localeCompare(right.title, "zh-CN"));
  tasks.forEach((task, index) => { task.rank = index + 1; });

  const hypotheses: InnovationResearchHypothesis[] = [
    {
      id: "broker-sector-specialization",
      title: "五大券商的硬科技项目储备可能存在稳定赛道集中度",
      status: "watch",
      evidence: brokerSector
        ? `当前最高频券商×赛道组合为 ${brokerSector.broker} × ${brokerSector.sector}（${brokerSector.count} 个样本）。`
        : "当前样本不足。",
      nextCheck: "随新增辅导项目更新矩阵，观察集中度是否跨期稳定。",
    },
    {
      id: "state-jump-over-duration",
      title: "状态跳变比辅导时长更适合作为项目成熟度信号",
      status: "watch",
      evidence: `当前 ${projects.length} 个储备项目中，辅导验收 ${accepted.length} 个；生命周期池另有 ${lifecycleProjects.length} 个项目。`,
      nextCheck: "记录辅导验收→受理→问询→注册的实际转化时间，而不是仅使用辅导持续天数。",
    },
    {
      id: "cross-market",
      title: "A+H / H→A 正形成独立的硬科技资本市场路径",
      status: "observed",
      evidence: `当前储备池标记 A+H 项目 ${aPlusH.length} 个。`,
      nextCheck: "分别维护A股与港股状态，统计先H后A、并行推进及路线切换样本。",
    },
    {
      id: "route-migration",
      title: "撤回后的二次申报与板块迁移值得单独建模",
      status: refiles.length > 0 ? "observed" : "watch",
      evidence: `当前二次申报/历史递表样本 ${refiles.length} 个。`,
      nextCheck: "维护 route_history，并识别撤回前后券商、板块和审核节点变化。",
    },
    {
      id: "hard-tech-lifecycle",
      title: "当前进入后续生命周期的样本呈科创板集中现象",
      status: "watch",
      evidence: `生命周期池 ${lifecycleProjects.length} 个项目，其中科创板 ${lifecycleStar} 个、已上市 ${lifecycleListed} 个。`,
      nextCheck: "这是当前样本现象，不外推总体概率；随创业板/港股样本增加继续验证。",
    },
    {
      id: "capital-repeat",
      title: "少数机构可能反复出现在成熟硬科技IPO管线中",
      status: "watch",
      evidence: topInstitution
        ? `当前关联项目最多的机构为 ${text(topInstitution.name)}（${numberValue(topInstitution.linkedProjectCount)} 个）。`
        : "当前尚无机构网络样本。",
      nextCheck: "按确认关系、候选关系和证据等级分别统计，避免把同名基金或品牌误合并。",
    },
    {
      id: "late-stage-to-guidance",
      title: "大额成长轮融资→股改/辅导可能构成成熟项目发现链",
      status: matureCandidates.length > 0 ? "observed" : "watch",
      evidence: `当前成熟候选池 ${matureCandidates.length} 个，均未因融资信息被自动推断上市板块。`,
      nextCheck: "持续寻找券商聘任、辅导备案和公司治理变化等一级证据。",
    },
  ];

  return {
    asOf: text(watchlist.asOf) || text(lifecycle.asOf) || text(mature.asOf),
    projectCount: projects.length,
    lifecycleCount: lifecycleProjects.length,
    institutionCount: institutions.length,
    matureCandidateCount: matureCandidates.length,
    unknownRouteCount: unknownRoute.length,
    aPlusHCount: aPlusH.length,
    refileCount: refiles.length,
    hypotheses,
    tasks,
    methodology:
      "Research lane 优先研究生命周期跳变、跨市场路径、路线迁移、券商×赛道结构、机构资本重复命中与成熟候选转化；Maintenance 只补板块、别名、证据时效等基础资料。所有结论均描述当前样本，不输出上市概率、券商排名或投资评级。",
  };
}
