import type { PersonMaterial, ResearchPerson } from "@/lib/people-data";
import {
  clusterPersonEventItems,
  personEventDateMs,
  personEventTitleSimilarity,
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

export type PersonViewChangeAssessment = {
  kind: "reinforced" | "shift" | "reversal" | "unchanged";
  confidence: "supported" | "candidate" | "insufficient";
  label: string;
  summary: string;
  evidence: PersonMaterial[];
};

export type PersonResearchCoverage = {
  score: number;
  label: "较完整" | "可用" | "待补充";
  gaps: string[];
  firstPartyCount: number;
  directExpressionEventCount: number;
  freshnessDays: number | null;
};

export type PersonResearchPriority = {
  level: "P0" | "P1" | "P2" | "P3";
  score: number;
  reasons: string[];
};

export type PersonResearchImplication = {
  dimension: "组织" | "技术 / 产品" | "赛道" | "证据性质";
  target: string;
  statement: string;
};

export type PersonResearchSnapshot = {
  whyImportant: string;
  latestChange: PersonMaterial | null;
  nextWatch: string;
  researchOverview: string;
  coreConcepts: PersonResearchConcept[];
  evolution: PersonResearchTimelineItem[];
  hasVerifiedEvolution: boolean;
  viewChange: PersonViewChangeAssessment;
  coverage: PersonResearchCoverage;
  priority: PersonResearchPriority;
  latestImplications: PersonResearchImplication[];
  events: PersonMaterialEvent[];
};

const DAY_MS = 24 * 60 * 60 * 1000;
const FIRST_PARTY_TYPES = new Set([
  "official_profile",
  "authored_work",
  "research_paper",
  "shareholder_letter",
  "public_post",
  "public_document",
  "speech",
  "qa",
]);
const DIRECT_EXPRESSION_TYPES = new Set([
  "authored_work",
  "research_paper",
  "shareholder_letter",
  "public_post",
  "speech",
  "qa",
  "interview",
]);
const SHIFT_MARKERS = /转向|转而|改为|重新聚焦|重心转|pivot|shift(?:ed|ing)?|move(?:d)? from|instead of/iu;
const REVERSAL_MARKERS = /改口|推翻|撤回|承认.{0,12}错|不再认为|changed my mind|was wrong|no longer believe|retract|reverse(?:d)?/iu;

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
  const sourceBonus = /官方|官网|本人|arxiv|sec|github|大学|研究院|实验室/i.test(material.source) ? 12 : 0;
  return (typeScore[material.type] ?? 50) + sourceBonus;
}

const LOW_SIGNAL_TITLE_MARKERS = /must watch|leaves audience speechless|震惊|炸裂|刷屏|全网热议|重磅突发|笑了.{0,12}哭了|附文稿|生肉|搬运/iu;

function materialDirectlyNamesPerson(material: PersonMaterial, person: ResearchPerson) {
  return [person.name, person.englishName, ...person.aliases]
    .filter((name): name is string => Boolean(name?.trim()))
    .some((name) => titleIncludes(material.title, name));
}

function materialMatchesResearchObject(material: PersonMaterial, person: ResearchPerson) {
  return [...person.organizations, ...person.products, ...person.concepts]
    .filter((value) => value.trim().length >= 2)
    .some((value) => titleIncludes(material.title, value));
}

function latestResearchChange(person: ResearchPerson, events: PersonMaterialEvent[]) {
  for (const event of events) {
    const candidates = [...event.items]
      .filter((material) => !LOW_SIGNAL_TITLE_MARKERS.test(material.title))
      .filter((material) =>
        DIRECT_EXPRESSION_TYPES.has(material.type)
        || materialDirectlyNamesPerson(material, person)
        || materialMatchesResearchObject(material, person))
      .sort((left, right) => materialScore(right) - materialScore(left));
    if (candidates[0]) return candidates[0];
  }
  return events[0]?.representative ?? null;
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
    .slice(0, 6);
}

