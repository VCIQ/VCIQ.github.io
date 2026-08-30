import type { Company, Institution, Person } from "./catalog-data";

type SectorLens = {
  industryPosition: string;
  commercialization: string;
  technology: string;
  researchQuestions: string[];
  risks: string[];
};

const sectorLens: Record<string, SectorLens> = {
  "AI / AGI": {
    industryPosition: "位于模型、数据、算力与应用之间的 AI 价值链。",
    commercialization: "重点观察 API 用量、订阅收入、企业合同与算力成本之间的关系。",
    technology: "比较模型能力、推理效率、开发工具和数据闭环，而不是只看参数规模。",
    researchQuestions: [
      "产品使用增长能否转化为可持续付费？",
      "推理成本下降是否快于价格下降？",
      "模型、分发与企业工作流中哪一层形成长期壁垒？",
    ],
    risks: ["高强度算力投入", "模型同质化与价格竞争", "数据、版权与监管约束"],
  },
  机器人: {
    industryPosition: "位于核心部件、机器人本体、具身模型与场景运营的交叉位置。",
    commercialization: "重点观察试点部署、作业时长、车队或设备规模、重复采购和服务收入。",
    technology: "比较感知—决策—控制闭环、硬件可靠性、数据采集效率与量产能力。",
    researchQuestions: [
      "真实场景运行时间和任务成功率如何变化？",
      "硬件成本、维护成本和人工替代价值能否闭合？",
      "从单点试验到跨客户复制需要哪些产品变化？",
    ],
    risks: ["硬件可靠性与安全责任", "场景碎片化", "量产良率和售后成本"],
  },
  半导体: {
    industryPosition: "连接芯片架构、先进制造、系统集成和软件生态。",
    commercialization: "重点观察量产供货、客户验证、系统订单与软件迁移成本。",
    technology: "比较单位功耗性能、内存与互连、编译器和完整系统的总拥有成本。",
    researchQuestions: [
      "目标负载上的系统级性能是否形成明确优势？",
      "软件生态能否降低客户迁移和部署成本？",
      "供货与现金周转能否支持规模增长？",
    ],
    risks: ["制造与供应链约束", "客户验证周期长", "研发与库存资本占用"],
  },
  新能源: {
    industryPosition: "连接材料、能源装备、系统集成和电力或交通终端。",
    commercialization: "重点观察产能利用、单位成本、项目交付和长期采购合同。",
    technology: "比较能量效率、寿命、安全性、制造良率和全生命周期成本。",
    researchQuestions: [
      "成本下降来自工艺、规模还是原材料周期？",
      "在手项目何时转化为交付和现金流？",
      "扩产是否带来可持续的资产回报？",
    ],
    risks: ["重资产扩张", "原材料与价格周期", "项目审批和并网进度"],
  },
  生物科技: {
    industryPosition: "连接生物数据、计算研发平台、实验验证和临床产品。",
    commercialization: "重点观察研发合作、里程碑付款、检测服务和自有管线价值。",
    technology: "比较计算筛选、实验验证和临床推进之间的端到端效率。",
    researchQuestions: [
      "平台是否持续产出可进入临床的候选项目？",
      "合作收入是否具有重复性和高质量里程碑？",
      "现金储备能否覆盖关键临床节点？",
    ],
    risks: ["临床与审批失败", "研发周期和现金消耗", "数据合规与知识产权"],
  },
  量子计算: {
    industryPosition: "连接量子器件、控制系统、云平台与早期行业试验。",
    commercialization: "重点观察研发合同、云端访问和政府或企业项目收入。",
    technology: "比较物理量子比特质量、纠错路径、系统扩展和可编程能力。",
    researchQuestions: [
      "错误率和逻辑量子比特里程碑是否按计划推进？",
      "技术改进是否扩大可运行算法的实际规模？",
      "商业合同是研发资助还是可重复产品收入？",
    ],
    risks: ["技术路线不确定", "商业化周期长", "持续融资和股权稀释"],
  },
  商业航天: {
    industryPosition: "连接火箭与卫星制造、发射服务、在轨任务和数据服务。",
    commercialization: "重点观察发射频次、订单储备、任务成功率与收入确认。",
    technology: "比较推进系统、可复用能力、任务可靠性和制造周转。",
    researchQuestions: [
      "任务成功与复飞节奏能否支持年度交付目标？",
      "订单储备中有多少可在未来数季转化为收入？",
      "新运载系统投入会如何影响现金消耗？",
    ],
    risks: ["任务失败和进度延误", "高额研发资本开支", "监管与关键供应链"],
  },
  "Web3 / 区块链": {
    industryPosition: "连接底层网络、协议、中间件与支付或金融应用。",
    commercialization: "重点观察真实用户、交易或服务收入以及合规准入。",
    technology: "比较安全、吞吐、互操作性和开发者生态。",
    researchQuestions: [
      "活跃度是否来自真实需求而非短期激励？",
      "协议收入与安全支出能否形成可持续结构？",
      "监管变化会如何影响可服务市场？",
    ],
    risks: ["监管与牌照变化", "安全事件", "激励退坡后的活跃度"],
  },
  新材料: {
    industryPosition: "连接材料配方、制造工艺、客户认证与终端产品。",
    commercialization: "重点观察认证进度、量产良率、单位成本和客户集中度。",
    technology: "比较性能提升、工艺兼容性和规模制造的一致性。",
    researchQuestions: [
      "关键客户认证是否进入量产阶段？",
      "扩产后良率与单位成本如何变化？",
      "材料优势能否转化为议价能力？",
    ],
    risks: ["认证周期长", "原料价格波动", "产能爬坡与客户集中"],
  },
  智能制造: {
    industryPosition: "连接工业数据、自动化装备、控制软件与现场交付。",
    commercialization: "重点观察实施周期、软件或服务占比、客户复购和项目毛利。",
    technology: "比较对复杂工况的适配、系统集成效率和持续优化能力。",
    researchQuestions: [
      "单个项目经验能否沉淀为标准产品？",
      "客户是否扩展到更多产线和场景？",
      "软硬件组合对毛利和现金流的影响是什么？",
    ],
    risks: ["项目制交付", "客户资本开支周期", "回款与售后成本"],
  },
};

