import type { Metadata } from "next";
import { LiveStatus } from "@/components/live-status";
import { SiteClientControls } from "@/components/site-client-controls";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://vciq.github.io"),
  title: {
    default: "丽泽路1号｜一级市场科技研究",
    template: "%s｜丽泽路1号",
  },
  description: "围绕核心赛道、重点技术主题、核心技术对象、核心人物与核心公司的可追溯一级市场科技研究。",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "丽泽路1号",
    description: "以核心赛道、技术主题和具体技术对象分层组织公开、克制、可追溯的一级市场科技研究。",
    type: "website",
    locale: "zh_CN",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" data-theme="light">
      <body>
        <SiteHeader status={<LiveStatus />} />
        {children}
        <SiteClientControls />
        <footer className="site-footer">
          <div>
            <strong>丽泽路1号</strong>
            <span>事实、计算与判断分层呈现</span>
          </div>
          <p>信息仅供研究，不构成投资建议。关键事实均应回溯原始信源。</p>
        </footer>
      </body>
    </html>
  );
}
