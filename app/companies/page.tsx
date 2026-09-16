import type { Metadata } from "next";
import Link from "next/link";
import { Building2 } from "lucide-react";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { CompanyDirectory } from "@/components/company-directory";
import { companies } from "@/lib/catalog-data";
import { projectHomepageCompanyDisclosureEvents } from "@/lib/homepage-company-disclosure-events";
import { listedDisclosureStats } from "@/lib/listed-company-disclosure-data";
import { researchSynergySummary } from "@/lib/research-relations";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "公司库",
  description: "以研究优先级组织科技公司档案，连接赛道、技术主题、关键人物、产品、融资与可追溯证据。",
};

const latestOfficialDisclosures = projectHomepageCompanyDisclosureEvents(6);
const latestDisclosureDate = latestOfficialDisclosures[0]?.publishedAt ?? "持续更新";

export default function CompaniesPage() {
  return (
    <main className="page-shell subpage">
      <header className={`page-header ${styles.channelHeader}`}>
        <p className="eyebrow">05 / COMPANY LIBRARY</p>
        <h1>公司库</h1>
        <div className="hero-chips">
          <span>{companies.length} 家已发布公司</span>
          <span>{listedDisclosureStats.companyCount} 家上市公司有监管披露</span>
          <span>CNINFO {listedDisclosureStats.cninfoAcceptedEventCount} 条结构化公告</span>
          <span>{researchSynergySummary.trackCount} 个核心赛道</span>
          <span>公司事件统一进入首页“公司”频道</span>
        </div>
      </header>

      <section className={styles.disclosurePanel} aria-labelledby="listed-disclosure-heading">
        <header className={styles.disclosureHeader}>
          <div>
            <span>LISTED COMPANY DISCLOSURES</span>
            <h2 id="listed-disclosure-heading">上市公司官方披露</h2>
            <p>
              公司库保留完整监管证据；首页“公司”频道只投射高价值变化。两处共用同一份
              CNINFO、交易所与 SEC 官方披露数据，不重复维护第二套事实。
            </p>
          </div>
          <dl className={styles.disclosureStats}>
            <div><dt>官方披露</dt><dd>{listedDisclosureStats.officialEventCount}</dd></div>
            <div><dt>CNINFO</dt><dd>{listedDisclosureStats.cninfoAcceptedEventCount}</dd></div>
            <div><dt>覆盖公司</dt><dd>{listedDisclosureStats.companyCount}</dd></div>
            <div><dt>最新</dt><dd>{latestDisclosureDate}</dd></div>
          </dl>
        </header>

        <div className={styles.disclosureGrid}>
          {latestOfficialDisclosures.map((event) => (
            <article className={styles.disclosureCard} key={event.id}>
              <div className={styles.disclosureMeta}>
                <Link href={`/companies/${event.companySlug}`}>{event.company}</Link>
                <span>{event.type}</span>
                <time dateTime={event.publishedAt}>{event.publishedAt}</time>
              </div>
              <h3>
                <a href={event.source.url} target="_blank" rel="noreferrer">
                  {event.title}
                </a>
              </h3>
              <p>{event.summary}</p>
              <footer>
                <span>{event.source.name} · {event.source.level}</span>
                <Link href={`/companies/${event.companySlug}`}>进入公司档案 →</Link>
              </footer>
            </article>
          ))}
        </div>
      </section>

      <ChannelSplitLayout
        channel="companies"
        eyebrow="COMPANY INTELLIGENCE LIBRARY"
        title="公司档案"
        description="这里保留公司长期研究资产：按研究优先级浏览公司摘要，并按地区、赛道、阶段、近期变化与证据覆盖筛选；监管披露会进入公司档案，高价值变化同步投射到首页“公司”频道。"
        count={companies.length}
        countLabel="已发布公司"
        statusText="研究关系与监管证据持续更新"
        icon={<Building2 size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
        directoryFirst
        showUpdates={false}
      >
        <CompanyDirectory pageSize={6} />
      </ChannelSplitLayout>

      <details className={styles.methodology}>
        <summary>
          <span>COMPANY RESEARCH METHOD</span>
          <strong>公司库说明</strong>
          <small>展开查看</small>
        </summary>
        <p>
          公司库负责沉淀长期实体研究：公司身份、技术路线、产品、关键人物、融资、监管披露与商业化关系在这里组织；
          高频新闻和高价值上市公司公告统一进入首页“公司”频道，并可从事件回链到对应公司档案。CNINFO 仍是 A 股指定披露平台的重要来源，
          同时保留 SSE / SZSE 等独立官方证据与来源状态，不以单一外部接口健康度替代整体监管覆盖判断。
        </p>
      </details>
    </main>
  );
}