const companyOverrides: Record<string, Partial<SectorLens>> = {
  openai: {
    industryPosition: "位于前沿基础模型、消费者入口、开发者平台与 AI 基础设施的核心交汇点。",
    commercialization: "订阅产品、API 使用和企业服务共同构成商业化观察框架。",
    technology: "关注多模态模型、推理能力、智能体工具与训练/推理基础设施的协同。",
  },
  anthropic: {
    industryPosition: "以 Claude 模型、企业 API 和模型安全研究连接前沿研发与企业部署。",
    commercialization: "企业 API、团队产品和云平台分发是主要商业化观察点。",
    technology: "关注长上下文、编码与智能体能力，以及安全评测和模型治理。",
  },
  "figure-ai": {
    industryPosition: "将人形机器人本体、Helix 具身模型和 BotQ 制造体系放在同一产品闭环内。",
    commercialization: "BMW、物流与零售合作提供从试验到多场景部署的验证路径。",
    technology: "关注全身自主、灵巧操作、真实环境数据和机器人制造的一体化。",
  },
  spacex: {
    industryPosition: "横跨可复用运载、载人航天、卫星网络与深空任务。",
    commercialization: "发射服务与 Starlink 运营构成高频现金流观察，Starship 决定下一阶段运力。",
    technology: "关注复用周转、发动机与整箭可靠性、任务频次和大规模卫星运营。",
  },
  deepseek: {
    industryPosition: "以开源模型、推理模型和开发者 API 参与全球基础模型竞争。",
    commercialization: "重点观察 API 使用、开源生态外溢和模型效率形成的成本优势。",
    technology: "关注训练效率、推理能力、开放权重和软硬件适配。",
  },
  unitree: {
    industryPosition: "产品覆盖四足机器人、人形机器人、机械臂与核心运动部件。",
    commercialization: "教育科研、消费展示和工业应用构成多层产品市场。",
    technology: "关注运动控制、执行器、自研部件和人形机器人量产迭代。",
  },
  "pony-ai": {
    industryPosition: "从自动驾驶软件延伸到 Robotaxi 车队运营和自动驾驶卡车。",
    commercialization: "付费订单、车队规模、城市扩张和整车合作是关键经营信号。",
    technology: "关注世界模型、虚拟司机系统、量产域控制器和运营数据闭环。",
  },
  weride: {
    industryPosition: "覆盖 Robotaxi、Robobus、Robosweeper 与乘用车智能驾驶方案。",
    commercialization: "城市运营、平台合作、整车前装与海外部署共同验证规模化能力。",
    technology: "关注端到端驾驶系统、多车型适配和跨地区运营验证。",
  },
};

