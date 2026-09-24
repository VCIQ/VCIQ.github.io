import { ExternalLink } from "lucide-react";
import lifecycle from "@/config/innovation_listing_lifecycle.json";
import styles from "./page.module.css";

const routeLabels: Record<string, string> = {
  STAR: "科创板",
  ChiNext: "创业板",
  "A-share-TBD": "A股待定",
  HK: "港股",
};

const statusLabels: Record<string, string> = {
  "exchange-review": "交易所审核",
  "registration-review": "注册阶段",
  registered: "注册",
  issuing: "发行",
  listed: "已上市",
  terminated: "终止/撤回",
};

export function InnovationListingLifecycle() {
  return (
    <section className={styles.lifecycleSection} id="listing-lifecycle">
      <div className={styles.sectionHeader}>
        <div>
          <span>LISTING LIFECYCLE</span>
          <h2>科创上市生命周期</h2>
        </div>
        <p>
          项目一旦从辅导储备进入交易所审核、注册、发行或上市，不从体系中删除，而是迁入生命周期层持续跟踪。
          状态以交易所/监管一级公开证据为准。
        </p>
      </div>

      <div className={styles.lifecycleGrid}>
        {lifecycle.projects.map((project) => (
          <article className={styles.lifecycleCard} key={project.id}>
            <header>
              <div>
                <span className={styles.broker}>{project.broker}</span>
                <h3>{project.company}</h3>
              </div>
              <span className={styles.lifecycleStatus}>
                {statusLabels[project.lifecycleStatus] ?? project.stage}
              </span>
            </header>

            <div className={styles.badges}>
              <span className={styles.routeBadge}>{routeLabels[project.route] ?? project.route}</span>
              <span>{project.stage}</span>
              {project.stockCode ? <span>{project.stockCode}</span> : null}
            </div>

            <p className={styles.sector}>{project.sector} · {project.subsector}</p>
            <p className={styles.event}>{project.latestEvent}</p>

            <dl className={styles.metaGrid}>
              <div><dt>首次辅导</dt><dd>{project.firstGuidanceDate}</dd></div>
              <div><dt>最新核验</dt><dd>{project.latestEventDate}</dd></div>
              <div><dt>辅导/保荐机构</dt><dd>{project.broker}</dd></div>
              <div><dt>资本路径</dt><dd>{project.capitalMarketPath}</dd></div>
            </dl>

            <div className={styles.themeRow}>
              {project.fifteenthTags.map((tag) => <span key={tag}>{tag}</span>)}
            </div>

            <div className={styles.lifecycleSources}>
              {project.sources.map((source) => (
                <a href={source.url} target="_blank" rel="noreferrer" key={source.url}>
                  <span>{source.title}</span>
                  <ExternalLink size={12} aria-hidden="true" />
                </a>
              ))}
            </div>
          </article>
        ))}
      </div>

      <p className={styles.scopeNote}>{lifecycle.scopeNote}</p>
    </section>
  );
}
