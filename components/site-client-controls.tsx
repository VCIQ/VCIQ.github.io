"use client";

import { usePathname } from "next/navigation";
import { IntelligenceFavoriteControls } from "@/components/homepage-favorite-controls";
import { IntelligenceHotnessControls } from "@/components/intelligence-hotness-controls";
import { WechatShareCompat } from "@/components/wechat-share-compat";

export function SiteClientControls() {
  const pathname = usePathname();
  const isTrackingAdmin = pathname.startsWith("/tracking");

  if (isTrackingAdmin) return null;

  return (
    <>
      <IntelligenceFavoriteControls />
      <IntelligenceHotnessControls />
      <WechatShareCompat />
    </>
  );
}
