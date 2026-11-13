import type { MouseEventHandler, ReactNode } from "react";
import { isNonDurableWeChatArticleUrl } from "@/lib/wechat-link-policy";

type SourceArticleLinkProps = {
  href: string;
  children?: ReactNode;
  className?: string;
  title?: string;
  "aria-label"?: string;
  onClick?: MouseEventHandler<HTMLAnchorElement>;
  unavailableText?: string;
  fallbackAs?: "span" | "div";
  [key: `data-${string}`]: string | undefined;
};

/** Never create a clickable public source link to an expiring WeChat search redirect. */
export function SourceArticleLink({
  href, children, className, title, onClick, unavailableText, fallbackAs = "span",
  "aria-label": ariaLabel,
  ...dataAttributes
}: SourceArticleLinkProps) {
  if (isNonDurableWeChatArticleUrl(href)) {
    const Fallback = fallbackAs === "div" ? "div" : "span";
    return (
      <Fallback
        {...dataAttributes}
        className={className}
        aria-label={ariaLabel}
        data-source-link-status="wechat-unverified"
        title="该微信链接可能已失效，需重新核对原文；当前没有经过确认的替代链接。"
      >
        {unavailableText ?? children}
        {!unavailableText && <small> · 原文链接待更新</small>}
      </Fallback>
    );
  }
  return (
    <a {...dataAttributes} href={href} className={className} title={title} aria-label={ariaLabel} onClick={onClick}
      target="_blank" rel="noreferrer">
      {children}
    </a>
  );
}
