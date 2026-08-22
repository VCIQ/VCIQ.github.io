import type { PersonMaterial, ResearchPerson } from "@/lib/people-data";
import {
  clusterPersonEventItems,
  type PersonEventCluster,
} from "@/lib/person-event-clustering";
import { getPersonProfile } from "@/lib/research-content";

export type PersonMaterialEvent = PersonEventCluster<
  PersonMaterial & { href: string; context: string }
>;

export type PersonResearchConcept = {
  name: string;
  explanation: string;
  evidence: PersonMaterial | null;
};

export type PersonResearchTimelineItem = {
  label: string;
  statement: string;
  evidence: PersonMaterial | null;
};

export type PersonResearchSnapshot = {
  whyImportant: string;
  latestChange: PersonMaterial | null;
  nextWatch: string;
  researchOverview: string;
  coreConcepts: PersonResearchConcept[];
  evolution: PersonResearchTimelineItem[];
  hasVerifiedEvolution: boolean;
  events: PersonMaterialEvent[];
};

function compact(value: string) {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

function distinctFrom(value: string, comparisons: string[]) {
  const normalized = compact(value);
  if (!normalized || normalized.length < 24) return false;
  return comparisons.every((comparison) => compact(comparison) !== normalized);
}

function materialScore(material: PersonMaterial) {
  const typeScore: Record<string, number> = {
    official_profile: 95,
    research_paper: 92,
    authored_work: 90,
    shareholder_letter: 88,
    public_document: 82,
    public_post: 78,
    speech: 74,
    qa: 70,
    interview: 68,
    biography: 55,
    compiled_work: 45,
    commentary: 35,
  };
  const sourceBonus = /官方|官网|本人|arxiv|sec|github/i.test(material.source) ? 12 : 0;
  return (typeScore[material.type] ?? 50) + sourceBonus;
}

export function clusterPersonMaterials(
  materials: PersonMaterial[],
  personName: string,
  referenceDate?: string,
): PersonMaterialEvent[] {
  const prepared = materials.map((material) => ({
    ...material,
    href: material.url,
    context: personName,
  }));
  return clusterPersonEventItems(prepared, {
    referenceDate,
    scopeKey: (item) => item.context,
    representativeScore: materialScore,
  });
}

function focusLabels(person: ResearchPerson) {
  const seen = new Set<string>();
  return [...person.sectors, ...person.concepts]
    .filter((value) => {
      const key = compact(value);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, 4);
}

function whyImportant(person: ResearchPerson) {
  const focus = focusLabels(person).slice(0, 2).join("、");
  const roleReady = person.role && !/(待补充|待抓取|待完善)/u.test(person.role);
  if (roleReady) {
    return `${person.name}目前以“${person.role}”为主要公开身份${focus ? `，持续关联${focus}` : ""}。跟踪价值在于观察其公开判断、技术或产品动作与所属组织的实际执行是否持续指向同一方向，而不是以材料数量替代影响力判断。`;
  }
  return `${person.name}已进入人物观察池${focus ? `，当前关联${focus}` : ""}，但身份与任职资料仍需继续核验。现阶段只把可追溯公开材料作为研究依据，不把自动抓取数量直接解释为人物影响力。`;
}

function nextWatch(person: ResearchPerson) {
  const text = [...person.sectors, ...person.concepts, ...person.products].join(" ");
  if (/机器人|具身|physical ai/i.test(text)) {
    return "下一步重点观察真实场景部署、量产节奏、数据闭环、模型控制，以及公开能力描述能否被产品交付验证。";
  }
  if (/半导体|芯片|gpu|加速器|chiplet|光刻/i.test(text)) {
    return "下一步重点观察量产供货、客户验证、系统级性能、软件生态与成本曲线，区分技术样片与可规模化商业交付。";
  }
  if (/人工智能|大模型|ai|模型|agent|智能体|world model|世界模型/i.test(text)) {
    return "下一步重点观察模型或产品发布、能力边界、推理成本、企业采用与基础设施动作，并核对公开判断是否转化为实际路线。";
  }
  if (/卫星|航天|6g|通信/i.test(text)) {
    return "下一步重点观察发射与组网进度、商用许可、客户交付、基础设施投入和单位经济性。";
  }
  if (/电池|储能|新能源|光伏/i.test(text)) {
    return "下一步重点观察量产良率、客户验证、成本下降、产能利用率与商业化节奏。";
  }
  if (/投资|资本|基金|vc|venture/i.test(text)) {
    return "下一步重点观察资本配置、组合变化、退出动作，以及其对技术周期的公开判断是否反映到实际投资行为。";
  }
  return "下一步重点观察下一次可核验的产品、技术、组织或资本动作，以及公开判断是否与实际执行保持一致。";
}

function researchOverview(person: ResearchPerson, curatedOverview: string) {
  if (distinctFrom(curatedOverview, [person.summary, person.background])) return curatedOverview;
  const focuses = focusLabels(person);
  if (!focuses.length) {
    return "当前材料尚不足以形成稳定研究主线。后续只有当同一主题在公开表达、产品或项目、论文或著作及组织动作中获得重复证据时，才升级为人物长期研究主线。";
  }
  return `当前研究主线围绕${focuses.join("、")}展开。判断主线是否成立时，优先核对同一主题能否在论文或著作、演讲采访、产品项目与组织动作之间相互印证；单次媒体表述不直接升级为长期观点。`;
}

function conceptEvidence(
  person: ResearchPerson,
  conceptName: string,
  evidenceIndex: number,
  curatedExplanation: boolean,
  events: PersonMaterialEvent[],
) {
  if (curatedExplanation && person.materials.length) {
    return person.materials[Math.min(Math.max(evidenceIndex, 0), person.materials.length - 1)] ?? null;
  }
  const target = compact(conceptName);
  if (!target) return null;
  for (const event of events) {
    const match = event.items.find((material) => compact(material.title).includes(target));
    if (match) return match;
  }
  return null;
}

function coreConcepts(
  person: ResearchPerson,
  events: PersonMaterialEvent[],
): PersonResearchConcept[] {
  const profile = getPersonProfile(person);
  return profile.concepts.map((concept) => {
    const curatedExplanation = distinctFrom(concept.explanation, [person.summary, person.background]);
    return {
      name: concept.name,
      explanation: curatedExplanation
        ? concept.explanation
        : `${concept.name}是当前档案中的持续观察主题。重点核对它在公开表达、论文或产品与组织动作中的具体落点，并区分长期方法论与单次媒体表述。`,
      evidence: conceptEvidence(
        person,
        concept.name,
        concept.evidenceIndex,
        curatedExplanation,
        events,
      ),
    };
  });
}

function evolutionTimeline(
  person: ResearchPerson,
  events: PersonMaterialEvent[],
): { items: PersonResearchTimelineItem[]; verified: boolean } {
  const profile = getPersonProfile(person);
  if (profile.evolution.length) {
    return {
      verified: true,
      items: profile.evolution.map((statement, index) => ({
        label: `阶段 ${String(index + 1).padStart(2, "0")}`,
        statement,
        evidence: null,
      })),
    };
  }

  const chronological = [...events].reverse();
  if (!chronological.length) return { verified: false, items: [] };
  const indexes = chronological.length <= 3
    ? chronological.map((_, index) => index)
    : [0, Math.floor((chronological.length - 1) / 2), chronological.length - 1];
  const selected = [...new Set(indexes)].map((index) => chronological[index]);
  return {
    verified: false,
    items: selected.map((event) => {
      const material = event.representative;
      return {
        label: material.date || "日期待核验",
        statement: material.title,
        evidence: material,
      };
    }),
  };
}

export function getPersonResearchSnapshot(person: ResearchPerson): PersonResearchSnapshot {
  const profile = getPersonProfile(person);
  const events = clusterPersonMaterials(person.materials, person.name, person.updatedAt);
  const timeline = evolutionTimeline(person, events);
  return {
    whyImportant: whyImportant(person),
    latestChange: events[0]?.representative ?? null,
    nextWatch: nextWatch(person),
    researchOverview: researchOverview(person, profile.overview),
    coreConcepts: coreConcepts(person, events),
    evolution: timeline.items,
    hasVerifiedEvolution: timeline.verified,
    events,
  };
}