export function getCompanyResearch(company: Company): SectorLens {
  const base = sectorLens[company.sector] ?? {
    industryPosition: `位于${company.sector}产业链，核心产品为${company.product}`,
    commercialization: "重点观察客户采用、收入质量和交付效率。",
    technology: "重点观察产品性能、研发进度和规模化能力。",
    researchQuestions: ["产品验证进展如何？", "商业化是否具有重复性？", "现金投入能否形成长期壁垒？"],
    risks: ["技术与交付风险", "市场竞争", "融资与现金流"],
  };
  return { ...base, ...(companyOverrides[company.slug] ?? {}) };
}

export type PortfolioItem = {
  name: string;
  slug?: string;
  note: string;
};

type InstitutionProfile = {
  thesis: string;
  portfolio: PortfolioItem[];
  observation: string[];
};

const institutionProfiles: Record<string, InstitutionProfile> = {
  "sequoia-capital": {
    thesis: "以创始人与长期公司建设为主线，覆盖早期到成长阶段，并持续扩大 AI 与企业科技布局。",
    portfolio: [
      { name: "Harvey", slug: "harvey", note: "法律 AI 工作平台" },
      { name: "Sierra", slug: "sierra", note: "企业客户体验智能体" },
      { name: "xAI", slug: "xai", note: "前沿模型与基础设施" },
    ],
    observation: ["AI 原生应用的收入质量", "模型基础设施与应用层的配置比例", "成长轮次的资本密度"],
  },
  a16z: {
    thesis: "以软件和技术平台为基础，AI、American Dynamism、生物科技与加密资产形成多条专业投资线。",
    portfolio: [
      { name: "Anduril", slug: "anduril", note: "自主系统与国防软件" },
      { name: "SpaceX", slug: "spacex", note: "商业航天与卫星网络" },
    ],
    observation: ["AI 基础设施到应用的全栈布局", "国防与制造软件化", "技术平台的网络效应"],
  },
  "founders-fund": {
    thesis: "偏好技术风险高、潜在产业影响大的公司，长期覆盖航天、国防、AI、金融与深科技。",
    portfolio: [
      { name: "SpaceX", slug: "spacex", note: "可复用运载与卫星网络" },
      { name: "Anduril", slug: "anduril", note: "自主系统与国防科技" },
      { name: "OpenAI", slug: "openai", note: "前沿基础模型" },
      { name: "Varda", slug: "varda", note: "在轨制造" },
      { name: "PsiQuantum", slug: "psiquantum", note: "光子量子计算" },
      { name: "Scale AI", slug: "scale-ai", note: "AI 数据与评测基础设施" },
    ],
    observation: ["深科技的长期资本需求", "政府与商业客户并行", "从技术里程碑到规模收入"],
  },
  yc: {
    thesis: "以批次制创业加速和种子投资为核心，组合跨度大，重视产品迭代速度与创始团队执行。",
    portfolio: [
      { name: "Perplexity", slug: "perplexity", note: "AI 搜索与研究" },
      { name: "Varda", slug: "varda", note: "在轨制造与返回舱" },
    ],
    observation: ["AI 原生产品的早期留存", "开发者工具到企业付费", "硬科技公司的后续资本衔接"],
  },
  greylock: {
    thesis: "长期聚焦企业软件、基础设施和消费者网络，强调早期产品与市场形成阶段。",
    portfolio: [
      { name: "Glean", slug: "glean", note: "企业搜索与工作场景智能体" },
      { name: "Cerebras", slug: "cerebras", note: "晶圆级 AI 计算系统" },
    ],
    observation: ["企业 AI 的席位扩张", "基础设施毛利与算力利用", "早期产品市场匹配"],
  },
  khosla: {
    thesis: "以高技术风险换取大规模产业变化，覆盖 AI、气候、能源、医疗与前沿科学。",
    portfolio: [
      { name: "OpenAI", slug: "openai", note: "前沿基础模型" },
      { name: "Commonwealth Fusion Systems", slug: "commonwealth-fusion", note: "高温超导聚变系统" },
    ],
    observation: ["科学突破到工程化的时间", "能源项目的示范节点", "AI 对传统产业成本曲线的改变"],
  },
  hongshan: {
    thesis: "覆盖科技、医疗与消费的多阶段投资，近年持续关注基础模型、机器人和硬科技。",
    portfolio: [
      { name: "月之暗面", slug: "moonshot-ai", note: "长上下文基础模型与 Kimi" },
      { name: "智谱AI", slug: "zhipu-ai", note: "GLM 基础模型与企业平台" },
      { name: "MiniMax", slug: "minimax", note: "多模态基础模型" },
    ],
    observation: ["中国基础模型的商业化分层", "机器人供应链与量产", "跨境与资本市场路径"],
  },
  qiming: {
    thesis: "医疗健康与 TMT 双线并行，长期参与早期技术公司的研发、产品和全球化进程。",
    portfolio: [
      { name: "英矽智能", slug: "insilico-medicine", note: "生成式 AI 药物研发" },
      { name: "晶泰科技", slug: "xtalpi", note: "AI 与自动化药物/材料研发" },
    ],
    observation: ["AI 制药的临床里程碑", "研发平台的合作收入", "医疗科技全球化"],
  },
};

