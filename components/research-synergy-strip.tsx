import { ArrowRight, Building2, Network, Users } from "lucide-react";
import Link from "next/link";
import { researchSynergySummary } from "@/lib/research-relations";
import styles from "./research-synergy-strip.module.css";

type ResearchChannel = "technology" | "people" | "companies";

const pillars = [
  {
    channel: "technology",
    href: "/technologies/",
    label: "赛道与技术",
    count: `${researchSynergySummary.trackCount} 赛道 · ${researchSynergySummary.topicCount} 主题`,
    icon: Network,
  },
  {
    channel: "people",
    href: "/people/",
    label: "人物",
    count: `${researchSynergySummary.peopleCount} 位研究对象`,
    icon: Users,
  },
  {
    channel: "companies",
    href: "/companies/",
    label: "公司",
    count: `${researchSynergySummary.companyCount} 家公司`,
    icon: Building2,
  },
] as const;

type ResearchSynergyStripProps = {
  currentChannel?: ResearchChannel;
};

export function ResearchSynergyStrip({
  currentChannel,
}: ResearchSynergyStripProps) {
  return (
    <section className={styles.section} aria-label="研究对象协同路径">
      <div className={styles.label}>
        <span>RESEARCH PATH</span>
        <strong>研究链路</strong>
      </div>

      <nav className={styles.path} aria-label="研究对象切换">
        {pillars.map((pillar, index) => {
          const Icon = pillar.icon;
          return (
            <Link
              href={pillar.href}
              data-active={currentChannel === pillar.channel ? "true" : undefined}
              key={pillar.href}
            >
              <Icon size={15} aria-hidden="true" />
              <b>{pillar.label}</b>
              <small>{pillar.count}</small>
              {index < pillars.length - 1 ? <ArrowRight size={12} aria-hidden="true" /> : null}
            </Link>
          );
        })}
      </nav>

      <details className={styles.method}>
        <summary>研究方法</summary>
        <div>
          <p>先用赛道确定变量，再用人物解释决策，最后用公司事件验证结果。</p>
          <small>
            已建立 {researchSynergySummary.companyPersonEdges} 条公司—人物显式关系；其余关系只在已有赛道、任职或技术证据时挂接。
          </small>
        </div>
      </details>
    </section>
  );
}
