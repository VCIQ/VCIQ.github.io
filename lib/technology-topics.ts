import type { TrackingResearchEntity } from "@/lib/tracking-entity-research";

export type TechnologyTopicDefinition = {
  slug: string;
  name: string;
  alertQuery: string;
  trackNames: string[];
  description: string;
  matchTerms: string[];
};

type TrackLike = {
  name: string;
  aliases?: string[];
};

type TechnologyEntityLike = Pick<
  TrackingResearchEntity,
  | "name"
  | "aliases"
  | "summary"
  | "reasons"
  | "notes"
  | "researchThesis"
  | "timeline"
>;

function normalizeTechnologyTerm(value: string) {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

export const technologyTopicDefinitions: TechnologyTopicDefinition[] = [
  {
    slug: "ai-agent",
    name: "AI 智能体",
    alertQuery: "AI Agent",
    trackNames: ["AI / AGI"],
    description: "面向可调用工具、执行任务和多智能体协作的 Agent 系统与基础设施。",
    matchTerms: [
      "AI Agent",
      "Agentic AI",
      "智能体",
      "A2A",
      "Agent Swarm",
      "Agent编译器",
      "Claude Agent",
      "multi-agent",
    ],
  },
  {
    slug: "large-models",
    name: "大模型",
    alertQuery: "大模型",
    trackNames: ["AI / AGI"],
    description: "基础模型、大语言模型及其训练、后训练和规模化能力演进。",
    matchTerms: [
      "大模型",
      "LLM",
      "large language model",
      "foundation model",
      "基础模型",
      "GPT",
      "Claude",
      "Gemini",
      "Qwen",
      "DeepSeek",
      "GLM",
      "Kimi",
      "MiniMax",
    ],
  },
  {
    slug: "reasoning-models",
    name: "推理模型",
    alertQuery: "推理模型",
    trackNames: ["AI / AGI"],
    description: "强调复杂推理、长程任务、规划与验证能力的新一代模型。",
    matchTerms: ["推理模型", "reasoning model", "reasoning", "推理能力", "长程推理"],
  },
  {
    slug: "multimodal-models",
    name: "多模态模型",
    alertQuery: "多模态模型",
    trackNames: ["AI / AGI"],
    description: "统一处理文本、图像、视频、语音与空间信息的模型与系统。",
    matchTerms: [
      "多模态",
      "multimodal",
      "VLM",
      "vision language",
      "vision-language",
      "视觉语言",
    ],
  },
  {
    slug: "world-models",
    name: "世界模型",
    alertQuery: "世界模型",
    trackNames: ["AI / AGI", "机器人"],
    description: "学习环境状态、物理规律与时序演化，用于预测、规划和具身决策。",
    matchTerms: ["世界模型", "world model", "world-model"],
  },
  {
    slug: "embodied-ai",
    name: "具身智能",
    alertQuery: "具身智能",
    trackNames: ["机器人"],
    description: "连接感知、推理、动作与真实物理世界交互的通用机器人智能。",
    matchTerms: [
      "具身智能",
      "embodied AI",
      "VLA",
      "Sim2Real",
      "机器人基础模型",
      "robot foundation model",
    ],
  },
  {
    slug: "humanoid-robots",
    name: "人形机器人",
    alertQuery: "人形机器人",
    trackNames: ["机器人"],
    description: "人形本体、灵巧操作、执行器和规模量产相关技术体系。",
    matchTerms: ["人形机器人", "humanoid robot", "humanoid", "灵巧手"],
  },
  {
    slug: "autonomous-driving",
    name: "自动驾驶",
    alertQuery: "自动驾驶",
    trackNames: ["机器人"],
    description: "Robotaxi、端到端驾驶、感知规划与车端自主系统。",
    matchTerms: [
      "自动驾驶",
      "robotaxi",
      "autonomous driving",
      "self-driving",
      "端到端驾驶",
    ],
  },
  {
    slug: "ai-chips",
    name: "AI 芯片",
    alertQuery: "AI芯片",
    trackNames: ["半导体", "AI / AGI"],
    description: "训练与推理加速器、专用计算架构和配套软件栈。",
    matchTerms: [
      "AI芯片",
      "AI accelerator",
      "AI加速器",
      "NPU",
      "TPU",
      "Wafer-Scale",
      "AI三芯",
    ],
  },
  {
    slug: "advanced-packaging",
    name: "先进封装",
    alertQuery: "先进封装",
    trackNames: ["半导体"],
    description: "Chiplet、2.5D/3D 集成、混合键合与高密度先进封装。",
    matchTerms: [
      "先进封装",
      "Chiplet",
      "3D IC",
      "2.5D",
      "CoWoS",
      "混合键合",
      "hybrid bonding",
      "三维集成",
    ],
  },
  {
    slug: "silicon-photonics",
    name: "硅光与光计算",
    alertQuery: "硅光",
    trackNames: ["半导体", "AI / AGI"],
    description: "硅光集成、光互连、CPO 与专用光计算体系。",
    matchTerms: [
      "硅光",
      "silicon photonics",
      "光互连",
      "CPO",
      "光计算",
      "optical computing",
    ],
  },
  {
    slug: "wide-bandgap-semiconductors",
    name: "宽禁带半导体",
    alertQuery: "宽禁带半导体",
    trackNames: ["半导体", "新材料"],
    description: "GaN、SiC、Ga₂O₃ 等宽禁带与超宽禁带功率/射频半导体。",
    matchTerms: [
      "宽禁带半导体",
      "宽禁带",
      "氧化镓",
      "Ga2O3",
      "氮化镓",
      "GaN",
      "碳化硅",
      "SiC",
    ],
  },
  {
    slug: "6g",
    name: "6G",
    alertQuery: "6G",
    trackNames: ["无线互联网", "商业航天"],
    description: "下一代移动通信、空天地融合网络和关键通信基础设施。",
    matchTerms: ["6G", "第六代移动通信", "空天地一体化"],
  },
  {
    slug: "ai-ran",
    name: "AI-RAN",
    alertQuery: "AI-RAN",
    trackNames: ["无线互联网", "AI / AGI"],
    description: "AI 与无线接入网融合，包括基站算力、智能调度与网络自治。",
    matchTerms: ["AI-RAN", "AI RAN", "RAN智能", "无线接入网AI"],
  },
  {
    slug: "satellite-internet",
    name: "卫星互联网",
    alertQuery: "卫星互联网",
    trackNames: ["商业航天", "无线互联网"],
    description: "低轨星座、卫星物联网、卫星移动通信与终端网络服务。",
    matchTerms: [
      "卫星互联网",
      "satellite internet",
      "卫星物联网",
      "satellite IoT",
      "低轨卫星",
      "LEO",
    ],
  },
  {
    slug: "solid-state-batteries",
    name: "固态电池",
    alertQuery: "固态电池",
    trackNames: ["新能源", "新材料"],
    description: "固态与半固态电池体系、材料路线和规模化制造进展。",
    matchTerms: ["固态电池", "solid-state battery", "固液混合电池", "半固态电池"],
  },
  {
    slug: "fusion-energy",
    name: "可控核聚变",
    alertQuery: "可控核聚变",
    trackNames: ["可控核聚变"],
    description: "磁约束、惯性约束、聚变装置与商业电站工程化。",
    matchTerms: [
      "可控核聚变",
      "fusion energy",
      "tokamak",
      "托卡马克",
      "stellarator",
      "仿星器",
    ],
  },
  {
    slug: "quantum-computing",
    name: "量子计算",
    alertQuery: "量子计算",
    trackNames: ["量子计算"],
    description: "量子处理器、纠错、控制系统、软件栈和早期应用。",
    matchTerms: [
      "量子计算",
      "quantum computing",
      "量子纠错",
      "quantum error correction",
      "量子处理器",
      "qubit",
    ],
  },
  {
    slug: "ai-drug-discovery",
    name: "AI 制药",
    alertQuery: "AI制药",
    trackNames: ["生物科技", "AI / AGI"],
    description: "AI 药物发现、计算生物学、蛋白与分子设计平台。",
    matchTerms: [
      "AI制药",
      "AI drug discovery",
      "计算生物学",
      "computational biology",
      "AlphaFold",
      "BioNeMo",
      "AI药物",
    ],
  },
  {
    slug: "stablecoins",
    name: "稳定币",
    alertQuery: "稳定币",
    trackNames: ["Web3"],
    description: "稳定币、RWA、链上支付和机构级数字资产基础设施。",
    matchTerms: [
      "稳定币",
      "stablecoin",
      "RWA",
      "real world asset",
      "链上支付",
      "tokenized asset",
    ],
  },
];

export function technologyTopicsForTrack(track: TrackLike) {
  const trackKeys = new Set(
    [track.name, ...(track.aliases ?? [])]
      .map(normalizeTechnologyTerm)
      .filter(Boolean),
  );
  return technologyTopicDefinitions.filter((topic) =>
    topic.trackNames.some((name) => trackKeys.has(normalizeTechnologyTerm(name))),
  );
}

export function technologyTopicsForEntity(entity: TechnologyEntityLike) {
  const corpus = [
    entity.name,
    ...entity.aliases,
    entity.summary,
    ...entity.reasons,
    ...entity.notes,
    entity.researchThesis,
    ...entity.timeline.flatMap((item) => [item.title, item.summary]),
  ]
    .filter(Boolean)
    .join(" ");
  const normalizedCorpus = normalizeTechnologyTerm(corpus);

  return technologyTopicDefinitions.filter((topic) =>
    topic.matchTerms.some((term) => {
      const normalizedTerm = normalizeTechnologyTerm(term);
      return normalizedTerm.length >= 2 && normalizedCorpus.includes(normalizedTerm);
    }),
  );
}