export function getInstitutionProfile(institution: Institution): InstitutionProfile {
  return (
    institutionProfiles[institution.slug] ?? {
      thesis: `${institution.name}公开投资方向覆盖${institution.sectors.join("、")}，阶段以${institution.stages}为主。`,
      portfolio: [],
      observation: institution.sectors.slice(0, 3).map((sector) => `${sector}项目的新增投资与退出节奏`),
    }
  );
}

export type ConceptNote = {
  name: string;
  explanation: string;
  evidenceIndex: number;
};

type PersonProfile = {
  overview: string;
  evolution: string[];
  concepts: ConceptNote[];
};

const personProfiles: Record<string, PersonProfile> = {
  "warren-buffett": {
    overview: "研究主线是资本配置、企业质量与长期复利。年度股东信提供了跨周期、连续且可核对的一手材料。",
    evolution: [
      "早期更强调价格相对资产价值的折价。",
      "在芒格影响下逐步提高对优秀企业、管理层和长期竞争优势的权重。",
      "近年股东信继续把资本配置、保险浮存金和长期持有放在同一框架中讨论。",
    ],
    concepts: [
      { name: "能力圈", explanation: "把可理解的企业边界放在机会数量之前，并承认边界本身需要持续校准。", evidenceIndex: 0 },
      { name: "护城河", explanation: "关注企业维持定价、客户关系和资本回报的长期结构，而非短期增速。", evidenceIndex: 1 },
      { name: "安全边际", explanation: "以价格、资产质量和未来现金流的不确定性共同决定可承受的错误空间。", evidenceIndex: 2 },
      { name: "浮存金", explanation: "保险业务形成的可投资资金与承保纪律共同决定长期价值。", evidenceIndex: 3 },
      { name: "复利", explanation: "优先让高质量资产和管理团队在更长时间内持续再投资。", evidenceIndex: 4 },
    ],
  },
  "charlie-munger": {
    overview: "研究主线是跨学科模型、激励机制和人类判断偏误。演讲与问答更适合按概念而非按股票建议阅读。",
    evolution: [
      "从法律与企业经营经验中形成跨学科分析框架。",
      "在公开演讲中系统讨论误判心理学和激励导致的行为偏差。",
      "晚年持续强调少做愚蠢决策、耐心等待少数高质量机会。",
    ],
    concepts: [
      { name: "多元思维模型", explanation: "把经济学、心理学、数学和工程等模型组合使用，避免单一学科解释一切。", evidenceIndex: 0 },
      { name: "逆向思维", explanation: "先识别失败路径、不可逆风险和明显错误，再讨论如何取得成功。", evidenceIndex: 0 },
      { name: "误判心理学", explanation: "系统观察激励、从众、承诺一致和社会认同等因素如何扭曲判断。", evidenceIndex: 1 },
      { name: "激励机制", explanation: "先看参与者为何这样行动，再判断制度设计会产生什么结果。", evidenceIndex: 1 },
    ],
  },
  "duan-yongping": {
    overview: "研究主线是企业文化、消费者导向与投资纪律。公开材料以长期发布的个人发言和企业实践为主。",
    evolution: [
      "经营阶段形成以消费者和长期企业价值为核心的“本分”文化。",
      "转向投资后，持续强调理解生意、管理层和长期现金流。",
      "近年的公开问答更多把“不做什么”与能力圈、平常心联系起来。",
    ],
    concepts: [
      { name: "本分", explanation: "回到事情本身和长期用户价值，不让短期竞争改变基本判断。", evidenceIndex: 0 },
      { name: "平常心", explanation: "减少结果导向带来的动作变形，以长期尺度评估经营和投资。", evidenceIndex: 0 },
      { name: "做对的事", explanation: "先确认方向、文化和商业模式，再讨论把事情做快或做大的方法。", evidenceIndex: 1 },
      { name: "Stop Doing List", explanation: "用明确的不做清单保护注意力、能力圈和组织资源。", evidenceIndex: 0 },
    ],
  },
  "li-lu": {
    overview: "研究主线把文明与现代化的长期变化，同价值投资的企业研究框架连接起来。",
    evolution: [
      "早期以中国现代化和制度演进解释长期经济机会。",
      "在公开演讲中讨论价值投资在中国市场的适用条件。",
      "后续文章继续强调诚实求知、扩大能力圈与长期持有优秀企业。",
    ],
    concepts: [
      { name: "文明演进", explanation: "从技术、制度和知识积累理解长期生产力与社会组织变化。", evidenceIndex: 1 },
      { name: "现代化", explanation: "把现代科学与市场交换带来的持续增长视为理解企业机会的背景。", evidenceIndex: 1 },
      { name: "价值投资在中国", explanation: "把所有权思维、能力圈和安全边际应用到快速变化的中国企业环境。", evidenceIndex: 0 },
      { name: "能力圈扩展", explanation: "通过持续学习扩大理解范围，同时维持对未知领域的边界意识。", evidenceIndex: 0 },
    ],
  },
  "kaiming-he": {
    overview: "研究主线是让视觉模型更深、更可训练，并把监督学习中的结构经验推进到检测、分割与大规模自监督表征。页面只把论文可验证结论作为事实。",
    evolution: [
      "以深度残差学习解决超深网络优化困难，推动 ResNet 成为视觉系统的通用骨干。",
      "将统一的检测框架扩展到像素级实例分割，形成 Mask R-CNN。",
      "转向可扩展自监督学习，以遮挡重建研究视觉表征的预训练方法。",
      "持续研究视觉模型结构、学习目标与规模化之间的关系。",
    ],
    concepts: [
      { name: "深度残差学习", explanation: "通过学习相对恒等映射的残差函数，使显著更深的网络能够稳定优化。", evidenceIndex: 1 },
      { name: "实例分割", explanation: "在目标检测的基础上增加并行掩码分支，把分类、定位与像素级分割纳入统一框架。", evidenceIndex: 2 },
      { name: "自监督学习", explanation: "用大比例遮挡后的图像重建任务学习无需人工标签的视觉表示。", evidenceIndex: 3 },
      { name: "可扩展视觉表征", explanation: "关注模型结构、训练规模和学习目标能否共同形成可迁移的通用表示。", evidenceIndex: 4 },
    ],
  },
  "shunyu-yao": {
    overview: "研究主线是把语言模型从只生成文本推进到可观察、可行动、可评测的智能体，并讨论预训练之后如何从环境反馈继续学习。",
    evolution: [
      "以 ReAct 将推理轨迹和外部行动交错组织，让模型在任务过程中获取新证据。",
      "以 Tree of Thoughts 探索多路径搜索、评估与回溯，而非固定为单条思维链。",
      "通过 SWE-bench 把真实软件仓库问题转化为可复现的智能体评测任务。",
      "在 The Second Half 中把研究重心转向预训练之后的环境、任务、反馈与持续学习。",
    ],
    concepts: [
      { name: "ReAct", explanation: "让语言模型交替产生推理步骤和环境动作，用观察结果修正后续决策。", evidenceIndex: 1 },
      { name: "Tree of Thoughts", explanation: "把中间思路视为可搜索状态，允许生成多个候选、评估并回溯。", evidenceIndex: 2 },
      { name: "智能体评测", explanation: "以真实 GitHub 问题检验模型能否理解代码库、修改程序并通过测试。", evidenceIndex: 3 },
      { name: "The Second Half", explanation: "强调预训练之后的真实环境学习、任务设计和可验证结果将成为下一阶段研究中心。", evidenceIndex: 4 },
    ],
  },
};

