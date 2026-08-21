import type { Metadata } from "next";
import { Users } from "lucide-react";
import Link from "next/link";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { peopleGeneratedAt, researchPeople } from "@/lib/people-data";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "核心人物",
  description: "整理一级市场核心技术与赛道中的创始人、科学家、工程负责人和关键决策者。",
};

const SUMMARY_LIMIT = 40;
const DIRECTORY_TAG_LIMIT = 1;

const statusLabels = {
  complete: "资料完整",
  partial: "补充中",
  pending: "待抓取",
} as const;

function compactSummary(summary: string) {
  const normalized = summary.replace(/\s+/gu, " ").trim();
  if (normalized.length <= SUMMARY_LIMIT) return normalized;
  return `${normalized.slice(0, SUMMARY_LIMIT).trimEnd()}…`;
}

export default function PeoplePage() {
  const trackedCount = researchPeople.filter((person) => person.tracked).length;
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">04 / CORE PEOPLE</p>
        <h1>核心人物</h1>
        <p>
          聚焦核心赛道中的创始人、科学家、工程负责人、产品领导者与关键资本决策者，
          统一整理其背景、所属公司、技术观点、作品、论文、演讲与公开材料。
        </p>
        <div className="hero-chips">
          <span>{trackedCount} 位重点人物</span>
          <span>{researchPeople.length} 位人物总计</span>
          <span>资料更新 {peopleGeneratedAt.slice(0, 10)}</span>
        </div>
      </header>

      <ChannelSplitLayout
        channel="people"
        eyebrow="LATEST CORE PEOPLE DIRECTORY"
        title="核心人物档案"
        description="按人物进入其背景、所属公司、技术贡献、核心观点、公开账号和可追溯原始材料。"
        count={researchPeople.length}
        countLabel="公开人物快照"
        statusText={`更新 ${peopleGeneratedAt.slice(0, 10)}`}
        icon={<Users size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
      >
        <div className="people-grid">
          {researchPeople.map((person) => (
            <Link href={`/people/${person.slug}`} key={person.slug}>
              <div className="person-monogram">{person.name.slice(0, 1)}</div>
              <h2>{person.name}</h2>
              <span>{person.role}</span>
              <strong>{compactSummary(person.summary)}</strong>
              <div>
                {person.sectors.slice(0, DIRECTORY_TAG_LIMIT).map((sector) => <i key={sector}>{sector}</i>)}
                {person.concepts
                  .slice(0, Math.max(0, DIRECTORY_TAG_LIMIT - person.sectors.length))
                  .map((concept) => <i key={concept}>{concept}</i>)}
              </div>
              <small>{statusLabels[person.status]} · {person.materials.length} 条材料</small>
            </Link>
          ))}
        </div>
      </ChannelSplitLayout>
    </main>
  );
}
