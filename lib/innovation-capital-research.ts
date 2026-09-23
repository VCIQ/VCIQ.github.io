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

export type InnovationResearchEvidenceMetrics = {
  sampleUnit: "project" | "institution" | "candidate";
  universeCount: number;
  supportCount: number;
  contrastCount: number;
  neutralCount: number;
  evidenceCoveredCount: number;
  evidenceCoveragePct: number;
  supportSharePct: number;
  supportDefinition: string;
  contrastDefinition: string;
};

export type InnovationResearchHypothesis = {
  id: string;
  title: string;
  status: "observed" | "watch";
  evidence: string;
  nextCheck: string;
  metrics: InnovationResearchEvidenceMetrics;
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

function numberValue(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function ratioPct(numerator: number, denominator: number) {
  if (denominator <= 0) return 0;
  return Math.round((numerator / denominator) * 1000) / 10;
}

function projectHasEvidence(project: AnyRecord) {
  const source = project.source && typeof project.source === "object"
    ? project.source as AnyRecord
    : {};
  return Boolean(text(source.url) || text(project.sourceUrl));
}

function lifecycleHasEvidence(project: AnyRecord) {
  const sources = Array.isArray(project.sources)
    ? project.sources.filter((item): item is AnyRecord => Boolean(item) && typeof item === "object")
    : [];
  return sources.some((source) => Boolean(text(source.url)));
}

function institutionHasEvidence(institution: AnyRecord) {
  return Array.isArray(institution.evidenceUrls)
    && institution.evidenceUrls.some((value) => Boolean(text(value)));
}

function candidateHasEvidence(candidate: AnyRecord) {
  const source = candidate.source && typeof candidate.source === "object"
    ? candidate.source as AnyRecord
    : {};
  return Boolean(text(source.url));
}

function daysBetween(start: unknown, end: unknown) {
  const left = Date.parse(text(start));
  const right = Date.parse(text(end));
  if (!Number.isFinite(left) || !Number.isFinite(right) || right < left) return null;
  return Math.round((right - left) / 86_400_000);
}

function metrics(
  sampleUnit: InnovationResearchEvidenceMetrics["sampleUnit"],
  universeCount: number,
  supportCount: number,
  contrastCount: number,
  evidenceCoveredCount: number,
  supportDefinition: string,
  contrastDefinition: string,
): InnovationResearchEvidenceMetrics {
  const neutralCount = Math.max(0, universeCount - supportCount - contrastCount);
  return {
    sampleUnit,
    universeCount,
    supportCount,
    contrastCount,
    neutralCount,
    evidenceCoveredCount,
    evidenceCoveragePct: ratioPct(evidenceCoveredCount, universeCount),
    supportSharePct: ratioPct(supportCount, universeCount),
    supportDefinition,
    contrastDefinition,
  };
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

  const brokerProjects = brokerSector
    ? projects.filter((item) => text(item.broker) === brokerSector.broker)
    : [];
  const brokerSectorSupport = brokerSector
    ? brokerProjects.filter((item) => text(item.sector) === brokerSector.sector)
    : [];
  const brokerSectorContrast = brokerSector
    ? brokerProjects.filter((item) => text(item.sector) !== brokerSector.sector)
    : [];

  const longGuidanceProjects = projects.filter((item) => {
    const duration = daysBetween(item.firstGuidanceDate, item.latestEventDate);
    return duration !== null && duration >= 365;
  });
  const longGuidanceStillInProgress = longGuidanceProjects.filter(
    (item) => text(item.stage) === "辅导中",
  );
  const longGuidanceReachedAcceptance = longGuidanceProjects.filter(
    (item) => text(item.stage) === "辅导验收",
  );

  const routeMigrationSupport = refiles.filter((item) => {
    const prior = text(item.priorFilingSummary);
    const route = text(item.route);
    return (
      (prior.includes("科创板") && route === "ChiNext")
      || (prior.includes("创业板") && route === "STAR")
    );
  });
  const routeMigrationContrast = refiles.filter(
    (item) => !routeMigrationSupport.includes(item),
  );

  const repeatedInstitutions = institutions.filter(
    (item) => numberValue(item.linkedProjectCount) >= 2,
  );
  const singletonInstitutions = institutions.filter(
    (item) => numberValue(item.linkedProjectCount) === 1,
  );

  const matureConverted = matureCandidates.filter((item) => {
    const brokerEvidence = Array.isArray(item.brokerEvidence) ? item.brokerEvidence : [];
    const routeEvidence = text(item.routeEvidence);
    return brokerEvidence.length > 0 || (routeEvidence && routeEvidence !== "unassigned");
  });
  const matureAwaitingConversion = matureCandidates.filter(
    (item) => !matureConverted.includes(item),
  );

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
      "没有一级证据时保持 A-share-TBD，不得根据行业属性推断板块。",
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
      metrics: metrics(
        "project",
        brokerProjects.length,
        brokerSectorSupport.length,
        brokerSectorContrast.length,
        brokerProjects.filter(projectHasEvidence).length,
        brokerSector
          ? `${brokerSector.broker} 当前归入 ${brokerSector.sector} 的已跟踪项目`
          : "当前最高频券商×赛道组合项目",
        brokerSector
          ? `${brokerSector.broker} 当前归入其他赛道的已跟踪项目`
          : "同券商其他赛道项目",
      ),
    },
    {
      id: "state-jump-over-duration",
      title: "长期辅导并不等于已进入下游监管阶段，状态跳变需要单独跟踪",
      status: longGuidanceStillInProgress.length > 0 ? "observed" : "watch",
      evidence: `当前有 ${longGuidanceProjects.length} 个项目的已记录辅导跨度达到 365 天，其中 ${longGuidanceStillInProgress.length} 个仍为“辅导中”，${longGuidanceReachedAcceptance.length} 个已到“辅导验收”。`,
      nextCheck: "继续记录长期辅导项目何时出现辅导验收、交易所受理等状态跃迁，不把时间本身当成成熟度结论。",
      metrics: metrics(
        "project",
        longGuidanceProjects.length,
        longGuidanceStillInProgress.length,
        longGuidanceReachedAcceptance.length,
        longGuidanceProjects.filter(projectHasEvidence).length,
        "已记录辅导跨度≥365天但当前仍处于“辅导中”的项目",
        "已记录辅导跨度≥365天且当前已到“辅导验收”的项目",
      ),
    },
    {
      id: "cross-market",
      title: "A+H / H→A 正形成独立的硬科技资本市场路径",
      status: aPlusH.length > 0 ? "observed" : "watch",
      evidence: `当前储备池标记 A+H 项目 ${aPlusH.length} 个。`,
      nextCheck: "分别维护A股与港股状态，统计先H后A、并行推进及路线切换样本。",
      metrics: metrics(
        "project",
        projects.length,
        aPlusH.length,
        projects.filter((item) => text(item.capitalMarketPath) === "A").length,
        projects.filter(projectHasEvidence).length,
        "明确标记 capitalMarketPath=A+H 的已跟踪项目",
        "当前仅标记 capitalMarketPath=A 的已跟踪项目；这是对照样本，不代表否定未来跨市场路径",
      ),
    },
    {
      id: "route-migration",
      title: "撤回后的二次申报与板块迁移值得单独建模",
      status: routeMigrationSupport.length > 0 ? "observed" : "watch",
      evidence: `当前二次申报/历史递表样本 ${refiles.length} 个，其中 ${routeMigrationSupport.length} 个已能从公开历史识别出科创板↔创业板的跨板迁移。`,
      nextCheck: "维护 route_history，并识别撤回前后券商、板块和审核节点变化。",
      metrics: metrics(
        "project",
        refiles.length,
        routeMigrationSupport.length,
        routeMigrationContrast.length,
        refiles.filter(projectHasEvidence).length,
        "历史公开申报板块与当前公开确认板块不同的二次申报项目",
        "存在历史申报/重启，但当前未形成可确认跨板迁移的项目",
      ),
    },
    {
      id: "hard-tech-lifecycle",
      title: "当前进入后续生命周期的样本呈科创板集中现象",
      status: "watch",
      evidence: `生命周期池 ${lifecycleProjects.length} 个项目，其中科创板 ${lifecycleStar} 个、已上市 ${lifecycleListed} 个。`,
      nextCheck: "这是当前样本现象，不外推总体概率；随创业板/港股样本增加继续验证。",
      metrics: metrics(
        "project",
        lifecycleProjects.length,
        lifecycleStar,
        lifecycleProjects.length - lifecycleStar,
        lifecycleProjects.filter(lifecycleHasEvidence).length,
        "后续生命周期池中公开路线为科创板的项目",
        "后续生命周期池中公开路线不是科创板的项目",
      ),
    },
    {
      id: "capital-repeat",
      title: "少数机构可能反复出现在成熟硬科技IPO管线中",
      status: repeatedInstitutions.length > 0 ? "watch" : "watch",
      evidence: topInstitution
        ? `当前关联项目最多的机构为 ${text(topInstitution.name)}（${numberValue(topInstitution.linkedProjectCount)} 个）；共有 ${repeatedInstitutions.length} 家机构关联至少 2 个项目。`
        : "当前尚无机构网络样本。",
      nextCheck: "按确认关系、候选关系和证据等级分别统计，避免把同名基金或品牌误合并。",
      metrics: metrics(
        "institution",
        institutions.length,
        repeatedInstitutions.length,
        singletonInstitutions.length,
        institutions.filter(institutionHasEvidence).length,
        "linkedProjectCount≥2 的机构节点",
        "当前仅关联 1 个已跟踪项目的机构节点",
      ),
    },
    {
      id: "late-stage-to-guidance",
      title: "大额成长轮融资→股改/辅导可能构成成熟项目发现链",
      status: matureConverted.length > 0 ? "observed" : "watch",
      evidence: `当前成熟候选池 ${matureCandidates.length} 个，其中 ${matureConverted.length} 个已出现券商/上市路线一级证据，${matureAwaitingConversion.length} 个仍停留在成熟候选阶段。`,
      nextCheck: "持续寻找券商聘任、辅导备案和公司治理变化等一级证据；没有一级证据时不得把融资成熟度当成上市路线。",
      metrics: metrics(
        "candidate",
        matureCandidates.length,
        matureConverted.length,
        matureAwaitingConversion.length,
        matureCandidates.filter(candidateHasEvidence).length,
        "成熟候选中已出现 brokerEvidence 或已分配 routeEvidence 的项目",
        "成熟候选中仍无券商/上市路线一级证据的项目",
      ),
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
      "Research lane 优先研究生命周期跳变、跨市场路径、路线迁移、券商×赛道结构、机构资本重复命中与成熟候选转化；每条 Thesis 同时公开支持样本、对照/未支持样本、样本宇宙与证据覆盖率。量化字段只描述当前可见样本，不输出上市概率、券商排名或投资评级。",
  };
}