export function getPersonProfile(person: Person): PersonProfile {
  return (
    personProfiles[person.slug] ?? {
      overview: person.summary,
      evolution: [],
      concepts: person.concepts.map((name, index) => ({
        name,
        explanation: person.summary,
        evidenceIndex: Math.min(index, person.materials.length - 1),
      })),
    }
  );
}

export type ReportContent = {
  thesis: string;
  points: { title: string; body: string }[];
  companySlugs: string[];
  eventSectors: string[];
  watchlist: string[];
};

export const reportContent: Record<string, ReportContent> = {
  "ai-capital-2026": {
    thesis:
      "前沿 AI 的竞争已同时发生在模型、算力、分发和企业工作流四层；融资规模只能解释资本供给，真正的经营验证来自使用量、单位推理成本和企业续约。",
    points: [
      { title: "资本密度继续上升", body: "模型训练、推理集群和数据中心使头部公司的资金需求显著高于传统软件创业公司。" },
      { title: "分发成为第二战场", body: "消费者入口、开发者 API、云平台和企业智能体共同决定模型能力如何转化为收入。" },
      { title: "效率比参数更可比", body: "单位任务成本、推理速度、工具使用成功率和客户留存更接近可持续竞争力。" },
    ],
    companySlugs: ["openai", "anthropic", "xai", "deepseek", "databricks", "scale-ai"],
    eventSectors: ["AI / AGI"],
    watchlist: ["推理价格与单位成本", "企业合同续约", "新增算力投产时间", "开源模型对价格体系的影响"],
  },
  "humanoid-robotics": {
    thesis:
      "人形机器人正在从演示能力进入真实作业、制造和客户部署阶段，研究重点应从单次视频表现转向运行时长、任务成功率、维护成本和重复采购。",
    points: [
      { title: "模型与本体开始一体化", body: "视觉—语言—行动模型逐步承担感知、规划和控制，硬件设计也围绕数据闭环重新优化。" },
      { title: "真实场景定义产品", body: "汽车制造、物流和零售配送中心提供了可量化的任务、节拍和安全边界。" },
      { title: "制造能力进入估值逻辑", body: "零部件自研、装配良率、供应链和售后体系决定从原型走向规模交付的速度。" },
    ],
    companySlugs: ["figure-ai", "unitree", "fourier-intelligence", "agibot", "galbot"],
    eventSectors: ["机器人"],
    watchlist: ["累计作业小时", "单机任务成功率", "量产节奏", "客户从试点到扩单"],
  },
  "ai-chips": {
    thesis:
      "AI 芯片竞争不是单点算力比较，而是芯片、内存、互连、编译器和服务交付共同决定的系统竞争。",
    points: [
      { title: "训练与推理路线分化", body: "训练看大规模并行和生态，推理更关注延迟、吞吐、功耗与部署灵活性。" },
      { title: "软件决定迁移成本", body: "编译器、框架适配和开发者工具决定客户能否把理论性能转化为实际工作负载收益。" },
      { title: "供给约束仍是核心", body: "先进制造、封装、内存和系统交付决定可销售产能，不能只看芯片发布。" },
    ],
    companySlugs: ["cerebras", "groq", "sambanova", "biren", "moore-threads", "horizon-robotics", "cambricon"],
    eventSectors: ["半导体"],
    watchlist: ["客户量产部署", "软件生态", "供货与库存", "推理总拥有成本"],
  },
  "space-commercialization": {
    thesis:
      "商业航天的验证顺序是任务可靠性、发射或在轨频次、订单转化和现金流；技术里程碑只有进入稳定运营后才形成经济价值。",
    points: [
      { title: "频次放大复用价值", body: "高频任务使制造、发射场、回收和运维体系形成学习曲线。" },
      { title: "业务从发射向系统延伸", body: "卫星平台、航天器、在轨制造和通信服务扩大了单次任务之外的收入来源。" },
      { title: "新火箭带来双重影响", body: "更大运力打开新市场，同时也提高研发支出、进度和执行风险。" },
    ],
    companySlugs: ["spacex", "rocket-lab", "relativity-space", "varda", "landspace", "galactic-energy"],
    eventSectors: ["商业航天"],
    watchlist: ["任务成功率", "年度发射频次", "订单储备转化", "新运载系统研发现金流"],
  },
  "autonomous-driving": {
    thesis:
      "Robotaxi 正从牌照与示范运营进入车队扩张和付费订单阶段；评估重点是每车利用率、远程支持成本、城市复制速度和整车合作。",
    points: [
      { title: "规模指标开始可见", body: "上市公司公告逐步提供车队、订单、收入和城市覆盖信息，为运营效率比较提供基础。" },
      { title: "前装与运营并行", body: "Robotaxi 运营形成数据闭环，乘用车前装方案扩大出货与商业化路径。" },
      { title: "全球扩张依赖伙伴", body: "出行平台、车企和本地运营商帮助进入新市场，也带来收入分成与执行复杂度。" },
    ],
    companySlugs: ["pony-ai", "weride", "aurora", "mobileye"],
    eventSectors: ["机器人"],
    watchlist: ["付费订单与每车利用率", "安全员/远程支持成本", "城市扩张", "前装车型量产"],
  },
};

