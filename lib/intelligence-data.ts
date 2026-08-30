import publicArticleData from "../public/data/articles.json";

export type Region = "中国" | "美国" | "全球";
export type EventType =
  | "融资"
  | "产业投资"
  | "产品发布"
  | "技术突破"
  | "商业进展"
  | "公司动态"
  | "并购"
  | "财报"
  | "政策"
  | "监管文件"
  | "IPO"
  | "论文"
  | "人物观点";

export type Source = {
  name: string;
  url: string;
  level:
    | "官方披露"
    | "原始材料"
    | "监管文件"
    | "媒体报道"
    | "数据库记录"
    | "待交叉验证";
  platform?: string;
};

export type IntelligenceEvent = {
  id: string;
  title: string;
  summary: string;
  type: EventType;
  region: Region;
  sector: string;
  company: string;
  companySlug?: string;
  personSlug?: string;
  sourceId?: string;
  authors?: string[];
  institutions?: string[];
  publishedAt: string;
  importance: number;
  source: Source;
  curated?: boolean;
};

export type FinancialMetric = {
  id: "revenue" | "netIncome" | "researchAndDevelopment" | "operatingCashFlow";
  label: string;
  value: number;
  unit: string;
  periodEnd: string;
  filedAt: string;
  form: string;
  fiscalYear?: number;
  fiscalPeriod?: string;
  accessionNumber?: string;
  concept: string;
};

export type CompanyFactProfile = {
  company: string;
  companySlug: string;
  ticker: string;
  cik: string;
  entityName: string;
  metrics: FinancialMetric[];
  source: Source;
};

type SnapshotFile = {
  schemaVersion: number;
  generatedAt: string;
  articleCount: number;
  articles: IntelligenceEvent[];
  companyFacts?: Record<string, CompanyFactProfile>;
  sourceStatus?: {
    id: string;
    name: string;
    status: string;
    scanned: number;
    accepted: number;
    failed?: number;
    platform?: string;
    error?: string;
  }[];
  qualityGate?: {
    passed: boolean;
    checks: Record<
      string,
      { actual: number; required: number; passed: boolean }
    >;
    invalidArticles?: { id: string; errors: string[] }[];
  };
};

const snapshot = publicArticleData as SnapshotFile;

export const snapshotDate =
  typeof snapshot.generatedAt === "string"
    ? snapshot.generatedAt.slice(0, 10)
    : new Date().toISOString().slice(0, 10);

export const intelligenceEvents: IntelligenceEvent[] = Array.isArray(
  snapshot.articles,
)
  ? snapshot.articles
  : [];

export const companyFacts: Record<string, CompanyFactProfile> =
  snapshot.companyFacts ?? {};

export const sourceStatus = snapshot.sourceStatus ?? [];

export const qualityGate = snapshot.qualityGate;

type SectorDefinition = {
  slug: string;
  name: string;
  definition: string;
  subsectors: string[];
  chain: { title: string; detail: string }[];
  chinaLens: string;
  usLens: string;
  researchFocus: string[];
  risks: string[];
};

