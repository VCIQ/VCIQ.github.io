import type { Metadata } from "next";
import { Users } from "lucide-react";
import Link from "next/link";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { peopleGeneratedAt, researchPeople } from "@/lib/people-data";
import { getPersonResearchSnapshot } from "@/lib/people-research";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "核心人物",
  description: "研究一级市场核心赛道中的创始人、科学家、工程负责人和关键决策者，并连接其公司与技术证据。",
};

const DIRECTORY_TAG_LIMIT = 1;

const statusLabels = {
  complete: "档案较完整",
  partial: "补充中",
  pending: "待抓取",
} as const;

export default function PeoplePage() {
  const trackedCount = researchPeople.filter((person) => person.tracked).length;
  const directory = researchPeople
    .map((person) => ({
      person,
      research: getPersonResearchSnapshot(person),
    }))
    .sort((left, right) =>
      right.research.priority.score - left.research.priority.score
      || (right.research.latestChange?.date ?? "").localeCompare(left.research.latestChange?.date ?? "")
      || left.person.name.localeCompare(right.person.name, "zh-CN"));
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">03 / CORE PEOPLE</p>
        <h1>核心人物</h1>
        <p>
          人物频道解释赛道中的技术判断、组织选择和路线演进：先回答为什么值得跟踪、最近发生了什么、
          下一步看什么，再连接其任职公司、产品项目、技术主题与事件级公开证据。
        </p>
        <div className="hero-chips">
          <span>{trackedCount} 位重点人物</span>
          <span>{researchPeople.length} 位已发布人物</span>
          <span>按研究优先级排序</span>
          <span>公司关系仅按显式任职证据挂接</span>
          <span>资料更新 {peopleGeneratedAt.slice(0, 10)}</span>
        </div>
      </header>

      <ChannelSplitLayout
        channel="people"
        eyebrow="CORE PEOPLE RESEARCH DIRECTORY"
        title="核心人物档案"
        description="人物研究承担赛道与公司之间的决策解释层：目录先展示研究摘要，再进入技术主线、观点演进、组织关系和事件级证据。"
        count={researchPeople.length}
        countLabel="已发布人物"
        statusText={`更新 ${peopleGeneratedAt.slice(0, 10)}`}
        icon={<Users size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
        directoryFirst
      >
        <div className="people-grid">
          {directory.map(({ person, research }) => (
            <Link href={`/people/${person.slug}`} key={person.slug}>
              <div className="person-monogram">{person.name.slice(0, 1)}</div>
              <h2>{person.name}</h2>
              <span>{person.role}</span>
              <div>
                {person.sectors.slice(0, DIRECTORY_TAG_LIMIT).map((sector) => <i key={sector}>{sector}</i>)}
                {person.concepts
                  .slice(0, Math.max(0, DIRECTORY_TAG_LIMIT - person.sectors.length))
                  .map((concept) => <i key={concept}>{concept}</i>)}
              </div>

              <div className={styles.cardResearch}>
                <div className={styles.researchRow}>
                  <b>为什么重要</b>
                  <p>{research.whyImportant}</p>
                </div>
                <div className={styles.researchRow}>
                  <b>最新变化</b>
                  <p className={styles.latestChange}>
                    {research.latestChange
                      ? `${research.latestChange.date} · ${research.latestChange.title}`
                      : "暂无可核验的近期人物事件。"}
                  </p>
                </div>
                <div className={styles.researchRow}>
                  <b>下一步观察</b>
                  <p>{research.nextWatch}</p>
                </div>
              </div>

              <small>
                {research.priority.level} · 证据 {research.coverage.score}% · {research.viewChange.label} · {statusLabels[person.status]} · {research.events.length} 个事件
              </small>
            </Link>
          ))}
        </div>
      </ChannelSplitLayout>
    </main>
  );
}
