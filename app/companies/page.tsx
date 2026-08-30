import type { Metadata } from "next";
import { ChannelUpdateDirectory } from "@/components/channel-update-directory";
import { CompanyChannelTabs } from "@/components/company-channel-tabs";
import { CompanyDirectory } from "@/components/company-directory";
import { ResearchSynergyStrip } from "@/components/research-synergy-strip";
import { companies } from "@/lib/catalog-data";
import { buildCompanyResearchSnapshot } from "@/lib/company-research";
import { curateCompanyUpdateDirectory } from "@/lib/company-update-curation";
import { getChannelUpdateDirectory } from "@/lib/channel-updates";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "核心公司",
  description: "以研究优先级组织核心科技公司，连接赛道、技术主题、关键人物、产品、融资与可追溯事件。",
};

export default function CompaniesPage() {
  const companyUpdates = curateCompanyUpdateDirectory(getChannelUpdateDirectory("companies"));
  const researchSnapshots = companies.map((company) => buildCompanyResearchSnapshot(company));
  const asOf = Date.parse(companyUpdates.generatedAt);
  const changedInSevenDays = researchSnapshots.filter((snapshot) => {
    const changedAt = Date.parse(snapshot.latestChange?.date ?? "");
    return Number.isFinite(asOf) && Number.isFinite(changedAt) && asOf - changedAt <= 7 * 86_400_000;
  }).length;
  const priorityCompanies = researchSnapshots.filter((snapshot) => snapshot.priority.level === "P1").length;
  const evidenceGaps = researchSnapshots.filter((snapshot) => !snapshot.coverage.hasProfile || snapshot.coverage.score < 65).length;

  return (
    <main className="page-shell subpage">
      <header className={`page-header ${styles.channelHeader}`}>
        <p className="eyebrow">05 / CORE COMPANIES</p>
        <h1>核心公司</h1>
        <div className="hero-chips">
          <span>{priorityCompanies} 家重点跟踪</span>
          <span>{changedInSevenDays} 家近 7 天有变化</span>
          <span>{companyUpdates.items.length} 个重要事件簇</span>
          <span>{evidenceGaps} 家待补关键证据</span>
        </div>
      </header>

      <CompanyChannelTabs
        companyCount={companies.length}
        eventCount={companyUpdates.items.length}
        directory={<CompanyDirectory pageSize={12} />}
        events={<ChannelUpdateDirectory channel="companies" layout="workspace" />}
      />

      <ResearchSynergyStrip compactOnMobile />

      <details className={styles.methodology}>
        <summary>
          <span>COMPANY RESEARCH METHOD</span>
          <strong>公司研究说明</strong>
          <small>展开查看</small>
        </summary>
        <p>
          公司频道把赛道与技术变量、关键人物判断落到真实产品、经营、融资和资本结果上；先看近期变化与研究对象，
          再通过完整档案和原始证据验证为什么值得研究、下一步需要验证什么。
        </p>
      </details>
    </main>
  );
}
