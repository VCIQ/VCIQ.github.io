import type { Metadata } from "next";
import { RotateCcw, Search, Users } from "lucide-react";
import Link from "next/link";
import Script from "next/script";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { getChannelUpdateDirectory } from "@/lib/channel-updates";
import { isPersonDirectoryChangeRecent } from "@/lib/person-directory-filter";
import { peopleGeneratedAt, researchPeople } from "@/lib/people-data";
import { getPersonResearchSnapshot } from "@/lib/people-research";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "核心人物",
  description: "研究一级市场核心赛道中的创始人、科学家、工程负责人和关键决策者，并连接其公司与技术证据。",
};

const DIRECTORY_TAG_LIMIT = 1;
const DIRECTORY_SUMMARY_LIMIT = 44;
const DIRECTORY_EVENT_LIMIT = 44;
const DIRECTORY_GRID_ID = "people-research-directory";

const statusLabels = {
  complete: "档案较完整",
  partial: "补充中",
  pending: "待抓取",
} as const;

const statusTokens = {
  complete: "tc",
  partial: "ti",
  pending: "tp",
} as const;

function directoryPreview(value: string, limit: number): string {
  const text = value.replace(/\s+/g, " ").trim();
  if (text.length <= limit) return text;
  return `${text.slice(0, Math.max(1, limit - 1)).trimEnd()}…`;
}

export default function PeoplePage() {
  const trackedCount = researchPeople.filter((person) => person.tracked).length;
  const watchCount = researchPeople.length - trackedCount;
  const peopleUpdates = getChannelUpdateDirectory("people");
  const sectors = Array.from(new Set(researchPeople.flatMap((person) => person.sectors)))
    .sort((left, right) => left.localeCompare(right, "zh-CN"));
  const sectorTokens = new Map(sectors.map((sector, index) => [sector, `s${index.toString(36)}`]));
  const directory = researchPeople
    .map((person) => {
      const research = getPersonResearchSnapshot(person);
      const recentChange = isPersonDirectoryChangeRecent(
        research.latestChange?.date,
        peopleGeneratedAt,
      );
      return {
        person,
        research,
        filterClass: [
          ...person.sectors.map((sector) => sectorTokens.get(sector)).filter(Boolean),
          statusTokens[person.status],
          recentChange ? "tr" : "",
        ].filter(Boolean).join(" "),
      };
    })
    .sort((left, right) =>
      right.research.priority.score - left.research.priority.score
      || (right.research.latestChange?.date ?? "").localeCompare(left.research.latestChange?.date ?? "")
      || left.person.name.localeCompare(right.person.name, "zh-CN"));
  return (
    <main className="page-shell subpage">
      <header className={`page-header ${styles.channelHeader}`}>
        <p className="eyebrow">03 / CORE PEOPLE</p>
        <h1>核心人物</h1>
        <div className="hero-chips">
          <span>{trackedCount} 位重点跟踪</span>
          {watchCount > 0 ? <span>{watchCount} 位观察对象</span> : null}
          <span>{peopleUpdates.items.length} 条人物更新</span>
          <span>资料更新 {peopleGeneratedAt.slice(0, 10)}</span>
        </div>
      </header>

      <ChannelSplitLayout
        channel="people"
        eyebrow="CORE PEOPLE RESEARCH DIRECTORY"
        title="核心人物档案"
        description="目录展示精简研究预览；完整判断、技术主线、观点演进、组织关系和事件证据进入人物详情查看。"
        count={researchPeople.length}
        countLabel="已发布人物"
        statusText={`更新 ${peopleGeneratedAt.slice(0, 10)}`}
        icon={<Users size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
        directoryFirst
      >
        <div className={styles.filters} aria-label="人物研究目录筛选" data-pf>
          <label className={styles.search}>
            <Search size={14} aria-hidden="true" />
            <input
              data-q
              placeholder="搜索人物、角色或研究摘要"
              aria-label="搜索人物研究档案"
              aria-controls={DIRECTORY_GRID_ID}
            />
          </label>
          <select data-sector aria-label="按赛道筛选人物" aria-controls={DIRECTORY_GRID_ID} defaultValue="">
            <option value="">全部赛道</option>
            {sectors.map((sector) => (
              <option value={sectorTokens.get(sector)} key={sector}>{sector}</option>
            ))}
          </select>
          <select data-status aria-label="按档案状态筛选人物" aria-controls={DIRECTORY_GRID_ID} defaultValue="">
            <option value="">全部状态</option>
            <option value="tc">档案较完整</option>
            <option value="ti">补充中</option>
            <option value="tp">待抓取</option>
          </select>
          <select data-change aria-label="按近期变化筛选人物" aria-controls={DIRECTORY_GRID_ID} defaultValue="">
            <option value="">全部变化</option>
            <option value="r">90 天内有变化</option>
            <option value="q">暂无近期变化</option>
          </select>
          <span className={styles.filterCount} data-count aria-live="polite">{directory.length} / {directory.length}</span>
          <button className={styles.filterReset} type="button" data-reset disabled aria-label="重置人物筛选">
            <RotateCcw size={13} aria-hidden="true" />
          </button>
        </div>

        <p className={styles.emptyFilter} data-people-empty role="status" hidden>
          没有匹配的人物档案，请调整关键词或筛选条件。
        </p>

        <div className="people-grid" id={DIRECTORY_GRID_ID}>
          {directory.map(({ person, research, filterClass }) => (
            <Link href={`/people/${person.slug}`} key={person.slug} className={filterClass}>
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
                  <b>最新变化</b>
                  <p className={styles.latestChange}>
                    {research.latestChange
                      ? `${research.latestChange.date} · ${directoryPreview(research.latestChange.title, DIRECTORY_EVENT_LIMIT)}`
                      : "暂无可核验的近期人物事件。"}
                  </p>
                </div>
                <div className={styles.researchRow}>
                  <b>为什么重要</b>
                  <p>{directoryPreview(research.whyImportant, DIRECTORY_SUMMARY_LIMIT)}</p>
                </div>
              </div>

              <small>
                {research.priority.level} · 完整度 {research.coverage.score}% · {statusLabels[person.status]}
              </small>
            </Link>
          ))}
        </div>
        <Script src="/people-directory-filter.js" strategy="afterInteractive" />
      </ChannelSplitLayout>

      <details className={styles.methodology}>
        <summary>
          <span>PEOPLE RESEARCH METHOD</span>
          <strong>人物研究说明</strong>
          <small>展开查看</small>
        </summary>
        <p>
          人物频道解释赛道中的技术判断、组织选择和路线演进：先回答为什么值得跟踪、最近发生了什么、下一步看什么，
          再连接其任职公司、产品项目、技术主题与事件级公开证据。公司关系仅按显式任职证据挂接。
        </p>
      </details>
    </main>
  );
}
