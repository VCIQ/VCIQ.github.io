import type { Metadata } from "next";
import { ShieldCheck } from "lucide-react";
import {
  sourceDirectory,
  sourceDirectoryStats,
} from "@/lib/source-directory";
import {
  sourceNeedsEvidence,
} from "@/lib/source-decision-dashboard";
import { sourceCoreEligible } from "@/lib/source-governance";
import SourceOperationsClient from "./source-operations-client";
import SourceQaQueue from "./source-qa-queue";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "重点信源",
  description: "将微信公众号、X 发现源、原始研究论文、专业媒体、公司官方来源与监管材料统一纳入 Source Entity 模型，并公开呈现角色、生命周期、覆盖缺口与采集健康。",
};

export default function SourcesPage() {
  const issueCount = sourceDirectoryStats.partial + sourceDirectoryStats.error;
  const coreEvidencePending = sourceDirectory.filter(sourceNeedsEvidence).length;
  const discoveryOnly = sourceDirectory.filter((source) => !sourceCoreEligible(source)).length;
  const coreReady = sourceDirectory.filter(
    (source) => sourceCoreEligible(source) && source.promotion?.state === "review_pending",
  ).length;
  const snapshotAt = new Date().toISOString();

  return (
    <main className="page-shell subpage">
      <header className={`page-header ${styles.channelHeader}`}>
        <p className="eyebrow">05 / SOURCE GOVERNANCE</p>
        <h1>重点信源</h1>
        <div className="hero-chips">
          <span>{sourceDirectoryStats.total} 个 Source Entity</span>
          <span>{sourceDirectoryStats.primary} 个 Primary Source</span>
          <span>{sourceDirectoryStats.papers} 个原始研究源</span>
          <span>{sourceDirectoryStats.xProfiles} 个 X Discovery Source</span>
          <span>{sourceDirectoryStats.healthy} 个当前健康</span>
          <span>{issueCount} 个存在采集异常</span>
          <span>{sourceDirectoryStats.unknown} 个 Unobserved / 未建立观测</span>
          <span>{coreEvidencePending} 个 Core 候选等待证据</span>
          <span>{discoveryOnly} 个 Discovery-only</span>
          <span>{coreReady} 个 Core Ready</span>
        </div>
      </header>

      <SourceOperationsClient sources={sourceDirectory} snapshotAt={snapshotAt} />
      <SourceQaQueue sources={sourceDirectory} />

      <details className={styles.lifecycle}>
        <summary>
          <span>SOURCE LIFECYCLE</span>
          <strong>Candidate → Tracked → Core</strong>
          <small>生命周期、晋级就绪度、证据角色与采集健康相互独立</small>
        </summary>
        <div className={styles.lifecycleDetails}>
          <p>
            Candidate 表示已进入信源图但尚未建立稳定采集入口；Tracked 表示已配置持续采集；Core 只会在滚动运行、跨日稳定性、可用率、有效产出、人工抽查全部达到版本化 Policy 后，再经过显式人工 Core 审批产生。
            人工批准不能绕过量化证据门，量化门达标也不能绕过人工批准。Primary / Corroboration 默认可进入 Core 候选流程；微信公众号与 X Profiles 默认 Discovery-only，不进入 Core 晋级或 Core QA 队列。
            Evidence Role、Lifecycle 与 Collector Health 分轴展示，不再压缩成一个“需要处理”状态。
          </p>
          <div className={styles.lifecycleFlow}>
            <div>
              <strong>Candidate</strong>
              <p>已有明确 Source Entity，但稳定采集入口或质量证据仍不足。</p>
            </div>
            <div>
              <strong>Tracked</strong>
              <p>已配置持续抓取与滚动质量观测；Core 候选继续区分 EVIDENCE PENDING 与 CORE READY，Discovery-only 保持发现角色。</p>
            </div>
            <div>
              <strong>Core</strong>
              <p>默认可晋级角色在跨运行证据、人工抽查与显式审批全部满足后，才成为长期研究入口。</p>
            </div>
          </div>
        </div>
      </details>

      <details className={styles.methodology}>
        <summary>
          <span>SOURCE RESEARCH METHOD</span>
          <strong>证据角色与信源频道说明</strong>
          <small>展开查看</small>
        </summary>
        <p>
          Primary Source 包括公司官网、监管/交易所披露、论文与原始研究材料；Corroboration Source 用于独立交叉验证；Discovery Source 包括微信公众号与 X Profiles，负责高召回和高时效发现。
          Source Entity 表示媒体、机构、公司、研究仓库或公开账号本身，Collection Endpoint 表示微信索引、官网、RSS、论文 API、X 公开时间线、监管接口或公开网页等采集通道。
        </p>
      </details>

      <section className={styles.group} aria-label="信源治理原则">
        <div className={styles.groupHeader}>
          <div>
            <span>SOURCE GOVERNANCE</span>
            <h2>信源进入核心层的约束</h2>
          </div>
          <ShieldCheck size={20} aria-hidden="true" />
        </div>
        <div className={styles.governance}>
          <article>
            <strong>文章价值 ≠ 媒体价值</strong>
            <p>单篇优秀文章只产生候选信号；不因一次收藏就把整个公众号或媒体升级为核心信源。</p>
          </article>
          <article>
            <strong>Source Entity ≠ Collection Endpoint</strong>
            <p>同一实体的微信、官网、RSS、论文 API 与公开时间线分别记录健康；可靠备用通道可用时，不把实体整体误判为失效。</p>
          </article>
          <article>
            <strong>发现 ≠ 事实确认</strong>
            <p>微信公众号与 X Profiles 默认只负责发现；重大公司、融资、监管、产品和研究结论必须回溯公司官网、论文、交易所、监管文件或其他原始材料。</p>
          </article>
          <article>
            <strong>Core 必须经过质量门槛</strong>
            <p>Tracked 不自动升级为 Core；持续可用性、有效产出、跨日稳定性、人工抽查和显式人工批准共同决定是否晋级。</p>
          </article>
        </div>
      </section>
    </main>
  );
}
