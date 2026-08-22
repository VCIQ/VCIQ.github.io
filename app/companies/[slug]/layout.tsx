import type { ReactNode } from "react";
import { ResearchRelationPanel } from "@/components/research-relation-panel";

export default async function CompanyResearchLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return (
    <>
      {children}
      <ResearchRelationPanel kind="company" slug={slug} />
    </>
  );
}
