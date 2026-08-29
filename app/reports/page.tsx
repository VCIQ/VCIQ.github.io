import type { Metadata } from "next";
import { FileText } from "lucide-react";
import Link from "next/link";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { ExternalDatabaseLinks } from "@/components/external-database-links";
import { ResearchReportLibrary } from "@/components/research-report-library";
import { reports } from "@/lib/catalog-data";
import { hanghangchaEntryLink } from "@/lib/external-database-links";
import { researchReportGeneratedAt, researchReports } from "@/lib/research-report-data";
import styles from "./split.module.css";

export const metadata: Metadata = {
  title: "研究简报与报告",
  description: "持续更新的专题 3 分钟研究简报，以及公开 PDF 研报归档。",
};

export default function ReportsPage() {
  const totalReports = researchReports.length + reports.length;
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">06 / RESEARCH</p>
        <h1>研究简报与报告</h1>
        <p>
          专题页将长期研究框架与最新可追溯证据合并为 3 分钟研究简报，并继续归档
          无需登录即可公开下载的研究报告 PDF。
        </p>
      </header>

      <ChannelSplitLayout
        channel="reports"
        eyebrow="RESEARCH BRIEF DIRECTORY"
        title="专题简报与公开研报"
        description="优先进入持续更新的专题 3 分钟简报，也可浏览可直接阅读的公开 PDF 与可追溯原始入口。"
        count={totalReports}
        countLabel="研究资产快照"
        statusText={researchReportGeneratedAt ? `更新 ${researchReportGeneratedAt.slice(0, 10)}` : "持续更新"}
        icon={<FileText size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
      >
        <section className={styles.block}>
          <div className={styles.blockHeader}>
            <div>
              <p className="section-index">TOPIC RESEARCH BRIEFS</p>
              <h3>专题研究 / 3 分钟简报</h3>
            </div>
            <span>{reports.length} 个持续更新专题</span>
          </div>
          <p className={styles.note}>
            每个专题自动执行主题证据收窄、来源质量门与证据去重；进入专题后可直接查看本期判断、最近证据信号、证据覆盖和完整证据时间线。
          </p>
          <div className="report-list">
            {reports.map((report, index) => (
              <Link href={`/reports/${report.slug}`} key={report.slug}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <p>{report.type} · 3 分钟简报</p>
                  <h2>{report.title}</h2>
                  <strong>{report.summary}</strong>
                  <div>{report.tags.map((tag) => <i key={tag}>{tag}</i>)}</div>
                </div>
                <small>持续更新</small>
              </Link>
            ))}
          </div>
        </section>

        <section className={styles.block}>
          <div className={styles.blockHeader}>
            <div>
              <p className="section-index">PUBLIC PDF ARCHIVE</p>
              <h3>公开研报 PDF 资产库</h3>
            </div>
            <span>{researchReports.length} 份已归档 PDF</span>
          </div>
          <p className={styles.note}>
            点击任意研报进入站内 PDF 阅读页。系统仅保存公开可直接下载且通过 PDF 文件校验的原文，不绕过登录、付费或访问权限。
          </p>
          <ResearchReportLibrary reports={researchReports} compact />
          <ExternalDatabaseLinks
            links={[hanghangchaEntryLink()]}
            lead="行行查是会员制行业研究数据库：各赛道、公司与人物详情页提供按实体的检索直达入口；报告与 PPT 需登录对方平台查看，本站不抓取、不缓存其内容。"
          />
        </section>
      </ChannelSplitLayout>
    </main>
  );
}
