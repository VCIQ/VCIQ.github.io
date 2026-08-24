import { ArrowRight, Building2, Network, Users } from "lucide-react";
import Link from "next/link";
import { researchSynergySummary } from "@/lib/research-relations";
import styles from "./research-synergy-strip.module.css";

const pillars = [
  {
    href: "/technologies/",
    label: "赛道与技术",
    eyebrow: "STRUCTURE & VARIABLES",
    count: `${researchSynergySummary.trackCount} 赛道 · ${researchSynergySummary.topicCount} 主题`,
    description: "定义产业结构、技术变量、发展阶段和需要持续验证的关键问题。",
    icon: Network,
  },
  {
    href: "/people/",
    label: "人物",
    eyebrow: "DECISIONS & EXECUTION",
    count: `${researchSynergySummary.peopleCount} 位研究对象`,
    description: "解释技术判断、组织选择和路线演进，连接决策者与其公开证据。",
    icon: Users,
  },
  {
    href: "/companies/",
    label: "公司",
    eyebrow: "PRODUCTS & OUTCOMES",
    count: `${researchSynergySummary.companyCount} 家公司`,
    description: "验证产品、商业化、融资与资本结果，把研究判断落到真实经营变化。",
    icon: Building2,
  },
] as const;

type ResearchSynergyStripProps = {
  compactOnMobile?: boolean;
};

export function ResearchSynergyStrip({
  compactOnMobile = false,
}: ResearchSynergyStripProps) {
  return (
    <section
      className={`${styles.section}${compactOnMobile ? ` ${styles.compactMobile}` : ""}`}
      aria-labelledby="research-synergy-title"
    >
      <header className={styles.header}>
        <div>
          <p>RESEARCH OBJECT GRAPH</p>
          <h2 id="research-synergy-title">赛道与技术、人物、公司协同研究</h2>
        </div>
        <span>
          先用赛道确定变量，再用人物解释决策，最后用公司事件验证结果。
        </span>
      </header>
      <div className={styles.grid}>
        {pillars.map((pillar, index) => {
          const Icon = pillar.icon;
          return (
            <Link href={pillar.href} className={styles.card} key={pillar.href}>
              <div className={styles.cardTop}>
                <Icon size={18} aria-hidden="true" />
                <span>{pillar.eyebrow}</span>
                <b>{String(index + 1).padStart(2, "0")}</b>
              </div>
              <strong>{pillar.label}</strong>
              <p>{pillar.description}</p>
              <small>
                {pillar.count}
                <ArrowRight size={14} aria-hidden="true" />
              </small>
            </Link>
          );
        })}
      </div>
      <footer>
        已建立 {researchSynergySummary.companyPersonEdges} 条公司—人物显式关系；其余关系只在已有赛道、任职或技术证据时挂接。
      </footer>
    </section>
  );
}