const sectorDefinitions: SectorDefinition[] = [
  {
    slug: "ai",
    name: "AI / AGI",
    definition:
      "覆盖基础模型、推理基础设施、开发工具与行业智能体，重点跟踪模型能力、算力供给和企业付费之间的传导。",
    subsectors: ["基础模型", "AI 基础设施", "智能体", "企业应用"],
    chain: [
      { title: "算力与数据", detail: "芯片、云算力、训练数据与评测" },
      { title: "模型平台", detail: "预训练、推理、API 与开发工具" },
      { title: "应用与交付", detail: "消费者产品、企业软件与行业方案" },
    ],
    chinaLens: "聚焦模型效率、开源生态、应用分发与国产算力适配。",
    usLens: "聚焦前沿模型能力、超大规模算力投入与企业开发者生态。",
    researchFocus: ["推理成本下降速度", "企业付费与留存", "算力投入转化效率"],
    risks: ["算力与资本开支压力", "模型同质化", "数据与监管约束"],
  },
  {
    slug: "robotics",
    name: "机器人",
    definition:
      "覆盖人形机器人、具身智能、自动驾驶与工业自主系统，核心变量是数据闭环、硬件可靠性和单位经济性。",
    subsectors: ["人形机器人", "自动驾驶", "工业机器人", "自主系统"],
    chain: [
      { title: "核心部件", detail: "执行器、传感器、控制器与计算平台" },
      { title: "本体与模型", detail: "机器人硬件、运动控制与具身模型" },
      { title: "场景运营", detail: "制造、物流、出行与专业服务" },
    ],
    chinaLens: "供应链完整、工程化迭代快，重点看量产节奏与真实场景收入。",
    usLens: "模型与软件投入高，重点看通用能力、数据规模和标杆客户部署。",
    researchFocus: ["量产良率与成本", "真实作业时长", "从试点到重复采购"],
    risks: ["硬件可靠性", "场景碎片化", "安全责任与监管"],
  },
  {
    slug: "semiconductor",
    name: "半导体",
    definition:
      "覆盖 AI 训练与推理芯片、通用 GPU、车载计算和相应软件栈，关注性能、供给和生态的共同约束。",
    subsectors: ["AI 加速器", "通用 GPU", "车载计算", "芯片软件栈"],
    chain: [
      { title: "设计与 IP", detail: "架构、芯片设计与关键接口" },
      { title: "制造与封装", detail: "晶圆制造、先进封装与供应链" },
      { title: "系统与软件", detail: "服务器、编译器、驱动与开发生态" },
    ],
    chinaLens: "重点看国产计算平台、软件生态与制造供应链协同。",
    usLens: "重点看新架构在训练、推理和系统级效率上的差异化。",
    researchFocus: ["性能功耗与总拥有成本", "软件生态迁移成本", "量产与供货能力"],
    risks: ["供应链限制", "迭代周期长", "客户验证与生态壁垒"],
  },
  {
    slug: "energy",
    name: "新能源",
    definition:
      "覆盖动力与储能电池、风电、长时储能和聚变技术，研究技术路线走向规模化供给的路径。",
    subsectors: ["动力电池", "储能", "风电", "聚变能源"],
    chain: [
      { title: "材料与设备", detail: "关键材料、生产设备与能源输入" },
      { title: "核心系统", detail: "电池、风机、聚变装置与控制系统" },
      { title: "电网与终端", detail: "电力系统、交通与工业应用" },
    ],
    chinaLens: "制造规模与供应链效率突出，重点看价格竞争和海外扩张。",
    usLens: "新路线融资活跃，重点看示范项目、工程进度与购电合同。",
    researchFocus: ["度电/储能成本", "产能利用率", "示范项目兑现"],
    risks: ["重资产投入", "原材料波动", "政策与并网周期"],
  },
  {
    slug: "biotech",
    name: "生物科技",
    definition:
      "覆盖 AI 药物发现、基因组学、自动化实验和计算生物学，核心是研发效率能否转化为临床与商业成果。",
    subsectors: ["AI 制药", "基因组学", "计算生物学", "自动化实验"],
    chain: [
      { title: "数据与靶点", detail: "组学数据、靶点发现与验证" },
      { title: "研发平台", detail: "分子设计、自动化实验与临床开发" },
      { title: "产品与服务", detail: "药物管线、检测与研发合作" },
    ],
    chinaLens: "重点看研发平台国际合作、临床推进和数据合规。",
    usLens: "重点看计算平台对候选药物成功率和研发周期的实际改善。",
    researchFocus: ["临床里程碑", "合作付款结构", "研发现金消耗"],
    risks: ["临床失败", "审批周期", "平台价值难以单独验证"],
  },
  {
    slug: "quantum",
    name: "量子计算",
    definition:
      "覆盖超导、离子阱、光子等量子计算路线，以及控制系统、云服务和早期行业应用。",
    subsectors: ["超导", "离子阱", "光子", "量子软件"],
    chain: [
      { title: "器件与材料", detail: "量子比特、低温与光学部件" },
      { title: "系统与控制", detail: "量子处理器、控制电子与纠错" },
      { title: "云与应用", detail: "量子云、算法与行业试验" },
    ],
    chinaLens: "关注科研平台、国产设备和专用场景验证。",
    usLens: "关注上市公司路线进展、纠错里程碑和商业合同。",
    researchFocus: ["逻辑量子比特进展", "错误率与可扩展性", "商业收入质量"],
    risks: ["技术路径不确定", "商业化周期长", "研发稀释与融资压力"],
  },
  {
    slug: "space",
    name: "商业航天",
    definition:
      "覆盖运载火箭、卫星平台、在轨服务和商业空间站，重点区分技术试验、订单储备与确认收入。",
    subsectors: ["运载火箭", "卫星系统", "在轨服务", "商业空间站"],
    chain: [
      { title: "制造与部件", detail: "发动机、结构、电子与卫星制造" },
      { title: "发射与在轨", detail: "运载服务、卫星部署与任务运营" },
      { title: "数据与服务", detail: "通信、遥感、科研与在轨制造" },
    ],
    chinaLens: "民营火箭密集验证，重点看成功率、发射频次和订单转化。",
    usLens: "可复用火箭和卫星网络领先，重点看规模化现金流与新任务形态。",
    researchFocus: ["发射成功率与频次", "订单转收入", "可复用系统周转"],
    risks: ["任务失败", "高资本开支", "监管与供应链"],
  },
  {
    slug: "web3",
    name: "Web3",
    definition:
      "覆盖区块链基础设施、数字资产应用和去中心化协议，跟踪真实使用、合规和可持续收入。",
    subsectors: ["基础设施", "交易与支付", "去中心化应用", "安全"],
    chain: [
      { title: "底层网络", detail: "共识、扩容、节点与开发工具" },
      { title: "协议与中间件", detail: "交易、数据、身份与安全" },
      { title: "终端应用", detail: "支付、金融、内容与企业场景" },
    ],
    chinaLens: "以联盟链、数字基础设施和合规应用为主要观察对象。",
    usLens: "重点看稳定币、机构化基础设施与监管变化。",
    researchFocus: ["真实活跃用户", "协议收入", "监管许可"],
    risks: ["监管变化", "代币激励失真", "安全事故"],
  },
  {
    slug: "materials",
    name: "新材料",
    definition:
      "覆盖先进电池材料、复合材料、半导体材料和高性能制造材料，关注认证周期与规模制造。",
    subsectors: ["电池材料", "半导体材料", "复合材料", "特种材料"],
    chain: [
      { title: "原料与配方", detail: "矿物、化学原料与材料设计" },
      { title: "工艺与制造", detail: "制备、加工、检测与良率" },
      { title: "认证与应用", detail: "汽车、电子、能源与航空客户" },
    ],
    chinaLens: "供应链与制造规模突出，重点看产品升级和利润结构。",
    usLens: "重点看新配方、国防与航空等高价值场景的认证。",
    researchFocus: ["客户认证进度", "良率与单位成本", "产能扩张节奏"],
    risks: ["认证周期长", "原料价格波动", "扩产带来的现金压力"],
  },
  {
    slug: "manufacturing",
    name: "智能制造",
    definition:
      "覆盖工业软件、自动化装备、自主系统和数字化工厂，研究效率提升能否形成可复制交付。",
    subsectors: ["工业软件", "自动化装备", "自主系统", "数字工厂"],
    chain: [
      { title: "工业数据", detail: "传感器、连接、数据采集与仿真" },
      { title: "控制与装备", detail: "控制系统、机器人与专用设备" },
      { title: "软件与服务", detail: "工业平台、运维和流程优化" },
    ],
    chinaLens: "制造场景丰富，重点看国产替代、交付效率和客户复购。",
    usLens: "软件与自主系统优势突出，重点看高价值场景和国防工业需求。",
    researchFocus: ["实施周期", "客户复购", "软硬件毛利结构"],
    risks: ["项目制交付", "客户集中", "资本开支周期"],
  },
];

