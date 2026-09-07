import type { Metadata } from "next";
import ResearchInvestigationClient from "./research-investigation-client";

export const metadata: Metadata = {
  title: "深研此条",
  description: "把当前 VCIQ 情报、来源、关联证据与追踪状态整理成可移交到 Research Workspace 的研究上下文。",
};

export default function ResearchInvestigationPage() {
  return <ResearchInvestigationClient />;
}
