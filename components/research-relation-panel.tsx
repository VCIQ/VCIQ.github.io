import { ArrowUpRight, Building2, Network, Users } from "lucide-react";
import Link from "next/link";
import {
  getCompanyResearchRelations,
  getPersonResearchRelations,
  getTrackResearchRelations,
  type ResearchRelationLink,
} from "@/lib/research-relations";
import styles from "./research-relation-panel.module.css";

type ResearchRelationPanelProps =
  | { kind: "company"; slug: string }
  | { kind: "person"; slug: string }
  | { kind: "track"; slug: string };

type RelationGroup = {
  title: string;
  description: string;
  href: string;
  icon: typeof Network;
  items: ResearchRelationLink[];
};

function linkList(items: ResearchRelationLink[], empty: string) {
  if (!items.length) return <p className={styles.empty}>{empty}</p>;
  return (
    <div className={styles.links}>
      {items.map((item) => (
        <Link href={item.href} key={`${item.href}-${item.slug}`}>
          <span>
            <strong>{item.name}</strong>
            {item.meta ? <small>{item.meta}</small> : null}
          </span>
          <ArrowUpRight size={14} aria-hidden="true" />
        </Link>
      ))}
    </div>
  );
}

export function ResearchRelationPanel(props: ResearchRelationPanelProps) {
  let groups: RelationGroup[] = [];
  let lead = "";

  if (props.kind === "company") {
    const relations = getCompanyResearchRelations(props.slug);
    const peerCompanies = relations.tracks[0]
      ? getTrackResearchRelations(relations.tracks[0].slug).companies
          .filter((company) => company.slug !== props.slug)
          .slice(0, 6)
      : [];
    groups = [
      {
        title: "赛道与技术",
        description: "公司所处的产业结构与可验证技术变量。",
        href: "/technologies/",
        icon: Network,
        items: [...relations.tracks, ...relations.topics].slice(0, 8),
      },
      {
        title: "关键人物",
        description: "仅展示已有任职或组织证据的人物关系。",
        href: "/people/",
        icon: Users,
        items: relations.people.slice(0, 6),
      },
      {
        title: "同赛道公司",
        description: "用于产品路线、商业化与资本结果的横向验证。",
        href: "/companies/",
        icon: Building2,
        items: peerCompanies,
      },
    ];
    lead = "从赛道变量进入公司结果，再回到人物决策与同赛道对照。";
  } else if (props.kind === "person") {
    const relations = getPersonResearchRelations(props.slug);
    const relatedCompanies = relations.companies.slice(0, 8);
    const peerCompanies = relations.tracks[0]
      ? getTrackResearchRelations(relations.tracks[0].slug).companies
          .filter((company) => !relatedCompanies.some((item) => item.slug === company.slug))
          .slice(0, 6)
      : [];
    groups = [
      {
        title: "赛道与技术",
        description: "人物公开工作所对应的产业方向与技术主题。",
        href: "/technologies/",
        icon: Network,
        items: [...relations.tracks, ...relations.topics].slice(0, 8),
      },
      {
        title: "任职与关联公司",
        description: "只使用已验证的组织与公司别名关系。",
        href: "/companies/",
        icon: Building2,
        items: relatedCompanies,
      },
      {
        title: "赛道验证样本",
        description: "用同赛道公司事件检验人物判断是否转化为执行结果。",
        href: "/companies/",
        icon: Building2,
        items: peerCompanies,
      },
    ];
    lead = "人物研究解释决策与路线，但最终仍需由公司产品、经营和资本事件验证。";
  } else {
    const relations = getTrackResearchRelations(props.slug);
    groups = [
      {
        title: "技术主题",
        description: "将宽赛道拆解为可持续跟踪的稳定技术变量。",
        href: "/technologies/",
        icon: Network,
        items: relations.topics.slice(0, 10),
      },
      {
        title: "关键人物",
        description: "解释路线选择、组织建设和公开判断的决策者。",
        href: "/people/",
        icon: Users,
        items: relations.people.slice(0, 8),
      },
      {
        title: "代表公司",
        description: "用产品、客户、融资和资本市场结果验证赛道判断。",
        href: "/companies/",
        icon: Building2,
        items: relations.companies.slice(0, 10),
      },
    ];
    lead = "赛道提供结构，人物解释决策，公司给出结果；三者共同形成可回溯研究闭环。";
  }

  if (!groups.some((group) => group.items.length)) return null;

  return (
    <div className={styles.shell}>
      <section className={styles.panel} aria-labelledby="related-research-objects-title">
        <header>
          <div>
            <p>CONNECTED RESEARCH OBJECTS</p>
            <h2 id="related-research-objects-title">关联研究对象</h2>
          </div>
          <span>{lead}</span>
        </header>
        <div className={styles.grid}>
          {groups.map((group) => {
            const Icon = group.icon;
            return (
              <article key={group.title}>
                <div className={styles.groupTitle}>
                  <Icon size={17} aria-hidden="true" />
                  <div>
                    <h3>{group.title}</h3>
                    <p>{group.description}</p>
                  </div>
                  <Link href={group.href} aria-label={`查看全部${group.title}`}>
                    全部
                  </Link>
                </div>
                {linkList(group.items, "当前没有达到显式证据门槛的关系。")}
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
