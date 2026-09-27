"use client";

import { usePathname } from "next/navigation";
import NativeResearchReportsPanel from "./native-research-reports-panel";
import styles from "./native-research-reports.module.css";

export default function ResearchChannelSections() {
  const pathname = usePathname();
  if (pathname?.replace(/\/+$/, "") !== "/research-agent") return null;
  return <div className="page-shell subpage">
    <nav className={styles.nav} aria-label="研究频道栏目"><a href="#native-reports">专题深研报告</a><a href="#brief">每日研究变化</a><a href="#queuecf">科创研究</a></nav>
    <NativeResearchReportsPanel />
  </div>;
}