function dateValue(value: string): number {
  const time = Date.parse(value);
  return Number.isFinite(time) ? time : 0;
}

function normalizer(values: number[]): (value: number) => number {
  const max = Math.max(...values, 0);
  return (value) => (max > 0 ? Math.round((value / max) * 100) : 0);
}

function buildSectorStats() {
  const asOf = dateValue(snapshotDate);
  const yearAgo = asOf - 365 * 24 * 60 * 60 * 1000;
  const ninetyDaysAgo = asOf - 90 * 24 * 60 * 60 * 1000;
  const previousNinetyDays = asOf - 180 * 24 * 60 * 60 * 1000;
  const raw = sectorDefinitions.map((definition) => {
    const events = intelligenceEvents.filter(
      (event) =>
        event.sector === definition.name &&
        dateValue(event.publishedAt) >= yearAgo,
    );
    const financing = events.filter((event) => event.type === "融资").length;
    const institutions = new Set(events.flatMap((event) => event.institutions ?? []))
      .size;
    const weightedEvents = Math.round(
      events.reduce((sum, event) => sum + event.importance, 0) / 100,
    );
    const ipo = events.filter((event) =>
      ["IPO", "监管文件", "财报"].includes(event.type),
    ).length;
    const research = events.filter((event) =>
      ["技术突破", "政策", "产品发布"].includes(event.type),
    ).length;
    const current = events.filter(
      (event) => dateValue(event.publishedAt) >= ninetyDaysAgo,
    ).length;
    const previous = events.filter((event) => {
      const date = dateValue(event.publishedAt);
      return date >= previousNinetyDays && date < ninetyDaysAgo;
    }).length;
    return {
      definition,
      events,
      financing,
      institutions,
      weightedEvents,
      ipo,
      research,
      current,
      previous,
    };
  });

  const normalizeFinancing = normalizer(raw.map((item) => item.financing));
  const normalizeInstitutions = normalizer(raw.map((item) => item.institutions));
  const normalizeEvents = normalizer(raw.map((item) => item.weightedEvents));
  const normalizeIpo = normalizer(raw.map((item) => item.ipo));
  const normalizeResearch = normalizer(raw.map((item) => item.research));

  return raw.map((item) => {
    const heat = Math.round(
      0.3 * normalizeFinancing(item.financing) +
        0.2 * normalizeInstitutions(item.institutions) +
        0.2 * normalizeEvents(item.weightedEvents) +
        0.15 * normalizeIpo(item.ipo) +
        0.15 * normalizeResearch(item.research),
    );
    const sourceCount = new Set(item.events.map((event) => event.source.url)).size;
    const completeness = Math.min(
      100,
      Math.round(
        (item.events.length > 0 ? 35 : 10) +
          Math.min(item.events.length, 10) * 4 +
          Math.min(sourceCount, 5) * 5,
      ),
    );
    const trend =
      item.current > item.previous
        ? "up"
        : item.current < item.previous
          ? "down"
          : "flat";
    return {
      ...item.definition,
      heat,
      completeness,
      trend,
      events: item.events.length,
      institutions: item.institutions,
      financingEvents: item.financing,
      sourceCount,
      fundingLabel: `${item.financing} 笔融资披露`,
    } as Sector;
  });
}

