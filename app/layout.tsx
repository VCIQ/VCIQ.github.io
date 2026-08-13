import type { Metadata } from "next";
import { LiveStatus } from "@/components/live-status";
import { SiteClientControls } from "@/components/site-client-controls";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

const SITE_URL = "https://vciq.github.io";
const SITE_NAME = "丽泽路1号";
const SITE_TITLE = "丽泽路1号｜一级市场科技研究";
const SITE_DESCRIPTION = "围绕核心技术、核心赛道、核心人物与核心公司的可追溯一级市场研究。";
const SOCIAL_DESCRIPTION = "以四类核心研究对象组织公开、克制、可追溯的一级市场科技研究。";
const SOCIAL_IMAGE = {
  url: "/og-image.png",
  width: 1200,
  height: 630,
  type: "image/png",
  alt: "丽泽路1号：围绕四类核心研究对象的一级市场科技研究",
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: SITE_TITLE,
    template: `%s｜${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION,
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: SITE_NAME,
    description: SOCIAL_DESCRIPTION,
    siteName: SITE_NAME,
    type: "website",
    locale: "zh_CN",
    images: [SOCIAL_IMAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_NAME,
    description: SOCIAL_DESCRIPTION,
    images: [SOCIAL_IMAGE],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" data-theme="light">
      <body>
        <a className="skip-link" href="#main-content">跳到主要内容</a>
        <SiteHeader status={<LiveStatus />} />
        <div id="main-content" tabIndex={-1}>{children}</div>
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
