import type { Metadata } from "next";
import { Suspense } from "react";
import ResearchInvestigationClient from "./research-investigation-client";

export const metadata: Metadata = {
  title: "深研此条",
  description: "把当前 VCIQ 情报、来源、关联证据与追踪状态整理成可移交到 Research Workspace 的研究上下文。",
};

function ResearchInvestigationFallback() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">CONTEXTUAL RESEARCH HANDOFF</p>
        <h1>深研此条</h1>
        <p>正在准备当前情报的研究上下文…</p>
      </header>
    </main>
  );
}

export default function ResearchInvestigationPage() {
  return (
    <Suspense fallback={<ResearchInvestigationFallback />}>
      <ResearchInvestigationClient />
    </Suspense>
  );
}
