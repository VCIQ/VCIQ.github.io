import type { Metadata } from "next";
import { Building2 } from "lucide-react";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { CompanyDirectory } from "@/components/company-directory";
import { companies } from "@/lib/catalog-data";
import { researchSynergySummary } from "@/lib/research-relations";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "公司库",
  description: "以研究优先级组织科技公司档案，连接赛道、技术主题、关键人物、产品、融资与可追溯证据。",
};

export default function CompaniesPage() {
  return (
    <main className="page-shell subpage">
      <header className={`page-header ${styles.channelHeader}`}>
        <p className="eyebrow">05 / COMPANY LIBRARY</p>
        <h1>公司库</h1>
        <div className="hero-chips">
          <span>{companies.length} 家已发布公司</span>
          <span>{researchSynergySummary.trackCount} 个核心赛道</span>
          <span>{researchSynergySummary.companyPersonEdges} 条公司—人物显式关系</span>
          <span>事件新闻统一进入首页“公司”频道</span>
        </div>
      </header>

      <ChannelSplitLayout
        channel="companies"
        eyebrow="COMPANY INTELLIGENCE LIBRARY"
        title="公司档案"
        description="这里保留公司长期研究资产：按研究优先级浏览公司摘要，并按地区、赛道、阶段、近期变化与证据覆盖筛选；公司事件新闻统一由首页“公司”信息流承载。"
        count={companies.length}
        countLabel="已发布公司"
        statusText="研究关系持续更新"
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
          公司库负责沉淀长期实体研究：公司身份、技术路线、产品、关键人物、融资与商业化关系在这里组织；
          高频事件和新闻不再重复维护，统一进入首页“公司”频道，并可从事件回链到对应公司档案。
        </p>
      </details>
    </main>
  );
}
