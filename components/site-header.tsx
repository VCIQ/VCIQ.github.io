"use client";

import { Bookmark, Bot, Menu, Search, Settings, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

const navItems = [
  ["研究首页", "/"],
  ["核心技术", "/technologies"],
  ["核心赛道", "/technology"],
  ["核心人物", "/people"],
  ["核心公司", "/companies"],
];

const TRACKING_ADMIN_URL = "https://vciq-tracking-console.pages.dev/";
const BUILD_PROVENANCE_URL = "https://vciq.github.io/build-provenance.json";
const PRIMARY_NAVIGATION_ID = "primary-navigation";

function isCurrentRoute(pathname: string, href: string) {
  if (href === "/") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SiteHeader({ status }: { status: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="brand" href="/" aria-label="丽泽路1号首页">
          <span className="brand-mark">LZ</span>
          <span>
            <strong>丽泽路1号</strong>
            <small>一级市场科技研究</small>
          </span>
        </Link>

        <nav
          id={PRIMARY_NAVIGATION_ID}
          className={open ? "main-nav is-open" : "main-nav"}
          aria-label="主导航"
        >
          {navItems.map(([label, href], index) => {
            const current = isCurrentRoute(pathname, href);
            return (
              <Link
                href={href}
                key={href}
                onClick={() => setOpen(false)}
                aria-current={current ? "page" : undefined}
              >
                <span>{String(index + 1).padStart(2, "0")}</span>
                {label}
              </Link>
            );
          })}
          <div className="mobile-nav-tools" role="group" aria-label="工具入口">
            <Link
              href="/research-agent"
              onClick={() => setOpen(false)}
              aria-current={isCurrentRoute(pathname, "/research-agent") ? "page" : undefined}
            >
              研究助手
            </Link>
            <Link
              href="/favorites"
              onClick={() => setOpen(false)}
              aria-current={isCurrentRoute(pathname, "/favorites") ? "page" : undefined}
            >
              收藏
            </Link>
            <a
              href={TRACKING_ADMIN_URL}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => setOpen(false)}
              aria-label="追踪管理台（外部链接，在新标签页打开）"
            >
              追踪管理台 ↗
            </a>
            <Link
              href="/search"
              onClick={() => setOpen(false)}
              aria-current={isCurrentRoute(pathname, "/search") ? "page" : undefined}
            >
              全局搜索
            </Link>
            <a href="/data/pipeline_health.json">数据健康</a>
            <a
              href={BUILD_PROVENANCE_URL}
              target="_blank"
              rel="noopener noreferrer"
            >
              构建记录
            </a>
          </div>
        </nav>

        <div className="header-actions">
          <div className="header-optional-status">{status}</div>
          <Link className="icon-button header-optional-tool" href="/research-agent" aria-label="研究助手" title="研究助手">
            <Bot size={18} aria-hidden="true" />
          </Link>
          <Link className="icon-button header-optional-tool" href="/favorites" aria-label="收藏" title="收藏">
            <Bookmark size={18} aria-hidden="true" />
          </Link>
          <a
            className="icon-button header-optional-tool"
            href={TRACKING_ADMIN_URL}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="追踪管理台（外部链接，在新标签页打开）"
            title="追踪管理台（外部链接，在新标签页打开）"
          >
            <Settings size={18} aria-hidden="true" />
          </a>
          <Link className="icon-button" href="/search" aria-label="全局搜索">
            <Search size={18} aria-hidden="true" />
          </Link>
          <button
            type="button"
            className="icon-button mobile-menu"
            onClick={() => setOpen((current) => !current)}
            aria-controls={PRIMARY_NAVIGATION_ID}
            aria-expanded={open}
            aria-label={open ? "收起导航" : "展开导航"}
          >
            {open ? <X size={19} aria-hidden="true" /> : <Menu size={19} aria-hidden="true" />}
          </button>
        </div>
      </div>
    </header>
  );
}
