"use client";

import { Building2, RadioTower } from "lucide-react";
import type { KeyboardEvent, ReactNode } from "react";
import { useRef, useSyncExternalStore } from "react";
import styles from "./company-channel-tabs.module.css";

type CompanyChannelView = "directory" | "events";

const VIEW_CHANGE_EVENT = "company-channel-view-change";

function subscribeToView(callback: () => void) {
  window.addEventListener("popstate", callback);
  window.addEventListener(VIEW_CHANGE_EVENT, callback);
  return () => {
    window.removeEventListener("popstate", callback);
    window.removeEventListener(VIEW_CHANGE_EVENT, callback);
  };
}

function viewSnapshot(): CompanyChannelView {
  return new URLSearchParams(window.location.search).get("view") === "events" ? "events" : "directory";
}

export function CompanyChannelTabs({
  companyCount,
  eventCount,
  directory,
  events,
}: {
  companyCount: number;
  eventCount: number;
  directory: ReactNode;
  events: ReactNode;
}) {
  const view = useSyncExternalStore(subscribeToView, viewSnapshot, () => "directory");
  const directoryTab = useRef<HTMLButtonElement>(null);
  const eventsTab = useRef<HTMLButtonElement>(null);

  function selectView(next: CompanyChannelView) {
    const url = new URL(window.location.href);
    if (next === "events") url.searchParams.set("view", "events");
    else url.searchParams.delete("view");
    window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
    window.dispatchEvent(new Event(VIEW_CHANGE_EVENT));
  }

  function handleTabKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
    event.preventDefault();
    const next = view === "directory" ? "events" : "directory";
    selectView(next);
    (next === "directory" ? directoryTab : eventsTab).current?.focus();
  }

  return (
    <section className={styles.workspace} aria-label="核心公司研究工作区">
      <div className={styles.tabList} role="tablist" aria-label="核心公司频道视图">
        <button
          type="button"
          ref={directoryTab}
          role="tab"
          id="company-directory-tab"
          aria-controls="company-directory-panel"
          aria-selected={view === "directory"}
          tabIndex={view === "directory" ? 0 : -1}
          onClick={() => selectView("directory")}
          onKeyDown={handleTabKey}
        >
          <Building2 size={18} aria-hidden="true" />
          <span><strong>公司档案</strong><small>搜索、筛选和比较研究对象</small></span>
          <b>{companyCount}</b>
        </button>
        <button
          type="button"
          ref={eventsTab}
          role="tab"
          id="company-events-tab"
          aria-controls="company-events-panel"
          aria-selected={view === "events"}
          tabIndex={view === "events" ? 0 : -1}
          onClick={() => selectView("events")}
          onKeyDown={handleTabKey}
        >
          <RadioTower size={18} aria-hidden="true" />
          <span><strong>重要事件</strong><small>同一事件合并多个公开信源</small></span>
          <b>{eventCount}</b>
        </button>
      </div>

      <section
        className={styles.panel}
        id="company-directory-panel"
        role="tabpanel"
        aria-labelledby="company-directory-tab"
        hidden={view !== "directory"}
      >
        <header className={styles.directoryHeader}>
          <div>
            <p className="section-index">COMPANY RESEARCH DIRECTORY</p>
            <h2>核心公司研究</h2>
          </div>
          <p>先查看公司定位、最新变化和下一步验证问题，再进入完整档案核对原始证据。</p>
        </header>
        {directory}
      </section>

      <section
        className={styles.panel}
        id="company-events-panel"
        role="tabpanel"
        aria-labelledby="company-events-tab"
        hidden={view !== "events"}
      >
        {events}
      </section>
    </section>
  );
}
