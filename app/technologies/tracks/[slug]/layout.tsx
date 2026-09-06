import type { ReactNode } from "react";
import { ResearchRelationPanel } from "@/components/research-relation-panel";
import { TrackWatchlistAdminEntry } from "@/components/track-watchlist-admin-entry";

export default async function TechnologyTrackAliasLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return (
    <>
      <TrackWatchlistAdminEntry slug={slug} />
      {children}
      <ResearchRelationPanel kind="track" slug={slug} />
    </>
  );
}
