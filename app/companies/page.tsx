import type { Metadata } from "next";
import { Building2 } from "lucide-react";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { CompanyDirectory } from "@/components/company-directory";
import { companies } from "@/lib/catalog-data";
import { researchSynergySummary } from "@/lib/research-relations";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "公司库",
  description: "以结构化公司档案组织一级市场科技公司，连接赛道、技术主题、关键人物、产品、融资与可追溯事件。",
};

export default function CompaniesPage() {
  return (
    <main className="page-shell subpage">
      <header className={`page-header ${styles.channelHeader}`}>
        <p className="eyebrow">05 / COMPANY DIRECTORY</p>
        <h1>公司库</h1>
        <div className="hero-chips">
          <span>{companies.length} 家已发布公司</span>
          <span>最新事件统一进入首页公司频道</span>
          <span>{researchSynergySummary.trackCount} 个核心赛道</span>
          <span>{researchSynergySummary.companyPersonEdges} 条公司—人物显式关系</span>
        </div>
      </header>

      <ChannelSplitLayout
        channel="companies"
        eyebrow="COMPANY RESEARCH DIRECTORY"
        title="公司档案库"
        description="公司库不再重复维护新闻流；按研究优先级浏览公司摘要，并按地区、赛道、阶段、近期变化与证据覆盖筛选。公司卡片直接连接技术主题和关键人物，公司相关最新事件统一在首页“公司”频道消费。"
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
          <strong>公司研究说明</strong>
          <small>展开查看</small>
        </summary>
        <p>
          公司库把赛道与技术变量、关键人物判断落到真实产品、经营、融资和资本结果上；先看结构化档案与研究对象，
          再通过原始证据验证为什么值得研究、下一步需要验证什么。最新公司事件统一在首页公司频道展示。
        </p>
      </details>
    </main>
  );
}
