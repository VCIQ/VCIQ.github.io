import type { ReactNode } from "react";
import { ResearchRelationPanel } from "@/components/research-relation-panel";

export default async function PersonResearchLayout({
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
      <ResearchRelationPanel kind="person" slug={slug} />
    </>
  );
}