export type Sector = SectorDefinition & {
  heat: number;
  completeness: number;
  trend: "up" | "flat" | "down";
  events: number;
  institutions: number;
  financingEvents: number;
  sourceCount: number;
  fundingLabel: string;
};

export const sectors: Sector[] = buildSectorStats();

export const focusCompanies = [
  {
    slug: "openai",
    name: "OpenAI",
    region: "美国",
    sector: "AI / AGI",
    stage: "成长期",
    focus: "基础模型、开发者平台与 AI 基础设施",
  },
  {
    slug: "deepseek",
    name: "DeepSeek",
    region: "中国",
    sector: "AI / AGI",
    stage: "成长期",
    focus: "开源推理模型与训练效率",
  },
  {
    slug: "figure-ai",
    name: "Figure AI",
    region: "美国",
    sector: "机器人",
    stage: "Series C",
    focus: "通用人形机器人、具身模型与制造",
  },
  {
    slug: "unitree",
    name: "宇树科技",
    region: "中国",
    sector: "机器人",
    stage: "成长期",
    focus: "四足与人形机器人产品化",
  },
  {
    slug: "pony-ai",
    name: "小马智行",
    region: "中国",
    sector: "机器人",
    stage: "已上市",
    focus: "Robotaxi 规模运营与车队扩张",
  },
  {
    slug: "rocket-lab",
    name: "Rocket Lab",
    region: "美国",
    sector: "商业航天",
    stage: "已上市",
    focus: "发射服务、航天系统与新火箭进度",
  },
];

export const heatMethodology =
  "HeatScore v1：融资活跃度 30% + 头部机构参与度 20% + 重要事件活跃度 20% + IPO/监管披露 15% + 技术与政策事件 15%。各子项以最近 365 天已收录记录在十个赛道间归一化，页面同时显示事件数与来源数。";