function whyImportant(person: ResearchPerson) {
  const focus = focusLabels(person).slice(0, 2).join("、");
  const roleReady = person.role && !/(待补充|待抓取|待完善)/u.test(person.role);
  if (roleReady) {
    return `${person.name}目前以“${person.role}”为主要公开身份${focus ? `，持续关联${focus}` : ""}。跟踪价值在于观察其公开判断、技术或产品动作与所属组织的实际执行是否持续指向同一方向，而不是以材料数量替代影响力判断。`;
  }
  return `${person.name}已进入人物观察池${focus ? `，当前关联${focus}` : ""}，但身份与任职资料仍需继续核验。现阶段只把可追溯公开材料作为研究依据，不把自动抓取数量直接解释为人物影响力。`;
}

function researchOverview(person: ResearchPerson, curatedOverview: string) {
  if (distinctFrom(curatedOverview, [person.summary, person.background])) return curatedOverview;
  const focuses = focusLabels(person).slice(0, 4);
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

function directExpressionMaterial(event: PersonMaterialEvent) {
  return [...event.items]
    .filter((material) => DIRECT_EXPRESSION_TYPES.has(material.type))
    .sort((left, right) => materialScore(right) - materialScore(left))[0] ?? null;
}

function eventDateMs(event: PersonMaterialEvent, referenceDate?: string) {
  const sortAt = Date.parse(event.sortAt);
  if (Number.isFinite(sortAt)) return sortAt;
  return personEventDateMs(event.representative.date, referenceDate);
}

function stripPersonName(title: string, person: ResearchPerson) {
  let value = title;
  for (const name of [person.name, person.englishName, ...person.aliases]) {
    if (name?.trim()) value = value.replaceAll(name, " ");
  }
  return value;
}

function sharedFocus(person: ResearchPerson, leftTitle: string, rightTitle: string) {
  const left = compact(leftTitle);
  const right = compact(rightTitle);
  return focusLabels(person).some((focus) => {
    const key = compact(focus);
    return key.length >= 2 && left.includes(key) && right.includes(key);
  });
}

function relatedViewEvents(person: ResearchPerson, leftTitle: string, rightTitle: string) {
  const left = stripPersonName(leftTitle, person);
  const right = stripPersonName(rightTitle, person);
  return personEventTitleSimilarity(left, right) >= 0.44 || sharedFocus(person, left, right);
}

export function assessPersonViewChange(
  person: ResearchPerson,
  events: PersonMaterialEvent[],
): PersonViewChangeAssessment {
  const directEvents = events
    .flatMap((event) => {
      const material = directExpressionMaterial(event);
      const dateMs = eventDateMs(event, person.updatedAt);
      return material && dateMs ? [{ material, dateMs }] : [];
    })
    .sort((left, right) => right.dateMs - left.dateMs);

  for (let newerIndex = 0; newerIndex < directEvents.length; newerIndex += 1) {
    const newer = directEvents[newerIndex];
    for (let olderIndex = newerIndex + 1; olderIndex < directEvents.length; olderIndex += 1) {
      const older = directEvents[olderIndex];
      const daysApart = Math.round((newer.dateMs - older.dateMs) / DAY_MS);
      if (daysApart < 30) continue;
      if (!relatedViewEvents(person, newer.material.title, older.material.title)) continue;

      if (REVERSAL_MARKERS.test(newer.material.title)) {
        return {
          kind: "reversal",
          confidence: "candidate",
          label: "观点反转候选",
          summary: `较新的本人公开表达出现明确反转措辞，并与 ${daysApart} 天前的同主题材料形成关联。当前仍只标记为候选，需阅读全文或原始视频确认上下文后才能认定观点反转。`,
          evidence: [newer.material, older.material],
        };
      }
      if (SHIFT_MARKERS.test(newer.material.title)) {
        return {
          kind: "shift",
          confidence: "candidate",
          label: "观点转向候选",
          summary: `较新的本人公开表达出现转向措辞，并与 ${daysApart} 天前的同主题材料形成关联。当前仍只标记为候选，不把标题级变化直接升级为已确认的观点迁移。`,
          evidence: [newer.material, older.material],
        };
      }

      if (daysApart >= 45) {
        return {
          kind: "reinforced",
          confidence: "supported",
          label: "同一主线持续强化",
          summary: `两条相隔 ${daysApart} 天的本人公开表达、论文或著作仍围绕同一主题。现有证据更支持“主线持续强化”，而不是根据发布时间差异推断发生转向。`,
          evidence: [newer.material, older.material],
        };
      }
    }
  }

  return {
    kind: "unchanged",
    confidence: "insufficient",
    label: "暂无可验证变化",
    summary: "尚未找到由两条以上跨时间、可归因于本人的同主题证据支持的观点转向或反转。当前只记录公开材料时间线，不把媒体标题和发布时间差异解释为观点变化。",
    evidence: [],
  };
}

function uniqueByUrl(materials: PersonMaterial[]) {
  const seen = new Set<string>();
  return materials.filter((material) => {
    const key = material.url.trim().toLocaleLowerCase("en-US");
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function assessPersonResearchCoverage(
  person: ResearchPerson,
  events: PersonMaterialEvent[],
): PersonResearchCoverage {
  const roleReady = Boolean(person.role && !/(待补充|待抓取|待完善)/u.test(person.role));
  const firstParty = uniqueByUrl(person.materials.filter((material) => FIRST_PARTY_TYPES.has(material.type)));
  const directExpressionEvents = events
    .map((event) => ({ material: directExpressionMaterial(event), dateMs: eventDateMs(event, person.updatedAt) }))
    .filter((item) => item.material && item.dateMs)
    .sort((left, right) => left.dateMs - right.dateMs);
  const directSpanDays = directExpressionEvents.length >= 2
    ? Math.round((directExpressionEvents.at(-1)!.dateMs - directExpressionEvents[0].dateMs) / DAY_MS)
    : 0;
  const latestMs = Math.max(...events.map((event) => eventDateMs(event, person.updatedAt)), 0);
  const referenceMs = Date.parse(person.updatedAt);
  const freshnessDays = Number.isFinite(referenceMs) && referenceMs > 0 && latestMs > 0
    ? Math.max(0, Math.round((referenceMs - latestMs) / DAY_MS))
    : null;

  let score = 0;
  if (roleReady) score += 15;
  if (person.organizations.length) score += 15;
  if (focusLabels(person).length) score += 15;
  score += firstParty.length >= 2 ? 20 : firstParty.length === 1 ? 10 : 0;
  score += events.length >= 5 ? 15 : events.length >= 2 ? 10 : events.length === 1 ? 5 : 0;
  if (directExpressionEvents.length >= 2 && directSpanDays >= 30) score += 10;
  if (freshnessDays !== null && freshnessDays <= 180) score += 10;
  else if (freshnessDays === null && events.length) score += 5;
  score = Math.min(100, score);

  const gaps: string[] = [];
  if (!roleReady) gaps.push("身份或任职仍需核验");
  if (!person.organizations.length) gaps.push("缺少可核验的公司或机构关联");
  if (!focusLabels(person).length) gaps.push("缺少稳定的研究主题");
  if (firstParty.length < 2) gaps.push("缺少两条以上一手表达、论文或公开文件");
  if (directExpressionEvents.length < 2 || directSpanDays < 30) gaps.push("缺少跨时间的一手观点证据");
  if (freshnessDays !== null && freshnessDays > 180) gaps.push("缺少近 180 天可核验事件");
  if (events.length < 2) gaps.push("事件样本过少，无法形成稳定研究判断");

  return {
    score,
    label: score >= 80 ? "较完整" : score >= 60 ? "可用" : "待补充",
    gaps,
    firstPartyCount: firstParty.length,
    directExpressionEventCount: directExpressionEvents.length,
    freshnessDays,
  };
}

export function assessPersonResearchPriority(
  person: ResearchPerson,
  events: PersonMaterialEvent[],
  coverage: PersonResearchCoverage,
  viewChange: PersonViewChangeAssessment,
): PersonResearchPriority {
  let score = person.tracked ? 45 : 20;
  const reasons: string[] = [];
  if (person.tracked) reasons.push("已进入重点追踪池");
  if (person.role && !/(待补充|待抓取|待完善)/u.test(person.role)) score += 10;
  if (person.organizations.length) score += 5;
  if (person.concepts.length) score += 5;

  if (coverage.freshnessDays !== null) {
    if (coverage.freshnessDays <= 30) {
      score += 20;
      reasons.push("近 30 天出现可核验事件");
    } else if (coverage.freshnessDays <= 90) {
      score += 12;
      reasons.push("近 90 天仍有新事件");
    } else if (coverage.freshnessDays <= 180) {
      score += 6;
    }
  }

  if ((events[0]?.sourceCount ?? 0) >= 2) {
    score += 8;
    reasons.push("最新事件获得多信源交叉覆盖");
  }
  if (viewChange.kind === "shift" || viewChange.kind === "reversal") {
    score += 8;
    reasons.push(`${viewChange.label}需要优先核验`);
  } else if (viewChange.kind === "reinforced") {
    score += 4;
    reasons.push("长期主线获得跨时间重复证据");
  }
  if (coverage.gaps.length) reasons.push(`仍有 ${coverage.gaps.length} 项证据缺口`);

  score = Math.min(100, score);
  return {
    level: score >= 80 ? "P0" : score >= 60 ? "P1" : score >= 40 ? "P2" : "P3",
    score,
    reasons: reasons.slice(0, 4),
  };
}

function titleIncludes(title: string, target: string) {
  const normalizedTarget = compact(target);
  return normalizedTarget.length >= 2 && compact(title).includes(normalizedTarget);
}

function evidenceRole(material: PersonMaterial) {
  if (["research_paper", "authored_work"].includes(material.type)) {
    return "更接近技术路线或方法论的一手证据，可用于研究主线，但不能单独代表组织已经执行。";
  }
  if (["speech", "interview", "qa", "public_post"].includes(material.type)) {
    return "主要属于人物公开判断或表达证据；需要与产品、组织或资本动作交叉验证，不能直接等同于执行。";
  }
  if (["shareholder_letter", "public_document", "official_profile"].includes(material.type)) {
    return "属于较强的公开文件或治理类证据，适合与后续组织、产品和资本动作连续核对。";
  }
  return "当前主要是第三方或整理型材料，只作为旁证，不单独用于认定观点变化或组织执行。";
}

function latestImplications(person: ResearchPerson, events: PersonMaterialEvent[]): PersonResearchImplication[] {
  const latest = events[0]?.representative;
  if (!latest) return [];
  const implications: PersonResearchImplication[] = [];
  const title = latest.title;

  const organization = person.organizations.find((value) => titleIncludes(title, value));
  if (organization) {
    implications.push({
      dimension: "组织",
      target: organization,
      statement: `该事件直接涉及 ${organization}。后续应核对人物表述是否伴随该组织的产品、团队、资本或商业动作，避免把个人观点直接等同于公司战略。`,
    });
  }

  const productOrConcept = [...person.products, ...person.concepts].find((value) => titleIncludes(title, value));
  if (productOrConcept) {
    implications.push({
      dimension: "技术 / 产品",
      target: productOrConcept,
      statement: `该事件直接命中 ${productOrConcept}，可作为这条技术或产品主线的新增证据；下一步看是否出现性能、交付、采用或后续论文等可验证进展。`,
    });
  }

  const sector = person.sectors.find((value) => titleIncludes(title, value));
  if (sector) {
    implications.push({
      dimension: "赛道",
      target: sector,
      statement: `该事件与 ${sector} 赛道直接相关。应与同赛道公司、技术和资本事件交叉验证，再判断它是否改变行业趋势，而不是由单个人物事件外推赛道结论。`,
    });
  }

  if (!organization && !productOrConcept && !sector) {
    implications.push({
      dimension: "赛道",
      target: person.sectors[0] ?? person.concepts[0] ?? "现有研究主线",
      statement: "当前事件标题未直接命中既有公司、技术或赛道标签，因此只作为人物上下文保留，不自动扩展研究主线或改变行业判断。",
    });
  }

  implications.push({
    dimension: "证据性质",
    target: latest.source,
    statement: evidenceRole(latest),
  });
  return implications.slice(0, 4);
}

function nextWatch(
  person: ResearchPerson,
  coverage: PersonResearchCoverage,
  viewChange: PersonViewChangeAssessment,
) {
  const text = [...person.sectors, ...person.concepts, ...person.products].join(" ");
  const prefix = viewChange.kind === "shift" || viewChange.kind === "reversal"
    ? `优先核验“${viewChange.label}”所依赖的原始上下文；`
    : coverage.gaps.length
      ? `优先补齐“${coverage.gaps[0]}”；`
      : "";
  if (/机器人|具身|physical ai/i.test(text)) {
    return `${prefix}继续观察真实场景部署、量产节奏、数据闭环、模型控制，以及公开能力描述能否被产品交付验证。`;
  }
  if (/半导体|芯片|gpu|加速器|chiplet|光刻/i.test(text)) {
    return `${prefix}继续观察量产供货、客户验证、系统级性能、软件生态与成本曲线，区分技术样片与可规模化商业交付。`;
  }
  if (/人工智能|大模型|ai|模型|agent|智能体|world model|世界模型/i.test(text)) {
    return `${prefix}继续观察模型或产品发布、能力边界、推理成本、企业采用与基础设施动作，并核对公开判断是否转化为实际路线。`;
  }
  if (/卫星|航天|6g|通信/i.test(text)) {
    return `${prefix}继续观察发射与组网进度、商用许可、客户交付、基础设施投入和单位经济性。`;
  }
  if (/电池|储能|新能源|光伏/i.test(text)) {
    return `${prefix}继续观察量产良率、客户验证、成本下降、产能利用率与商业化节奏。`;
  }
  if (/投资|资本|基金|vc|venture/i.test(text)) {
    return `${prefix}继续观察资本配置、组合变化、退出动作，以及其对技术周期的公开判断是否反映到实际投资行为。`;
  }
  return `${prefix}继续观察下一次可核验的产品、技术、组织或资本动作，以及公开判断是否与实际执行保持一致。`;
}

function bestTimelineEvidence(statement: string, events: PersonMaterialEvent[]) {
  let best: { score: number; material: PersonMaterial } | null = null;
  for (const event of events) {
    for (const material of event.items) {
      const score = personEventTitleSimilarity(statement, material.title);
      if (score >= 0.42 && (!best || score > best.score)) best = { score, material };
    }
  }
  return best?.material ?? null;
}

function evolutionTimeline(
  person: ResearchPerson,
  events: PersonMaterialEvent[],
): { items: PersonResearchTimelineItem[]; verified: boolean } {
  const profile = getPersonProfile(person);
  if (profile.evolution.length) {
    const items = profile.evolution.map((statement, index) => ({
      label: `阶段 ${String(index + 1).padStart(2, "0")}`,
      statement,
      evidence: bestTimelineEvidence(statement, events),
    }));
    return {
      verified: items.length >= 2 && items.every((item) => Boolean(item.evidence)),
      items,
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
  const coverage = assessPersonResearchCoverage(person, events);
  const viewChange = assessPersonViewChange(person, events);
  const timeline = evolutionTimeline(person, events);
  return {
    whyImportant: whyImportant(person),
    latestChange: latestResearchChange(person, events),
    nextWatch: nextWatch(person, coverage, viewChange),
    researchOverview: researchOverview(person, profile.overview),
    coreConcepts: coreConcepts(person, events),
    evolution: timeline.items,
    hasVerifiedEvolution: timeline.verified,
    viewChange,
    coverage,
    priority: assessPersonResearchPriority(person, events, coverage, viewChange),
    latestImplications: latestImplications(person, events),
    events,
  };
}