export type IpoProfile = {
  exchange: string;
  listedAt: string;
  description: string;
  watchItems: string[];
};

export const ipoProfiles: Record<string, IpoProfile> = {
  cambricon: { exchange: "上海证券交易所科创板", listedAt: "2020-07-20", description: "AI 芯片与基础系统软件公司。", watchItems: ["云端产品收入", "研发投入", "客户集中度"] },
  catl: { exchange: "深圳证券交易所创业板", listedAt: "2018-06-11", description: "动力电池与储能系统公司。", watchItems: ["动力电池出货", "储能业务", "海外产能"] },
  "bgi-genomics": { exchange: "深圳证券交易所创业板", listedAt: "2017-07-14", description: "基因检测与多组学服务公司。", watchItems: ["检测服务收入", "研发投入", "海外业务"] },
  "horizon-robotics": { exchange: "香港交易所主板", listedAt: "2024-10-24", description: "乘用车高级辅助驾驶计算方案提供商。", watchItems: ["征程芯片出货", "软件收入", "车企定点"] },
  xtalpi: { exchange: "香港交易所主板", listedAt: "2024-06-13", description: "AI、量子物理与自动化实验驱动的药物和材料研发平台。", watchItems: ["项目收入", "合作里程碑", "研发现金消耗"] },
  "pony-ai": { exchange: "NASDAQ", listedAt: "2024-11-27", description: "Robotaxi 与自动驾驶卡车技术及运营公司。", watchItems: ["Robotaxi 收入", "车队规模", "运营现金流"] },
  weride: { exchange: "NASDAQ", listedAt: "2024-10-25", description: "覆盖多类自动驾驶产品和运营场景的技术公司。", watchItems: ["车队与城市覆盖", "前装方案", "海外部署"] },
  rigetti: { exchange: "NASDAQ", listedAt: "2022-03-02", description: "超导量子处理器与云端量子服务公司。", watchItems: ["量子比特路线图", "研发收入", "现金储备"] },
  ionq: { exchange: "NYSE", listedAt: "2021-10-01", description: "离子阱量子计算系统与云服务公司。", watchItems: ["技术里程碑", "订单储备", "研发投入"] },
  "rocket-lab": { exchange: "NASDAQ", listedAt: "2021-08-25", description: "发射服务、航天系统与运载火箭公司。", watchItems: ["发射频次", "航天系统收入", "Neutron 进度"] },
  "tempus-ai": { exchange: "NASDAQ", listedAt: "2024-06-14", description: "临床数据与 AI 精准医疗平台。", watchItems: ["数据与服务收入", "毛利率", "研发投入"] },
  recursion: { exchange: "NASDAQ", listedAt: "2021-04-16", description: "计算生物学与自动化实验驱动的药物研发公司。", watchItems: ["临床里程碑", "合作收入", "现金消耗"] },
  mobileye: { exchange: "NASDAQ", listedAt: "2022-10-26", description: "高级辅助驾驶芯片、软件与自动驾驶方案提供商。", watchItems: ["EyeQ 出货", "设计定点", "驾驶方案收入"] },
  aurora: { exchange: "NASDAQ", listedAt: "2021-11-04", description: "面向无人卡车和出行的自动驾驶系统公司。", watchItems: ["商业运营里程", "合作车队", "现金消耗"] },
  joby: { exchange: "NYSE", listedAt: "2021-08-11", description: "电动垂直起降飞行器与空中出行公司。", watchItems: ["认证进度", "试生产", "商业运营准备"] },
};
