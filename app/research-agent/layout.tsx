import type { ReactNode } from "react";
import { Suspense } from "react";
import ResearchChannelSections from "./research-channel-sections";

export default function ResearchAgentLayout({ children }: { children: ReactNode }) {
  return <><Suspense fallback={null}><ResearchChannelSections /></Suspense>{children}</>;
}
