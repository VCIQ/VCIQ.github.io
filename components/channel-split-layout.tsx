import type { ReactNode } from "react";
import { ChannelUpdateDirectory } from "@/components/channel-update-directory";
import { ResearchSynergyStrip } from "@/components/research-synergy-strip";
import type { ChannelUpdateKey } from "@/lib/channel-updates";
import styles from "./channel-split-layout.module.css";

type ChannelSplitLayoutProps = {
  channel: ChannelUpdateKey;
  eyebrow: string;
  title: string;
  description: string;
  count: number;
  countLabel: string;
  statusText?: string;
  icon: ReactNode;
  bodyClassName?: string;
  directoryFirst?: boolean;
  beforeResearchSynergy?: ReactNode;
  children: ReactNode;
};

export function ChannelSplitLayout({
  channel,
  eyebrow,
  title,
  description,
  count,
  countLabel,
  statusText = "持续更新",
  icon,
  bodyClassName,
  directoryFirst = false,
  beforeResearchSynergy,
  children,
}: ChannelSplitLayoutProps) {
  const updatesPanel = (
    <div className={styles.updatesPanel}>
      <ChannelUpdateDirectory channel={channel} layout="split" />
    </div>
  );
  const directoryPanel = (
    <section className={styles.directoryPanel} aria-labelledby={`${channel}-directory-title`}>
      <header className={styles.panelHeader}>
        <div>
          <p className="section-index">{eyebrow}</p>
          <div className={styles.titleLine}>
            {icon}
            <h2 id={`${channel}-directory-title`}>{title}</h2>
          </div>
        </div>
        <div className={styles.snapshot}>
          <span>{countLabel}</span>
          <strong>{count}</strong>
          <small>{statusText}</small>
        </div>
      </header>

      <div className={`${styles.panelBody}${bodyClassName ? ` ${bodyClassName}` : ""}`}>
        {children}
      </div>
    </section>
  );
  const showResearchSynergy = ["technology", "people", "companies"].includes(channel);

  return (
    <>
      {beforeResearchSynergy}
      <div className={styles.splitLayout}>
        {directoryFirst ? (
          <>
            {directoryPanel}
            {updatesPanel}
          </>
        ) : (
          <>
            {updatesPanel}
            {directoryPanel}
          </>
        )}
      </div>
      {showResearchSynergy ? <ResearchSynergyStrip compactOnMobile /> : null}
      <details className={styles.directoryNote}>
        <summary>
          <span>DIRECTORY NOTE</span>
          <strong>{title}说明</strong>
          <small>展开查看</small>
        </summary>
        <p>{description}</p>
      </details>
    </>
  );
}
